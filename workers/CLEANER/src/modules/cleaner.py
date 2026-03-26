from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import time

import cv2
import numpy as np
from pdf2image import convert_from_path

from src.config import config
from src.logger import get_logger
from src.models.file import FileJob, FileType
from src.modules.base import BaseModule

logger = get_logger(__name__)


class CleanerModule(BaseModule):
    name = "cleaner"
    description = "Clean pages before layout detection"
    version = "1.0.0"
    supported_file_types = {FileType.IMAGE, FileType.PDF}

    def __init__(self, module_config: Optional[Dict[str, Any]] = None):
        super().__init__(module_config)
        self.default_config = {"dpi": config.default_dpi}
        self.config = {**self.default_config, **(module_config or {})}

    def process(self, job: FileJob) -> bool:
        start_time = time.time()

        if not self.validate_file_type(job):
            error = f"Unsupported file type: {job.file_type.value}"
            logger.warning(error)
            job.fail_module(self.name, error)
            return False

        input_path = job.get_original_path(str(config.shared_files_dir))
        output_dir = job.get_module_dir(self.name, str(config.shared_files_dir))

        if not input_path.exists():
            error = f"Input file not found: {input_path}"
            logger.error(error)
            job.fail_module(self.name, error)
            return False

        try:
            outputs = self._process_file(input_path, output_dir)
            duration = time.time() - start_time
            job.metadata.setdefault("cleaner", {})
            job.metadata["cleaner"].update(
                {
                    "outputs": [str(path) for path in outputs],
                    "count": len(outputs),
                    "dpi": self.config["dpi"],
                }
            )
            job.add_to_history("cleaner_process", self.name, True, duration=duration)
            logger.info("Cleaner completed: %s output(s)", len(outputs))
            return True
        except Exception as exc:
            duration = time.time() - start_time
            logger.exception("Cleaner exception: %s", exc)
            job.fail_module(self.name, str(exc))
            job.add_to_history("cleaner_process", self.name, False, error=str(exc), duration=duration)
            return False

    def _process_file(self, input_path: Path, output_dir: Path) -> list[Path]:
        ext = input_path.suffix.lower()
        if ext == ".pdf":
            return self._process_pdf(input_path, output_dir)
        return [self._process_image(input_path, output_dir / f"{input_path.stem}_clean.png")]

    def _process_pdf(self, input_path: Path, output_dir: Path) -> list[Path]:
        pages = convert_from_path(str(input_path), dpi=int(self.config["dpi"]))
        outputs: list[Path] = []
        for idx, page in enumerate(pages, start=1):
            rgb = np.array(page.convert("RGB"))
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            cleaned = clean_page_bgr_exact(bgr)
            output_path = output_dir / f"{input_path.stem}_p{idx:02d}_clean.png"
            cv2.imwrite(str(output_path), cleaned)
            outputs.append(output_path)
        return outputs

    def _process_image(self, input_path: Path, output_path: Path) -> Path:
        img = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Cannot read image: {input_path}")
        cleaned = clean_page_bgr_exact(img)
        cv2.imwrite(str(output_path), cleaned)
        return output_path


def deskew(gray: np.ndarray) -> np.ndarray:
    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        35,
        7,
    )
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 200:
        return gray

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle

    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        gray,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _remove_small_components(mask: np.ndarray, min_area: int = 24) -> np.ndarray:
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    cleaned = np.zeros_like(mask)
    for idx in range(1, num_labels):
        if stats[idx, cv2.CC_STAT_AREA] >= min_area:
            cleaned[labels == idx] = 255
    return cleaned


def clean_page_bgr_exact(img_bgr: np.ndarray) -> np.ndarray:
    gray0 = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    scale = 2
    gray = cv2.resize(gray0, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = deskew(gray)

    text_mask = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        35,
        7,
    )

    k = 60 * scale
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1))
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k))
    h_lines = cv2.morphologyEx(text_mask, cv2.MORPH_OPEN, kernel_h)
    v_lines = cv2.morphologyEx(text_mask, cv2.MORPH_OPEN, kernel_v)
    table_mask = cv2.bitwise_or(h_lines, v_lines)
    protect_mask = cv2.bitwise_or(text_mask, table_mask)

    bg = cv2.GaussianBlur(gray, (81, 81), 0)
    flat = cv2.divide(gray, bg, scale=255)
    flat = cv2.normalize(flat, None, 0, 255, cv2.NORM_MINMAX)

    foreground = cv2.adaptiveThreshold(
        flat,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        9,
    )
    foreground = cv2.bitwise_or(foreground, protect_mask)
    foreground = cv2.morphologyEx(
        foreground,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
    )
    foreground = _remove_small_components(foreground, min_area=24)

    restored = np.full_like(flat, 255)
    restored[foreground > 0] = flat[foreground > 0]
    restored = cv2.GaussianBlur(restored, (3, 3), 0)
    return cv2.resize(
        restored,
        (gray0.shape[1], gray0.shape[0]),
        interpolation=cv2.INTER_AREA,
    )
