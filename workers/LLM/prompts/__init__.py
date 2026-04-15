#!/usr/bin/env python3
# workers/LLM/prompts/__init__.py
from pathlib import Path
import json
from typing import Optional
from shared.utils.logger import setup_logger

logger = setup_logger("workers.llm.prompts")


def load_classifier_prompt(text: str, allowed_types: list[str]) -> str:
    template_path = Path(__file__).parent / "classifier.txt"
    if not template_path.exists():
        raise FileNotFoundError(f"Шаблон не найден: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # Форматируем типы как маркированный список для лучшей читаемости моделью
    types_formatted = "\n".join(f"- {t}" for t in allowed_types)

    prompt = template.replace("{allowed_types}", types_formatted)
    prompt = prompt.replace("{text}", text[:4000] if text else "[ТЕКСТ ОТСУТСТВУЕТ]")

    logger.debug(f"📝 Classifier prompt ready | Length: {len(prompt)} | Types: {allowed_types}")
    return prompt


def load_extractor_prompt(
        text: str,
        schema: dict,
        doc_type: str,
        prompt_hints: Optional[str] = None
) -> str:
    template_path = Path(__file__).parent / "extractor_template.txt"
    if not template_path.exists():
        raise FileNotFoundError(f"Шаблон не найден: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    hints_block = prompt_hints.strip() if prompt_hints else "Без дополнительных ограничений."
    schema_json = json.dumps(schema, ensure_ascii=False, indent=2)
    text_clean = text[:4000].strip() if text else "[OCR ТЕКСТ ПУСТ]"

    prompt = template
    prompt = prompt.replace("{doc_type}", str(doc_type))
    prompt = prompt.replace("{prompt_hints}", hints_block)
    prompt = prompt.replace("{schema}", schema_json)
    prompt = prompt.replace("{text}", text_clean)

    return prompt


__all__ = ["load_classifier_prompt", "load_extractor_prompt"]