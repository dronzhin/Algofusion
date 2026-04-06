# workers/LLM/prompts/__init__.py
"""
Загрузчики промптов из файлов.

Модуль предоставляет функции для загрузки и рендеринга шаблонов промптов
для классификации и экстракции документов.

Требования:
- Файлы шаблонов 'classifier.txt' и 'extractor_template.txt' должны существовать в директории модуля.
- Все промпты поддерживают форматирование через .format()
"""

from pathlib import Path
import json
from typing import Optional

from shared.utils.logger import setup_logger

logger = setup_logger("workers.llm.prompts")


def load_classifier_prompt(text: str, allowed_types: list[str]) -> str:
    """
    Загружает и рендерит промпт для классификации документа.

    Args:
        text: Текст документа из OCR (будет обрезан до ~2000 символов)
        allowed_types: Список допустимых типов документа для выбора

    Returns:
        str: Готовый промпт для отправки в LLM

    Raises:
        FileNotFoundError: Если шаблон не найден
        RuntimeError: При ошибке чтения/рендеринга шаблона
    """
    template_path = Path(__file__).parent / "classifier.txt"

    # 🔹 Строгая проверка наличия шаблона
    if not template_path.exists():
        logger.critical(f"❌ Шаблон классификации не найден: {template_path}")
        raise FileNotFoundError(
            f"Шаблон промпта не найден: {template_path}. "
            "Убедитесь, что директория prompts/ корректно скопирована в образ."
        )

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()

        # 🔹 Безопасная обрезка текста перед подстановкой
        return template.format(
            text=text[:2000],
            allowed_types=", ".join(allowed_types)
        )
    except KeyError as e:
        logger.error(f"❌ В шаблоне отсутствует плейсхолдер: {e}")
        raise RuntimeError(f"Ошибка структуры шаблона классификации: отсутствует {e}") from e
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки шаблона классификации: {e}")
        raise RuntimeError(f"Не удалось загрузить шаблон классификации: {e}") from e


def load_extractor_prompt(
        text: str,
        schema: dict,
        doc_type: str,
        prompt_hints: Optional[str] = None
) -> str:
    """
    Загружает и рендерит промпт для извлечения структурированных данных.

    Args:
        text: Текст документа из OCR (будет обрезан до ~4000 символов)
        schema: JSON-схема для валидации результата извлечения
        doc_type: Тип документа (для контекста промпта)
        prompt_hints: Дополнительные подсказки для формата вывода (опционально)

    Returns:
        str: Готовый промпт для отправки в LLM

    Raises:
        FileNotFoundError: Если шаблон не найден
        RuntimeError: При ошибке чтения/рендеринга шаблона
    """
    template_path = Path(__file__).parent / "extractor_template.txt"

    # 🔹 Строгая проверка наличия шаблона
    if not template_path.exists():
        logger.critical(f"❌ Шаблон экстракции не найден: {template_path}")
        raise FileNotFoundError(
            f"Шаблон промпта не найден: {template_path}. "
            "Убедитесь, что директория prompts/ корректно скопирована в образ."
        )

    # Подготовка данных ДО формирования строки
    hints_block = prompt_hints.strip() if prompt_hints else "Без дополнительных ограничений."
    schema_json = json.dumps(schema, ensure_ascii=False, indent=2)
    text_preview = text[:4000]

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()

        # Передаём уже готовую строку JSON
        return template.format(
            text=text_preview,
            schema=schema_json,
            doc_type=doc_type,
            prompt_hints=hints_block
        )
    except KeyError as e:
        logger.error(f"❌ В шаблоне отсутствует плейсхолдер: {e}")
        raise RuntimeError(f"Ошибка структуры шаблона экстракции: отсутствует {e}") from e
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки шаблона экстракции: {e}")
        raise RuntimeError(f"Не удалось загрузить шаблон экстракции: {e}") from e


# ============================================================================
# PUBLIC API — Явный экспорт функций для импорта
# ============================================================================

__all__ = [
    "load_classifier_prompt",
    "load_extractor_prompt",
]