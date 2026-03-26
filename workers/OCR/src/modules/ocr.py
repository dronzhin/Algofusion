from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import cv2

from src.config import config
from src.logger import get_logger
from src.models.file import FileJob, FileType
from src.modules import ocr_assign, ocr_input_helpers, ocr_prepare
from src.modules.base import BaseModule
from src.ocr import suraya  # noqa: F401
from src.ocr.registry import OCREngineRegistry

logger = get_logger(__name__)


class OCRModule(BaseModule):
    name = "ocr"
    description = "Prepare clean pages, run OCR, and assign text to ROI regions"
    version = "1.0.0"
    supported_file_types = {FileType.IMAGE, FileType.PDF}

    def __init__(self, module_config: Optional[Dict[str, Any]] = None):
        super().__init__(module_config)
        self.default_config = {
            "dpi": config.ocr_dpi,
            "engine": config.ocr_engine,
            "lang": config.ocr_lang,
        }
        self.config = {**self.default_config, **(module_config or {})}

    def process(self, job: FileJob) -> bool:
        start_time = time.time()

        if not self.validate_file_type(job):
            error = f"Unsupported file type: {job.file_type.value}"
            logger.warning(error)
            job.fail_module(self.name, error)
            return False

        try:
            base_dir = job.get_base_path(str(config.shared_files_dir))
            input_dir = self._resolve_input_dir(base_dir)
            stage1_dir = base_dir / "out_table_merge"
            stage2_dir = base_dir / "final_rebuilt_auto"
            ocr_dir = stage2_dir / "_clean_page_plus_roi_json"
            ocr_dir.mkdir(parents=True, exist_ok=True)

            prepare_count = self._run_prepare(input_dir, stage1_dir, stage2_dir, ocr_dir)
            raw_count = self._run_raw_ocr(ocr_dir)
            assign_count = self._run_roi_assignment(ocr_dir)

            duration = time.time() - start_time
            job.metadata.setdefault("ocr", {})
            job.metadata["ocr"].update(
                {
                    "input_dir": str(input_dir),
                    "ocr_dir": str(ocr_dir),
                    "prepared_pages": prepare_count,
                    "raw_pages": raw_count,
                    "assigned_pages": assign_count,
                    "engine": self.config["engine"],
                    "lang": self.config["lang"],
                }
            )
            job.add_to_history("ocr_process", self.name, True, duration=duration)
            logger.info(
                "OCR completed: prepared=%s raw=%s assigned=%s engine=%s",
                prepare_count,
                raw_count,
                assign_count,
                self.config["engine"],
            )
            return True
        except Exception as exc:
            duration = time.time() - start_time
            logger.exception("OCR exception: %s", exc)
            job.fail_module(self.name, str(exc))
            job.add_to_history("ocr_process", self.name, False, error=str(exc), duration=duration)
            return False

    def _resolve_input_dir(self, base_dir: Path) -> Path:
        cleaner_dir = base_dir / "cleaner"
        original_dir = base_dir / "original"

        cleaner_files = [path for path in cleaner_dir.rglob("*") if path.is_file()]
        if cleaner_files:
            return cleaner_dir
        if original_dir.exists():
            return original_dir
        raise FileNotFoundError(f"No OCR input files found in {cleaner_dir} or {original_dir}")

    def _run_prepare(self, input_dir: Path, stage1_dir: Path, stage2_dir: Path, ocr_dir: Path) -> int:
        mask_files = sorted(list(stage1_dir.rglob("*__mask.json")) + list(stage1_dir.rglob("*__mask.json.gz")))
        prepared = 0

        for mask_json_path in mask_files:
            meta = ocr_prepare.read_mask_meta(mask_json_path)
            page_id = meta.get("page_id", mask_json_path.stem.replace("__mask", ""))
            final_json_path = ocr_prepare.find_final_json_by_page_id(page_id, stage2_dir)
            if final_json_path is None:
                logger.warning("Skip OCR prepare: no stage2 json for %s", page_id)
                continue

            orig_bgr, _ = ocr_input_helpers.resolve_original_image(page_id, input_dir, mask_json_path)
            if orig_bgr is None:
                logger.warning("Skip OCR prepare: no input image for %s", page_id)
                continue

            line_mask = ocr_input_helpers.load_mask_from_json(mask_json_path)
            if line_mask is None:
                logger.warning("Skip OCR prepare: bad mask for %s", page_id)
                continue

            with final_json_path.open("r", encoding="utf-8") as handle:
                page_json = json.load(handle)

            clean_bgr = ocr_prepare.remove_lines(orig_bgr, line_mask)
            page_out_dir = ocr_dir / page_id
            page_out_dir.mkdir(parents=True, exist_ok=True)

            clean_page_path = page_out_dir / f"{page_id}__clean.png"
            roi_json_path = page_out_dir / f"{page_id}__roi_coords.json"
            roi_debug_path = page_out_dir / f"{page_id}__clean_with_roi.png"

            cv2.imwrite(str(clean_page_path), clean_bgr)

            objects = ocr_prepare.collect_objects(page_json)
            roi_items = []
            for obj in objects:
                item = ocr_prepare.extract_box(obj)
                if item is not None:
                    roi_items.append(item)

            roi_items = sorted(
                roi_items,
                key=lambda item: (
                    int(item["bbox"]["y1"]) // 15,
                    int(item["bbox"]["y1"]),
                    int(item["bbox"]["x1"]),
                ),
            )

            out_json = {
                "page_id": page_id,
                "clean_image": str(clean_page_path),
                "image_size": {
                    "width": int(clean_bgr.shape[1]),
                    "height": int(clean_bgr.shape[0]),
                },
                "rois": roi_items,
            }
            with roi_json_path.open("w", encoding="utf-8") as handle:
                json.dump(out_json, handle, ensure_ascii=False, indent=2)

            roi_debug_bgr = ocr_prepare.draw_rois_on_clean(clean_bgr, roi_items)
            cv2.imwrite(str(roi_debug_path), roi_debug_bgr)
            prepared += 1

        return prepared

    def _run_raw_ocr(self, ocr_dir: Path) -> int:
        engine = OCREngineRegistry.create(
            self.config["engine"],
            config={"lang": self.config["lang"], "dpi": self.config["dpi"]},
        )

        clean_png_files = sorted(ocr_dir.glob("*/*__clean.png"))
        all_pages = []
        saved = 0

        for clean_png in clean_png_files:
            page_id = clean_png.name.replace("__clean.png", "")
            result = engine.process(clean_png)
            if not result.success:
                raise RuntimeError(f"Raw OCR failed for {page_id}: {result.error}")

            payload = {
                "page_id": page_id,
                "engine": result.engine,
                "text": result.text,
                "ocr_items": result.metadata.get("ocr_items", []),
            }
            out_path = clean_png.parent / f"{page_id}__ocr_raw.json"
            with out_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            all_pages.append(payload)
            saved += 1

        with (ocr_dir / "all_pages_ocr_raw.json").open("w", encoding="utf-8") as handle:
            json.dump(all_pages, handle, ensure_ascii=False, indent=2)

        return saved

    def _run_roi_assignment(self, ocr_dir: Path) -> int:
        roi_json_files = sorted(ocr_dir.glob("*/*__roi_coords.json"))
        all_results_json = []
        saved = 0

        for roi_json in roi_json_files:
            file_id = roi_json.name.replace("__roi_coords.json", "")
            folder = roi_json.parent
            clean_png = folder / f"{file_id}__clean.png"
            raw_ocr_json = folder / f"{file_id}__ocr_raw.json"

            if not clean_png.exists() or not raw_ocr_json.exists():
                continue

            result_json, _ = ocr_assign.run_roi_assignment_pipeline(
                str(clean_png),
                str(roi_json),
                str(raw_ocr_json),
            )
            if result_json:
                all_results_json.append(result_json)
                saved += 1

        with (ocr_dir / "all_pages_roi_text.json").open("w", encoding="utf-8") as handle:
            json.dump(all_results_json, handle, ensure_ascii=False, indent=2)

        return saved
