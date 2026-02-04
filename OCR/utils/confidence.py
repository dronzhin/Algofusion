# utils/confidence.py

"""
Утилита для расчёта метрик уверенности распознавания текста.
Поддерживает токенную уверенность (для моделей с доступом к логитам)
и эвристическую оценку (для всех моделей).
"""

from utils import logger
import torch
import re
from typing import Tuple, Optional, List


class ConfidenceCalculator:
    """Калькулятор метрик уверенности для распознанного текста"""

    def __init__(self):
        self.min_token_confidence = 0.01  # Минимальная вероятность токена для учёта

    def calculate_from_logits(
            self,
            generated_ids: torch.Tensor,
            scores: Optional[List[torch.Tensor]],
            input_length: int
    ) -> Tuple[float, List[float]]:
        """
        Расчёт уверенности на основе логитов/вероятностей токенов.

        Args:
            generated_ids: сгенерированные токены [seq_len]
            scores: список тензоров логитов для каждого шага генерации
            input_length: длина входной последовательности (промпт + изображение)

        Returns:
            (средняя_уверенность, список_уверенностей_по_токенам)
        """
        if scores is None or len(scores) == 0:
            logger.warning("⚠️  Невозможно рассчитать токенную уверенность: нет данных о логитах")
            return 0.5, []  # Нейтральное значение по умолчанию

        try:
            # Извлекаем только сгенерированные токены (без промпта)
            generated_tokens = generated_ids[input_length:]
            token_confidences = []

            # Для каждого сгенерированного токена получаем вероятность
            for i, token_id in enumerate(generated_tokens):
                if i >= len(scores):
                    break

                # Получаем логиты для текущего шага
                logits = scores[i].squeeze(0)  # [vocab_size]

                # Применяем softmax для получения вероятностей
                probs = torch.softmax(logits, dim=-1)

                # Получаем вероятность предсказанного токена
                token_prob = probs[token_id].item()

                # Ограничиваем минимальное значение для стабильности
                token_prob = max(token_prob, self.min_token_confidence)
                token_confidences.append(token_prob)

            # Рассчитываем среднюю уверенность (геометрическое среднее для консервативности)
            if token_confidences:
                import math
                avg_confidence = math.exp(sum(math.log(p) for p in token_confidences) / len(token_confidences))
                return avg_confidence, token_confidences
            else:
                return 0.5, []

        except Exception as e:
            logger.warning(f"⚠️  Ошибка расчёта токенной уверенности: {str(e)}")
            return 0.5, []

    def calculate_heuristic(self, text: str, image_size: Tuple[int, int]) -> float:
        """
        Эвристическая оценка уверенности на основе качества вывода.

        Учитывает:
        - Длину текста (слишком короткий = низкая уверенность)
        - Наличие повторяющихся символов (признак артефактов)
        - Соотношение букв/цифр/спецсимволов
        - Размер изображения (маленькое изображение = ниже потенциал качества)

        Возвращает значение от 0.0 (низкая) до 1.0 (высокая)
        """
        if not text or len(text.strip()) == 0:
            return 0.1

        text = text.strip()
        confidence = 0.7  # Базовое значение

        # 1. Длина текста
        if len(text) < 10:
            confidence *= 0.7  # Очень короткий текст — низкая уверенность
        elif len(text) > 5000:
            confidence *= 0.9  # Очень длинный текст — возможны артефакты

        # 2. Повторяющиеся символы (признак галлюцинаций)
        if re.search(r'(.)\1{4,}', text):  # 5+ повторений одного символа
            confidence *= 0.6

        # 3. Соотношение "мусорных" символов
        total_chars = len(text)
        alphanumeric = sum(c.isalnum() or c.isspace() for c in text)
        if total_chars > 0:
            quality_ratio = alphanumeric / total_chars
            confidence *= (0.5 + quality_ratio * 0.5)  # Масштабируем от 0.5 до 1.0

        # 4. Размер изображения (эвристика)
        width, height = image_size
        img_area = width * height
        if img_area < 50000:  # Меньше 250x200
            confidence *= 0.85

        # Ограничиваем диапазон [0.0, 1.0]
        return max(0.0, min(1.0, confidence))

    def combine_confidences(
            self,
            token_confidence: Optional[float],
            heuristic_confidence: float,
            has_token_scores: bool
    ) -> float:
        """
        Комбинирование токенной и эвристической уверенности.

        Если доступна токенная уверенность — используем её как основную,
        но корректируем эвристикой для надёжности.
        """
        if has_token_scores and token_confidence is not None:
            # Взвешенная комбинация (токенная 70%, эвристическая 30%)
            return 0.7 * token_confidence + 0.3 * heuristic_confidence
        else:
            return heuristic_confidence


# Глобальный экземпляр для импорта
confidence_calculator = ConfidenceCalculator()