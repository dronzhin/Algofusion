#!/usr/bin/env python3
# workers/OCR/src/ocr/surya.py
"""
Surya OCR движок (распознавание в памяти).
✅ Исправлено: патч rope_type + очистка кэша + совместимость версий
"""

from typing import List, Optional
from PIL import Image
import os
import shutil
import json

from shared.utils.logger import setup_logger
from workers.OCR.src.ocr.base import OCREngine

logger = setup_logger("workers.ocr.ocr.surya")


class SuryaEngine(OCREngine):
    """
    Surya OCR с обработкой в памяти.
    🔹 Только распознавание: PIL.Image → str
    🔹 Патч rope_type для совместимости с transformers >= 4.45
    🔹 Кэширование всех моделей на уровне класса
    """

    name = "surya"

    _recognizer = None
    _detector = None
    _foundation = None

    def __init__(self, config: dict):
        super().__init__(config)

        lang_config = config.get("lang", "rus+eng")
        if isinstance(lang_config, str):
            self.lang_list = lang_config.split("+")
        else:
            self.lang_list = list(lang_config)

        logger.info(f"🔤 Surya инициализирован: языки={self.lang_list}")

    @classmethod
    def _patch_rope_config(cls, config_path: str):
        """Патчит config.json модели, заменяя rope_type='default' на 'linear'."""
        config_file = os.path.join(config_path, "config.json")
        decoder_config_file = os.path.join(config_path, "decoder", "config.json")

        patched = False

        for cfg_file in [config_file, decoder_config_file]:
            if os.path.exists(cfg_file):
                try:
                    with open(cfg_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)

                    # 🔹 Патчим rope_type в корне конфига
                    if config.get('rope_type') == 'default':
                        config['rope_type'] = 'linear'
                        patched = True
                        logger.debug(f"✅ Запатчено rope_type в {cfg_file}")

                    # 🔹 Патчим вложенный decoder config
                    if 'decoder' in config and isinstance(config['decoder'], dict):
                        if config['decoder'].get('rope_type') == 'default':
                            config['decoder']['rope_type'] = 'linear'
                            patched = True
                            logger.debug(f"✅ Запатчено rope_type в decoder секции {cfg_file}")

                    if patched:
                        with open(cfg_file, 'w', encoding='utf-8') as f:
                            json.dump(config, f, indent=2, ensure_ascii=False)

                except Exception as e:
                    logger.warning(f"⚠️ Не удалось запатчить {cfg_file}: {e}")

        return patched

    @classmethod
    def _clear_surya_cache(cls):
        """Очищает кэш моделей Surya при ошибке загрузки."""
        cache_dirs = [
            os.path.expanduser("~/.cache/surya"),
            "/app/cache/surya",
        ]
        # Также ищем кэш huggingface для модели surya
        hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
        if os.path.exists(hf_cache):
            for item in os.listdir(hf_cache):
                if "surya" in item.lower() or "vikp" in item.lower():
                    cache_dirs.append(os.path.join(hf_cache, item))

        for cache_dir in cache_dirs:
            if os.path.exists(cache_dir):
                try:
                    shutil.rmtree(cache_dir)
                    logger.info(f"🗑️ Очищен кэш Surya: {cache_dir}")
                except Exception as e:
                    logger.debug(f"⚠️ Не удалось очистить кэш {cache_dir}: {e}")

    @classmethod
    def _ensure_models(cls):
        """Загрузка моделей Surya с патчем rope_type и обработкой ошибок."""

        # 🔹 1. Детектор
        if cls._detector is None:
            logger.info("🔤 Загрузка детектора Surya...")
            try:
                from surya.detection import DetectionPredictor
                cls._detector = DetectionPredictor()
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки детектора Surya: {e}")
                raise

        # 🔹 2. Foundation Predictor (с патчем rope_type)
        if cls._foundation is None:
            logger.info("🔤 Загрузка FoundationPredictor для Surya...")

            try:
                # 🔹 Патчим конфиг перед загрузкой, если модель уже в кэше
                from huggingface_hub import snapshot_download
                model_path = snapshot_download(
                    repo_id="vikp/surya",
                    local_files_only=True,  # Не качать, только локальный кэш
                    ignore_patterns=["*.safetensors"]  # Не загружать веса, только конфиг
                )
                cls._patch_rope_config(model_path)

            except Exception as e:
                logger.debug(f"⚠️ Не удалось запатчить кэш (возможно, ещё не скачан): {e}")

            try:
                # Пробуем разные пути импорта
                try:
                    from surya.model import FoundationPredictor
                except ImportError:
                    try:
                        from surya.foundation import FoundationPredictor
                    except ImportError:
                        from surya.models import FoundationPredictor

                cls._foundation = FoundationPredictor()

            except KeyError as e:
                if "'default'" in str(e) or "rope_type" in str(e):
                    logger.warning("⚠️ Ошибка rope_type='default' — очищаем кэш и патчим")
                    cls._clear_surya_cache()

                    # 🔹 Повторная загрузка с патчем
                    try:
                        from huggingface_hub import snapshot_download
                        model_path = snapshot_download(repo_id="vikp/surya")
                        cls._patch_rope_config(model_path)

                        from surya.foundation import FoundationPredictor
                        cls._foundation = FoundationPredictor()

                    except Exception as e2:
                        logger.error(f"❌ Повторная ошибка загрузки FoundationPredictor: {e2}")
                        raise
                else:
                    raise
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки FoundationPredictor: {e}")
                raise

        # 🔹 3. Распознаватель
        if cls._recognizer is None:
            logger.info("🔤 Загрузка распознавателя Surya...")
            try:
                from surya.recognition import RecognitionPredictor
                cls._recognizer = RecognitionPredictor(
                    foundation_predictor=cls._foundation
                )
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки RecognitionPredictor: {e}")
                raise

        return cls._recognizer, cls._detector

    def process(self, img: Image.Image) -> str:
        """Распознаёт текст на одном изображении в памяти."""
        logger.debug(f"🔤 Surya: {img.size}px, режим={img.mode}")

        if img.mode != "RGB":
            img = img.convert("RGB")

        try:
            recognizer, detector = self._ensure_models()

            predictions = recognizer(
                [img],
                det_predictor=detector,
                langs=[self.lang_list]
            )

            text_lines = []
            for page_pred in predictions:
                for line in getattr(page_pred, 'text_lines', []):
                    text = getattr(line, 'text', None)
                    if text and text.strip():
                        text_lines.append(text.strip())

            result = "\n".join(text_lines)
            logger.debug(f"✅ Surya: {len(result)} символов")
            return result

        except Exception as e:
            logger.error(f"❌ Ошибка инференса Surya: {e}", exc_info=True)
            # 🔹 При ошибке rope_type сбрасываем кэш
            if "rope_type" in str(e) or "'default'" in str(e):
                logger.warning("🔄 Сброс кэша Surya после ошибки rope_type")
                cls = SuryaEngine
                cls._foundation = None
                cls._recognizer = None
                cls._clear_surya_cache()
            raise

    def process_batch(self, images: List[Image.Image]) -> List[str]:
        """Пакетная обработка изображений."""
        if not images:
            return []

        logger.info(f"🔤 Surya: пакетная обработка {len(images)} изображений")

        rgb_images = [
            img.convert("RGB") if img.mode != "RGB" else img
            for img in images
        ]

        try:
            recognizer, detector = self._ensure_models()

            predictions = recognizer(
                rgb_images,
                det_predictor=detector,
                langs=[self.lang_list]
            )

            results = []
            for page_pred in predictions:
                text_lines = [
                    line.text.strip()
                    for line in getattr(page_pred, 'text_lines', [])
                    if getattr(line, 'text', None) and getattr(line, 'text', '').strip()
                ]
                results.append("\n".join(text_lines))

            logger.debug(f"✅ Surya batch: обработано {len(results)} изображений")
            return results

        except Exception as e:
            logger.error(f"❌ Ошибка пакетного инференса Surya: {e}", exc_info=True)
            raise