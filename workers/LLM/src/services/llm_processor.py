#!/usr/bin/env python3
# workers/LLM/src/services/llm_processor.py
"""
Сервис LLM-обработки.
Пайплайн: классификация → экстракция → сохранение JSON.
✅ УБРАНО: ожидание пользователя (pending), Redis-уведомления, отложенные очереди.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import json
from datetime import datetime, timezone

from shared.utils.logger import setup_logger
from shared.models.file import FileJob
from shared.models.file.enums import DocumentType
from core.services.file_service import FileService
from workers.LLM.src.config import LLMProcessingConfig
from workers.LLM.src.llm.classifier import OllamaClassifier
from workers.LLM.src.llm.extractor import OllamaExtractor
from workers.LLM.schemas import get_schema_for_type
from shared.utils.ocr_normalizer import normalize_ocr_text

logger = setup_logger("workers.llm.services.llm_processor")


class LLMProcessingError(Exception):
    """Исключение при ошибке LLM-обработки."""
    pass


class LLMProcessor:
    """
    LLM-обработка в памяти.
    Возвращает путь к JSON-файлу с извлечёнными данными.
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

        # 🔹 Конфиг для классификатора
        classifier_config = {
            "ollama_endpoint": config.ollama_endpoint,
            "ollama_model": config.classifier_model,
            "ollama_timeout": config.ollama_timeout,
            "json_mode": True,
            "allowed_doc_types": list(config.allowed_doc_types),
        }

        # 🔹 Конфиг для экстрактора
        extractor_config = {
            "ollama_endpoint": config.ollama_endpoint,
            "ollama_model": config.extractor_model,
            "ollama_timeout": config.ollama_timeout,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "json_mode": True,
        }

        self.classifier = OllamaClassifier(classifier_config)
        self.extractor = OllamaExtractor(extractor_config)

    def process(
            self,
            job: FileJob,
            file_service: Optional[FileService] = None
    ) -> Optional[Path]:
        """
        Полный пайплайн LLM-обработки (без ожидания пользователя).
        """
        fs = file_service or self.file_service
        if not fs:
            raise LLMProcessingError("FileService не предоставлен")

        # 🔹 Чтение и нормализация OCR-текста
        ocr_text = self._read_ocr_text(job, fs)
        if not ocr_text or len(ocr_text.strip()) < 50:
            raise LLMProcessingError(f"Слишком мало текста для LLM: {len(ocr_text or '')} симв.")

        ocr_text = normalize_ocr_text(ocr_text)
        logger.info(f"🎯 LLM обработка: {job.file_id} ({len(ocr_text)} симв.)")

        # ====================================================================
        # ЭТАП 1: Классификация документа (ВСЕГДА завершается, без pending)
        # ====================================================================
        doc_type, confidence = self.classifier.classify(ocr_text)
        logger.info(f"📋 Классификация: {doc_type} (уверенность: {confidence:.2f})")

        # Сохраняем метаданные
        job.metadata["document_type"] = doc_type
        job.metadata["classification_confidence"] = confidence
        job.metadata["classification_source"] = "llm"

        # 🔹 Явно сбрасываем любые флаги ожидания
        job.classification_pending = False

        # ====================================================================
        # ЭТАП 2: Экстракция структурированных данных
        # ====================================================================
        schema_obj = get_schema_for_type(doc_type)
        schema = schema_obj.json_schema if schema_obj else {}

        extracted_data = self.extractor.extract(ocr_text, schema, doc_type)
        if not extracted_data:
            raise LLMProcessingError("Не удалось извлечь структурированные данные")

        logger.info(f"✅ Извлечено полей: {len(extracted_data)}")

        # ====================================================================
        # ЭТАП 3: Сохранение JSON-результата
        # ====================================================================
        json_path = self._save_json_result(job, extracted_data, fs)
        job.metadata["llm_output_json"] = str(json_path.relative_to(fs.base_dir))
        job.metadata["extracted_fields_count"] = len(extracted_data)

        logger.info(f"💾 JSON сохранён: {json_path.name}")
        return json_path

    def _read_ocr_text(self, job: FileJob, file_service: FileService) -> Optional[str]:
        """Читает текст из OCR-результата."""
        # 🔹 Попытка через FileService
        try:
            preview = file_service.get_text_preview(job.file_id, file_type="ocr", max_lines=1000)
            if preview and len(preview.strip()) >= 50:
                return preview
        except Exception as e:
            logger.debug(f"⚠️ Ошибка получения preview: {e}")

        # 🔹 Fallback: прямое чтение
        ocr_dir = Path(file_service.base_dir) / job.file_id / "ocr"
        if not ocr_dir.exists():
            return None

        pages = sorted(list(ocr_dir.glob(f"{job.file_id}_page_*.txt")) or ocr_dir.glob("*.txt"))
        if not pages:
            return None

        texts = []
        for page_file in pages:
            content = None
            for encoding in ["utf-8", "cp1251", "koi8-r", "latin-1"]:
                try:
                    content = page_file.read_text(encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if content and page_file.suffix == ".txt" and len(content.strip()) > 10:
                texts.append(content.strip())

        return "\n\n".join(texts) if texts else None

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

        output_data = {
            "_meta": {
                "file_id": job.file_id,
                "original_filename": job.original_filename,
                "document_type": job.metadata.get("document_type"),
                "classification_confidence": job.metadata.get("classification_confidence"),
                "classification_source": job.metadata.get("classification_source"),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "model": getattr(self.extractor, 'model', 'unknown'),
            },
            **data
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)

        return output_path