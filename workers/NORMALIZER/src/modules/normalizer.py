from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from src.config import config
from src.logger import get_logger
from src.models.file import FileJob, FileType
from src.modules import normalizer_core as core
from src.modules.base import BaseModule

logger = get_logger(__name__)


class NormalizerModule(BaseModule):
    name = "normalizer"
    description = "Normalize pred json files"
    version = "1.0.0"
    supported_file_types = {FileType.IMAGE, FileType.PDF}

    def __init__(self, module_config: Optional[Dict[str, Any]] = None):
        super().__init__(module_config)
        self.config = module_config or {}

    def process(self, job: FileJob) -> bool:
        start_time = time.time()
        try:
            base_dir = job.get_base_path(str(config.shared_files_dir))
            pred_dir = base_dir / "data" / "pred"
            pred_norm_dir = base_dir / "data" / "pred_normalized"
            pred_norm_dir.mkdir(parents=True, exist_ok=True)

            pred_files = sorted(pred_dir.glob("*.json"))
            normalized_count = 0
            for src in pred_files:
                with src.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                norm_data = core.normalize_pred(data)
                out_path = pred_norm_dir / src.name
                with out_path.open("w", encoding="utf-8") as handle:
                    json.dump(norm_data, handle, ensure_ascii=False, indent=2)
                normalized_count += 1

            duration = time.time() - start_time
            job.metadata.setdefault("normalizer", {})
            job.metadata["normalizer"].update(
                {
                    "pred_dir": str(pred_dir),
                    "pred_normalized_dir": str(pred_norm_dir),
                    "normalized": normalized_count,
                }
            )
            job.add_to_history("normalizer_process", self.name, True, duration=duration)
            logger.info("Normalizer completed: normalized=%s", normalized_count)
            return True
        except Exception as exc:
            duration = time.time() - start_time
            logger.exception("Normalizer exception: %s", exc)
            job.fail_module(self.name, str(exc))
            job.add_to_history("normalizer_process", self.name, False, error=str(exc), duration=duration)
            return False
