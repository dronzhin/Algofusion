#!/usr/bin/env python3
# workers/LLM/prompts.py
"""
Промпты для LLM-компонентов.
"""

from typing import Dict, Any, List


def load_classifier_prompt(text: str, allowed_types: List[str]) -> str:
    """Промпт для классификации документа."""
    types_list = ", ".join(f'"{t}"' for t in allowed_types)

    return f"""Ты — классификатор документов. Определи тип документа по тексту.

ДОСТУПНЫЕ ТИПЫ: [{types_list}]

Текст документа:
\"\"\"
{text[:3000]}
\"\"\"

Верни ответ ТОЛЬКО в формате JSON:
{{
  "type": "один из доступных типов",
  "confidence": число от 0.0 до 1.0
}}

Не добавляй пояснений, только JSON."""


def load_extractor_prompt(
        text: str,
        schema: Dict[str, Any],
        doc_type: str,
        prompt_hints: str = ""
) -> str:
    """
    Формирует ПРОСТЫЙ промпт для экстракции.
    🔹 Структура контролируется JSON Schema через format в Ollama API.
    """
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    fields_summary = []
    for field_name, field_info in list(properties.items())[:10]:
        desc = field_info.get("description", "")
        req = " [обязательно]" if field_name in required else ""
        fields_summary.append(f"{field_name}: {desc}{req}")

    fields_text = "; ".join(fields_summary) if fields_summary else "извлеки ключевые данные"

    prompt = f"""Документ типа: {doc_type}
Извлеки данные по полям: {fields_text}

Текст:
\"\"\"
{text}
\"\"\"

{prompt_hints.strip() if prompt_hints.strip() else ""}

Верни ТОЛЬКО валидный JSON. Не добавляй пояснений, не используй markdown."""

    return prompt