from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import config
from src.logger import get_logger
from src.models.file import FileJob, FileType
from src.modules import layout_core as core
from src.modules.base import BaseModule

logger = get_logger(__name__)


class LayoutModule(BaseModule):
    name = "layout"
    description = "Combined Stage 1 and Stage 2 layout detection"
    version = "1.0.0"
    supported_file_types = {FileType.IMAGE, FileType.PDF}

    def __init__(self, module_config: Optional[Dict[str, Any]] = None):
        super().__init__(module_config)
        self.default_config = {"dpi": config.layout_dpi}
        self.config = {**self.default_config, **(module_config or {})}

    def process(self, job: FileJob) -> bool:
        start_time = time.time()

        if not self.validate_file_type(job):
            error = f"Unsupported file type: {job.file_type.value}"
            logger.warning(error)
            job.fail_module(self.name, error)
            return False

        try:
            input_dir = self._resolve_input_dir(job)
            stage1_dir = self._prepare_output_dir(job, "out_table_merge")
            stage2_dir = self._prepare_output_dir(job, "final_rebuilt_auto")

            core.DPI = int(self.config["dpi"])
            core.INPUT_DIR = input_dir
            core.OUT_STAGE1_DIR = stage1_dir
            core.OUT_STAGE2_DIR = stage2_dir

            core.run_stage1(input_dir, stage1_dir)
            core.run_stage2(stage1_dir, input_dir, stage2_dir)

            duration = time.time() - start_time
            stage1_masks = list(stage1_dir.rglob("*__mask.json")) + list(stage1_dir.rglob("*__mask.json.gz"))
            stage2_pages = list(stage2_dir.rglob("*__ocr.json"))

            job.metadata.setdefault("layout", {})
            job.metadata["layout"].update(
                {
                    "input_dir": str(input_dir),
                    "stage1_dir": str(stage1_dir),
                    "stage2_dir": str(stage2_dir),
                    "mask_count": len(stage1_masks),
                    "page_count": len(stage2_pages),
                    "dpi": core.DPI,
                }
            )
            job.add_to_history("layout_process", self.name, True, duration=duration)
            logger.info(
                "Layout completed: masks=%s stage2_pages=%s input=%s",
                len(stage1_masks),
                len(stage2_pages),
                input_dir,
            )
            return True
        except Exception as exc:
            duration = time.time() - start_time
            logger.exception("Layout exception: %s", exc)
            job.fail_module(self.name, str(exc))
            job.add_to_history("layout_process", self.name, False, error=str(exc), duration=duration)
            return False

    def _resolve_input_dir(self, job: FileJob) -> Path:
        base_dir = job.get_base_path(str(config.shared_files_dir))
        cleaner_dir = base_dir / "cleaner"
        original_dir = base_dir / "original"

        cleaner_files = [path for path in cleaner_dir.rglob("*") if path.is_file()]
        if cleaner_files:
            return cleaner_dir
        if original_dir.exists():
            return original_dir
        raise FileNotFoundError(f"No input files found for layout in {cleaner_dir} or {original_dir}")

    def _prepare_output_dir(self, job: FileJob, name: str) -> Path:
        output_dir = job.get_base_path(str(config.shared_files_dir)) / name
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
