# models/glm_ocr.py

"""
GLM-OCR 0.9B модель для распознавания текста с изображений
Лёгкая и быстрая модель на базе архитектуры GLM-4V
"""

from transformers import AutoProcessor, AutoModelForImageTextToText
import torch
from PIL import Image
import warnings
from utils import logger
import time
from typing import Tuple, Optional


class GLMOCRModel:
    def __init__(self):
        logger.info("⏳ Загрузка модели GLM-OCR 0.9B (zai-org)...")

        try:
            start_time = time.time()

            # Подавляем предупреждения transformers
            warnings.filterwarnings("ignore", category=FutureWarning)

            # Загрузка модели
            self.model = AutoModelForImageTextToText.from_pretrained(
                "zai-org/GLM-OCR",
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True
            )

            self.processor = AutoProcessor.from_pretrained(
                "zai-org/GLM-OCR",
                trust_remote_code=True
            )

            load_time = time.time() - start_time
            device = next(self.model.parameters()).device

            logger.info(f"✅ GLM-OCR 0.9B загружена за {load_time:.2f} сек | Устройство: {device}")
            logger.debug(f"   Параметры модели: {sum(p.numel() for p in self.model.parameters()) / 1e9:.1f}B")

        except ImportError as e:
            if "AutoModelForImageTextToText" in str(e):
                logger.error(
                    "❌ Требуется transformers >= 4.46.0 или установка из main:\n"
                    "   pip install git+https://github.com/huggingface/transformers.git"
                )
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки GLM-OCR: {str(e)}", exc_info=True)
            raise

    def infer(self, image: Image.Image, prompt: str = "Text Recognition:", return_confidence: bool = False) -> Tuple[str, Optional[float]]:
        """
        Распознавание текста с изображения

        Args:
            image: PIL Image в формате RGB
            prompt: инструкция для модели (рекомендуется "Text Recognition:")
            return_confidence: возвращать ли метрику уверенности

        Returns:
            (распознанный текст, уверенность или None)
        """
        start_time = time.time()

        try:
            logger.debug(f"📝 GLM-OCR инференс | Промпт: {prompt[:50]}...")
            logger.debug(f"   Размер изображения: {image.size} | Формат: {image.mode}")

            # Формирование сообщения в формате чата
            messages = [{
                "role": "user",
                "content": [{"type": "image"}, {"type": "text", "text": prompt}]
            }]

            # Применение шаблона чата + токенизация
            inputs = self.processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
                images=image
            ).to(self.model.device)

            # Убираем ненужные поля
            inputs.pop("token_type_ids", None)

            # Генерация с опциональным возвратом логитов
            with torch.no_grad():
                if return_confidence:
                    output = self.model.generate(
                        **inputs,
                        max_new_tokens=2048,
                        output_scores=True,
                        return_dict_in_generate=True
                    )
                    generated_ids = output.sequences[0]
                    scores = output.scores
                else:
                    generated_ids = self.model.generate(
                        **inputs,
                        max_new_tokens=2048,
                        do_sample=False,
                        temperature=0.0
                    )[0]
                    scores = None

            # Декодирование
            output_text = self.processor.decode(
                generated_ids[inputs["input_ids"].shape[1]:],
                skip_special_tokens=True
            )

            result = output_text.strip()

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
            logger.info(f"✅ GLM-OCR завершена | Время: {infer_time:.2f} сек" +
                       (f" | Уверенность: {confidence:.2f}" if confidence else ""))
            logger.debug(f"   Результат (первые 100 символов): {result[:100]}...")

            return result, confidence

        except Exception as e:
            logger.error(f"❌ Ошибка инференса GLM-OCR: {str(e)}", exc_info=True)
            raise