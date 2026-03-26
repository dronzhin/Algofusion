from __future__ import annotations

import gzip
import json
from pathlib import Path

import cv2
import fitz
import numpy as np


def load_mask_from_json(mask_json_path: Path) -> np.ndarray | None:
    try:
        if str(mask_json_path).endswith(".gz"):
            with gzip.open(mask_json_path, "rt", encoding="utf-8") as handle:
                data = json.load(handle)
        else:
            data = json.loads(mask_json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"skip: bad json: {mask_json_path} {exc}")
        return None

    if "mask" not in data:
        print(f"skip: key 'mask' not found: {mask_json_path}")
        return None

    mask = np.array(data["mask"], dtype=np.uint8)
    if mask.ndim != 2:
        print(f"skip: mask is not 2D: {mask_json_path}")
        return None

    if mask.max() <= 1:
        mask = mask * 255
    else:
        mask = (mask > 0).astype(np.uint8) * 255
    return mask


def _resolve_image_path_by_name(file_name: str, input_dir: Path) -> Path | None:
    direct = input_dir / file_name
    if direct.exists():
        return direct

    matches = sorted(
        path for path in input_dir.rglob("*")
        if path.is_file() and path.name == file_name
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
            with gzip.open(mask_json_path, "rt", encoding="utf-8") as handle:
                data = json.load(handle)
        else:
            data = json.loads(mask_json_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}

    source = data.get("source") or {}
    kind = source.get("kind")

    if kind == "image":
        file_name = source.get("file_name")
        if file_name:
            path = _resolve_image_path_by_name(file_name, input_dir)
            if path is not None:
                img = cv2.imread(str(path))
                if img is not None:
                    return img, path

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
        path = input_dir / f"{page_id}{ext}"
        if path.exists():
            img = cv2.imread(str(path))
            if img is not None:
                return img, path

    matches = sorted(
        path for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in exts and path.stem == page_id
    )
    for path in matches:
        img = cv2.imread(str(path))
        if img is not None:
            return img, path

    return None, None
