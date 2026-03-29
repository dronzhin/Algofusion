from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import time

import cv2
import numpy as np
from pdf2image import convert_from_path
from PIL import Image

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


def detect_skew_angle_by_hough_lines(
    image: np.ndarray,
) -> tuple[float, bool]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, config.hough_canny1, config.hough_canny2, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180 / 4,
        threshold=config.hough_threshold,
        minLineLength=config.hough_min_line_length,
        maxLineGap=config.hough_max_line_gap,
    )

    angles: list[float] = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if abs(angle) <= config.hough_max_abs_angle:
                angles.append(angle)

    if not angles:
        return 0.0, False
    return float(np.median(angles)), True


def detect_skew_angle_by_text_contours(image: np.ndarray) -> tuple[float, bool]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    th = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        config.text_block_size,
        config.text_c,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (config.text_open_kernel, config.text_open_kernel))
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    angles: list[float] = []
    for cnt in contours:
        if cv2.contourArea(cnt) < config.text_min_contour_area:
            continue
        rect = cv2.minAreaRect(cnt)
        angle = float(rect[-1])
        if angle < -45:
            angle = 90 + angle
        angles.append(angle)

    if not angles:
        return 0.0, False
    return float(np.median(angles)), True


def detect_skew_angle(image: np.ndarray) -> float:
    angle, reliable = detect_skew_angle_by_hough_lines(image)
    if reliable:
        return angle
    angle, reliable = detect_skew_angle_by_text_contours(image)
    if reliable:
        return angle
    return 0.0


def rotate_image_by_angle(image: np.ndarray, angle: float) -> np.ndarray:
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def safe_rotate_image(image_bgr: np.ndarray) -> np.ndarray:
    angle = detect_skew_angle(image_bgr)
    if abs(angle) < config.rotate_min_abs_angle:
        return image_bgr
    if abs(angle) > config.rotate_max_abs_angle:
        logger.warning("Skipping rotate with suspicious angle: %.2f", angle)
        return image_bgr
    logger.info("Cleaner rotate angle: %.2f", angle)
    return rotate_image_by_angle(image_bgr, angle)


def preprocessing_stage_4_1(input_img: Image.Image) -> Image.Image:
    arr = np.array(input_img).copy()
    rgb = arr[..., :3]
    min_val = rgb.min(axis=2)
    max_val = rgb.max(axis=2)
    diff = max_val - min_val
    mask = (diff >= config.stage41_diff_min) & (diff <= config.stage41_diff_max)
    rgb[mask] = np.stack([min_val[mask], min_val[mask], min_val[mask]], axis=1)
    arr[..., :3] = rgb
    return Image.fromarray(arr)


def preprocessing_stage_4_2(input_img: Image.Image) -> Image.Image:
    arr = np.array(input_img).copy()
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
    arr = np.array(input_img).copy()
    rgb = arr[..., :3]
    min_val = rgb.min(axis=2)
    max_val = rgb.max(axis=2)
    diff = max_val - min_val
    mask = (diff >= config.stage43_diff_min) & (diff <= config.stage43_diff_max)
    rgb[mask] = np.stack([max_val[mask], max_val[mask], max_val[mask]], axis=1)
    arr[..., :3] = rgb
    return Image.fromarray(arr)


def preprocessing_stage_5_2_binarization(input_img: Image.Image) -> Image.Image:
    arr = np.array(input_img.convert("L"))
    result = arr.copy()
    result[result < config.bin_low_threshold] = 0
    result[(result >= config.bin_low_threshold) & (result <= config.bin_mid_threshold)] = 128
    result[result > config.bin_mid_threshold] = 255

    kernel = config.bin_median_kernel
    if kernel % 2 == 0:
        kernel += 1

    result = result.astype(np.uint8)
    for _ in range(max(0, config.bin_median_passes)):
        result = cv2.medianBlur(result, kernel)

    return Image.fromarray(result)


def preprocess_page_bgr(
    image_bgr: np.ndarray,
    target_dpi: int = 600,
) -> np.ndarray:
    rotated = safe_rotate_image(image_bgr)
    rgb = cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb)
    img = preprocessing_stage_4_1(img)
    img = preprocessing_stage_4_2(img)
    img = preprocessing_stage_4_3(img)
    img = preprocessing_stage_5_2_binarization(img)
    if config.a4_canvas_enabled:
        img = fit_to_a4_canvas(img, target_dpi=target_dpi)
    return np.array(img.convert("L"))


def clean_page_bgr_exact(
    img_bgr: np.ndarray,
    target_dpi: int = 600,
) -> np.ndarray:
    return preprocess_page_bgr(img_bgr, target_dpi=target_dpi)
