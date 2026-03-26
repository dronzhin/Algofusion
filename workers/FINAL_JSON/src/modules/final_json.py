from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from src.config import config
from src.logger import get_logger
from src.models.file import FileJob, FileType
from src.modules import final_json_core as core
from src.modules.base import BaseModule

logger = get_logger(__name__)


class FinalJsonModule(BaseModule):
    name = "final_json"
    description = "Build final json output"
    version = "1.0.0"
    supported_file_types = {FileType.IMAGE, FileType.PDF}

    def __init__(self, module_config: Optional[Dict[str, Any]] = None):
        super().__init__(module_config)
        self.config = module_config or {}

    def process(self, job: FileJob) -> bool:
        start_time = time.time()
        try:
            base_dir = job.get_base_path(str(config.shared_files_dir))
            input_dir = base_dir / "data" / "pred_reconciled"
            output_dir = base_dir / "data" / "final_json"
            output_dir.mkdir(parents=True, exist_ok=True)

            src_files = sorted(input_dir.glob("*.json"))
            saved = 0
            for src in src_files:
                with src.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                final_json = core.build_final_json(data, file_key=job.file_id)
                out_path = output_dir / src.name
                with out_path.open("w", encoding="utf-8") as handle:
                    json.dump(final_json, handle, ensure_ascii=False, indent=2)
                saved += 1

            duration = time.time() - start_time
            job.metadata.setdefault("final_json", {})
            job.metadata["final_json"].update(
                {
                    "pred_reconciled_dir": str(input_dir),
                    "final_json_dir": str(output_dir),
                    "saved": saved,
                }
            )
            job.add_to_history("final_json_process", self.name, True, duration=duration)
            logger.info("Final JSON completed: saved=%s", saved)
            return True
        except Exception as exc:
            duration = time.time() - start_time
            logger.exception("Final JSON exception: %s", exc)
            job.fail_module(self.name, str(exc))
            job.add_to_history("final_json_process", self.name, False, error=str(exc), duration=duration)
            return False
