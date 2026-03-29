from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import time

import cv2
import numpy as np
from pdf2image import convert_from_path
from PIL import Image, ImageFilter

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
        self.default_config = {
            "dpi": config.default_dpi,
            "output_dpi": config.output_dpi,
        }
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
                    "output_dpi": self.config["output_dpi"],
                    "a4_canvas_enabled": config.a4_canvas_enabled,
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
            cleaned = clean_page_bgr_exact(
                bgr,
                target_dpi=int(self.config["output_dpi"]),
            )
            output_path = output_dir / f"{input_path.stem}_p{idx:02d}_clean.png"
            cv2.imwrite(str(output_path), cleaned)
            outputs.append(output_path)
        return outputs

    def _process_image(self, input_path: Path, output_path: Path) -> Path:
        img = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Cannot read image: {input_path}")
        cleaned = clean_page_bgr_exact(
            img,
            target_dpi=int(self.config["output_dpi"]),
        )
        cv2.imwrite(str(output_path), cleaned)
        return output_path


def fit_to_a4_canvas(input_img: Image.Image, target_dpi: int = 600) -> Image.Image:
    if target_dpi <= 0:
        return input_img

    portrait_size = (
        max(1, int(round(8.27 * target_dpi))),
        max(1, int(round(11.69 * target_dpi))),
    )
    landscape_size = (portrait_size[1], portrait_size[0])
    target_size = portrait_size if input_img.height >= input_img.width else landscape_size

    scale = min(target_size[0] / input_img.width, target_size[1] / input_img.height)
    new_size = (
        max(1, int(round(input_img.width * scale))),
        max(1, int(round(input_img.height * scale))),
    )

    resized = input_img.resize(new_size, resample=Image.LANCZOS)
    fill = 255 if resized.mode == "L" else (255, 255, 255)
    canvas = Image.new(resized.mode, target_size, color=fill)
    offset = (
        (target_size[0] - new_size[0]) // 2,
        (target_size[1] - new_size[1]) // 2,
    )
    canvas.paste(resized, offset)
    return canvas


def detect_rotation_angle_notebook_style(image_bgr: np.ndarray) -> tuple[float, bool]:
    if image_bgr.ndim == 2:
        gray = image_bgr
    else:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0.0, False

    max_contour = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(max_contour)
    angle = float(rect[-1])
    if angle > 45:
        angle = angle + 270
    return angle, True


def rotate_image_by_angle(image: np.ndarray, angle: float) -> np.ndarray:
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, matrix, (w, h))


def rotate_image_notebook_style(image_bgr: np.ndarray) -> np.ndarray:
    angle, found = detect_rotation_angle_notebook_style(image_bgr)
    if not found:
        logger.info("Cleaner rotate: no contour found, skipping")
        return image_bgr
    if abs(angle) < config.rotate_min_abs_angle:
        return image_bgr
    logger.info("Cleaner rotate angle: %.2f", angle)
    return rotate_image_by_angle(image_bgr, angle)


def preprocessing_stage_4_1(input_img: Image.Image) -> Image.Image:
    arr = np.array(input_img.convert("RGB")).copy()
    rgb = arr[..., :3]
    min_val = rgb.min(axis=2)
    max_val = rgb.max(axis=2)
    diff = max_val - min_val
    mask = (diff >= config.stage41_diff_min) & (diff <= config.stage41_diff_max)
    rgb[mask] = np.stack([min_val[mask], min_val[mask], min_val[mask]], axis=1)
    arr[..., :3] = rgb
    return Image.fromarray(arr)


def preprocessing_stage_4_2(input_img: Image.Image) -> Image.Image:
    arr = np.array(input_img.convert("RGB")).copy()
    rgb = arr[..., :3]
    min_val = rgb.min(axis=2)
    max_val = rgb.max(axis=2)
    diff = max_val - min_val
    gray_value = ((min_val.astype(np.uint16) + max_val.astype(np.uint16)) // 2).astype(np.uint8)
    mask = (diff >= config.stage42_diff_min) & (diff <= config.stage42_diff_max)
    rgb[mask] = np.stack([gray_value[mask], gray_value[mask], gray_value[mask]], axis=1)
    arr[..., :3] = rgb
    return Image.fromarray(arr)


def preprocessing_stage_4_3(input_img: Image.Image) -> Image.Image:
    arr = np.array(input_img.convert("RGB")).copy()
    rgb = arr[..., :3]
    min_val = rgb.min(axis=2)
    max_val = rgb.max(axis=2)
    diff = max_val - min_val
    mask = (diff >= config.stage43_diff_min) & (diff <= config.stage43_diff_max)
    rgb[mask] = np.stack([max_val[mask], max_val[mask], max_val[mask]], axis=1)
    arr[..., :3] = rgb
    return Image.fromarray(arr)


def preprocessing_stage_5_2_background(input_img: Image.Image) -> Image.Image:
    arr = np.array(input_img).copy()
    arr[arr > config.background_threshold] = config.background_fill_value
    return Image.fromarray(arr.astype(np.uint8))


def preprocessing_stage_5_2_binary_and_denoise(input_img: Image.Image) -> Image.Image:
    arr = np.array(input_img).copy()
    arr[arr <= config.binary_threshold] = config.binary_foreground_value
    arr[arr > config.binary_threshold] = config.binary_background_value
    result = Image.fromarray(arr.astype(np.uint8))

    kernel = config.bin_median_kernel
    if kernel % 2 == 0:
        kernel += 1

    for _ in range(max(0, config.bin_median_passes)):
        result = result.filter(ImageFilter.MedianFilter(size=kernel))
    return result


def preprocess_page_bgr(
    image_bgr: np.ndarray,
    target_dpi: int = 600,
) -> np.ndarray:
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb)
    img = preprocessing_stage_4_1(img)
    img = preprocessing_stage_4_2(img)
    img = preprocessing_stage_4_3(img)
    img = preprocessing_stage_5_2_background(img)
    img = preprocessing_stage_5_2_binary_and_denoise(img)
    processed_rgb = np.array(img.convert("RGB"))
    processed_bgr = cv2.cvtColor(processed_rgb, cv2.COLOR_RGB2BGR)
    rotated = rotate_image_notebook_style(processed_bgr)
    img = Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB))
    if config.a4_canvas_enabled:
        img = fit_to_a4_canvas(img, target_dpi=target_dpi)
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def clean_page_bgr_exact(
    img_bgr: np.ndarray,
    target_dpi: int = 600,
) -> np.ndarray:
    return preprocess_page_bgr(img_bgr, target_dpi=target_dpi)
