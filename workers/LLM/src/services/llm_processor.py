"""
Сервис LLM-обработки.
Пайплайн: классификация → экстракция → XML-конвертация.
Все шаги выполняются с текстом в памяти.
Синхронизировано с core.services.file_service.FileService
"""

from pathlib import Path
from typing import Optional, Dict, Any
import json

from shared.utils.logger import setup_logger
from shared.models.file import FileJob
from core.services.file_service import FileService
from workers.LLM.src.config import LLMProcessingConfig
from workers.LLM.src.llm.classifier import OllamaClassifier
from workers.LLM.src.llm.extractor import OllamaExtractor
from workers.LLM.src.llm.converter import XmlConverter
from workers.LLM.schemas import get_schema_for_type

logger = setup_logger("workers.llm.services.llm_processor")


class LLMProcessingError(Exception):
    """Исключение при ошибке LLM-обработки."""
    pass


class LLMProcessor:
    """
    LLM-обработка в памяти.
    """

    def __init__(
        self,
        config: LLMProcessingConfig,
        redis_client=None,
        file_service: Optional[FileService] = None
    ):
        self.config = config
        self.redis = redis_client
        self.file_service = file_service

        # Инициализируем компоненты с конфиг-словарём
        engine_config = {
            "ollama_endpoint": config.ollama_endpoint,
            "ollama_model": config.ollama_model,
            "ollama_timeout": config.ollama_timeout,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "json_mode": config.json_mode,
            "allowed_doc_types": list(config.allowed_doc_types),
        }

        self.classifier = OllamaClassifier(engine_config)
        self.extractor = OllamaExtractor(engine_config)
        self.converter = XmlConverter({
            "xml_encoding": "utf-8",
            "xml_indent": "  ",
        })

    def process(
        self,
        job: FileJob,
        file_service: Optional[FileService] = None
    ) -> Optional[Path]:
        """Полный пайплайн LLM-обработки."""
        fs = file_service or self.file_service
        if not fs:
            raise LLMProcessingError("FileService не предоставлен")

        # 🔹 Читаем OCR-текст
        ocr_text = self._read_ocr_text(job, fs)
        if not ocr_text or len(ocr_text.strip()) < 50:
            raise LLMProcessingError(f"Слишком мало текста для LLM: {len(ocr_text or '')} симв.")

        logger.info(f"🎯 LLM обработка: {job.file_id} ({len(ocr_text)} симв.)")

        # ====================================================================
        # ЭТАП 1: Классификация
        # ====================================================================
        doc_type, confidence = self.classifier.classify(ocr_text)
        logger.info(f"📋 Классификация: {doc_type} (уверенность: {confidence:.2f})")

        if confidence < self.config.classification_threshold and self.redis:
            logger.warning(f"⚠️ Низкая уверенность ({confidence:.2f}), запрос к UI")
            doc_type = self._request_user_classification(job, doc_type, confidence)
            if not doc_type:
                raise LLMProcessingError("Таймаут ожидания ввода пользователя")
            logger.info(f"✅ Получен тип от пользователя: {doc_type}")

        job.metadata["document_type"] = doc_type
        job.metadata["classification_confidence"] = confidence

        # ====================================================================
        # ЭТАП 2: Экстракция
        # ====================================================================
        schema_obj = get_schema_for_type(doc_type)
        schema = schema_obj.get_json_schema() if schema_obj else {}

        extracted_data = self.extractor.extract(ocr_text, schema, doc_type)

        if not extracted_data:
            raise LLMProcessingError("Не удалось извлечь структурированные данные")

        logger.info(f"✅ Извлечено полей: {len(extracted_data)}")

        json_path = self._save_json_result(job, extracted_data, fs)
        logger.debug(f"💾 JSON сохранён: {json_path}")

        # ====================================================================
        # ЭТАП 3: Конвертация в XML
        # ====================================================================
        xml_path = None
        if self.config.output_format == "xml":
            # ✅ Исправленный вызов: convert_to_file(data, doc_type, job, file_service)
            xml_path = self.converter.convert_to_file(
                data=extracted_data,
                doc_type=doc_type,
                job=job,
                file_service=fs
            )
            if xml_path:
                logger.info(f"📄 XML сохранён: {xml_path.name}")

        return xml_path

    def _read_ocr_text(self, job: FileJob, file_service: FileService) -> Optional[str]:
        """Читает текст из OCR-результата."""
        # Попытка через FileService
        try:
            preview = file_service.get_text_preview(job.file_id, file_type="ocr", max_lines=1000)
            if preview and len(preview.strip()) >= 50:
                return preview
        except Exception as e:
            logger.debug(f"⚠️ get_text_preview не сработал: {e}")

        # Fallback: ручное чтение всех страниц
        ocr_dir = Path(file_service.base_dir) / job.file_id / "ocr"

        if not ocr_dir.exists():
            logger.warning(f"⚠️ OCR-директория не найдена: {ocr_dir}")
            return None

        pages = sorted(ocr_dir.glob(f"{job.file_id}_page_*.txt"))

        if not pages:
            logger.warning(f"⚠️ Нет файлов страниц в: {ocr_dir}")
            return None

        try:
            texts = [p.read_text(encoding="utf-8") for p in pages]
            return "\n\n".join(texts)
        except Exception as e:
            logger.error(f"❌ Ошибка чтения OCR-файлов: {e}")
            return None

    def _request_user_classification(
            self,
            job: FileJob,
            suggested_type: str,
            confidence: float,
            timeout: int = 300
    ) -> Optional[str]:
        """
        Запрашивает тип документа у пользователя через UI.

        Механизм:
        1. Публикует событие в канал "ui:llm_requests"
        2. Подписывается на ответный канал "{file_id}:llm_response"
        3. Ждёт ответ с таймаутом
        4. Возвращает выбранный тип документа или None при таймауте

        Args:
            job: FileJob с метаданными
            suggested_type: Тип, предложенный моделью
            confidence: Уверенность модели (0.0..1.0)
            timeout: Максимальное время ожидания в секундах

        Returns:
            Optional[str]: Выбранный тип документа или None
        """
        import time
        from datetime import datetime, timezone

        # Формируем событие для UI
        event = {
            "type": "llm_classification_request",
            "version": "1.0",
            "file_id": job.file_id,
            "suggested_type": suggested_type,
            "confidence": confidence,
            "allowed_types": list(self.config.allowed_doc_types),
            "filename": job.original_filename,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Публикуем в канал для UI
        self.redis.publish(
            "ui:llm_requests",
            json.dumps(event, ensure_ascii=False)
        )
        logger.info(f"📤 Запрос классификации отправлен в UI для {job.file_id}")

        # Подписываемся на ответный канал
        pubsub = self.redis.pubsub()
        response_channel = f"{job.file_id}:llm_response"
        pubsub.subscribe(response_channel)

        start_time = time.time()
        try:
            while time.time() - start_time < timeout:
                message = pubsub.get_message(timeout=1.0)

                if message and message["type"] == "message":
                    try:
                        response_data = json.loads(message["data"])
                        # ✅ Исправлено: проверка "document_type" in response_data
                        if response_data.get("file_id") == job.file_id and "document_type" in response_data:
                            doc_type = response_data["document_type"]
                            # Валидация типа
                            if doc_type in self.config.allowed_doc_types:
                                logger.info(f"✅ Получен тип от пользователя: {doc_type}")
                                return doc_type
                            else:
                                logger.warning(f"⚠️ Неверный тип документа: {doc_type}")
                    except json.JSONDecodeError as e:
                        logger.debug(f"⚠️ Ошибка парсинга ответа UI: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки ответа: {e}")
                        continue

            # Таймаут
            logger.warning(f"⏰ Таймаут ожидания ответа от пользователя для {job.file_id}")
            return None

        finally:
            # Гарантированная очистка подписки
            pubsub.unsubscribe(response_channel)
            pubsub.close()
            logger.debug(f"🔕 Подписка на {response_channel} закрыта")

    def _save_json_result(
            self,
            job: FileJob,
            data: Dict[str, Any],
            file_service: FileService
    ) -> Path:
        """
        Сохраняет извлечённые данные в JSON файл.

        Именование: {file_id}_llm.json (консистентно с OCR: {file_id}_page_N.txt)
        Папка: {base_dir}/{file_id}/llm/ (как определено в FileService)

        Args:
            job: FileJob с метаданными файла
             Извлечённые структурированные данные
            file_service: FileService для работы с путями

        Returns:
            Path: Путь к сохранённому файлу
        """
        # Используем структуру папок из FileService
        llm_dir = Path(file_service.base_dir) / job.file_id / "llm"
        llm_dir.mkdir(parents=True, exist_ok=True)

        # Имя файла: {file_id}_llm.json (единый файл на документ)
        output_path = llm_dir / f"{job.file_id}_llm.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.debug(f"💾 JSON сохранён: {output_path}")
        return output_path