# models/paddleocr_vl.py

"""
PaddleOCR-VL-1.5 модель для распознавания текста с изображений
Специализация на многоязычных документах (китайский, японский, корейский)
"""

from paddlenlp.transformers import AutoTokenizer, AutoModelForCausalLM
from paddlenlp.transformers.image_processing_paddleocr_vl import PaddleOCRVLImageProcessor
import paddle
from PIL import Image
import numpy as np
from utils import logger
import time
from typing import Tuple, Optional


class PaddleOCRVLModel:
    def __init__(self):
        logger.info("⏳ Загрузка модели PaddleOCR-VL-1.5...")

        try:
            start_time = time.time()

            self.model = AutoModelForCausalLM.from_pretrained(
                "PaddlePaddle/PaddleOCR-VL-1.5",
                dtype="float16"
            )
            self.tokenizer = AutoTokenizer.from_pretrained("PaddlePaddle/PaddleOCR-VL-1.5")
            self.image_processor = PaddleOCRVLImageProcessor.from_pretrained("PaddlePaddle/PaddleOCR-VL-1.5")

            load_time = time.time() - start_time

            logger.info(f"✅ PaddleOCR-VL-1.5 загружена за {load_time:.2f} сек")
            logger.debug(f"   GPU доступен: {paddle.is_compiled_with_cuda()}")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки PaddleOCR-VL-1.5: {str(e)}", exc_info=True)
            raise

    def infer(self, image: Image.Image, prompt: str = "Extract all text", return_confidence: bool = False) -> Tuple[str, Optional[float]]:
        """
        Распознавание текста с изображения

        Args:
            image: PIL Image в формате RGB
            prompt: инструкция для модели
            return_confidence: возвращать ли метрику уверенности (только эвристическая)

        Returns:
            (распознанный текст, уверенность или None)
        """
        start_time = time.time()

        try:
            logger.debug(f"📝 PaddleOCR-VL-1.5 инференс | Промпт: {prompt[:50]}...")
            logger.debug(f"   Размер изображения: {image.size} | Формат: {image.mode}")

            # Конвертация PIL → numpy
            image_np = np.array(image)

            # Предобработка
            inputs = self.image_processor(images=image_np, return_tensors="pd")
            text_inputs = self.tokenizer(prompt, return_tensors="pd")
            inputs.update(text_inputs)

            # Инференс
            with paddle.no_grad():
                output = self.model.generate(**inputs, max_length=1024)

            result = self.tokenizer.decode(output[0], skip_special_tokens=True)

            # Только эвристическая уверенность (нет доступа к логитам)
            confidence = None
            if return_confidence:
                from utils import confidence_calculator
                confidence = confidence_calculator.calculate_heuristic(result, image.size)
                logger.debug(f"   Эвристическая уверенность: {confidence:.2f}")

            infer_time = time.time() - start_time
            logger.info(f"✅ PaddleOCR-VL-1.5 завершена | Время: {infer_time:.2f} сек" +
                       (f" | Уверенность: {confidence:.2f}" if confidence else ""))
            logger.debug(f"   Результат (первые 100 символов): {result[:100]}...")

            return result, confidence

        except Exception as e:
            logger.error(f"❌ Ошибка инференса PaddleOCR-VL-1.5: {str(e)}", exc_info=True)
            raise