# models/deepseek_ocr.py

"""
DeepSeek-OCR модель для распознавания текста с изображений
"""

from transformers import AutoProcessor, AutoModelForCausalLM
import torch
from PIL import Image
from utils import logger
import time
from typing import Tuple, Optional


class DeepSeekOCRModel:
    def __init__(self):
        logger.info("⏳ Загрузка модели DeepSeek-OCR...")

        try:
            start_time = time.time()

            self.model = AutoModelForCausalLM.from_pretrained(
                "deepseek-ai/DeepSeek-OCR",
                trust_remote_code=True,
                torch_dtype=torch.float16,
                device_map="auto"
            )

            self.processor = AutoProcessor.from_pretrained(
                "deepseek-ai/DeepSeek-OCR",
                trust_remote_code=True
            )

            load_time = time.time() - start_time
            device = next(self.model.parameters()).device

            logger.info(f"✅ DeepSeek-OCR загружена за {load_time:.2f} сек | Устройство: {device}")
            logger.debug(f"   Параметры модели: {sum(p.numel() for p in self.model.parameters()) / 1e9:.1f}B")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки DeepSeek-OCR: {str(e)}", exc_info=True)
            raise

    def infer(self, image: Image.Image, prompt: str = "Extract all text", return_confidence: bool = False) -> Tuple[str, Optional[float]]:
        """
        Распознавание текста с изображения

        Args:
            image: PIL Image в формате RGB
            prompt: инструкция для модели
            return_confidence: возвращать ли метрику уверенности

        Returns:
            (распознанный текст, уверенность или None)
        """
        start_time = time.time()

        try:
            logger.debug(f"📝 DeepSeek-OCR инференс | Промпт: {prompt[:50]}...")
            logger.debug(f"   Размер изображения: {image.size} | Формат: {image.mode}")

            # Подготовка входных данных
            inputs = self.processor(images=image, text=prompt, return_tensors="pt").to(self.model.device)

            # Генерация с опциональным возвратом логитов
            with torch.no_grad():
                if return_confidence:
                    output = self.model.generate(
                        **inputs,
                        max_new_tokens=1024,
                        output_scores=True,
                        return_dict_in_generate=True
                    )
                    generated_ids = output.sequences[0]
                    scores = output.scores
                else:
                    generated_ids = self.model.generate(**inputs, max_new_tokens=1024)[0]
                    scores = None

            result = self.processor.decode(generated_ids, skip_special_tokens=True)

            # Расчёт уверенности
            confidence = None
            if return_confidence:
                from utils import confidence_calculator
                token_conf, _ = confidence_calculator.calculate_from_logits(
                    generated_ids,
                    scores,
                    inputs["input_ids"].shape[1]
                )
                heuristic_conf = confidence_calculator.calculate_heuristic(result, image.size)
                confidence = confidence_calculator.combine_confidences(
                    token_conf,
                    heuristic_conf,
                    has_token_scores=(scores is not None)
                )
                logger.debug(f"   Уверенность: токенная={token_conf:.2f}, эвристическая={heuristic_conf:.2f}, итоговая={confidence:.2f}")

            infer_time = time.time() - start_time
            logger.info(f"✅ DeepSeek-OCR завершена | Время: {infer_time:.2f} сек" +
                       (f" | Уверенность: {confidence:.2f}" if confidence else ""))
            logger.debug(f"   Результат (первые 100 символов): {result[:100]}...")

            return result, confidence

        except Exception as e:
            logger.error(f"❌ Ошибка инференса DeepSeek-OCR: {str(e)}", exc_info=True)
            raise