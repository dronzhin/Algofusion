# workers/LLM/src/services/llm_processor.py
"""
Сервис LLM-обработки.
Пайплайн: классификация → экстракция → XML-конвертация.
С поддержкой асинхронной классификации через UI.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import json
from datetime import datetime, timezone

from shared.utils.logger import setup_logger
from shared.models.file import FileJob, FileStatus
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
    """LLM-обработка в памяти с поддержкой асинхронной классификации."""

    def __init__(
        self,
        config: LLMProcessingConfig,
        redis_client=None,
        file_service: Optional[FileService] = None
    ):
        self.config = config
        self.redis = redis_client
        self.file_service = file_service

        # Инициализируем компоненты
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
        """
        Полный пайплайн LLM-обработки.

        Returns:
            Optional[Path]: Путь к XML-файлу, или None если требуется классификация от пользователя
        """
        fs = file_service or self.file_service
        if not fs:
            raise LLMProcessingError("FileService не предоставлен")

        # 🔹 Читаем OCR-текст
        ocr_text = self._read_ocr_text(job, fs)
        if not ocr_text or len(ocr_text.strip()) < 50:
            raise LLMProcessingError(f"Слишком мало текста для LLM: {len(ocr_text or '')} симв.")

        logger.info(f"🎯 LLM обработка: {job.file_id} ({len(ocr_text)} симв.)")

        # ====================================================================
        # ЭТАП 1: Классификация документа
        # ====================================================================
        classification_result = self._handle_classification(job, ocr_text)

        # Если классификация требует ввода пользователя — останавливаемся
        if classification_result.get("pending"):
            logger.info(f"⏳ Классификация отложена для {job.file_id}, ожидание UI")
            return None  # 🔹 Ключевое: возвращаем None, не блокируем воркер

        doc_type = classification_result["type"]
        confidence = classification_result["confidence"]
        source = classification_result["source"]

        # Сохраняем результат классификации в job
        job.metadata["document_type"] = doc_type
        job.metadata["classification_confidence"] = confidence
        job.metadata["classification_source"] = source

        # ====================================================================
        # ЭТАП 2: Экстракция структурированных данных
        # ====================================================================
        schema_obj = get_schema_for_type(doc_type)
        schema = schema_obj.get_json_schema() if schema_obj else {}

        extracted_data = self.extractor.extract(ocr_text, schema, doc_type)
        if not extracted_data:
            raise LLMProcessingError("Не удалось извлечь структурированные данные")

        logger.info(f"✅ Извлечено полей: {len(extracted_data)}")
        json_path = self._save_json_result(job, extracted_data, fs)

        # ====================================================================
        # ЭТАП 3: Конвертация в XML
        # ====================================================================
        xml_path = None
        if self.config.output_format == "xml":
            xml_path = self.converter.convert_to_file(
                data=extracted_data,
                doc_type=doc_type,
                job=job,
                file_service=fs
            )
            if xml_path:
                logger.info(f"📄 XML сохранён: {xml_path.name}")

        return xml_path

    def _handle_classification(
        self,
        job: FileJob,
        ocr_text: str
    ) -> Dict[str, Any]:
        """
        Обрабатывает классификацию: проверяет кэш, запускает LLM, при необходимости запрашивает у пользователя.

        Returns:
            Dict с ключами:
            - type: str — тип документа
            - confidence: float — уверенность
            - source: str — "llm" | "user"
            - pending: bool — True если требуется ввод пользователя
        """
        # 🔹 1. Проверяем, есть ли уже классификация от пользователя (приоритет)
        if job.user_classification_type and job.user_classification_type in self.config.allowed_doc_types:
            logger.info(f"✅ Используем классификацию от пользователя: {job.user_classification_type}")
            return {
                "type": job.user_classification_type,
                "confidence": 1.0,  # Пользователь = 100% уверенность
                "source": "user",
                "pending": False
            }

        # 🔹 2. Проверяем, есть ли классификация от LLM с высокой уверенностью
        if (job.llm_classification_type and
            job.llm_classification_confidence is not None and
            job.llm_classification_confidence >= self.config.classification_threshold and
            job.llm_classification_type in self.config.allowed_doc_types):

            logger.info(f"✅ Используем классификацию от LLM: {job.llm_classification_type} ({job.llm_classification_confidence:.2f})")
            return {
                "type": job.llm_classification_type,
                "confidence": job.llm_classification_confidence,
                "source": "llm",
                "pending": False
            }

        # 🔹 3. Если нет валидной классификации — классифицируем через LLM
        doc_type, confidence = self.classifier.classify(ocr_text)
        logger.info(f"📋 Авто-классификация LLM: {doc_type} (уверенность: {confidence:.2f})")

        # Сохраняем результат LLM в job (для кэширования и отображения в UI)
        job.llm_classification_type = doc_type
        job.llm_classification_confidence = confidence
        job.llm_classification_at = datetime.now(timezone.utc)

        # 🔹 4. Если уверенность высокая — используем результат LLM
        if confidence >= self.config.classification_threshold:
            logger.info(f"✅ Уверенность выше порога ({confidence:.2f} >= {self.config.classification_threshold}), продолжаем")
            return {
                "type": doc_type,
                "confidence": confidence,
                "source": "llm",
                "pending": False
            }

        # 🔹 5. Если уверенность низкая — асинхронный запрос к UI
        if self.redis:
            logger.warning(f"⚠️ Низкая уверенность ({confidence:.2f} < {self.config.classification_threshold}), запрос к UI")

            self._publish_classification_request(job, doc_type, confidence)

            # Обновляем статус job для отображения в UI
            job.classification_pending = True
            job.user_classification_requested_at = datetime.now(timezone.utc)
            job.metadata["classification_pending"] = True
            job.metadata["llm_suggestion"] = doc_type
            job.metadata["llm_confidence"] = confidence

            # Сохраняем состояние в Redis
            self._update_job_in_redis(job)

            return {
                "type": doc_type,  # Предложение LLM (может быть изменено пользователем)
                "confidence": confidence,
                "source": "llm",
                "pending": True  # 🔹 Ключевой флаг: требуется ввод пользователя
            }

        # 🔹 Fallback: если нет Redis — используем LLM несмотря на низкую уверенность
        logger.warning("⚠️ Нет Redis для запроса к UI, используем LLM классификацию")
        return {
            "type": doc_type,
            "confidence": confidence,
            "source": "llm",
            "pending": False
        }

    def _publish_classification_request(
        self,
        job: FileJob,
        suggested_type: str,
        confidence: float
    ) -> None:
        """Публикует запрос классификации в UI (асинхронно, без ожидания)."""
        event = {
            "type": "llm_classification_request",
            "version": "1.0",
            "file_id": job.file_id,
            "suggested_type": suggested_type,
            "confidence": confidence,
            "allowed_types": list(self.config.allowed_doc_types),
            "filename": job.original_filename,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            # 🔹 Дополнительные данные для отображения в UI
            "file_size": job.file_size,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }

        self.redis.publish(
            "ui:llm_requests",
            json.dumps(event, ensure_ascii=False)
        )
        logger.info(f"📤 Запрос классификации отправлен в UI для {job.file_id} (async)")

    def _update_job_in_redis(self, job: FileJob) -> None:
        """Обновляет состояние job в Redis для отображения в UI."""
        try:
            from shared.utils.redis_helpers import update_file_in_redis
            update_file_in_redis(self.redis, job)
        except Exception as e:
            logger.error(f"❌ Ошибка обновления job в Redis: {e}")

    def _read_ocr_text(self, job: FileJob, file_service: FileService) -> Optional[str]:
        """Читает текст из OCR-результата."""
        try:
            preview = file_service.get_text_preview(job.file_id, file_type="ocr", max_lines=1000)
            if preview and len(preview.strip()) >= 50:
                return preview
        except Exception as e:
            logger.debug(f"⚠️ get_text_preview не сработал: {e}")

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

    def _save_json_result(
        self,
        job: FileJob,
        data: Dict[str, Any],
        file_service: FileService
    ) -> Path:
        """Сохраняет извлечённые данные в JSON файл."""
        llm_dir = Path(file_service.base_dir) / job.file_id / "llm"
        llm_dir.mkdir(parents=True, exist_ok=True)

        output_path = llm_dir / f"{job.file_id}_llm.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.debug(f"💾 JSON сохранён: {output_path}")
        return output_path