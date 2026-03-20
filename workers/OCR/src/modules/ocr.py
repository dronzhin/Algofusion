# workers/ocr/src/modules/ocr.py
"""OCR модуль с поддержкой нескольких движков."""

from typing import Any, Dict, Optional
import json
import time

from src.modules.base import BaseModule
from src.models.file import FileJob, FileType
from src.ocr.registry import OCREngineRegistry
from src.logger import get_logger

logger = get_logger(__name__)


class OCRModule(BaseModule):
    """OCR модуль с выбором движка."""

    name = "ocr"
    description = "Распознавание текста через OCR"
    version = "1.0.0"
    supported_file_types = {FileType.IMAGE, FileType.PDF}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.default_config = {
            "engine": "tesseract",
            "lang": "rus+eng",
            "preprocess": False
        }
        self.config = {**self.default_config, **(config or {})}

    def process(self, job: FileJob) -> bool:
        """Обработка файла через OCR."""
        start_time = time.time()

        if not self.validate_file_type(job):
            logger.warning(f"Файл не поддерживается: {job.file_type.value}")
            job.fail_module(self.name, f"Неподдерживаемый тип: {job.file_type.value}")
            return False

        input_path = job.get_module_input_path("ocr")
        output_path = job.get_module_output_path("ocr")

        if not input_path.exists():
            logger.error(f"Файл не найден: {input_path}")
            job.fail_module(self.name, f"Файл не найден: {input_path}")
            return False

        engine_name = job.ocr_engine or self.config.get("engine", "tesseract")
        engine_config = {
            "lang": job.ocr_lang or self.config.get("lang", "rus+eng"),
            "preprocess": self.config.get("preprocess", False)
        }

        logger.info(f"OCR обработка: движок={engine_name}, язык={engine_config['lang']}")

        try:
            engine = OCREngineRegistry.create(engine_name, engine_config)
            result = engine.process(input_path, output_path)

            duration = time.time() - start_time

            if result.success:
                logger.info(
                    f"OCR завершён: {len(result.text)} символов, "
                    f"уверенность={result.confidence:.2f}, "
                    f"время={duration:.2f}с"
                )

                metadata_path = output_path.parent / f"{output_path.stem}.meta.json"
                metadata_path.write_text(
                    json.dumps(result.metadata, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )

                job.add_to_history(
                    action="ocr_process",
                    module=self.name,
                    success=True,
                    duration=duration,
                    error=None
                )

                return True
            else:
                logger.error(f"OCR ошибка: {result.error}")
                job.fail_module(self.name, result.error)
                return False

        except ValueError as e:
            logger.error(f"OCR движок не найден: {e}")
            job.fail_module(self.name, str(e))
            return False
        except Exception as e:
            duration = time.time() - start_time
            logger.exception(f"OCR исключение: {e}")
            job.fail_module(self.name, str(e))
            job.add_to_history(
                action="ocr_process",
                module=self.name,
                success=False,
                error=str(e),
                duration=duration
            )
            return False

    def get_available_engines(self) -> Dict[str, str]:
        """Получить список доступных движков."""
        return OCREngineRegistry.list_available()