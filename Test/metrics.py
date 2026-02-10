def compare_nested_dicts(original_dict: dict, recognized_dict: dict):
    """
    Сравнивает два словаря с вложенными структурами (включая списки словарей)
    и вычисляет CER и WER с учётом ВСЕХ данных: строк, чисел, процентов.

    Возвращает:
        tuple[float, float]: (CER, WER)
    """

    def extract_all_values(d) -> list[str]:
        """
        Рекурсивно извлекает ВСЕ значимые значения (строки, числа) из любой вложенной структуры.
        Поддерживает: dict, list, str, int, float, None.
        """
        texts = []
        stack = [d]

        while stack:
            current = stack.pop()

            # Строки: добавляем как есть (игнорируем пустые)
            if isinstance(current, str) and current.strip():
                texts.append(current.strip())

            # Числа: преобразуем в строку для учёта в метриках
            elif isinstance(current, (int, float)):
                texts.append(str(current))

            # Словари: обрабатываем только значения (ключи игнорируем — они технические)
            elif isinstance(current, dict):
                for value in current.values():
                    stack.append(value)

            # Списки: обрабатываем все элементы
            elif isinstance(current, list):
                for item in current:
                    stack.append(item)

            # None и другие типы игнорируем

        return texts

    def levenshtein_distance(seq1, seq2):
        """Универсальное расстояние Левенштейна для строк или списков."""
        if len(seq1) < len(seq2):
            return levenshtein_distance(seq2, seq1)
        if not seq1:
            return len(seq2)

        previous_row = list(range(len(seq2) + 1))
        for i, c1 in enumerate(seq1, 1):
            current_row = [i]
            for j, c2 in enumerate(seq2, 1):
                insertions = previous_row[j] + 1
                deletions = current_row[j - 1] + 1
                substitutions = previous_row[j - 1] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def compute_cer(ref: str, hyp: str) -> float:
        if not ref:
            return 0.0 if not hyp else 1.0
        return levenshtein_distance(ref, hyp) / len(ref)

    def compute_wer(ref_words: list[str], hyp_words: list[str]) -> float:
        if not ref_words:
            return 0.0 if not hyp_words else 1.0
        return levenshtein_distance(ref_words, hyp_words) / len(ref_words)

    # === Извлечение текста с сохранением ВСЕХ данных ===
    original_texts = extract_all_values(original_dict)
    recognized_texts = extract_all_values(recognized_dict)

    # Объединяем с разделителем-пробелом для сохранения границ
    original_combined = " ".join(original_texts)
    recognized_combined = " ".join(recognized_texts)

    # === Расчёт метрик ===
    cer = compute_cer(original_combined, recognized_combined)
    wer = compute_wer(original_combined.split(), recognized_combined.split())

    return cer, wer

# Оригинал (идеальные данные)
original = {
    "invoice_number": "286552",
    "invoice_date": "23.08.2024",
    "items": [
        {
            "line_number": 1,
            "description": "REU032 HAIR STYLING CLAY Reuzel Clay Mate Pomade, 35g",
            "unit": "pcs",
            "quantity": 100,
            "unit_price": 0.80,
            "vat_rate": "20%"
        },
        {
            "line_number": 2,
            "description": "REU44 EXTRA STRONG HOLD Reuzel Extreme Hold Matte Pomade, 35g",
            "unit": "pcs",
            "quantity": 3,
            "unit_price": 30.00,
            "vat_rate": "20%"
        }
    ],
    "totals": {
        "total_incl_vat": 753.80
    }
}

# Распознано (с ошибками: числа искажены, опечатки в тексте)
recognized = {
    "invoice_number": "28655Z",          # '2' → 'Z'
    "invoice_date": "23.08.2O24",        # '0' → 'O'
    "items": [
        {
            "line_number": 1,
            "description": "REU032 HAIR STYLING CLAY Reuzel Clay Mate Pomade, 35g",
            "unit": "pcs",
            "quantity": 10,              # 100 → 10 (критическая ошибка!)
            "unit_price": 0.80,
            "vat_rate": "2O%"            # '0' → 'O'
        },
        {
            "line_number": 2,
            "description": "REU44 EXTRA STRONG HOLD Reuzel Extreme Hold Matte Pomade, 35g",
            "unit": "pcs",
            "quantity": 3,
            "unit_price": 30.00,
            "vat_rate": "20%"
        }
    ],
    "totals": {
        "total_incl_vat": 752.8          # пропущен последний '0'
    }
}

cer, wer = compare_nested_dicts(original, recognized)
print(f"CER: {cer:.4f} ({cer*100:.2f}%)")
print(f"WER: {wer:.4f} ({wer*100:.2f}%)")