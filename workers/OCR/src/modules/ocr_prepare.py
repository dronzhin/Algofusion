# ====== SAVE CLEAN PAGE + ROI COORDS JSON + DEBUG ROI PNG FOR ALL PAGES ======

import cv2
import numpy as np
import json
import gzip
from pathlib import Path

OUT_DIR = Path("final_rebuilt_auto") / "_clean_page_plus_roi_json"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def remove_lines(orig, mask):
    mask = (mask > 0).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    clean = cv2.inpaint(orig, mask, 3, cv2.INPAINT_TELEA)
    return clean


def collect_objects(page_json):
    return page_json.get("ocr_targets", [])


def expand_box(x1, y1, x2, y2, w, h, pad=2):
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(w, x2 + pad)
    y2 = min(h, y2 + pad)
    return x1, y1, x2, y2


def extract_box(obj):
    b = obj.get("bbox")
    if not b:
        return None

    x1 = int(b["x1"])
    y1 = int(b["y1"])
    x2 = int(b["x2"])
    y2 = int(b["y2"])

    if x2 <= x1 or y2 <= y1:
        return None

    return {
        "id": obj.get("id", ""),
        "kind": obj.get("kind", "roi"),
        "bbox": {
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "w": x2 - x1,
            "h": y2 - y1,
        }
    }


def read_mask_meta(mask_json_path: Path):
    if str(mask_json_path).endswith(".gz"):
        with gzip.open(mask_json_path, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(mask_json_path.read_text(encoding="utf-8"))


def find_final_json_by_page_id(page_id: str, stage2_dir: Path):
    matches = list(stage2_dir.rglob(f"{page_id}__ocr.json"))
    if matches:
        return matches[0]
    return None


def draw_rois_on_clean(clean_bgr, roi_items):
    out = clean_bgr.copy()
    h, w = out.shape[:2]

    color_map = {
        "table_cell": (0, 0, 255),
        "header_box": (180, 0, 180),
        "header_form_roi": (180, 0, 180),
        "footer_box": (255, 0, 0),
        "unp_cell": (0, 165, 255),
        "form_outer_rect": (180, 0, 180),
        "outer_rect": (180, 0, 180),
        "form_roi": (180, 0, 180),
        "roi": (180, 0, 180),
    }

    font = cv2.FONT_HERSHEY_SIMPLEX

    for i, item in enumerate(roi_items, 1):
        kind = item.get("kind", "roi")
        b = item["bbox"]

        x1, y1, x2, y2 = expand_box(
            int(b["x1"]), int(b["y1"]), int(b["x2"]), int(b["y2"]),
            w=w, h=h, pad=2
        )

        color = color_map.get(kind, (180, 0, 180))

        # рамка
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)

        # номер
        label = item['id'].split('_')[-1]
        tx = x1 + 3
        ty = y1 + 13

        (tw, th), _ = cv2.getTextSize(label, font, 0.4, 1)

        # белый фон под цифру
        cv2.rectangle(
            out,
            (tx - 2, ty - th - 2),
            (tx + tw + 2, ty + 3),
            (255, 255, 255),
            -1
        )

        # сама цифра
        cv2.putText(
            out,
            label,
            (tx, ty),
            font,
            0.4,
            color,
            1,
            cv2.LINE_AA
        )

    return out


