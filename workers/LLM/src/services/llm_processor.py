#!/usr/bin/env python3
# workers/LLM/src/services/llm_processor.py
"""
Сервис LLM-обработки.
Пайплайн: проверка pending → классификация → экстракция → сохранение JSON.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import json
from datetime import datetime, timezone, timedelta

from shared.utils.logger import setup_logger
from shared.models.file import FileJob
# 🔹 Импортируем DocumentType для конвертации строк в Enum
from shared.models.file.enums import DocumentType
from core.services.file_service import FileService
from workers.LLM.src.config import LLMProcessingConfig
from workers.LLM.src.llm.classifier import OllamaClassifier
from workers.LLM.src.llm.extractor import OllamaExtractor
from workers.LLM.schemas import get_schema_for_type

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

        # 🔹 Конфиг для классификатора (быстрая модель)
        classifier_config = {
            "ollama_endpoint": config.ollama_endpoint,
            "ollama_model": config.classifier_model,
            "ollama_timeout": config.ollama_timeout,
            "json_mode": True,
            "allowed_doc_types": list(config.allowed_doc_types),
        }

        # 🔹 Конфиг для экстрактора (мощная модель)
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
        Полный пайплайн LLM-обработки.
        Returns: Path к JSON-файлу, или None если требуется ожидание (pending).
        """
        fs = file_service or self.file_service
        if not fs:
            raise LLMProcessingError("FileService не предоставлен")

        # 🔍 0. Проверка состояния ожидания (Re-entry check)
        if job.classification_pending:
            if self._is_classification_timeout_expired(job):
                logger.warning(f"⏰ Таймаут ожидания UI для {job.file_id}. Fallback на LLM.")
                job.classification_pending = False
                job.metadata["classification_timeout_fallback"] = True
                job.metadata["classification_source"] = "llm_timeout_fallback"
                self._update_job_in_redis(job)
            else:
                logger.info(f"⏳ {job.file_id} ожидает классификацию от пользователя")
                return None  # Сигнал воркеру: пауза

        # 🔹 Чтение OCR-текста
        ocr_text = self._read_ocr_text(job, fs)
        if not ocr_text or len(ocr_text.strip()) < 50:
            raise LLMProcessingError(f"Слишком мало текста для LLM: {len(ocr_text or '')} симв.")

        logger.info(f"🎯 LLM обработка: {job.file_id} ({len(ocr_text)} симв.) {ocr_text[:500]}...")

        # ====================================================================
        # ЭТАП 1: Классификация документа
        # ====================================================================
        classification_result = self._handle_classification(job, ocr_text)

        if classification_result.get("pending"):
            return None  # Сигнал воркеру: пауза

        doc_type = classification_result["type"]  # str
        confidence = classification_result["confidence"]
        source = classification_result["source"]

        # Сохраняем метаданные
        job.metadata["document_type"] = doc_type
        job.metadata["classification_confidence"] = confidence
        job.metadata["classification_source"] = source

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

    def _is_classification_timeout_expired(self, job: FileJob) -> bool:
        """Проверяет, истёк ли таймаут ожидания пользователя."""
        if not job.user_classification_requested_at:
            return False

        requested_at = job.user_classification_requested_at
        # Парсинг из строки, если пришло из Redis
        if isinstance(requested_at, str):
            requested_at = datetime.fromisoformat(requested_at.replace('Z', '+00:00'))

        timeout_delta = timedelta(minutes=self.config.classification_pending_timeout_minutes)
        return datetime.now(timezone.utc) > (requested_at + timeout_delta)

    def _handle_classification(
            self,
            job: FileJob,
            ocr_text: str
    ) -> Dict[str, Any]:
        """
        State-first обработка классификации.
        Сначала сохраняем состояние в Redis, потом публикуем уведомление.

        🔹 КЛЮЧЕВОЕ: Все присваивания job.llm_classification_type используют Enum DocumentType
        """
        # 1. Приоритет: выбор пользователя
        # 🔹 ИСПРАВЛЕНО: self.config вместо config
        if job.user_classification_type and job.user_classification_type in self.config.allowed_doc_types:
            logger.info(f"✅ Используем классификацию от пользователя: {job.user_classification_type}")
            return {
                "type": job.user_classification_type,  # str для возврата
                "confidence": 1.0,
                "source": "user",
                "pending": False
            }

        # 2. Кэш: успешная классификация от LLM
        # 🔹 Проверяем через .value, т.к. в Redis хранится Enum
        llm_type_value = job.llm_classification_type.value if hasattr(job.llm_classification_type,
                                                                      'value') else job.llm_classification_type
        # 🔹 ИСПРАВЛЕНО: self.config вместо config
        if (llm_type_value and
                job.llm_classification_confidence is not None and
                job.llm_classification_confidence >= self.config.classification_threshold and
                llm_type_value in self.config.allowed_doc_types):
            return {
                "type": llm_type_value,  # str для возврата
                "confidence": job.llm_classification_confidence,
                "source": "llm",
                "pending": False
            }

        # 3. Запуск классификатора LLM
        doc_type_str, confidence = self.classifier.classify(ocr_text)  # ← возвращает (str, float)
        logger.info(f"📋 Авто-классификация LLM: {doc_type_str} (уверенность: {confidence:.2f})")

        # 🔹 КОНВЕРТАЦИЯ: строка → Enum DocumentType для корректной сериализации
        doc_type_enum = DocumentType.safe_parse(doc_type_str) or DocumentType.UNKNOWN

        # Сохраняем Enum в поле для сериализации
        job.llm_classification_type = doc_type_enum
        job.llm_classification_confidence = confidence
        job.llm_classification_at = datetime.now(timezone.utc)

        # 4. Проверка порога уверенности
        if confidence >= self.config.classification_threshold:
            return {
                "type": doc_type_enum.value,  # str для возврата
                "confidence": confidence,
                "source": "llm",
                "pending": False
            }

        # 5. Низкая уверенность → Запрос к UI (State-First)
        if self.redis:
            logger.warning(f"⚠️ Низкая уверенность ({confidence:.2f}), запрос к UI")

            # 🔹 ШАГ 1: Атомарно сохраняем состояние (ИСТОЧНИК ИСТИНЫ)
            job.classification_pending = True
            job.user_classification_requested_at = datetime.now(timezone.utc)
            job.metadata.update({
                "classification_pending": True,
                "llm_suggestion": doc_type_enum.value,  # str для UI
                "llm_confidence": confidence,
                # 🔹 ИСПРАВЛЕНО: self.config вместо config
                "allowed_types": list(self.config.allowed_doc_types),
            })
            # Сначала сохраняем, потом шлем уведомление
            self._update_job_in_redis(job)

            # 🔹 ШАГ 2: Публикуем уведомление (опционально, fire-and-forget)
            try:
                event = {
                    "type": "llm_classification_request",
                    "version": "1.0",
                    "file_id": job.file_id,
                    "suggested_type": doc_type_enum.value,  # str для UI
                    "confidence": confidence,
                    # 🔹 ИСПРАВЛЕНО: self.config вместо config
                    "allowed_types": list(self.config.allowed_doc_types),
                    "filename": job.original_filename,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                # Используем константу из модели
                self.redis.publish_event(FileJob.CHANNEL_UI_LLM_REQUESTS, event)
            except Exception as e:
                # Не критично, состояние уже в Redis
                logger.error(f"⚠️ Ошибка отправки уведомления: {e}")

            return {
                "type": doc_type_enum.value,  # str для возврата
                "confidence": confidence,
                "source": "llm",
                "pending": True
            }

        # Fallback: нет Redis → продолжаем с LLM
        logger.warning("⚠️ Нет Redis, используем LLM классификацию")
        return {
            "type": doc_type_enum.value,  # str для возврата
            "confidence": confidence,
            "source": "llm",
            "pending": False
        }

    def _update_job_in_redis(self, job: FileJob) -> None:
        """Обновление статуса в Redis."""
        if not self.redis:
            return
        try:
            self.redis.set_file_status(job.file_id, job.to_dict())
        except Exception as e:
            logger.error(f"❌ Ошибка обновления job в Redis: {e}", exc_info=True)
            raise LLMProcessingError(f"Не удалось сохранить состояние: {e}")

    def _read_ocr_text(self, job: FileJob, file_service: FileService) -> Optional[str]:
        """Читает текст из OCR-результата с детальным логированием."""

        # 🔹 1. Попытка через FileService (предпочтительный способ)
        try:
            preview = file_service.get_text_preview(job.file_id, file_type="ocr", max_lines=1000)
            if preview and len(preview.strip()) >= 50:
                logger.debug(f"✅ OCR-текст получен через preview: {len(preview)} симв.")
                logger.debug(f"📄 Preview (первые 300 симв.): {preview[:300]}")
                return preview
        except Exception as e:
            logger.debug(f"⚠️ Ошибка получения preview: {e}")

        # 🔹 2. Fallback: прямое чтение из файловой системы
        ocr_dir = Path(file_service.base_dir) / job.file_id / "ocr"
        logger.debug(f"🔍 Попытка прямого чтения из: {ocr_dir}")

        if not ocr_dir.exists():
            logger.warning(f"❌ Папка OCR не существует: {ocr_dir}")
            return None

        # 🔹 Логирование: что вообще есть в папке
        try:
            all_files = list(ocr_dir.iterdir())
            logger.debug(f"📁 Файлов в папке: {len(all_files)}")
            for f in all_files[:10]:  # Первые 10 файлов
                logger.debug(f"   - {f.name} ({f.stat().st_size} байт)")
        except Exception as e:
            logger.debug(f"⚠️ Не удалось перечислить файлы: {e}")

        # 🔹 Ищем файлы по шаблону
        pages = sorted(ocr_dir.glob(f"{job.file_id}_page_*.txt"))
        logger.debug(f"📄 Найдено файлов по шабону '{job.file_id}_page_*.txt': {len(pages)}")

        # 🔹 Если не найдено по шаблону — пробуем найти любые .txt файлы
        if not pages:
            pages = sorted(ocr_dir.glob("*.txt"))
            logger.debug(f"📄 Найдено любых .txt файлов: {len(pages)}")
            for p in pages:
                logger.debug(f"   - {p.name}")

        if not pages:
            logger.warning(f"❌ Не найдено текстовых файлов в {ocr_dir}")
            return None

        # 🔹 Читаем и логируем содержимое
        try:
            texts = []
            for i, page_file in enumerate(pages):
                # 🔹 Пробуем разные кодировки
                content = None
                for encoding in ["utf-8", "cp1251", "koi8-r", "latin-1"]:
                    try:
                        content = page_file.read_text(encoding=encoding)
                        logger.debug(f"✅ {page_file.name} прочитан с кодировкой {encoding}")
                        break
                    except UnicodeDecodeError:
                        continue

                if content is None:
                    logger.warning(f"⚠️ Не удалось прочитать {page_file.name} ни с одной кодировкой")
                    continue

                # 🔹 Логируем первые 200 символов каждого файла для отладки
                logger.debug(f"📝 {page_file.name} (первые 200 симв.): {content[:200].replace(chr(10), '↵')}")

                # 🔹 Фильтруем служебные файлы (если вдруг попали .json или .log)
                if page_file.suffix == ".txt" and len(content.strip()) > 10:
                    texts.append(content.strip())

            if not texts:
                logger.warning(f"❌ Ни один файл не удалось прочитать корректно")
                return None

            combined = "\n\n".join(texts)
            logger.debug(f"✅ Итоговый текст: {len(combined)} симв. из {len(texts)} файлов")
            return combined

        except Exception as e:
            logger.error(f"❌ Ошибка чтения OCR-файлов: {e}", exc_info=True)
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

        logger.debug(f"💾 JSON сохранён: {output_path}")
        return output_path