#!/usr/bin/env python3
# shared/utils/ocr_normalizer.py
"""
Нормализация OCR-текста для GLM-OCR.
Исправляет: смешивание латиницы/кириллицы, опечатки, визуальные дубликаты символов.
"""

import re

# Латинские символы, которые OCR часто путает с кириллицей
HOMOGLYPHS = {
    'A': 'А', 'B': 'В', 'C': 'С', 'E': 'Е', 'H': 'Н', 'K': 'К', 'M': 'М',
    'O': 'О', 'P': 'Р', 'T': 'Т', 'X': 'Х', 'Y': 'У',
    'a': 'а', 'c': 'с', 'e': 'е', 'o': 'о', 'p': 'р', 'x': 'х', 'y': 'у'
}


def normalize_ocr_text(text: str) -> str:
    if not text or not isinstance(text, str):
        return text

    # 1. Явные паттерны-артефакты GLM-OCR
    replacements = [
        (r'\bYJI\.?\b', 'УЛ.'),
        (r'YJI', 'УЛ'),
        (r'\bMAKAEHKA\b', 'МАКАРЕНКА'),  # GLM часто роняет 'Р' и пишет 'H' вместо 'Н'
        (r'\bOTHR\b', 'ДРУГОЕ'),  # Платёжные коды → человекочитаемый вид
        (r'Белarus', 'Беларусь'),
        (r'р/с', 'расчётный счёт'),
        (r'л/с', 'лицевой счёт'),
        (r'INN\s*№?\s*', 'ИНН '),
        (r'KPP\s*№?\s*', 'КПП '),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    # 2. Контекстная замена латиницы на кириллицу
    # Применяем только если текст преимущественно кириллический (>30%)
    cyr_count = len(re.findall(r'[а-яА-ЯёЁ]', text))
    total_letters = len(re.findall(r'[a-zA-Zа-яА-ЯёЁ]', text))

    if total_letters > 0 and (cyr_count / total_letters) > 0.3:
        for lat, cyr in HOMOGLYPHS.items():
            text = text.replace(lat, cyr)

    # 3. Нормализация пробелов, переносов, пунктуации
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'([а-яА-ЯёЁ])\s*-\s*([а-яА-ЯёЁ])', r'\1-\2', text)
    text = re.sub(r'\s*([.,;:!?)])', r'\1', text)
    text = re.sub(r'([(\[])\\s*', r'\1', text)

    return text.strip()