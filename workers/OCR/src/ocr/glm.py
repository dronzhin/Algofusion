#!/usr/bin/env python3
# workers/OCR/src/ocr/glm.py
"""
GLM-OCR движок на базе transformers (zai-org/GLM-OCR).
✅ Работает через apply_chat_template — как в официальном примере HuggingFace.
"""

from typing import List, Optional
from PIL import Image
import torch
import warnings
import time

from shared.utils.logger import setup_logger
from workers.OCR.src.ocr.base import OCREngine
from transformers import AutoProcessor, AutoModelForImageTextToText

logger = setup_logger("workers.ocr.ocr.glm")

# =============================================================================
# 🔹 МОДУЛЬНЫЙ КЭШ
# =============================================================================
_MODULE_CACHE = {
    "model": None,
    "processor": None,
    "device": None,
    "loaded": False,
    "model_id": None,
}


class GLMEngine(OCREngine):
    """
    GLM-OCR с использованием официального API через apply_chat_template.
    🔹 Только распознавание: PIL.Image → str
    🔹 Кэширование моделей на уровне класса
    🔹 Работает точно как в примере из HuggingFace
    """

    name = "glm"
    MODEL_ID = "zai-org/GLM-OCR"

    _model = None
    _processor = None
    _device = None

    def __init__(self, config: dict):
        super().__init__(config)

        lang_config = config.get("lang", "rus+eng")
        self.lang_list = lang_config.split("+") if isinstance(lang_config, str) else list(lang_config)
        self.prompt = config.get("glm_prompt", "Text Recognition:")
        self.max_tokens = config.get("glm_max_tokens", 8192)

        logger.info(f"🔤 GLM-OCR инициализирован: языки={self.lang_list}, промпт='{self.prompt}'")

    @classmethod
    def _ensure_models(cls):
        """Загрузка моделей с явным управлением памятью (без accelerate-хуков)."""
        if cls._model is not None and cls._processor is not None:
            logger.debug("✅ Кэш класса GLM-OCR: HIT")
            return cls._model, cls._processor, cls._device

        if _MODULE_CACHE["loaded"] and _MODULE_CACHE["model_id"] == cls.MODEL_ID:
            logger.info("✅ Кэш модуля GLM-OCR: HIT")
            cls._model = _MODULE_CACHE["model"]
            cls._processor = _MODULE_CACHE["processor"]
            cls._device = _MODULE_CACHE["device"]
            return cls._model, cls._processor, cls._device

        logger.info(f"🔤 Загрузка модели {cls.MODEL_ID}...")
        start = time.time()

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")

            # 🔹 ЯВНОЕ УПРАВЛЕНИЕ ПАМЯТЬЮ (РЕШАЕТ ОШИБКУ ACCELERATE)
            dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            cls._model = AutoModelForImageTextToText.from_pretrained(
                cls.MODEL_ID,
                torch_dtype=dtype,
                device_map=None,  # 🔹 Отключаем автоматическое распределение accelerate
                trust_remote_code=True,
                low_cpu_mem_usage=True
            )

            cls._processor = AutoProcessor.from_pretrained(
                cls.MODEL_ID,
                trust_remote_code=True,
            )

            # 🔹 Явно перемещаем модель на устройство
            if torch.cuda.is_available():
                cls._model = cls._model.to("cuda")
                cls._device = torch.device("cuda")
                logger.info("🎮 CUDA доступна, используем GPU")
            else:
                cls._device = torch.device("cpu")
                logger.warning("⚠️ CUDA не доступна, используем CPU")

            _MODULE_CACHE.update({
                "model": cls._model,
                "processor": cls._processor,
                "device": cls._device,
                "loaded": True,
                "model_id": cls.MODEL_ID,
            })

        elapsed = time.time() - start
        logger.info(f"✅ GLM-OCR загружена: {elapsed:.1f}с | {cls._device}")
        return cls._model, cls._processor, cls._device

    def process(self, img: Image.Image) -> str:
        """Распознавание текста с оптимизацией памяти для 4GB VRAM."""
        if img.mode != "RGB":
            img = img.convert("RGB")

        model, processor, device = self._ensure_models()

        try:
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image", "image": img},
                    {"type": "text", "text": self.prompt}
                ],
            }]

            inputs = processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt"
            ).to(device)

            inputs.pop("token_type_ids", None)

            # 🔹 inference_mode() экономит память лучше, чем no_grad()
            with torch.inference_mode():
                generated_ids = model.generate(
                    **inputs,
                    max_new_tokens=self.max_tokens,
                    # 🔹 Дефолтные параметры (как в ноутбуке)
                    do_sample=False,
                    repetition_penalty=1.05,
                )

            prompt_len = inputs["input_ids"].shape[1]
            output_text = processor.decode(
                generated_ids[0][prompt_len:],
                skip_special_tokens=False
            ).replace("<|assistant|>", "").strip()

            # 🔹 Очистка VRAM после инференса (критично для 4GB)
            if device.type == "cuda":
                torch.cuda.empty_cache()

            logger.debug(f"✅ GLM: {len(output_text)} символов")
            return output_text

        except Exception as e:
            logger.error(f"❌ Ошибка инференса GLM: {e}", exc_info=True)
            if "CUDA" in str(e) or "memory" in str(e).lower():
                logger.warning("🔄 Очистка кэша VRAM из-за ошибки памяти")
                torch.cuda.empty_cache()
            raise

    def process(self, img: Image.Image) -> str:
        """
        Распознавание текста — ТОЧНО как в официальном примере.
        """
        if img.mode != "RGB":
            img = img.convert("RGB")

        model, processor, device = self._ensure_models()

        try:
            # 🔹 Формат сообщений КАК В ОФИЦИАЛЬНОМ ПРИМЕРЕ
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image", "image": img},  # ← PIL Image напрямую!
                    {"type": "text", "text": self.prompt}
                ],
            }]

            # 🔹 apply_chat_template — БЕЗ ручного text=/images=
            inputs = processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt"
            ).to(device)

            inputs.pop("token_type_ids", None)

            # 🔹 Генерация — как в примере
            with torch.no_grad():
                generated_ids = model.generate(
                    **inputs,
                    max_new_tokens=self.max_tokens,
                    # 🔹 Параметры против зацикливания (можно раскомментировать при необходимости)
                    # do_sample=True,
                    # temperature=0.3,
                    # top_p=0.9,
                    # repetition_penalty=1.05,
                    # no_repeat_ngram_size=3,
                )

            # 🔹 Декодирование — ТОЧНО как в примере
            prompt_len = inputs["input_ids"].shape[1]
            output_text = processor.decode(
                generated_ids[0][prompt_len:],  # ← generated_ids[0] это 1D тензор
                skip_special_tokens=False
            ).strip()

            # Очистка от служебных токенов
            result = output_text.replace("<|assistant|>", "").strip()

            logger.debug(f"✅ GLM: {len(result)} символов")
            return result

        except Exception as e:
            logger.error(f"❌ Ошибка инференса GLM: {e}", exc_info=True)
            # 🔹 Сброс кэша при критических ошибках
            if "image tokens" in str(e) or "NoneType" in str(e):
                logger.warning("🔄 Сброс кэша процессора после ошибки")
                cls = GLMEngine
                cls._processor = None
                cls._model = None
                _MODULE_CACHE["loaded"] = False
            raise