# OCR stage A2: raw OCR JSON + ROI coords -> ROI text JSON + all_pages_roi_text.json

import cv2
import glob
import os
import re
import json


# ====== Utils ======
def intersect_len(a1, a2, b1, b2):
    return max(0, min(a2, b2) - max(a1, b1))


def _bbox_area_for_ocr_target(roi):
    b = roi["bbox"]
    return max(0, b["x2"] - b["x1"]) * max(0, b["y2"] - b["y1"])


def _roi_priority_key(roi):
    kind = str(roi.get("kind", ""))
    nested_rank = 0 if kind in {"header_form_roi", "form_roi", "table_cell"} else 1
    b = roi["bbox"]
    return (nested_rank, _bbox_area_for_ocr_target(roi), b["y1"], b["x1"])


def _largest_remainder_counts(total, weights):
    if total <= 0 or not weights:
        return [0] * len(weights)

    positive = [max(0.0, float(w)) for w in weights]
    weight_sum = sum(positive)
    if weight_sum <= 0:
        base = total // len(weights)
        counts = [base] * len(weights)
        for i in range(total - sum(counts)):
            counts[i] += 1
        return counts

    scaled = [(w / weight_sum) * total for w in positive]
    counts = [int(v) for v in scaled]
    remainder = total - sum(counts)
    order = sorted(
        range(len(weights)),
        key=lambda i: (scaled[i] - counts[i], positive[i], -i),
        reverse=True,
    )
    for i in range(remainder):
        counts[order[i % len(order)]] += 1
    return counts


def _split_text_by_weights(text, weights):
    cleaned = clean_text(text)
    if not cleaned or not weights:
        return []

    words = cleaned.split()
    use_word_units = len(words) > 1 and len(words) >= len(weights)
    units = words if use_word_units else list(cleaned)
    joiner = " " if use_word_units else ""
    counts = _largest_remainder_counts(len(units), weights)

    chunks = []
    used = 0
    for i, count in enumerate(counts):
        if i == len(counts) - 1:
            part_units = units[used:]
        else:
            part_units = units[used:used + count]
        used += count
        chunks.append(joiner.join(part_units).strip())

    return chunks


def _build_strict_roi_hits(item, rois):
    x1, y1, x2, y2 = item["bbox"]
    item_w = max(1, x2 - x1)
    item_h = max(1, y2 - y1)
    min_inter_w = max(2, min(18, int(round(item_w * 0.04))))
    min_inter_h = max(2, min(14, int(round(item_h * 0.18))))

    hits = []
    for roi in rois:
        b = roi["bbox"]
        rx1, ry1, rx2, ry2 = b["x1"], b["y1"], b["x2"], b["y2"]

        inter_w = intersect_len(x1, x2, rx1, rx2)
        inter_h = intersect_len(y1, y2, ry1, ry2)
        if inter_w < min_inter_w or inter_h < min_inter_h:
            continue

        roi_w = max(1, rx2 - rx1)
        roi_h = max(1, ry2 - ry1)
        x_ratio_item = inter_w / item_w
        y_ratio_item = inter_h / item_h
        x_ratio_roi = inter_w / roi_w
        y_ratio_roi = inter_h / roi_h

        strong_x = x_ratio_item >= 0.03 or x_ratio_roi >= 0.20
        strong_y = y_ratio_item >= 0.10 or y_ratio_roi >= 0.35
        if not (strong_x and strong_y):
            continue

        hits.append({
            "roi": roi,
            "sx1": max(x1, rx1),
            "sx2": min(x2, rx2),
            "sy1": max(y1, ry1),
            "sy2": min(y2, ry2),
            "inter_area": inter_w * inter_h,
        })

    return hits


def _segment_owner_key(hit, left, top, right, bottom):
    own_w = intersect_len(left, right, hit["sx1"], hit["sx2"])
    own_h = intersect_len(top, bottom, hit["sy1"], hit["sy2"])
    owned_area = own_w * own_h
    return (_roi_priority_key(hit["roi"]), -owned_area, -hit["inter_area"])


def _build_owned_segments(item_bbox, hits):
    x1, y1, x2, y2 = item_bbox
    x_points = sorted({x1, x2, *[hit["sx1"] for hit in hits], *[hit["sx2"] for hit in hits]})
    y_points = sorted({y1, y2, *[hit["sy1"] for hit in hits], *[hit["sy2"] for hit in hits]})

    owned_segments = []
    for top, bottom in zip(y_points, y_points[1:]):
        if bottom <= top:
            continue
        mid_y = (top + bottom) / 2
        for left, right in zip(x_points, x_points[1:]):
            if right <= left:
                continue
            mid_x = (left + right) / 2
            owners = [
                hit
                for hit in hits
                if hit["sx1"] <= mid_x <= hit["sx2"] and hit["sy1"] <= mid_y <= hit["sy2"]
            ]
            if not owners:
                continue

            owner = min(owners, key=lambda hit: _segment_owner_key(hit, left, top, right, bottom))
            weight = max(1, (right - left) * (bottom - top))

            if owned_segments and owned_segments[-1]["roi"]["id"] == owner["roi"]["id"]:
                owned_segments[-1]["left"] = min(owned_segments[-1]["left"], left)
                owned_segments[-1]["right"] = max(owned_segments[-1]["right"], right)
                owned_segments[-1]["top"] = min(owned_segments[-1]["top"], top)
                owned_segments[-1]["bottom"] = max(owned_segments[-1]["bottom"], bottom)
                owned_segments[-1]["weight"] += weight
            else:
                owned_segments.append({
                    "roi": owner["roi"],
                    "left": left,
                    "right": right,
                    "top": top,
                    "bottom": bottom,
                    "weight": weight,
                })

    return owned_segments


def split_line_by_rois(item, rois):
    text = clean_text(item.get("text"))
    if not text:
        return []

    hits = _build_strict_roi_hits(item, rois)
    if not hits:
        return []

    if len(hits) == 1:
        return [(hits[0]["roi"], text)]

    owned_segments = _build_owned_segments(item["bbox"], hits)
    if not owned_segments:
        owner = min(hits, key=lambda hit: (_roi_priority_key(hit["roi"]), -hit["inter_area"]))
        return [(owner["roi"], text)]

    chunks = _split_text_by_weights(text, [seg["weight"] for seg in owned_segments])
    result = []
    for seg, chunk in zip(owned_segments, chunks):
        part_text = clean_text(chunk)
        if not part_text:
            continue
        if result and result[-1][0]["id"] == seg["roi"]["id"]:
            merged = clean_text(result[-1][1] + " " + part_text)
            result[-1] = (result[-1][0], merged)
        else:
            result.append((seg["roi"], part_text))

    return result


def clean_text(s):
    if s is None:
        return None
    s = str(s).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def build_box_lines_from_ocr(ocr_items, box_bbox, y_tol=14):
    bx1, by1, bx2, by2 = box_bbox

    box_items = []
    for item in ocr_items:
        x1, y1, x2, y2 = item["bbox"]

        if intersect_len(y1, y2, by1, by2) <= 0:
            continue
        if intersect_len(x1, x2, bx1, bx2) <= 0:
            continue

        text = clean_text(item.get("text"))
        if not text:
            continue

        box_items.append({
            "text": text,
            "bbox": item["bbox"],
        })

    box_items.sort(key=lambda it: (it["bbox"][1], it["bbox"][0]))

    lines = []
    for item in box_items:
        y = item["bbox"][1]

        placed = False
        for line in lines:
            if abs(y - line["y"]) <= y_tol:
                line["parts"].append(item)
                line["y_values"].append(y)
                placed = True
                break

        if not placed:
            lines.append({
                "y": y,
                "parts": [item],
                "y_values": [y],
            })

    out = []
    for line in lines:
        parts = sorted(line["parts"], key=lambda it: it["bbox"][0])
        text = clean_text(" ".join(p["text"] for p in parts if clean_text(p["text"])))
        if text:
            out.append({
                "y": int(round(sum(line["y_values"]) / len(line["y_values"]))),
                "text": text,
            })

    return out


def run_roi_assignment_pipeline(clean_png, roi_json, raw_ocr_json):
    with open(roi_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(raw_ocr_json, "r", encoding="utf-8") as f:
        raw_ocr_data = json.load(f)

    ocr_items = raw_ocr_data.get("ocr_items", [])
    rois = data.get("ocr_targets", data.get("rois", []))

    def get_area(roi):
        b = roi["bbox"]
        return (b["x2"] - b["x1"]) * (b["y2"] - b["y1"])

    rois_sorted = sorted(rois, key=get_area)
    roi_texts = {roi["id"]: [] for roi in rois_sorted}

    for item in ocr_items:
        parts = split_line_by_rois(item, rois_sorted)
        for roi, part in parts:
            if part:
                roi_texts[roi["id"]].append(part)

    page_id_lc = str(data.get("page_id", "")).lower()

    if "waybill" in page_id_lc:
        table_rois = [roi for roi in rois_sorted if roi.get("kind") == "table_cell"]

        rows_map = {}
        for roi in table_rois:
            rows_map.setdefault(roi.get("row"), []).append(roi)

        def _roi_height(roi):
            b = roi.get("bbox", {})
            return max(0, int(b.get("y2", 0)) - int(b.get("y1", 0)))

        def _is_pure_col_index_text(text, col):
            t = clean_text(text)
            return bool(t) and t == str(col)

        def _looks_like_waybill_index_row(row_rois):
            if not row_rois:
                return False

            row_rois = sorted(row_rois, key=lambda r: (r.get("col") or 0))

            matched = 0
            nonempty = 0
            heights = []

            for roi in row_rois:
                rid = roi["id"]
                col = roi.get("col")
                txt = clean_text(" ".join(roi_texts.get(rid, [])))
                heights.append(_roi_height(roi))

                if not txt:
                    continue

                nonempty += 1
                if _is_pure_col_index_text(txt, col):
                    matched += 1

            if nonempty < 5:
                return False

            numeric_ratio_ok = matched >= 5 and matched / max(nonempty, 1) >= 0.6

            heights = [h for h in heights if h > 0]
            if not heights:
                return False

            row_h = min(heights)

            other_row_heights = []
            for other_row_num, other_rois in rows_map.items():
                if other_rois is row_rois:
                    continue
                hs = [_roi_height(r) for r in other_rois if _roi_height(r) > 0]
                if hs:
                    other_row_heights.append(min(hs))

            if not other_row_heights:
                return numeric_ratio_ok

            median_other_h = sorted(other_row_heights)[len(other_row_heights) // 2]
            height_ratio_ok = row_h <= max(18, int(median_other_h * 0.45))

            return numeric_ratio_ok and height_ratio_ok

        index_row_num = None
        for row_num in sorted(rows_map):
            if _looks_like_waybill_index_row(rows_map[row_num]):
                index_row_num = row_num
                break

        if index_row_num is not None:
            next_row_num = index_row_num + 1
            next_row_by_col = {
                roi.get("col"): roi
                for roi in rows_map.get(next_row_num, [])
            }

            for roi in rows_map[index_row_num]:
                rid = roi["id"]
                col = roi.get("col")
                raw_text = clean_text(" ".join(roi_texts.get(rid, [])))

                if raw_text and not _is_pure_col_index_text(raw_text, col):
                    target_roi = next_row_by_col.get(col)
                    if target_roi is not None:
                        target_id = target_roi["id"]
                        roi_texts[target_id] = [raw_text] + roi_texts.get(target_id, [])

                roi_texts[rid] = []

    regions_raw = []

    for roi in rois_sorted:
        rb = [
            roi["bbox"]["x1"],
            roi["bbox"]["y1"],
            roi["bbox"]["x2"],
            roi["bbox"]["y2"]
        ]

        text = " ".join(roi_texts[roi["id"]]).strip()

        region_obj = {
            "id": roi["id"],
            "kind": roi.get("kind", "unknown"),
            "bbox": rb,
            "text": text
        }

        if roi["id"] == "header_box":
            region_obj["header_lines"] = build_box_lines_from_ocr(ocr_items, rb)

        if roi["id"] == "footer_box":
            region_obj["footer_lines"] = build_box_lines_from_ocr(ocr_items, rb)

        regions_raw.append(region_obj)

    step = 20
    regions_sorted = sorted(
        regions_raw,
        key=lambda r: (round(r["bbox"][1] / step), r["bbox"][0])
    )

    html_blocks = []
    for r in regions_sorted:
        if r["text"]:
            html_blocks.append(
                f"<div class='roi'><h3>{r['id']} ({r['kind']})</h3><p>{r['text']}</p></div>"
            )

    out_json = {
        "page_id": data.get("page_id", os.path.basename(clean_png)),
        "regions": regions_sorted
    }

    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>OCR ROI: {os.path.basename(clean_png)}</title>
<style>
body {{ font-family: Arial, sans-serif; line-height: 1.5; padding: 20px; }}
.roi {{ border: 1px solid #aaa; padding: 10px; margin: 10px 0; border-radius: 5px; }}
.roi h3 {{ margin: 0 0 5px 0; font-size: 1.1em; color: #333; }}
.roi p {{ margin: 0; }}
</style>
</head>
<body>
<h1>Страница: {os.path.basename(clean_png)}</h1>
{''.join(html_blocks)}
</body>
</html>"""

    out_json_path = os.path.join(
        os.path.dirname(clean_png),
        f"{os.path.basename(clean_png).replace('__clean.png','')}_roi_text.json"
    )
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(out_json, f, ensure_ascii=False, indent=2)

    out_html_path = os.path.join(
        os.path.dirname(clean_png),
        f"{os.path.basename(clean_png).replace('__clean.png','')}_roi_text.html"
    )
    with open(out_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"ROI text saved: {out_json_path}")
    return out_json, html_content


