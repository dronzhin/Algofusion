# ===== PRED NORMALIZER: /content/data/pred -> /content/data/pred_normalized =====

import json
import math
import re
from pathlib import Path

# =========================
# CONFIG
# =========================

PRED_DIR = Path("data") / "pred"
PRED_NORM_DIR = Path("data") / "pred_normalized"
PRED_NORM_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# CONST
# =========================

MONTHS = {
    "января": "01",
    "февраля": "02",
    "марта": "03",
    "апреля": "04",
    "мая": "05",
    "июня": "06",
    "июля": "07",
    "августа": "08",
    "сентября": "09",
    "октября": "10",
    "ноября": "11",
    "декабря": "12",
}

NUMERIC_KEY_HINTS = {
    "amount",
    "price",
    "cost",
    "cost_with_vat",
    "quantity_total",
    "cost_total",
    "vat_total",
    "cost_with_vat_total",
    "free_unit_price_excl_vat",
    "extra_charge",
    "unit_price_excl_vat",
    "total_excl_vat",
    "total_incl_vat",
    "subtotal_excl_vat",
    "subtotal_no_disc_incl_vat",
    "total_disc_amount",
    "subtotal_with_disc_excl_vat",
    "vat_amount",
    "total_with_disc_incl_vat",
    "amount_no_disc_incl_vat",
    "disc_amount",
    "amount_with_disc_excl_vat",
    "unit_price_incl_vat",
}

INT_KEY_HINTS = {
    "line_number",
    "quantity",
    "total_quantity",
    "quantity_total",
}

BOOL_KEY_HINTS = {
    "urgent",
    "non_urgent",
    "is_valid",
}

DATE_KEY_HINTS = {
    "document_date",
    "invoice_date",
    "date",
    "contract_date",
    "receipt_date",
    "execution_date",
    "valid_until",
}

PERCENT_KEY_HINTS = {
    "vat_rate",
}

ACCOUNT_KEYS = {
    "bank_account",
    "account",
}

CODE_KEYS = {
    "tax_id",
    "kpp",
    "bic",
    "bank_code",
    "barcode",
    "sku",
}

ADDRESS_KEYS = {
    "address",
    "bank_address",
}

BANK_NAME_KEYS = {
    "bank_name",
    "executing_bank",
}

MONEY_WORD_KEYS = {
    "amount_in_words",
    "total_in_words",
    "vat_total_words",
    "cost_with_vat_total_words",
}

FREE_TEXT_KEYS = {
    "note",
    "notes",
    "purpose",
    "basis",
    "warning",
    "publisher",
    "released_by",
    "handed_by",
    "accepted_for_delivery",
    "received_by",
    "documents_transferred",
    "status_note",
    "payment_order_type",
    "currency",
    "currency_full",
    "status",
    "document_type",
    "document_series",
    "document_number",
    "invoice_number",
    "payment_deadline",
    "contract_number",
    "contract_type",
    "article",
}

PARTY_BLOCK_KEYS = {
    "supplier",
    "customer",
    "payer",
    "payee",
    "sender",
    "receiver",
    "signatory",
}

VISUAL_QUOTES_MAP = str.maketrans({
    "«": '"',
    "»": '"',
    "“": '"',
    "”": '"',
    "„": '"',
    "’": "'",
    "‘": "'",
})

CYR_TO_LAT_MAP = str.maketrans({
    "А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "К": "K",
    "М": "M", "О": "O", "Р": "P", "Т": "T", "У": "Y", "Х": "X",
    "І": "I", "Ү": "Y",
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
})

# =========================
# HELPERS
# =========================

def is_nan_like(v):
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str) and v.strip().lower() in {"", "nan", "none", "null"}:
        return True
    return False

def clean_spaces(s: str) -> str:
    s = str(s).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def clean_text(value):
    if is_nan_like(value):
        return None
    s = clean_spaces(value)
    return s or None

def path_leaf(path):
    return path[-1] if path else None

def path_has(path, *keys):
    return any(part in keys for part in path)

def is_product_text_field(path):
    leaf = path_leaf(path)
    return leaf in {"name", "description"} and path_has(path, "items")

def is_party_name_field(path):
    leaf = path_leaf(path)
    return leaf == "name" and path_has(path, *PARTY_BLOCK_KEYS) and not path_has(path, "items")

def normalize_bool(value):
    if is_nan_like(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s in {"true", "1", "да", "yes"}:
            return True
        if s in {"false", "0", "нет", "no"}:
            return False
    return value

def normalize_number(value, force_int=False):
    if is_nan_like(value):
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if force_int:
            return int(round(float(value)))
        val = round(float(value), 2)
        return int(val) if float(val).is_integer() else val

    s = clean_spaces(value)
    s = s.translate(CYR_TO_LAT_MAP)
    s = s.replace("О", "0").replace("O", "0")
    s = s.replace("І", "1").replace("I", "1").replace("L", "1")
    s = s.replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)

    if not s:
        return None

    try:
        num = float(s)
        if force_int:
            return int(round(num))
        num = round(num, 2)
        return int(num) if num.is_integer() else num
    except:
        return value

def normalize_percent(value):
    if is_nan_like(value):
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        num = float(value)
        return f"{int(num) if num.is_integer() else round(num, 2)}%"

    s = clean_spaces(value)
    s = s.translate(CYR_TO_LAT_MAP)
    s = s.replace("％", "%")
    s = s.replace(" ", "")
    s = s.replace(",", ".")
    s = s.replace("О", "0").replace("O", "0")
    s = s.replace("І", "1").replace("I", "1").replace("L", "1")

    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    if not m:
        return clean_text(value)

    num = float(m.group(1))
    return f"{int(num) if num.is_integer() else round(num, 2)}%"

def normalize_date(value):
    if is_nan_like(value):
        return None
    if not isinstance(value, str):
        return value

    s = clean_spaces(value)
    low = s.lower()

    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+(\d{2}:\d{2}))?", low)
    if m:
        dd, mm, yyyy, hm = m.groups()
        out = f"{int(dd):02d}.{int(mm):02d}.{yyyy}"
        if hm:
            out += f" {hm}"
        return out

    m = re.fullmatch(r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})(?:\s*г\.?)?", low)
    if m:
        dd, mon, yyyy = m.groups()
        if mon in MONTHS:
            return f"{int(dd)} {mon} {yyyy} г."

    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", low)
    if m:
        yyyy, mm, dd = m.groups()
        return f"{yyyy}-{mm}-{dd}"

    return s

def normalize_account(value):
    if is_nan_like(value):
        return None
    s = clean_spaces(value)
    s = s.translate(CYR_TO_LAT_MAP).upper()
    s = re.sub(r"\s+", "", s)
    s = s.replace("О", "0").replace("O", "0")
    s = s.replace("І", "1").replace("I", "1").replace("L", "1")
    return s or None

def normalize_code_text(value):
    if is_nan_like(value):
        return None
    s = clean_spaces(value)
    s = s.translate(CYR_TO_LAT_MAP).upper()
    s = re.sub(r"\s+", "", s)
    return s or None

def normalize_phone(value):
    if is_nan_like(value):
        return None
    s = clean_spaces(value)
    digits = re.sub(r"[^\d]", "", s)
    if digits.startswith("375") and len(digits) == 12:
        return f"+{digits}"
    return s or None

def normalize_email(value):
    if is_nan_like(value):
        return None
    s = clean_spaces(value).lower()
    return s or None

def normalize_generic_text(value):
    if is_nan_like(value):
        return None

    s = clean_spaces(value)
    s = s.translate(VISUAL_QUOTES_MAP)
    s = re.sub(r"<[^>]+>", " ", s)

    s = re.sub(r"\s+([,.;:])", r"\1", s)
    s = re.sub(r"([,.;:])(\S)", r"\1 \2", s)
    s = re.sub(r"\s+", " ", s).strip(" ,.;:")

    return s or None

def normalize_free_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    s = re.sub(r"\bДата документа:?\s*$", "", s, flags=re.I).strip(" ,.;:")
    return s or None

def normalize_address_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    s = re.sub(r"^\s*,\s*", "", s)
    s = re.sub(r"\s*,\s*", ", ", s)
    s = re.sub(r"\s*;\s*", "; ", s)

    # Нормализуем частые адресные сокращения
    s = re.sub(r"\b(г|ул|пр|д|кв|пом|оф|корп)\.\s*", r"\1. ", s, flags=re.I)
    s = re.sub(r"\b(дом)\s+(?=\d)", r"\1 ", s, flags=re.I)

    # "6a" -> "6а" в адресном контексте
    s = re.sub(r"(\d)\s*([aA])\b", r"\1а", s)

    s = re.sub(r"\s+", " ", s).strip(" ,;:")
    return s or None

def normalize_bank_name_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    s = re.sub(r"^\s*в банке\s+", "", s, flags=re.I)
    s = re.sub(r"\b(?:БИК|BIC|Код банка)\b.*$", "", s, flags=re.I)
    s = re.sub(r"\b[A-Z]{6}[A-Z0-9]{2}\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;:")
    return s or None

def normalize_party_name_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    s = re.sub(
        r"^\s*(Организация|Поставщик|Покупатель|Плательщик|Бенефициар|Грузоотправитель|Грузополучатель)\s*:?\s*",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(r"\s+", " ", s).strip(" ,;:")
    return s or None

def normalize_unit_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    low = s.lower().replace(".", "").strip()
    if low in {"шт", "шτ", "шп", "sp", "pc", "pcs"}:
        return "шт"
    return low or None

def normalize_product_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    # "HOMME. 200 мл" -> "HOMME, 200 мл"
    s = re.sub(
        r"([A-Za-zА-Яа-яЁё])\.\s+(?=\d+\s*(?:мл|г|кг|л|см|мм|шт|м|мкм)\b)",
        r"\1, ",
        s,
    )

    # "1000 мл. 460645..." -> "1000 мл, 460645..."
    s = re.sub(
        r"(\d+\s*(?:мл|г|кг|л|см|мм|шт|м|мкм))\.\s+(?=\d{8,14}\b)",
        r"\1, ",
        s,
    )

    s = re.sub(
        r"\.\s+(?=(?:\d+\s*(?:мл|г|кг|л|см|мм|шт|м|мкм)\b|\d{8,14}\b))",
        ", ",
        s,
    )

    s = re.sub(r"\s*,\s*", ", ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,.;:")
    return s or None

def normalize_money_words_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    s = re.sub(r"\bкопейк\b", "копейки", s, flags=re.I)
    s = re.sub(r"(?<=\d)\s*руб\b\.?", " руб.", s, flags=re.I)
    s = re.sub(r"(?<=\d)\s*коп\b\.?", " коп.", s, flags=re.I)

    s = re.sub(r"\s+", " ", s).strip(" ,.;:")
    return s or None

def is_total_row(item):
    if not isinstance(item, dict):
        return False
    label = item.get("name") or item.get("description") or ""
    label = normalize_generic_text(label)
    if not label:
        return False
    return label.lower() in {"итого", "итог", "итого:"}

def safe_float(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    if not s:
        return 0.0
    try:
        return float(s)
    except:
        return 0.0

def cleanup_items_and_totals(obj):
    if isinstance(obj, dict):
        cleaned = {k: cleanup_items_and_totals(v) for k, v in obj.items()}

        if isinstance(cleaned.get("items"), list):
            cleaned["items"] = [x for x in cleaned["items"] if not is_total_row(x)]

        return cleaned

    if isinstance(obj, list):
        return [cleanup_items_and_totals(x) for x in obj]

    return obj


def normalize_by_path(path, value):
    if is_nan_like(value):
        return None

    leaf = path_leaf(path)

    if leaf in BOOL_KEY_HINTS:
        return normalize_bool(value)

    if leaf in DATE_KEY_HINTS:
        return normalize_date(value)

    if leaf in PERCENT_KEY_HINTS:
        return normalize_percent(value)

    if leaf in INT_KEY_HINTS:
        return normalize_number(value, force_int=True)

    if leaf in NUMERIC_KEY_HINTS:
        return normalize_number(value, force_int=False)

    if leaf in ACCOUNT_KEYS:
        return normalize_account(value)

    if leaf in CODE_KEYS:
        return normalize_code_text(value)

    if leaf == "phone":
        return normalize_phone(value)

    if leaf == "email":
        return normalize_email(value)

    if leaf == "unit":
        return normalize_unit_text(value)

    if leaf in MONEY_WORD_KEYS:
        return normalize_money_words_text(value)

    if leaf in ADDRESS_KEYS:
        return normalize_address_text(value)

    if leaf in BANK_NAME_KEYS:
        return normalize_bank_name_text(value)

    if is_product_text_field(path):
        return normalize_product_text(value)

    if is_party_name_field(path):
        return normalize_party_name_text(value)

    if leaf in FREE_TEXT_KEYS:
        return normalize_free_text(value)

    if isinstance(value, str):
        s = clean_spaces(value)

        # Осторожный fallback: если строка действительно выглядит как число
        s_num = s.translate(CYR_TO_LAT_MAP)
        s_num = s_num.replace(",", ".")
        s_num = re.sub(r"[^\d.\-%]", "", s_num)

        if s_num:
            try:
                if "%" in s_num:
                    num = float(s_num.replace("%", ""))
                    return f"{int(num) if num.is_integer() else round(num, 2)}%"
                num = float(s_num)
                num = round(num, 2)
                return int(num) if num.is_integer() else num
            except:
                pass

        return normalize_generic_text(s)

    return value

def walk(obj, path=()):
    if isinstance(obj, dict):
        return {k: walk(v, path + (k,)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [walk(x, path + ("[]",)) for x in obj]
    return normalize_by_path(path, obj)

def normalize_pred(pred_raw):
    return cleanup_items_and_totals(walk(pred_raw))

# =========================
# RUN
# =========================

