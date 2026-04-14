# workers/OCR/src/ocr/glm.py
"""
GLM-OCR движок на базе transformers (zai-org/GLM-OCR).
Только распознавание: PIL.Image → str.
✅ Исправлено для transformers >= 4.45: images в processor_kwargs
"""

from typing import List, Optional, Tuple
from PIL import Image
import torch
import warnings

from shared.utils.logger import setup_logger
from workers.OCR.src.ocr.base import OCREngine
from transformers import AutoProcessor, AutoModelForImageTextToText

logger = setup_logger("workers.ocr.ocr.glm")


class GLMEngine(OCREngine):
    """
    GLM-OCR с обработкой в памяти.
    🔹 Только распознавание: PIL.Image → str
    🔹 Модели загружаются лениво и кэшируются на уровне класса
    🔹 Поддержка float16 для экономии памяти
    """

    name = "glm"
    MODEL_ID = "zai-org/GLM-OCR"

    # 🔹 Кэш моделей на уровне класса
    _model: Optional["AutoModelForImageTextToText"] = None
    _processor: Optional["AutoProcessor"] = None
    _device: Optional[torch.device] = None

    def __init__(self, config: dict):
        super().__init__(config)

        lang_config = config.get("lang", "rus+eng")
        self.lang_list = lang_config.split("+") if isinstance(lang_config, str) else list(lang_config)
        self.prompt = config.get("glm_prompt", "Text Recognition:")
        self.max_tokens = config.get("glm_max_tokens", 2048)
        self.temperature = config.get("glm_temperature", 0.0)

        logger.info(f"🔤 GLM-OCR инициализирован: языки={self.lang_list}, промпт='{self.prompt}'")

    @classmethod
    def _ensure_models(cls):
        """Ленивая загрузка моделей GLM-OCR (кэшируется)."""
        try:
            from transformers import AutoProcessor, AutoModelForImageTextToText
        except ImportError:
            raise RuntimeError(
                "GLM-OCR требует библиотеки transformers. Установите: pip install transformers>=4.45 accelerate"
            )

        if cls._model is None or cls._processor is None:
            logger.info(f"🔤 Загрузка модели {cls.MODEL_ID}...")

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning)

                cls._processor = AutoProcessor.from_pretrained(cls.MODEL_ID, trust_remote_code=True)

                cls._model = AutoModelForImageTextToText.from_pretrained(
                    cls.MODEL_ID,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto" if torch.cuda.is_available() else None,
                    trust_remote_code=True
                )

                if torch.cuda.is_available():
                    cls._device = next(cls._model.parameters()).device
                else:
                    cls._device = torch.device("cpu")

                logger.info(f"✅ GLM-OCR загружен | Устройство: {cls._device}")
                logger.debug(f"   Параметры: {sum(p.numel() for p in cls._model.parameters()) / 1e9:.2f}B")

        return cls._model, cls._processor, cls._device

    def process(self, img: Image.Image) -> str:
        """
        Распознаёт текст на одном изображении в памяти.
        ✅ Исправлено: images передаётся через processor_kwargs для transformers >= 4.45
        """
        logger.debug(f"🔤 GLM: {img.size}px, режим={img.mode}")

        if img.mode != "RGB":
            img = img.convert("RGB")

        model, processor, device = self._ensure_models()

        # 🔹 Формируем сообщение в формате чата
        messages = [{
            "role": "user",
            "content": [
                {"type": "image"},  # ← Только тип, без данных
                {"type": "text", "text": self.prompt}
            ]
        }]

        try:
            # 🔹 Применяем chat template
            # ✅ FIX для transformers >= 4.45: images в processor_kwargs
            inputs = processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
                processor_kwargs={"images": [img]}  # ← ЕДИНСТВЕННОЕ место передачи изображения
            ).to(device)

            # 🔹 Убираем ненужные поля
            inputs.pop("token_type_ids", None)

            # 🔹 Генерация
            with torch.no_grad():
                generated_ids = model.generate(
                    **inputs,
                    max_new_tokens=self.max_tokens,
                    do_sample=(self.temperature > 0),
                    temperature=self.temperature if self.temperature > 0 else None,
                )[0]

            # 🔹 Декодирование: пропускаем входные токены
            output_text = processor.decode(
                generated_ids[inputs["input_ids"].shape[1]:],
                skip_special_tokens=True
            )

            result = output_text.strip()
            logger.debug(f"✅ GLM: {len(result)} символов")
            return result

        except TypeError as e:
            if "multiple values for keyword argument 'images'" in str(e):
                logger.error(
                    "❌ Ошибка: дублирование аргумента 'images'.\n"
                    "   Для transformers >= 4.45 передавайте images через processor_kwargs={\"images\": [img]}"
                )
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка инференса GLM: {e}", exc_info=True)
            raise

    def process_batch(self, images: List[Image.Image]) -> List[str]:
        """Пакетная обработка: по одному изображению за вызов."""
        if not images:
            return []

        logger.info(f"🔤 GLM: пакетная обработка {len(images)} изображений")

        results = []
        for i, img in enumerate(images):
            try:
                result = self.process(img)
                results.append(result)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка обработки изображения #{i + 1}: {e}")
                results.append("")

        logger.debug(f"✅ GLM batch: обработано {len(results)}/{len(images)} изображений")
        return results