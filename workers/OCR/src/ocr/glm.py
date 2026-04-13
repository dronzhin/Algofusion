# workers/OCR/src/ocr/glm.py
"""
GLM-OCR движок на базе transformers (zai-org/GLM-OCR).
Только распознавание: PIL.Image → str.
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

        # 🔹 Языки: GLM-OCR мультиязычен, но можно подсказать через промпт
        lang_config = config.get("lang", "rus+eng")
        if isinstance(lang_config, str):
            self.lang_list = lang_config.split("+")
        else:
            self.lang_list = list(lang_config)

        # 🔹 Промпт для распознавания (можно кастомизировать)
        self.prompt = config.get("glm_prompt", "Text Recognition:")

        # 🔹 Параметры генерации
        self.max_tokens = config.get("glm_max_tokens", 2048)
        self.temperature = config.get("glm_temperature", 0.0)

        logger.info(f"🔤 GLM-OCR инициализирован: языки={self.lang_list}, промпт='{self.prompt}'")

    @classmethod
    def _ensure_models(cls):
        """Ленивая загрузка моделей GLM-OCR (кэшируется)."""
        # Импортируем здесь, чтобы не ломать систему, если transformers не установлен
        try:
            from transformers import AutoProcessor, AutoModelForImageTextToText
        except ImportError:
            raise RuntimeError(
                "GLM-OCR требует библиотеки transformers. Установите: pip install transformers>=4.45 accelerate"
            )

        if cls._model is None or cls._processor is None:
            logger.info(f"🔤 Загрузка модели {cls.MODEL_ID}...")

            # 🔹 Подавляем предупреждения transformers при загрузке
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning)

                # 🔹 Загрузка процессора
                cls._processor = AutoProcessor.from_pretrained(
                    cls.MODEL_ID,
                    trust_remote_code=True
                )

                # 🔹 Загрузка модели с авто-выбором устройства
                cls._model = AutoModelForImageTextToText.from_pretrained(
                    cls.MODEL_ID,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto" if torch.cuda.is_available() else None,
                    trust_remote_code=True
                )

                # 🔹 Определяем устройство
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

        🔹 КЛЮЧЕВОЕ: изображение передаётся ТОЛЬКО через параметр `images=`,
        а в messages указывается только {"type": "image"} без данных.
        """
        logger.debug(f"🔤 GLM: {img.size}px, режим={img.mode}")

        # 🔹 Конвертируем в RGB если нужно
        if img.mode != "RGB":
            img = img.convert("RGB")

        # 🔹 Загружаем модели при первом вызове
        model, processor, device = self._ensure_models()

        # 🔹 Формируем сообщение в формате чата
        # ❗ ВАЖНО: в content передаём ТОЛЬКО тип, без данных изображения
        messages = [{
            "role": "user",
            "content": [
                {"type": "image"},  # ← Только тип, без image_url или данных
                {"type": "text", "text": self.prompt}
            ]
        }]

        try:
            # 🔹 Применяем chat template
            # ❗ ВАЖНО: изображение передаётся ТОЛЬКО через параметр `images=`
            inputs = processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
                images=img  # ← ЕДИНСТВЕННОЕ место передачи изображения
            ).to(device)

            # 🔹 Убираем ненужные поля (может вызвать ошибку в некоторых версиях)
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
                    "   Убедитесь, что в messages.content используется только {{'type': 'image'}},\n"
                    "   а само изображение передаётся ТОЛЬКО через параметр images= в apply_chat_template."
                )
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка инференса GLM: {e}", exc_info=True)
            raise

    def process_batch(self, images: List[Image.Image]) -> List[str]:
        """
        Пакетная обработка: по одному изображению за вызов.

        🔹 Примечание: GLM-OCR пока не поддерживает нативную пакетную обработку,
        поэтому вызываем process() для каждого изображения.
        """
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
                results.append("")  # Пустая строка при ошибке

        logger.debug(f"✅ GLM batch: обработано {len(results)}/{len(images)} изображений")
        return results