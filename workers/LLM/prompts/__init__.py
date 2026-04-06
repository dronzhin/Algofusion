"""
Загрузчики
промптов
из
файлов.
"""

from pathlib import Path
import json

from workers.LLM.src.config import LLMProcessingConfig


def load_classifier_prompt(text: str, allowed_types: list[str]) -> str:
    """
Загружает
промпт
для
классификации.
"""
    template_path = Path(__file__).parent / "classifier.txt"

    if not template_path.exists():
        return f"""
Определи
тип: {allowed_types}.Текст: {text[:2000]}
Верни: {{"type": "...", "confidence": 0.X}}
"""

    with open(template_pa…    template_path = Path(__file__).parent / "extractor_template.txt"

    if not template_path.exists():
        return f"""
Извлеки
по
схеме: {schema}.Тип: {doc_type}.Текст: {text[:3000]}
Верни
только
JSON.
"""

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    return template.format(
        text=text,
        schema=json.dumps(schema, ensure_ascii=False, indent=2),
        doc_type=doc_type,
        prompt_hints=prompt_hints.strip()
    )