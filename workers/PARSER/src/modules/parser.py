from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import config
from src.logger import get_logger
from src.models.file import FileJob, FileType
from src.modules import parser_core as core
from src.modules.base import BaseModule

logger = get_logger(__name__)


class ParserModule(BaseModule):
    name = "parser"
    description = "Parse ROI text into pred json files"
    version = "1.0.0"
    supported_file_types = {FileType.IMAGE, FileType.PDF}

    def __init__(self, module_config: Optional[Dict[str, Any]] = None):
        super().__init__(module_config)
        self.config = module_config or {}

    def process(self, job: FileJob) -> bool:
        start_time = time.time()
        try:
            base_dir = job.get_base_path(str(config.shared_files_dir))
            core.ROI_ROOT = base_dir / "final_rebuilt_auto" / "_clean_page_plus_roi_json"
            core.PRED_DIR = base_dir / "data" / "pred"
            core.PRED_DIR.mkdir(parents=True, exist_ok=True)

            roi_files = [
                path for path in sorted(core.ROI_ROOT.rglob("*_roi_text.json"))
                if path.name != "all_pages_roi_text.json"
            ]
            created = 0
            skipped = 0

            for roi_path in roi_files:
                doc_type = core.detect_doc_type(roi_path)
                if doc_type == "account_prot":
                    pred = core.parse_account_protocol(roi_path)
                elif doc_type == "invoice":
                    pred = core.parse_invoice(roi_path)
                elif doc_type == "payment_order":
                    pred = core.parse_payment_order(roi_path)
                elif doc_type == "waybill":
                    pred = core.parse_waybill(roi_path)
                else:
                    skipped += 1
                    continue

                out_name = roi_path.name.replace("_roi_text.json", ".json")
                out_path = core.PRED_DIR / out_name
                with out_path.open("w", encoding="utf-8") as handle:
                    json.dump(pred, handle, ensure_ascii=False, indent=2)
                created += 1

            duration = time.time() - start_time
            job.metadata.setdefault("parser", {})
            job.metadata["parser"].update(
                {
                    "roi_root": str(core.ROI_ROOT),
                    "pred_dir": str(core.PRED_DIR),
                    "created": created,
                    "skipped": skipped,
                }
            )
            job.add_to_history("parser_process", self.name, True, duration=duration)
            logger.info("Parser completed: created=%s skipped=%s", created, skipped)
            return True
        except Exception as exc:
            duration = time.time() - start_time
            logger.exception("Parser exception: %s", exc)
            job.fail_module(self.name, str(exc))
            job.add_to_history("parser_process", self.name, False, error=str(exc), duration=duration)
            return False
