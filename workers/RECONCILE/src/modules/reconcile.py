from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from src.config import config
from src.logger import get_logger
from src.models.file import FileJob, FileType
from src.modules import reconcile_core as core
from src.modules.base import BaseModule

logger = get_logger(__name__)


class ReconcileModule(BaseModule):
    name = "reconcile"
    description = "Build reconciled predictions"
    version = "1.0.0"
    supported_file_types = {FileType.IMAGE, FileType.PDF}

    def __init__(self, module_config: Optional[Dict[str, Any]] = None):
        super().__init__(module_config)
        self.config = module_config or {}

    def process(self, job: FileJob) -> bool:
        start_time = time.time()
        try:
            base_dir = job.get_base_path(str(config.shared_files_dir))
            pred_norm_dir = base_dir / "data" / "pred_normalized"
            pred_recon_dir = base_dir / "data" / "pred_reconciled"
            pred_recon_dir.mkdir(parents=True, exist_ok=True)

            norm_files = sorted(pred_norm_dir.glob("*.json"))
            reconciled_count = 0
            for src in norm_files:
                with src.open("r", encoding="utf-8") as handle:
                    pred_normalized = json.load(handle)
                pred_reconciled = core.build_pred_reconciled(pred_normalized)
                out_path = pred_recon_dir / src.name
                with out_path.open("w", encoding="utf-8") as handle:
                    json.dump(pred_reconciled, handle, ensure_ascii=False, indent=2)
                reconciled_count += 1

            duration = time.time() - start_time
            job.metadata.setdefault("reconcile", {})
            job.metadata["reconcile"].update(
                {
                    "pred_normalized_dir": str(pred_norm_dir),
                    "pred_reconciled_dir": str(pred_recon_dir),
                    "reconciled": reconciled_count,
                }
            )
            job.add_to_history("reconcile_process", self.name, True, duration=duration)
            logger.info("Reconcile completed: reconciled=%s", reconciled_count)
            return True
        except Exception as exc:
            duration = time.time() - start_time
            logger.exception("Reconcile exception: %s", exc)
            job.fail_module(self.name, str(exc))
            job.add_to_history("reconcile_process", self.name, False, error=str(exc), duration=duration)
            return False
