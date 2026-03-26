from __future__ import annotations

import json
import shutil
from pathlib import Path
import gzip

import cv2
import fitz
import numpy as np


# =========================================================
# КОНФИГУРАЦИЯ
# =========================================================

INPUT_DIR = Path("input")
OUT_STAGE1_DIR = Path("out_table_merge")
OUT_STAGE2_DIR = Path("final_rebuilt_auto")
DPI = 200

# параметры восстановления правой границы
RIGHT_BORDER_MIN_H_LEN = 80
RIGHT_BORDER_END_TOL = 12
RIGHT_BORDER_AGREE_RATIO = 0.35
RIGHT_BORDER_BAND = 8
RIGHT_BORDER_THICKNESS = 2
RIGHT_BORDER_RIGHT_ZONE_RATIO = 0.30

# параметры морфологии и кластеризации
H_OPEN = 35
V_OPEN = 35
H_CLOSE = 12
V_CLOSE = 12

ROW_CLUSTER_TOL = 2
COL_CLUSTER_TOL = 3

MIN_ROW_COUNT = 4
MIN_H_LEN_ABS = 50
MIN_V_LEN_ABS = 35

OUT_STAGE1_DIR.mkdir(parents=True, exist_ok=True)
OUT_STAGE2_DIR.mkdir(parents=True, exist_ok=True)
INPUT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# ОБЩИЕ УТИЛИТЫ
# =========================================================

import json

def detect_form_closed_regions(
    mask: np.ndarray,
    h_segments: list[tuple[int,int,int]],
    v_segments: list[tuple[int,int,int]],
    outer_rect=None,
    min_area: int = 500,
):

    bin_img = prepare_binary_mask(mask)

    grid = np.zeros_like(bin_img)

    for y, x1, x2 in h_segments:
        cv2.line(grid, (int(x1), int(y)), (int(x2), int(y)), 255, 2)

    for x, y1, y2 in v_segments:
        cv2.line(grid, (int(x), int(y1)), (int(x), int(y2)), 255, 2)

    # добавляем внешний прямоугольник формы
    if outer_rect is not None:
        x1, y1, x2, y2 = map(int, outer_rect)

        cv2.line(grid, (x1, y1), (x2, y1), 255, 2)
        cv2.line(grid, (x1, y2), (x2, y2), 255, 2)
        cv2.line(grid, (x1, y1), (x1, y2), 255, 2)
        cv2.line(grid, (x2, y1), (x2, y2), 255, 2)

    grid = cv2.morphologyEx(
        grid,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (5,5)),
    )

    contours, hierarchy = cv2.findContours(
        grid,
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    rois = []

    if hierarchy is None:
        return rois

    hierarchy = hierarchy[0]

    for i, cnt in enumerate(contours):

        x,y,w,h = cv2.boundingRect(cnt)

        if w*h < min_area:
            continue
        if w < 20 or h < 15:
            continue

        parent = hierarchy[i][3]
        if parent == -1:
            continue

        rois.append((int(x),int(y),int(x+w),int(y+h)))

    # удалить дубликаты
    uniq = []
    for box in sorted(rois):

        if not uniq:
            uniq.append(box)
            continue

        x1,y1,x2,y2 = box
        px1,py1,px2,py2 = uniq[-1]

        if (
            abs(x1-px1) <= 3 and
            abs(y1-py1) <= 3 and
            abs(x2-px2) <= 3 and
            abs(y2-py2) <= 3
        ):
            continue

        uniq.append(box)

    return uniq

def make_bbox(x1, y1, x2, y2):
    return {
        "x1": int(x1),
        "y1": int(y1),
        "x2": int(x2),
        "y2": int(y2),
        "w": int(x2 - x1),
        "h": int(y2 - y1),
    }


def clip_box_to_image(box, shape):
    x1, y1, x2, y2 = map(int, box)
    h, w = shape[:2]

    x1 = max(0, min(w - 1, x1))
    x2 = max(0, min(w - 1, x2))
    y1 = max(0, min(h - 1, y1))
    y2 = max(0, min(h - 1, y2))

    if x2 <= x1 or y2 <= y1:
        return None

    return (x1, y1, x2, y2)


def build_table_cells(rows, cols, image_shape, pad=6):
    rows = [int(v) for v in rows]
    cols = [int(v) for v in cols]

    cells = []
    cell_id = 1

    if len(rows) < 2 or len(cols) < 2:
        return cells

    for i in range(len(rows) - 1):
        for j in range(len(cols) - 1):
            x1 = cols[j] + pad
            y1 = rows[i] + pad
            x2 = cols[j + 1] - pad
            y2 = rows[i + 1] - pad

            clipped = clip_box_to_image((x1, y1, x2, y2), image_shape)
            if clipped is None:
                continue

            x1, y1, x2, y2 = clipped

            cells.append({
                "id": f"table_cell_{cell_id:04d}",
                "kind": "table_cell",
                "row": i + 1,
                "col": j + 1,
                "bbox": make_bbox(x1, y1, x2, y2),
            })
            cell_id += 1

    return cells


def build_overlay_objects_for_table(
    rows,
    cols,
    image_shape,
    header_box=None,
    footer_box=None,
    unp_cells=None,
    header_form_rois=None,
):
    objects = []
    rows = [int(v) for v in rows]
    cols = [int(v) for v in cols]
    unp_cells = unp_cells or []
    header_form_rois = header_form_rois or []

    if len(rows) >= 2 and len(cols) >= 2:
        x1 = int(min(cols))
        x2 = int(max(cols))
        y1 = int(min(rows))
        y2 = int(max(rows))

        for i, y in enumerate(rows, 1):
            objects.append({
                "id": f"grid_hline_{i:03d}",
                "kind": "grid_hline",
                "line": {
                    "x1": x1,
                    "y1": int(y),
                    "x2": x2,
                    "y2": int(y),
                }
            })

        for i, x in enumerate(cols, 1):
            objects.append({
                "id": f"grid_vline_{i:03d}",
                "kind": "grid_vline",
                "line": {
                    "x1": int(x),
                    "y1": y1,
                    "x2": int(x),
                    "y2": y2,
                }
            })

    if header_box is not None:
        clipped = clip_box_to_image(header_box, image_shape)
        if clipped is not None:
            objects.append({
                "id": "header_box",
                "kind": "header_box",
                "bbox": make_bbox(*clipped),
            })

    if footer_box is not None:
        clipped = clip_box_to_image(footer_box, image_shape)
        if clipped is not None:
            objects.append({
                "id": "footer_box",
                "kind": "footer_box",
                "bbox": make_bbox(*clipped),
            })

    for i, box in enumerate(unp_cells, 1):
        clipped = clip_box_to_image(box, image_shape)
        if clipped is None:
            continue

        objects.append({
            "id": f"unp_cell_{i:03d}",
            "kind": "unp_cell",
            "bbox": make_bbox(*clipped),
        })

    for i, box in enumerate(header_form_rois, 1):
        clipped = clip_box_to_image(box, image_shape)
        if clipped is None:
            continue

        objects.append({
            "id": f"header_form_roi_{i:04d}",
            "kind": "header_form_roi",
            "bbox": make_bbox(*clipped),
        })

    return objects


def build_overlay_objects_for_form(image_shape, outer_rect=None, form_rois=None):
    objects = []
    form_rois = form_rois or []

    if outer_rect is not None:
        clipped = clip_box_to_image(outer_rect, image_shape)
        if clipped is not None:
            objects.append({
                "id": "outer_rect",
                "kind": "form_outer_rect",
                "bbox": make_bbox(*clipped),
            })

    for i, box in enumerate(form_rois, 1):
        clipped = clip_box_to_image(box, image_shape)
        if clipped is None:
            continue
        objects.append({
            "id": f"form_roi_{i:04d}",
            "kind": "form_roi",
            "bbox": make_bbox(*clipped),
        })

    return objects


def build_page_ocr_json(
    page_id,
    layout,
    image_shape,
    rows=None,
    cols=None,
    header_box=None,
    footer_box=None,
    unp_cells=None,
    outer_rect=None,
    form_rois=None,
    header_form_rois=None,
    extra_meta=None,
):
    rows = rows or []
    cols = cols or []
    unp_cells = unp_cells or []
    form_rois = form_rois or []
    header_form_rois = header_form_rois or []
    extra_meta = extra_meta or {}

    h, w = image_shape[:2]
    page = {
        "page_id": page_id,
        "layout": str(layout),
        "image_size": {
            "width": int(w),
            "height": int(h),
        },
        "overlay_objects": [],
        "cells": [],
        "ocr_targets": [],
        "meta": extra_meta,
    }
    if layout == "table":
        table_cells = build_table_cells(rows, cols, image_shape=image_shape, pad=2)

        header_form_cells = []
        for i, box in enumerate(header_form_rois, 1):
            clipped = clip_box_to_image(box, image_shape)
            if clipped is None:
                continue

            header_form_cells.append({
                "id": f"header_form_roi_{i:04d}",
                "kind": "header_form_roi",
                "bbox": make_bbox(*clipped),
            })

        overlay_objects = build_overlay_objects_for_table(
            rows=rows,
            cols=cols,
            image_shape=image_shape,
            header_box=header_box,
            footer_box=footer_box,
            unp_cells=unp_cells,
            header_form_rois=header_form_rois,
        )

        special_targets = []

        if header_box is not None:
            clipped = clip_box_to_image(header_box, image_shape)
            if clipped is not None:
                special_targets.append({
                    "id": "header_box",
                    "kind": "header_box",
                    "bbox": make_bbox(*clipped),
                })

        if footer_box is not None:
            clipped = clip_box_to_image(footer_box, image_shape)
            if clipped is not None:
                special_targets.append({
                    "id": "footer_box",
                    "kind": "footer_box",
                    "bbox": make_bbox(*clipped),
                })

        for i, box in enumerate(unp_cells, 1):
            clipped = clip_box_to_image(box, image_shape)
            if clipped is None:
                continue

            special_targets.append({
                "id": f"unp_cell_{i:03d}",
                "kind": "unp_cell",
                "bbox": make_bbox(*clipped),
            })

        page["overlay_objects"] = overlay_objects
        page["cells"] = table_cells + header_form_cells
        page["ocr_targets"] = table_cells + header_form_cells + special_targets

    elif layout == "form":
        overlay_objects = build_overlay_objects_for_form(
            image_shape=image_shape,
            outer_rect=outer_rect,
            form_rois=form_rois,
        )

        form_cells = []
        for i, box in enumerate(form_rois, 1):
            clipped = clip_box_to_image(box, image_shape)
            if clipped is None:
                continue
            form_cells.append({
                "id": f"form_roi_{i:04d}",
                "kind": "form_roi",
                "bbox": make_bbox(*clipped),
            })

        page["overlay_objects"] = overlay_objects
        page["cells"] = form_cells
        page["ocr_targets"] = form_cells[:]

    return page

def extract_rows_cols_from_grid_mask(grid_mask: np.ndarray):
    bin_img = (grid_mask > 0).astype(np.uint8) * 255

    h_segments = extract_h_segments(bin_img, min_len=20)
    v_segments = extract_v_segments(bin_img, min_len=20)

    rows = merge_close_values([y for y, _, _ in h_segments], 3)
    cols = merge_close_values([x for x, _, _ in v_segments], 3)

    return rows, cols

def extend_cols_with_page_boxes(
    cols: list[int],
    header_box=None,
    footer_box=None,
    min_extra_width: int = 120,
) -> list[int]:
    cols = [int(v) for v in cols]
    if not cols:
        return cols

    candidates = []

    if header_box is not None:
        candidates.append(int(header_box[2]))

    if footer_box is not None:
        candidates.append(int(footer_box[2]))

    if not candidates:
        return cols

    right_x = max(candidates)

    # если box уходит заметно правее последней найденной колонки,
    # считаем это правой границей последней колонки
    if right_x - cols[-1] >= min_extra_width:
        cols = merge_close_values(cols + [right_x], 3)

    return cols

def clean_content_except_input(base: str = "/content", keep: str = "/content/input") -> None:
    """
    Очищает /content, но сохраняет папку input.
    При желании можешь вызывать вручную перед запуском.
    """
    base_path = Path(base).resolve()
    keep_paths = {
        Path(keep).resolve(),
        Path("/content/word_highlight_out_strict").resolve(),
    }

    for item in base_path.iterdir():
        if item.resolve() in keep_paths:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    print("✅ Очистка завершена. Сохранена папка:", keep)


def list_inputs(input_dir: Path) -> list[Path]:
    exts = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
    return sorted(
        [p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts]
    )


def merge_close_values(vals: list[int], tol: int) -> list[int]:
    vals = sorted(vals)
    if not vals:
        return []

    groups = [[vals[0]]]
    for v in vals[1:]:
        if abs(v - groups[-1][-1]) <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])

    return [int(round(np.mean(g))) for g in groups]


def _to_str(v):
    if v is None:
        return ""
    return str(v).strip()


def is_index_row(texts):
    vals = [_to_str(v) for v in texts if _to_str(v) != ""]
    if len(vals) < 3:
        return False
    expected = [str(i) for i in range(1, len(vals) + 1)]
    return vals == expected


def is_header_row(texts):
    joined = " ".join(_to_str(t).lower() for t in texts)
    return any(w in joined for w in [
        "артикул", "товар", "штрих",
        "цена", "сумма", "ндс",
        "кол", "кол-во", "количество",
        "ед", "ед."
    ])


def is_total_row(texts):
    joined = " ".join(_to_str(t).lower() for t in texts)
    return "итого" in joined


def filter_table_rows(table_rows):
    clean_rows = []

    for row in table_rows:
        texts = [cell.get("text", "") for cell in row]

        if is_header_row(texts):
            continue
        if is_index_row(texts):
            continue
        if is_total_row(texts):
            continue

        clean_rows.append(row)

    return clean_rows


def prepare_binary_mask(mask: np.ndarray) -> np.ndarray:
    """
    Приводит маску к бинарному виду и закрывает мелкие разрывы.
    """
    bin_img = (mask > 0).astype(np.uint8) * 255
    bin_img = cv2.morphologyEx(
        bin_img,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
    )
    return bin_img


def save_mask_json(line_mask: np.ndarray, out_json: Path, page_id: str, source: dict | None = None) -> None:
    """
    Сохраняет маску линий в json.gz
    """
    mask01 = (line_mask > 0).astype(np.uint8)

    data = {
        "page_id": page_id,
        "image_size_hw": [int(mask01.shape[0]), int(mask01.shape[1])],
        "mask": mask01.tolist(),
    }

    if source is not None:
        data["source"] = source

    out_json = out_json.with_suffix(".json.gz")

    with gzip.open(out_json, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def load_mask_from_json(mask_json_path: Path) -> np.ndarray | None:
    try:
        if str(mask_json_path).endswith(".gz"):
            with gzip.open(mask_json_path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(mask_json_path.read_text(encoding="utf-8"))
    except Exception as e:
        print("skip: bad json:", mask_json_path, e)
        return None

    if "mask" not in data:
        print("skip: key 'mask' not found:", mask_json_path)
        return None

    mask = np.array(data["mask"], dtype=np.uint8)

    if mask.ndim != 2:
        print("skip: mask is not 2D:", mask_json_path)
        return None

    if mask.max() <= 1:
        mask = mask * 255
    else:
        mask = (mask > 0).astype(np.uint8) * 255

    return mask

# =========================================================
# ЭТАП 1 — ПОИСК ЛИНИЙ
# =========================================================

def thin_lines_ximgproc(lines: np.ndarray) -> np.ndarray:
    """
    Утончение линий + утолщение обратно примерно до 2 px.
    """
    if lines.dtype != np.uint8:
        lines = lines.astype(np.uint8)

    lines_bin = (lines > 0).astype(np.uint8) * 255

    thin = cv2.ximgproc.thinning(
        lines_bin,
        thinningType=cv2.ximgproc.THINNING_ZHANGSUEN,
    )

    thin = cv2.dilate(
        thin,
        cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
        1,
    )

    return thin


def render_pdf_to_images(pdf_path: Path, dpi: int = 200) -> list[tuple[int, np.ndarray]]:
    doc = fitz.open(str(pdf_path))
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    pages: list[tuple[int, np.ndarray]] = []

    for i in range(len(doc)):
        pix = doc.load_page(i).get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        pages.append((i + 1, img))

    return pages


def binarize_for_lines(bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        25,
        15,
    )


def detect_table_lines_mask(bgr: np.ndarray) -> np.ndarray:
    bw = binarize_for_lines(bgr)
    h, w = bw.shape[:2]

    k_h = max(20, w // 60)
    k_v = 31

    horiz = cv2.morphologyEx(
        bw,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (k_h, 1)),
    )

    vert = cv2.morphologyEx(
        bw,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_v)),
    )

    return cv2.bitwise_or(horiz, vert)


def draw_overlay_stage1(bgr: np.ndarray, line_mask: np.ndarray, out_png: Path) -> None:
    out = bgr.copy()

    mask2 = cv2.dilate(
        line_mask,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        1,
    )

    out[mask2 > 0] = (0, 255, 0)
    cv2.imwrite(str(out_png), out)


def process_stage1_page(
    bgr: np.ndarray,
    page_stem: str,
    doc_out: Path,
    source: dict,
) -> None:
    lines = detect_table_lines_mask(bgr)
    lines_clean = thin_lines_ximgproc(lines)

    overlay_path = doc_out / f"{page_stem}__overlay.png"
    mask_json_path = doc_out / f"{page_stem}__mask.json"
    mask_png_path = doc_out / f"{page_stem}__mask.png"

    draw_overlay_stage1(bgr, lines_clean, overlay_path)

    # сохранить бинарную маску как PNG
    cv2.imwrite(str(mask_png_path), lines_clean)

    save_mask_json(lines_clean, mask_json_path, page_stem, source=source)

    print("OK:", page_stem)




def run_stage1(input_dir: Path, out_dir: Path) -> None:
    files = list_inputs(input_dir)

    if not files:
        print("No input files.")
        return

    for f in files:
        doc_out = out_dir / f.stem
        doc_out.mkdir(parents=True, exist_ok=True)

        if f.suffix.lower() == ".pdf":
            pages = render_pdf_to_images(f, dpi=DPI)
            for page_idx, bgr in pages:
                page_stem = f"{f.stem}__p{page_idx:04d}"
                process_stage1_page(
                    bgr=bgr,
                    page_stem=page_stem,
                    doc_out=doc_out,
                    source={
                        "kind": "pdf",
                        "pdf_name": f.name,
                        "page_num_1based": int(page_idx),
                        "dpi": int(DPI),
                    },
                )
        else:
            bgr = cv2.imread(str(f))
            if bgr is None:
                continue

            process_stage1_page(
                bgr=bgr,
                page_stem=f.stem,
                doc_out=doc_out,
                source={
                    "kind": "image",
                    "file_name": f.name,
                },
            )

    print("Done. Results in:", out_dir)


# =========================================================
# ЗАГРУЗКА ОРИГИНАЛА
# =========================================================

def _resolve_image_path_by_name(file_name: str, input_dir: Path) -> Path | None:
    p = input_dir / file_name
    if p.exists():
        return p

    matches = sorted(
        p for p in input_dir.rglob("*")
        if p.is_file() and p.name == file_name
    )
    return matches[0] if matches else None


def _render_original_from_pdf(pdf_path: Path, page_num_1based: int, dpi: int) -> np.ndarray | None:
    try:
        doc = fitz.open(str(pdf_path))
        page_index = int(page_num_1based) - 1
        if page_index < 0 or page_index >= len(doc):
            return None

        zoom = float(dpi) / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = doc.load_page(page_index).get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        return img
    except Exception:
        return None


def resolve_original_image(page_id: str, input_dir: Path, mask_json_path: Path) -> tuple[np.ndarray | None, Path | None]:
    exts = [".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"]

    try:
        if str(mask_json_path).endswith(".gz"):
            with gzip.open(mask_json_path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(mask_json_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}

    source = data.get("source") or {}
    kind = source.get("kind")

    if kind == "image":
        file_name = source.get("file_name")
        if file_name:
            p = _resolve_image_path_by_name(file_name, input_dir)
            if p is not None:
                img = cv2.imread(str(p))
                if img is not None:
                    return img, p

    if kind == "pdf":
        pdf_name = source.get("pdf_name")
        page_num_1based = source.get("page_num_1based")
        dpi = int(source.get("dpi", 200))

        if pdf_name and page_num_1based is not None:
            pdf_path = _resolve_image_path_by_name(pdf_name, input_dir)
            if pdf_path is not None:
                img = _render_original_from_pdf(pdf_path, int(page_num_1based), dpi)
                if img is not None:
                    return img, pdf_path

    for ext in exts:
        p = input_dir / f"{page_id}{ext}"
        if p.exists():
            img = cv2.imread(str(p))
            if img is not None:
                return img, p

    matches = sorted(
        p for p in input_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in exts and p.stem == page_id
    )
    for p in matches:
        img = cv2.imread(str(p))
        if img is not None:
            return img, p

    return None, None


# =========================================================
# ЭТАП 2 — ОСИ, СЕГМЕНТЫ, ПОДДЕРЖКА
# =========================================================

def build_axis_masks(binary: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (H_OPEN, 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, V_OPEN))

    hmask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, hk)
    vmask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vk)

    h_close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (H_CLOSE, 1))
    v_close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, V_CLOSE))

    hmask = cv2.morphologyEx(hmask, cv2.MORPH_CLOSE, h_close_kernel)
    vmask = cv2.morphologyEx(vmask, cv2.MORPH_CLOSE, v_close_kernel)

    return hmask, vmask


def build_table_axis_masks(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Общая подготовка mask для table-логики.
    Возвращает:
    - bin_img
    - hmask
    - vmask (уже с доп. close 1x11)
    """
    bin_img = prepare_binary_mask(mask)
    hmask, vmask = build_axis_masks(bin_img)
    vmask = cv2.morphologyEx(
        vmask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, 11)),
    )
    return bin_img, hmask, vmask


def extract_h_segments(binary: np.ndarray, min_len: int) -> list[tuple[int, int, int]]:
    segs: list[tuple[int, int, int]] = []
    h, _ = binary.shape

    for y in range(h):
        xs = np.where(binary[y] > 0)[0]
        if len(xs) == 0:
            continue

        start = prev = int(xs[0])

        for x in xs[1:]:
            x = int(x)
            if x == prev + 1:
                prev = x
            else:
                if prev - start + 1 >= min_len:
                    segs.append((y, start, prev))
                start = prev = x

        if prev - start + 1 >= min_len:
            segs.append((y, start, prev))

    return segs


def extract_v_segments(binary: np.ndarray, min_len: int) -> list[tuple[int, int, int]]:
    segs: list[tuple[int, int, int]] = []
    _, w = binary.shape

    for x in range(w):
        ys = np.where(binary[:, x] > 0)[0]
        if len(ys) == 0:
            continue

        start = prev = int(ys[0])

        for y in ys[1:]:
            y = int(y)
            if y == prev + 1:
                prev = y
            else:
                if prev - start + 1 >= min_len:
                    segs.append((x, start, prev))
                start = prev = y

        if prev - start + 1 >= min_len:
            segs.append((x, start, prev))

    return segs


def row_vertical_support(row_y: int, v_segments: list[tuple[int, int, int]], x0: int, x1: int, band: int = 2) -> int:
    cnt = 0
    for x, y1, y2 in v_segments:
        if x0 <= x <= x1 and (y1 - band) <= row_y <= (y2 + band):
            cnt += 1
    return cnt


def col_horizontal_support(col_x: int, h_segments: list[tuple[int, int, int]], y0: int, y1: int, band: int = 2) -> int:
    cnt = 0
    for y, x1, x2 in h_segments:
        if y0 <= y <= y1 and (x1 - band) <= col_x <= (x2 + band):
            cnt += 1
    return cnt


def vertical_coverage(col_x: int, v_segments: list[tuple[int, int, int]], y0: int, y1: int, band: int = 3) -> float:
    spans: list[tuple[int, int]] = []

    for x, ya, yb in v_segments:
        if abs(x - col_x) <= band:
            a = max(ya, y0)
            b = min(yb, y1)
            if a <= b:
                spans.append((a, b))

    if not spans:
        return 0.0

    spans.sort()
    merged = [list(spans[0])]

    for a, b in spans[1:]:
        if a <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])

    covered = sum(b - a + 1 for a, b in merged)
    total = max(1, y1 - y0 + 1)
    return covered / total


def count_intersections(h_segments: list[tuple[int, int, int]], v_segments: list[tuple[int, int, int]], band: int = 2) -> int:
    intersections = 0
    for y, x1, x2 in h_segments:
        for x, y1, y2 in v_segments:
            if (x1 - band) <= x <= (x2 + band) and (y1 - band) <= y <= (y2 + band):
                intersections += 1
    return intersections


# =========================================================
# ЭТАП 2 — КЛАССИФИКАЦИЯ LAYOUT
# =========================================================

def detect_layout_type(mask: np.ndarray) -> tuple[str, dict]:
    bin_img = prepare_binary_mask(mask)

    hmask, vmask = build_axis_masks(bin_img)

    h_segments = extract_h_segments(hmask, 40)
    v_segments = extract_v_segments(vmask, 40)

    rows = merge_close_values([y for y, _, _ in h_segments], 3)
    cols = merge_close_values([x for x, _, _ in v_segments], 3)
    intersections = count_intersections(h_segments, v_segments, band=3)

    density = intersections / max(1, len(rows) * len(cols))

    if (
        len(rows) >= 6
        and len(cols) >= 4
        and (intersections > 60 or density > 0.25)
    ):
        return "table", {
            "rows_n": len(rows),
            "cols_n": len(cols),
            "intersections": intersections,
            "density": density,
        }

    return "form", {
        "rows_n": len(rows),
        "cols_n": len(cols),
        "intersections": intersections,
        "density": density,
    }


def has_form_structure(mask: np.ndarray) -> bool:
    bin_img = prepare_binary_mask(mask)

    hmask, vmask = build_axis_masks(bin_img)
    h_segments = extract_h_segments(hmask, 30)
    v_segments = extract_v_segments(vmask, 30)

    rows = merge_close_values([y for y, _, _ in h_segments], 3)
    cols = merge_close_values([x for x, _, _ in v_segments], 3)
    nonzero = int(np.count_nonzero(bin_img))

    return (
        nonzero > 500
        and (len(rows) >= 3 or len(cols) >= 2 or (len(h_segments) + len(v_segments)) >= 8)
    )


# =========================================================
# ЭТАП 2 — ПОИСК TABLE BLOCK
# =========================================================

def detect_table_start_row_by_dense_verticals(
    rows_all: list[int],
    v_segments: list[tuple[int, int, int]],
    cols_all: list[int],
    min_dense_support: int = 6,
    consecutive_rows: int = 2,
    band: int = 3,
) -> int | None:
    """
    Ищем первую строку, с которой начинается плотная вертикальная сетка.
    """
    if len(rows_all) < consecutive_rows:
        return None

    if not cols_all:
        return None

    x0, x1 = min(cols_all), max(cols_all)

    supports: list[tuple[int, int]] = []
    for r in rows_all:
        s = row_vertical_support(r, v_segments, x0, x1, band=band)
        supports.append((r, s))

    for i in range(len(supports) - consecutive_rows + 1):
        ok = True
        for j in range(consecutive_rows):
            if supports[i + j][1] < min_dense_support:
                ok = False
                break
        if ok:
            return supports[i][0]

    return None


def _select_candidate_cols(
    cols_all: list[int],
    h_segments: list[tuple[int, int, int]],
    y0: int,
    y1: int,
) -> list[int]:
    """
    Первый отбор колонок:
    - крайние колонки мягче
    - внутренние строже
    """
    cols: list[int] = []

    for col_idx, c in enumerate(cols_all):
        support = col_horizontal_support(c, h_segments, y0, y1, band=3)

        if col_idx == 0 or col_idx == len(cols_all) - 1:
            if support >= 1:
                cols.append(c)
            continue

        if support >= 2:
            cols.append(c)

    return cols


def _select_good_cols(
    cols: list[int],
    h_segments: list[tuple[int, int, int]],
    v_segments: list[tuple[int, int, int]],
    y0g: int,
    y1g: int,
) -> list[int]:
    """
    Финальный отбор колонок:
    - крайние оставляем мягко
    - внутренние принимаем либо по coverage,
      либо по сильной горизонтальной поддержке внутри грида
    """
    good_cols: list[int] = []

    if not cols:
        return good_cols

    x0, x1 = cols[0], cols[-1]
    total_h = max(1, y1g - y0g + 1)

    for col_idx, c in enumerate(cols):
        h_support = col_horizontal_support(c, h_segments, y0g, y1g, band=3)
        coverage = vertical_coverage(c, v_segments, y0g, y1g, band=3)
        covered_px = coverage * total_h

        if h_support < 2:
            continue

        # крайние колонки оставляем как раньше
        if col_idx == 0 or col_idx == len(cols) - 1:
            good_cols.append(c)
            continue

        # обычное правило
        if coverage >= 0.8:
            good_cols.append(c)
            continue

        # новое fallback-правило:
        # внутренняя колонка внутри грида + очень сильная поддержка строками
        inside_grid = (x0 + 5) <= c <= (x1 - 5)

        if inside_grid and h_support >= 20 and covered_px >= 80:
            good_cols.append(c)
            continue

    return good_cols


def find_strict_table_block(mask: np.ndarray) -> dict | None:
    _, hmask, vmask = build_table_axis_masks(mask)
    h, w = mask.shape[:2]

    min_h_len = max(MIN_H_LEN_ABS, int(w * 0.12))
    min_v_len = max(MIN_V_LEN_ABS, int(h * 0.08))

    h_segments = extract_h_segments(hmask, min_h_len)
    v_segments = extract_v_segments(vmask, min_v_len)

    if not h_segments or not v_segments:
        return None

    rows_all = merge_close_values([y for y, _, _ in h_segments], ROW_CLUSTER_TOL)
    cols_all = merge_close_values([x for x, _, _ in v_segments], COL_CLUSTER_TOL)

    table_start_y = detect_table_start_row_by_dense_verticals(
        rows_all,
        v_segments,
        cols_all,
        min_dense_support=6,
        consecutive_rows=2,
        band=3,
    )

    if table_start_y is not None:
        rows_all = [r for r in rows_all if r >= table_start_y]

    if len(rows_all) < MIN_ROW_COUNT or len(cols_all) < 3:
        return None

    def search_with_support(required_support: int) -> dict | None:
        best = None

        for i in range(len(rows_all)):
            for j in range(i + MIN_ROW_COUNT - 1, len(rows_all)):
                rows = rows_all[i:j + 1]
                if not rows:
                    continue

                y0, y1 = rows[0], rows[-1]

                cols = _select_candidate_cols(cols_all, h_segments, y0, y1)
                if len(cols) < required_support:
                    continue

                x0, x1 = cols[0], cols[-1]

                good_rows = [
                    r for r in rows
                    if row_vertical_support(r, v_segments, x0, x1, band=3) >= required_support
                ]
                if len(good_rows) < MIN_ROW_COUNT:
                    continue

                y0g, y1g = good_rows[0], good_rows[-1]

                good_cols = _select_good_cols(cols, h_segments, v_segments, y0g, y1g)
                if len(good_cols) < required_support:
                    continue

                score = (
                    len(good_rows) * 100
                    + len(good_cols) * 25
                    + (good_rows[-1] - good_rows[0]) * 0.8
                    + (good_cols[-1] - good_cols[0]) * 0.15
                )

                item = {
                    "rows": good_rows,
                    "cols": good_cols,
                    "score": score,
                    "required_support": required_support,
                    "mode": "strict",
                }

                if best is None or item["score"] > best["score"]:
                    best = item

        return best

    best = search_with_support(4)
    if best is not None:
        return best

    return search_with_support(3)


def find_continuation_table_block(mask: np.ndarray) -> dict | None:
    _, hmask, vmask = build_table_axis_masks(mask)
    h, w = mask.shape[:2]

    min_h_len = max(50, int(w * 0.12))
    min_v_len = max(35, int(h * 0.08))

    h_segments = extract_h_segments(hmask, min_h_len)
    v_segments = extract_v_segments(vmask, min_v_len)

    if not h_segments or not v_segments:
        return None

    rows = merge_close_values([y for y, _, _ in h_segments], ROW_CLUSTER_TOL)
    cols_all = merge_close_values([x for x, _, _ in v_segments], COL_CLUSTER_TOL)

    if len(rows) < MIN_ROW_COUNT or len(cols_all) < 4:
        return None

    best_run: list[int] = []
    current = [rows[0]]

    for r_prev, r in zip(rows, rows[1:]):
        if abs(r - r_prev) <= max(80, int(h * 0.05)):
            current.append(r)
        else:
            if len(current) > len(best_run):
                best_run = current[:]
            current = [r]

    if len(current) > len(best_run):
        best_run = current[:]

    best_rows = best_run if len(best_run) >= MIN_ROW_COUNT else rows
    y0, y1 = best_rows[0], best_rows[-1]

    stable_cols: list[int] = []
    for c in cols_all:
        cov = vertical_coverage(c, v_segments, y0, y1, band=3)
        if cov >= 0.45:
            stable_cols.append(c)

    if len(stable_cols) < 4:
        stable_cols = []
        for c in cols_all:
            cov = vertical_coverage(c, v_segments, y0, y1, band=3)
            if cov >= 0.25:
                stable_cols.append(c)

    if len(stable_cols) < 4:
        return None

    x0, x1 = stable_cols[0], stable_cols[-1]

    filtered_rows: list[int] = []
    for r in best_rows:
        supports = 0
        for y, xa, xb in h_segments:
            if abs(y - r) <= 2:
                inter = max(0, min(xb, x1) - max(xa, x0) + 1)
                if inter >= max(40, int((x1 - x0) * 0.35)):
                    supports += 1
        if supports > 0:
            filtered_rows.append(r)

    if len(filtered_rows) < MIN_ROW_COUNT:
        return None

    score = len(filtered_rows) * 100 + len(stable_cols) * 30 + (filtered_rows[-1] - filtered_rows[0]) * 0.5

    return {
        "rows": filtered_rows,
        "cols": stable_cols,
        "score": score,
        "mode": "continuation",
    }


def find_main_table_block(mask: np.ndarray) -> dict | None:
    best = find_strict_table_block(mask)
    if best is not None:
        return best
    return find_continuation_table_block(mask)


# =========================================================
# ЭТАП 2 — ВОССТАНОВЛЕНИЕ ГРАНИЦ
# =========================================================

def restore_missing_left_col_from_rows(mask: np.ndarray, table_block: dict | None, thickness: int = 2) -> tuple[dict | None, dict]:
    """
    Рабочий и устойчивый способ восстановления левой границы:
    не рисуем линию в маску,
    а добавляем недостающий x в cols на основе начал строк.
    """
    if table_block is None:
        return table_block, {
            "restored": False,
            "left_x": None,
            "reason": "table_block is None",
        }

    rows = merge_close_values(table_block.get("rows", []), 3)
    cols = merge_close_values(table_block.get("cols", []), 3)

    if len(rows) < 2 or len(cols) < 2:
        return table_block, {
            "restored": False,
            "left_x": None,
            "reason": "not enough rows/cols",
        }

    y0, y1 = min(rows), max(rows)

    bin_img = prepare_binary_mask(mask)
    hmask, _ = build_axis_masks(bin_img)

    min_h_len = max(MIN_H_LEN_ABS, int(mask.shape[1] * 0.12))
    h_segments = extract_h_segments(hmask, min_h_len)

    starts: list[int] = []

    for y, xa, xb in h_segments:
        if not (y0 - 8 <= y <= y1 + 8):
            continue
        starts.append(int(xa))

    if len(starts) < 3:
        return table_block, {
            "restored": False,
            "left_x": None,
            "reason": "too few starts",
        }

    left_x = int(np.percentile(starts, 10))

    if abs(left_x - cols[0]) < 15:
        return table_block, {
            "restored": False,
            "left_x": cols[0],
            "reason": "already close",
        }

    new_cols = merge_close_values([left_x] + cols, 3)

    new_block = dict(table_block)
    new_block["cols"] = new_cols

    return new_block, {
        "restored": True,
        "left_x": left_x,
        "reason": "restored from row starts",
    }


def restore_right_border_from_horizontal_ends(
    mask: np.ndarray,
    table_block: dict,
    min_h_len: int = RIGHT_BORDER_MIN_H_LEN,
    end_tol: int = RIGHT_BORDER_END_TOL,
    agree_ratio: float = RIGHT_BORDER_AGREE_RATIO,
    right_zone_ratio: float = RIGHT_BORDER_RIGHT_ZONE_RATIO,
    band: int = RIGHT_BORDER_BAND,
    thickness: int = RIGHT_BORDER_THICKNESS,
) -> tuple[np.ndarray, list[int] | None, list[int] | None, dict]:
    """
    Восстанавливает правую вертикальную границу таблицы
    по правым концам горизонталей внутри найденного блока.
    """
    if table_block is None:
        return mask, None, None, {
            "restored": False,
            "reason": "table_block is None",
            "right_x": None,
            "share": 0.0,
        }

    rows = merge_close_values(table_block.get("rows", []), 3)
    cols = merge_close_values(table_block.get("cols", []), 3)

    if len(rows) < 2 or len(cols) < 2:
        return mask, rows, cols, {
            "restored": False,
            "reason": "not enough rows/cols in table_block",
            "right_x": None,
            "share": 0.0,
        }

    y0, y1 = int(min(rows)), int(max(rows))
    x0, x1 = int(min(cols)), int(max(cols))

    bin_img = prepare_binary_mask(mask)
    hmask, _ = build_axis_masks(bin_img)
    h_segments = extract_h_segments(hmask, min_h_len)

    table_w = max(1, x1 - x0)
    right_zone_x = x0 + int(table_w * right_zone_ratio)

    candidate_ends: list[int] = []
    used_segments: list[tuple[int, int, int]] = []

    for y, xa, xb in h_segments:
        seg_len = xb - xa + 1
        if seg_len < min_h_len:
            continue

        if not (y0 - band <= y <= y1 + band):
            continue

        if xb < right_zone_x:
            continue

        if xb < x0 - band or xa > x1 + band:
            continue

        candidate_ends.append(int(xb))
        used_segments.append((int(y), int(xa), int(xb)))

    if len(candidate_ends) < 3:
        return mask, rows, cols, {
            "restored": False,
            "reason": "too few horizontal candidates",
            "right_x": None,
            "share": 0.0,
            "candidate_count": len(candidate_ends),
        }

    ends = np.array(sorted(candidate_ends), dtype=np.int32)

    med = float(np.median(ends))
    mad = float(np.median(np.abs(ends - med))) + 1e-6

    keep = np.abs(ends - med) <= max(end_tol * 2, 2.5 * mad + 4)
    ends_kept = ends[keep]

    if len(ends_kept) < 3:
        ends_kept = ends

    share = len(ends_kept) / max(1, len(ends))

    if share < agree_ratio:
        return mask, rows, cols, {
            "restored": False,
            "reason": f"share too low after filtering: {share:.3f}",
            "right_x": None,
            "share": share,
            "candidate_count": len(candidate_ends),
            "all_ends": candidate_ends,
            "kept_ends": ends_kept.tolist(),
        }

    best_x = int(np.percentile(ends_kept, 85))

    out = mask.copy()
    cv2.line(out, (best_x, y0), (best_x, y1), 255, thickness)

    rows2 = merge_close_values(rows, 3)

    base_cols = merge_close_values(cols, 3)
    base_cols = [c for c in base_cols if abs(c - best_x) > 6]
    cols2 = merge_close_values(base_cols + [best_x], 3)

    if len(rows2) >= 2:
        rows2 = [r for r in rows2 if (y0 - band) <= r <= (y1 + band)]
        rows2 = merge_close_values(rows2 + [y0, y1], 3)
    else:
        rows2 = rows

    info = {
        "restored": True,
        "reason": "ok",
        "right_x": best_x,
        "share": share,
        "candidate_count": len(candidate_ends),
        "all_ends": candidate_ends,
        "kept_ends": ends_kept.tolist(),
        "used_segments": used_segments,
    }

    return out, rows2, cols2, info


def rebuild_grid(mask: np.ndarray, table_block: dict | None) -> tuple[np.ndarray, np.ndarray, dict]:
    """
    Итоговая схема восстановления:
    1) table_block уже может быть поправлен по left col
    2) восстанавливаем только правую границу
    3) строим финальный grid
    """
    if table_block is None:
        return np.zeros_like(mask), mask.copy(), {
            "right_restored": False,
            "right_x": None,
        }

    mask2, rows2, cols2, right_info = restore_right_border_from_horizontal_ends(mask, table_block)

    if rows2 is None or cols2 is None or len(rows2) < 2 or len(cols2) < 2:
        rows0 = merge_close_values(table_block.get("rows", []), 3)
        cols0 = merge_close_values(table_block.get("cols", []), 3)
        grid0 = build_grid_mask(mask.shape, rows0, cols0, thickness=2)
        return grid0, mask2, {
            "right_restored": bool(right_info.get("restored", False)),
            "right_x": right_info.get("right_x"),
            "right_reason": right_info.get("reason"),
        }

    grid = build_grid_mask(mask.shape, rows2, cols2, thickness=2)

    return grid, mask2, {
        "right_restored": bool(right_info.get("restored", False)),
        "right_x": right_info.get("right_x"),
        "right_reason": right_info.get("reason"),
    }


# =========================================================
# ЭТАП 2 — OVERLAY / FORM
# =========================================================

def _cm_to_px(cm: float, dpi: int) -> int:
    return max(1, int(round(cm * dpi / 2.54)))


def _extract_axis_segments_for_unp(binary: np.ndarray) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    """
    Из бинарной ROI-маски достаёт горизонтальные и вертикальные сегменты.
    Возвращает:
      h_segments: [(y, x1, x2), ...]
      v_segments: [(x, y1, y2), ...]
    """
    h_open = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1)),
    )
    v_open = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, 25)),
    )

    h_segments = extract_h_segments(h_open, min_len=20)
    v_segments = extract_v_segments(v_open, min_len=20)
    return h_segments, v_segments


def _build_mask_from_segments(shape: tuple[int, int], h_segments, v_segments, thickness: int = 1) -> np.ndarray:
    out = np.zeros(shape, dtype=np.uint8)

    for y, x1, x2 in h_segments:
        cv2.line(out, (int(x1), int(y)), (int(x2), int(y)), 255, thickness)

    for x, y1, y2 in v_segments:
        cv2.line(out, (int(x), int(y1)), (int(x), int(y2)), 255, thickness)

    return out


def _segments_to_component_candidates(grid: np.ndarray):
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(grid, 8)
    candidates = []

    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]
        if area < 50:
            continue

        comp = (labels[y:y + h, x:x + w] == i).astype(np.uint8) * 255
        candidates.append({
            "bbox": (int(x), int(y), int(w), int(h)),
            "area": int(area),
            "mask": comp,
        })

    return candidates


def _analyze_unp_component(comp_mask: np.ndarray) -> dict | None:
    """
    Проверяет, можно ли считать компоненту UNP-блоком 2x2 / 2x3.
    Возвращает словарь с геометрией или None.
    """
    if comp_mask is None or comp_mask.size == 0:
        return None

    row_sum = (comp_mask > 0).sum(axis=1)
    col_sum = (comp_mask > 0).sum(axis=0)

    def merge_close(vals, tol=8):
        vals = sorted(int(v) for v in vals)
        if not vals:
            return []
        groups = [[vals[0]]]
        for v in vals[1:]:
            if abs(v - groups[-1][-1]) <= tol:
                groups[-1].append(v)
            else:
                groups.append([v])
        return [int(round(sum(g) / len(g))) for g in groups]

    h_, w_ = comp_mask.shape[:2]
    ys = merge_close(np.where(row_sum > max(10, int(w_ * 0.18)))[0], tol=8)
    xs = merge_close(np.where(col_sum > max(10, int(h_ * 0.18)))[0], tol=8)

    rows_n = len(ys) - 1
    cols_n = len(xs) - 1

    if rows_n == 2 and cols_n in (2, 3):
        return {
            "rows_n": rows_n,
            "cols_n": cols_n,
            "ys": ys,
            "xs": xs,
        }

    return None


def _clip_h_segment(seg, w: int, h: int):
    y, x1, x2 = seg
    y = max(0, min(h - 1, int(y)))
    x1 = max(0, min(w - 1, int(x1)))
    x2 = max(0, min(w - 1, int(x2)))
    if x2 < x1:
        x1, x2 = x2, x1
    return (y, x1, x2)


def _clip_v_segment(seg, w: int, h: int):
    x, y1, y2 = seg
    x = max(0, min(w - 1, int(x)))
    y1 = max(0, min(h - 1, int(y1)))
    y2 = max(0, min(h - 1, int(y2)))
    if y2 < y1:
        y1, y2 = y2, y1
    return (x, y1, y2)


def _extend_segments_stepwise(
    h_segments: list[tuple[int, int, int]],
    v_segments: list[tuple[int, int, int]],
    step_px: int,
    max_px: int,
    w: int,
    h: int,
):
    """
    Генерирует наборы сегментов:
    0 см, 0.5 см, 1.0 см, ... до 4 см.
    Горизонтали тянем влево/вправо.
    Вертикали тянем вверх/вниз.
    """
    yield h_segments, v_segments, 0

    steps = max_px // step_px
    for i in range(1, steps + 1):
        ext = i * step_px

        hs = []
        for y, x1, x2 in h_segments:
            hs.append(_clip_h_segment((y, x1 - ext, x2 + ext), w, h))

        vs = []
        for x, y1, y2 in v_segments:
            vs.append(_clip_v_segment((x, y1 - ext, y2 + ext), w, h))

        yield hs, vs, ext

def detect_unp_cells(mask: np.ndarray, table_top_y: int, dpi: int = 200):
    H, W = mask.shape[:2]

    # зона поиска: только над основной таблицей
    y0 = max(0, table_top_y - int(H * 0.26))
    y1 = max(y0 + 20, table_top_y - 20)

    roi = (mask[y0:y1] > 0).astype(np.uint8) * 255

    # ищем только центрально-правую часть шапки
    x0 = int(W * 0.18)
    x1 = int(W * 0.92)
    roi = roi[:, x0:x1]

    if roi.size == 0 or np.count_nonzero(roi) == 0:
        return []

    roi_h, roi_w = roi.shape[:2]

    # параметры вытягивания
    step_px = _cm_to_px(0.5, dpi)   # 0.5 см
    max_px = _cm_to_px(4.0, dpi)    # 4 см

    # 1) извлекаем осевые сегменты
    h_segments, v_segments = _extract_axis_segments_for_unp(roi)

    if not h_segments and not v_segments:
        return []

    # 2) сначала пробуем найти идеальный блок без вытягивания,
    #    потом с вытягиванием 0.5см, 1см, ... до 4см
    best_result = []
    best_score = -1

    for hs, vs, ext_px in _extend_segments_stepwise(
        h_segments=h_segments,
        v_segments=v_segments,
        step_px=step_px,
        max_px=max_px,
        w=roi_w,
        h=roi_h,
    ):
        grid = _build_mask_from_segments((roi_h, roi_w), hs, vs, thickness=1)

        # небольшой close, чтобы соединить почти касающиеся линии
        grid = cv2.morphologyEx(
            grid,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        )

        candidates = _segments_to_component_candidates(grid)

        for cand in candidates:
            x, y, w_box, h_box = cand["bbox"]
            area = cand["area"]
            comp = cand["mask"]

            # мягкие фильтры размера
            if area < 200:
                continue
            if not (20 <= h_box <= max(25, int(0.50 * roi_h))):
                continue
            if not (30 <= w_box <= int(0.80 * roi_w)):
                continue

            info = _analyze_unp_component(comp)
            if info is None:
                continue

            rows_n = info["rows_n"]
            cols_n = info["cols_n"]
            ys = info["ys"]
            xs = info["xs"]

            # собираем ячейки
            cells = []
            for r in range(rows_n):
                for c in range(cols_n):
                    cx1 = x0 + x + xs[c]
                    cx2 = x0 + x + xs[c + 1]
                    cy1 = y0 + y + ys[r]
                    cy2 = y0 + y + ys[r + 1]
                    cells.append((int(cx1), int(cy1), int(cx2), int(cy2)))

            # score:
            # - меньше вытягивание лучше
            # - 2x2 / 2x3 подходит
            # - чуть выше на странице лучше
            score = (
                area
                + cols_n * 500
                - y * 2
                - ext_px * 3
            )

            # как только нашли валидный 2x2/2x3 на текущем шаге —
            # можно сразу выбрать лучший среди найденных на этом шаге
            if score > best_score:
                best_score = score
                best_result = cells

        if best_result:
            return best_result

    return []


def build_form_overlay_mask(mask: np.ndarray) -> np.ndarray:
    out = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
    )
    out = cv2.dilate(
        out,
        cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
        iterations=1,
    )
    return out


def build_form_mask_above_table(mask: np.ndarray, table_top_y: int) -> np.ndarray:
    """
    Всё выше основной таблицы считаем формой.
    """
    form_mask = np.zeros_like(mask)
    if table_top_y <= 0:
        return form_mask

    form_mask[:table_top_y, :] = mask[:table_top_y, :]
    return form_mask


def build_grid_mask(shape: tuple[int, int], rows: list[int], cols: list[int], thickness: int = 2) -> np.ndarray:
    rows = merge_close_values(rows, 3)
    cols = merge_close_values(cols, 3)

    grid = np.zeros(shape, dtype=np.uint8)

    if len(rows) < 2 or len(cols) < 2:
        return grid

    x0, x1 = min(cols), max(cols)
    y0, y1 = min(rows), max(rows)

    for y in rows:
        cv2.line(grid, (x0, y), (x1, y), 255, thickness)

    for x in cols:
        cv2.line(grid, (x, y0), (x, y1), 255, thickness)

    return grid


def make_overlay(orig_bgr: np.ndarray, grid_mask: np.ndarray) -> np.ndarray:
    out = orig_bgr.copy()
    ys, xs = np.where(grid_mask > 0)
    out[ys, xs] = (0, 0, 255)
    return out


def make_overlay_two_colors(orig_bgr: np.ndarray, red_mask: np.ndarray | None = None, green_mask: np.ndarray | None = None) -> np.ndarray:
    out = orig_bgr.copy()

    if green_mask is not None:
        ys, xs = np.where(green_mask > 0)
        out[ys, xs] = (0, 255, 0)

    if red_mask is not None:
        ys, xs = np.where(red_mask > 0)
        out[ys, xs] = (0, 0, 255)

    return out

def detect_header_last_text_y(orig_bgr: np.ndarray, y1: int) -> int:
    h, w = orig_bgr.shape[:2]
    y1 = max(1, min(h, int(y1)))

    roi = orig_bgr[0:y1]
    if roi.size == 0:
        return 0

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    bw = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        25,
        15,
    )

    bw = cv2.morphologyEx(
        bw,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
    )

    bw = cv2.morphologyEx(
        bw,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (12, 3)),
    )

    cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    last_y = 0
    for c in cnts:
        x, y, ww, hh = cv2.boundingRect(c)

        if ww < 10 or hh < 6:
            continue
        if ww * hh < 80:
            continue

        last_y = max(last_y, y + hh)

    return last_y

def detect_footer_last_text_y(orig_bgr: np.ndarray, y0: int) -> int:
    h, w = orig_bgr.shape[:2]
    y0 = max(0, min(h - 1, int(y0)))

    roi = orig_bgr[y0:h]
    if roi.size == 0:
        return y0

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    bw = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        25,
        15,
    )

    bw = cv2.morphologyEx(
        bw,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
    )

    bw = cv2.morphologyEx(
        bw,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (12, 3)),
    )

    cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    last_y = y0
    for c in cnts:
        x, y, ww, hh = cv2.boundingRect(c)

        if ww < 10 or hh < 6:
            continue
        if ww * hh < 80:
            continue

        last_y = max(last_y, y0 + y + hh)

    return last_y


def draw_footer_blue_box(
    overlay: np.ndarray,
    table_bottom_y: int,
    footer_bottom_y: int,
    dpi: int = 200,
) -> tuple[np.ndarray, tuple[int, int, int, int] | None]:
    h, w = overlay.shape[:2]

    pad_x = _cm_to_px(0.5, dpi)
    pad_top = _mm_to_px(1.0, dpi)

    x1 = pad_x
    x2 = w - pad_x
    y1 = min(h - 1, table_bottom_y + pad_top)
    y2 = min(h - 1, footer_bottom_y)

    if y2 <= y1:
        return overlay, None

    out = overlay.copy()
    cv2.rectangle(out, (x1, y1), (x2, y2), (255, 0, 0), 3)
    return out, (x1, y1, x2, y2)

def draw_header_green_box(
    overlay: np.ndarray,
    header_bottom_y: int,
    dpi: int = 200,
) -> tuple[np.ndarray, tuple[int, int, int, int] | None]:
    h, w = overlay.shape[:2]

    pad_x = _cm_to_px(0.5, dpi)
    pad_bottom = _cm_to_px(0.3, dpi)

    x1 = pad_x
    x2 = w - pad_x
    y1 = _cm_to_px(0.5, dpi)
    y2 = min(h - 1, header_bottom_y + pad_bottom)

    if y2 <= y1:
        return overlay, None

    out = overlay.copy()
    cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 3)
    return out, (x1, y1, x2, y2)


# =========================================================
# ЭТАП 2 — ОБРАБОТКА СТРАНИЦ
# =========================================================

def _mm_to_px(mm: float, dpi: int) -> int:
    return max(1, int(round(mm * dpi / 25.4)))


def merge_nearby_h_segments(
    h_segments: list[tuple[int, int, int]],
    axis_tol: int = 3,
    gap_tol: int = 16,
) -> list[tuple[int, int, int]]:
    """
    Склеивает горизонтали, если:
    - они почти на одной высоте
    - расстояние между ними по X маленькое
    """
    if not h_segments:
        return []

    rows = merge_close_values([y for y, _, _ in h_segments], axis_tol)
    grouped: dict[int, list[tuple[int, int]]] = {r: [] for r in rows}

    for y, x1, x2 in h_segments:
        r = min(rows, key=lambda rr: abs(rr - y))
        if abs(r - y) <= axis_tol:
            grouped[r].append((int(x1), int(x2)))

    merged: list[tuple[int, int, int]] = []

    for y in rows:
        parts = sorted(grouped[y])
        if not parts:
            continue

        cur_x1, cur_x2 = parts[0]
        for x1, x2 in parts[1:]:
            if x1 <= cur_x2 + gap_tol:
                cur_x2 = max(cur_x2, x2)
            else:
                merged.append((int(y), int(cur_x1), int(cur_x2)))
                cur_x1, cur_x2 = x1, x2

        merged.append((int(y), int(cur_x1), int(cur_x2)))

    return merged


def merge_nearby_v_segments(
    v_segments: list[tuple[int, int, int]],
    axis_tol: int = 3,
    gap_tol: int = 16,
) -> list[tuple[int, int, int]]:
    """
    Склеивает вертикали, если:
    - они почти на одном X
    - расстояние между ними по Y маленькое
    """
    if not v_segments:
        return []

    cols = merge_close_values([x for x, _, _ in v_segments], axis_tol)
    grouped: dict[int, list[tuple[int, int]]] = {c: [] for c in cols}

    for x, y1, y2 in v_segments:
        c = min(cols, key=lambda cc: abs(cc - x))
        if abs(c - x) <= axis_tol:
            grouped[c].append((int(y1), int(y2)))

    merged: list[tuple[int, int, int]] = []

    for x in cols:
        parts = sorted(grouped[x])
        if not parts:
            continue

        cur_y1, cur_y2 = parts[0]
        for y1, y2 in parts[1:]:
            if y1 <= cur_y2 + gap_tol:
                cur_y2 = max(cur_y2, y2)
            else:
                merged.append((int(x), int(cur_y1), int(cur_y2)))
                cur_y1, cur_y2 = y1, y2

        merged.append((int(x), int(cur_y1), int(cur_y2)))

    return merged


def extract_form_geometry_segments(
    mask: np.ndarray,
    dpi: int = 200,
    min_h_len: int = 30,
    min_v_len: int = 30,
) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    """
    Для form-страницы:
    - берём только геометрические осевые линии
    - склеиваем близкие сегменты, если зазор <= 2 мм
    """
    bin_img = prepare_binary_mask(mask)
    hmask, vmask = build_axis_masks(bin_img)

    h_segments = extract_h_segments(hmask, min_len=min_h_len)
    v_segments = extract_v_segments(vmask, min_len=min_v_len)

    gap_tol = _mm_to_px(2.0, dpi)

    h_segments = merge_nearby_h_segments(
        h_segments,
        axis_tol=3,
        gap_tol=gap_tol,
    )
    v_segments = merge_nearby_v_segments(
        v_segments,
        axis_tol=3,
        gap_tol=gap_tol,
    )

    return h_segments, v_segments



def draw_form_geometry_overlay(
    orig: np.ndarray,
    h_segments: list[tuple[int, int, int]],
    v_segments: list[tuple[int, int, int]],
    color: tuple[int, int, int] = (0, 0, 255),
    thickness: int = 2,
) -> np.ndarray:
    out = orig.copy()

    for y, x1, x2 in h_segments:
        cv2.line(out, (int(x1), int(y)), (int(x2), int(y)), color, thickness)

    for x, y1, y2 in v_segments:
        cv2.line(out, (int(x), int(y1)), (int(x), int(y2)), color, thickness)

    return out

def _pick_outer_form_lines(
    h_segments: list[tuple[int, int, int]],
    v_segments: list[tuple[int, int, int]],
    min_h_len: int = 60,
    min_v_len: int = 60,
) -> dict | None:
    """
    Берём самые крайние длинные линии формы:
    - top:    самая верхняя горизонталь
    - bottom: самая нижняя горизонталь
    - left:   самая левая вертикаль
    - right:  самая правая вертикаль
    """
    h_long = [(y, x1, x2) for (y, x1, x2) in h_segments if abs(x2 - x1) >= min_h_len]
    v_long = [(x, y1, y2) for (x, y1, y2) in v_segments if abs(y2 - y1) >= min_v_len]

    if not h_long or not v_long:
        return None

    top = min(h_long, key=lambda s: s[0])
    bottom = max(h_long, key=lambda s: s[0])
    left = min(v_long, key=lambda s: s[0])
    right = max(v_long, key=lambda s: s[0])

    return {
        "top": top,
        "bottom": bottom,
        "left": left,
        "right": right,
    }

def extend_horizontal_segments_to_outer_verticals(
    h_segments,
    picked,
    max_ratio: float = 0.30,
) -> list[tuple[int, int, int]]:
    if picked is None:
        return h_segments

    left_x = int(picked["left"][0])
    right_x = int(picked["right"][0])

    out = []

    for y, x1, x2 in h_segments:
        y = int(y)
        x1 = int(x1)
        x2 = int(x2)

        line_len = max(1, x2 - x1)

        add_left = max(0, x1 - left_x)
        add_right = max(0, right_x - x2)

        can_extend_left = add_left <= max_ratio * line_len
        can_extend_right = add_right <= max_ratio * line_len

        new_x1 = left_x if can_extend_left else x1
        new_x2 = right_x if can_extend_right else x2

        out.append((y, new_x1, new_x2))

    return out



def _build_outer_rect_from_picked_lines(
    picked: dict | None,
    shape: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    """
    По 4 крайним линиям строим внешний прямоугольник:
    линии мысленно тянутся до пересечений,
    но в итоговый overlay рисуется только прямоугольник.
    """
    if picked is None:
        return None

    H, W = shape[:2]

    top_y = int(picked["top"][0])
    bottom_y = int(picked["bottom"][0])
    left_x = int(picked["left"][0])
    right_x = int(picked["right"][0])

    left_x = max(0, min(W - 1, left_x))
    right_x = max(0, min(W - 1, right_x))
    top_y = max(0, min(H - 1, top_y))
    bottom_y = max(0, min(H - 1, bottom_y))

    if right_x <= left_x or bottom_y <= top_y:
        return None

    return (left_x, top_y, right_x, bottom_y)


def _draw_outer_rect_on_overlay(
    overlay: np.ndarray,
    rect: tuple[int, int, int, int] | None,
    color: tuple[int, int, int] = (0, 0, 255),
    thickness: int = 2,
) -> np.ndarray:
    out = overlay.copy()

    if rect is None:
        return out

    x1, y1, x2, y2 = rect

    cv2.line(out, (x1, y1), (x2, y1), color, thickness)
    cv2.line(out, (x1, y2), (x2, y2), color, thickness)
    cv2.line(out, (x1, y1), (x1, y2), color, thickness)
    cv2.line(out, (x2, y1), (x2, y2), color, thickness)

    return out


def process_form_page(
    page_id: str,
    mask: np.ndarray,
    orig: np.ndarray,
    out_dir: Path,
    stats: dict,
) -> bool:
    h_segments, v_segments = extract_form_geometry_segments(
        mask,
        dpi=DPI,
        min_h_len=30,
        min_v_len=30,
    )

    picked = _pick_outer_form_lines(
        h_segments,
        v_segments,
        min_h_len=60,
        min_v_len=60,
    )

    h_segments_ext = extend_horizontal_segments_to_outer_verticals(
        h_segments,
        picked,
        max_ratio=0.80,
    )

    overlay = draw_form_geometry_overlay(
        orig,
        h_segments_ext,
        v_segments,
        color=(0, 0, 255),
        thickness=2,
    )

    outer_rect = _build_outer_rect_from_picked_lines(
        picked,
        shape=mask.shape,
    )

    overlay = _draw_outer_rect_on_overlay(
        overlay,
        outer_rect,
        color=(0, 0, 255),
        thickness=2,
    )

    # >>> ВОТ ЭТОГО У ТЕБЯ НЕ ХВАТАЛО
    # >>> ВОТ ЭТОГО У ТЕБЯ НЕ ХВАТАЛО
    # >>> ВОТ ЭТОГО У ТЕБЯ НЕ ХВАТАЛО
    # >>> ВОТ ЭТОГО У ТЕБЯ НЕ ХВАТАЛО
    # >>> ВОТ ЭТОГО У ТЕБЯ НЕ ХВАТАЛО
    form_rois = detect_form_closed_regions(
        mask,
        h_segments_ext,
        v_segments,
        outer_rect=outer_rect,
        min_area=100,
    )

    out_png = out_dir / f"{page_id}__form_red.png"
    out_meta_json = out_dir / f"{page_id}__meta.json"
    out_ocr_json = out_dir / f"{page_id}__ocr.json"

    cv2.imwrite(str(out_png), overlay)

    meta = {
        "page_id": page_id,
        "layout": "form",
        "layout_stats": stats,
        "reason": "detected as form",
        "render_mode": "geometry_segments_red_2px_plus_outer_rect_plus_extended_hlines",
        "h_segments_n": len(h_segments),
        "h_segments_extended_n": len(h_segments_ext),
        "v_segments_n": len(v_segments),
        "outer_lines_found": picked is not None,
        "outer_rect_found": outer_rect is not None,
        "outer_rect": None if outer_rect is None else [int(v) for v in outer_rect],
        "outer_top_line": None if picked is None else [int(v) for v in picked["top"]],
        "outer_bottom_line": None if picked is None else [int(v) for v in picked["bottom"]],
        "outer_left_line": None if picked is None else [int(v) for v in picked["left"]],
        "outer_right_line": None if picked is None else [int(v) for v in picked["right"]],
        "form_rois_n": len(form_rois),
    }

    out_meta_json.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    page_ocr = build_page_ocr_json(
        page_id=page_id,
        layout="form",
        image_shape=orig.shape,
        outer_rect=outer_rect,
        form_rois=form_rois,
        extra_meta={
            "render_mode": meta["render_mode"],
            "outer_lines_found": meta["outer_lines_found"],
            "outer_rect_found": meta["outer_rect_found"],
            "form_rois_n": len(form_rois),
        },
    )

    out_ocr_json.write_text(
        json.dumps(page_ocr, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("outer_lines_found:", picked is not None)
    print("outer_rect_found :", outer_rect is not None)
    print("form_rois_found  :", len(form_rois))
    print("saved:", out_png)
    print("saved:", out_meta_json)
    print("saved:", out_ocr_json)
    return True

def process_table_page(
    page_id: str,
    mask: np.ndarray,
    orig: np.ndarray,
    out_dir: Path,
    layout: str,
    stats: dict,
) -> bool:

    table_block = find_main_table_block(mask)
    table_block, left_fix_info = restore_missing_left_col_from_rows(mask, table_block)

    if table_block is None:
        return False

    grid_mask, mask_with_restored_right, rb_info = rebuild_grid(mask, table_block)

    rows, cols = extract_rows_cols_from_grid_mask(grid_mask)
    mode = table_block.get("mode", "table")

    if len(rows) < 2 or len(cols) < 2:
        return False

    table_top_y = int(min(rows))
    table_bottom_y = int(max(rows))


    # ---- detect header / unp above table ----
    header_mask = np.zeros_like(mask)
    header_mask[:table_top_y, :] = mask[:table_top_y, :]

    # сначала ищем UNP
    unp_cells = detect_unp_cells(mask, table_top_y, dpi=DPI)

    # если UNP найден, header_form_roi не строим
    header_form_rois = []

    if not unp_cells:
        h_segments_h, v_segments_h = extract_form_geometry_segments(
            header_mask,
            dpi=DPI,
            min_h_len=20,
            min_v_len=20,
        )

        header_form_rois = detect_form_closed_regions(
            header_mask,
            h_segments_h,
            v_segments_h,
            min_area=100,
        )

    footer_bottom_y = detect_footer_last_text_y(
        orig,
        table_bottom_y + _cm_to_px(0.3, DPI),
    )

    header_bottom_y = detect_header_last_text_y(
        orig,
        max(1, table_top_y - _cm_to_px(0.3, DPI)),
    )

    overlay = make_overlay_two_colors(
        orig,
        red_mask=grid_mask,
        green_mask=None,
    )

    overlay, header_box = draw_header_green_box(
        overlay,
        header_bottom_y=header_bottom_y,
        dpi=DPI,
    )

    overlay, footer_box = draw_footer_blue_box(
        overlay,
        table_bottom_y=table_bottom_y,
        footer_bottom_y=footer_bottom_y,
        dpi=DPI,
    )

    cols = extend_cols_with_page_boxes(
        cols,
        header_box=header_box,
        footer_box=footer_box,
        min_extra_width=120,
    )

    for x1, y1, x2, y2 in unp_cells:
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 165, 255), 3)

    out_png = out_dir / f"{page_id}__grid_red.png"
    out_mask_png = out_dir / f"{page_id}__mask_with_restored_right.png"

    cv2.imwrite(str(out_png), overlay)
    cv2.imwrite(str(out_mask_png), mask_with_restored_right)

    meta = {
        "page_id": page_id,
        "layout": layout,
        "layout_stats": stats,
        "table_mode": mode,
        "rows": rows,
        "cols": cols,
        "score": float(table_block.get("score", 0)),
        "table_top_y": table_top_y,
        "table_bottom_y": table_bottom_y,
        "header_box": header_box,
        "footer_box": footer_box,
    }

    (out_dir / f"{page_id}__meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ---------- OCR JSON ----------

    page_ocr = build_page_ocr_json(
        page_id=page_id,
        layout="table",
        image_shape=orig.shape,
        rows=rows,
        cols=cols,
        header_box=header_box,
        footer_box=footer_box,
        unp_cells=unp_cells,
        header_form_rois=header_form_rois,
    )

    (out_dir / f"{page_id}__ocr.json").write_text(
        json.dumps(page_ocr, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("saved:", out_png)
    print("saved:", out_dir / f"{page_id}__ocr.json")

    return True

# =========================================================
# MAIN
# =========================================================
# =========================================================
# MAIN
# =========================================================

def run_stage2(roi_root: Path, input_dir: Path, out_root: Path) -> None:
    mask_paths = sorted(roi_root.rglob("*__mask.json*"))
    print("found mask jsons:", len(mask_paths))

    ok = 0
    skip = 0
    skip_reasons: dict[str, int] = {}
    layout_counts = {"form": 0, "table": 0, "form_fallback": 0}

    def add_skip(reason: str) -> None:
        skip_reasons[reason] = skip_reasons.get(reason, 0) + 1

    for mask_path in mask_paths:
        name = mask_path.name

        if name.endswith("__mask.json.gz"):
            page_id = name[:-len("__mask.json.gz")]
        elif name.endswith("__mask.json"):
            page_id = name[:-len("__mask.json")]
        else:
            page_id = mask_path.stem.replace("__mask", "")

        print("\npage_id:", page_id)

        mask = load_mask_from_json(mask_path)
        if mask is None:
            reason = "mask not loaded"
            print("skip:", reason)
            add_skip(reason)
            skip += 1
            continue

        orig, orig_path = resolve_original_image(page_id, input_dir, mask_path)
        if orig_path is None or orig is None:
            reason = "original not found"
            print("skip:", reason)
            add_skip(reason)
            skip += 1
            continue

        if orig.shape[:2] != mask.shape[:2]:
            reason = f"shape mismatch: mask={mask.shape}, orig={orig.shape[:2]}"
            print("skip:", reason)
            add_skip(reason)
            skip += 1
            continue

        layout, stats = detect_layout_type(mask)
        layout_counts[layout] = layout_counts.get(layout, 0) + 1
        print("layout:", layout, stats)

        out_dir = out_root / page_id
        out_dir.mkdir(parents=True, exist_ok=True)

        if layout == "form":
            process_form_page(page_id, mask, orig, out_dir, stats)
            ok += 1
            continue

        saved = process_table_page(page_id, mask, orig, out_dir, layout, stats)
        if saved:
            ok += 1
            continue

        if has_form_structure(mask):
            process_form_page(page_id, mask, orig, out_dir, stats)
            layout_counts["form_fallback"] = layout_counts.get("form_fallback", 0) + 1
            ok += 1
            continue

        reason = "table not found and form not found"
        print("skip:", reason)
        add_skip(reason)
        skip += 1

    print("\nDONE")
    print("ok  :", ok)
    print("skip:", skip)
    print("out :", out_root)

    print("\nLAYOUT COUNTS:")
    for k, v in layout_counts.items():
        print(k, ":", v)

    print("\nSKIP REASONS:")
    for k, v in skip_reasons.items():
        print(k, ":", v)

if __name__ == "__main__":
    print("INPUT_DIR      :", INPUT_DIR)
    print("OUT_STAGE1_DIR :", OUT_STAGE1_DIR)
    print("OUT_STAGE2_DIR :", OUT_STAGE2_DIR)

    run_stage1(INPUT_DIR, OUT_STAGE1_DIR)
    run_stage2(OUT_STAGE1_DIR, INPUT_DIR, OUT_STAGE2_DIR)

