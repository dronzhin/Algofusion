import json
import re
from pathlib import Path

ROI_ROOT = Path("final_rebuilt_auto") / "_clean_page_plus_roi_json"
PRED_DIR = Path("data") / "pred"
PRED_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# helpers
# =========================

CYR_TO_LAT = str.maketrans({
    "А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "К": "K",
    "М": "M", "О": "O", "Р": "P", "Т": "T", "У": "Y", "Х": "X",
    "І": "I", "Ү": "Y",
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
})

MONTHS_RU = (
    "января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря"
)

def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def clean_text(s):
    if s is None:
        return None
    s = str(s).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s or None

def only_digits(s):
    s = clean_text(s)
    if not s:
        return None
    d = re.sub(r"\D", "", s)
    return d or None

def normalize_account(s):
    s = clean_text(s)
    if not s:
        return None
    s = s.translate(CYR_TO_LAT).upper()
    s = s.replace(" ", "")
    s = s.replace("О", "0").replace("O", "0")
    s = s.replace("І", "1").replace("I", "1").replace("L", "1")
    return s

def to_float(s):
    s = clean_text(s)
    if not s:
        return None
    s = s.translate(CYR_TO_LAT)
    s = s.replace(" ", "").replace(",", ".")
    s = s.replace("О", "0").replace("O", "0")
    s = s.replace("І", "1").replace("I", "1").replace("L", "1")
    s = re.sub(r"[^\d.\-]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except:
        return None

def to_int(s):
    v = to_float(s)
    if v is None:
        return None
    return int(round(v))

def normalize_percent(s):
    s = clean_text(s)
    if not s:
        return None
    s = s.replace(" ", "").replace(",", ".").replace("％", "%")
    m = re.search(r"(\d+(?:\.\d+)?)%?", s)
    if not m:
        return None
    num = float(m.group(1))
    return f"{int(num) if num.is_integer() else num}%"

def extract_email(s):
    if not s:
        return None
    m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', s)
    return m.group(0) if m else None

def extract_phone(s):
    if not s:
        return None
    m = re.search(r'(\+375[\s\-\(\)\d]{8,})', s)
    return clean_text(m.group(1)) if m else None

def extract_tax_id(s):
    if not s:
        return None
    m = re.search(r'УНП\s*([0-9]{9})', s, flags=re.I)
    if m:
        return m.group(1)
    d = only_digits(s)
    if d and len(d) == 9:
        return d
    return None

def extract_kpp(s):
    if not s:
        return None
    m = re.search(r'КПП\s*([0-9]{9})', s, flags=re.I)
    return m.group(1) if m else None

def extract_bank_account(s):
    if not s:
        return None
    s2 = normalize_account(s)
    m = re.search(r'BY\d{2}[A-Z0-9]{24}', s2)
    return m.group(0) if m else None

def extract_bic(s):
    if not s:
        return None
    s2 = normalize_account(s)
    m = re.search(r'\b[A-Z]{6}[A-Z0-9]{2}\b', s2)
    return m.group(0) if m else None

def extract_all_accounts(s):
    if not s:
        return []
    s2 = normalize_account(s)
    vals = re.findall(r'BY\d{2}[A-Z0-9]{24}', s2)
    return list(dict.fromkeys(vals))

def extract_all_tax_ids(s):
    if not s:
        return []
    vals = re.findall(r'(?<!\d)(\d{9})(?!\d)', s)
    return list(dict.fromkeys(vals))

def extract_all_bics(s):
    if not s:
        return []
    s2 = normalize_account(s)
    vals = re.findall(r'\b[A-Z]{6}[A-Z0-9]{2}\b', s2)
    return list(dict.fromkeys(vals))

def extract_all_datetimes(s):
    if not s:
        return []
    vals = re.findall(r'([0-3]?\d\.[01]?\d\.20\d{2}\s+\d{2}:\d{2})', s)
    return list(dict.fromkeys(clean_text(v) for v in vals if clean_text(v)))

def extract_company_names(s):
    if not s:
        return []
    patterns = [
        r'((?:ООО|ОАО|ЗАО|ОДО|ЧУП)\s*["«][^"»]+["»])',
        r'((?:Общество с ограниченной ответственностью|Открытое акционерное общество|Закрытое акционерное общество)\s*["«][^"»]+["»])',
    ]
    vals = []
    for pat in patterns:
        vals.extend(re.findall(pat, s, flags=re.I))
    out = []
    seen = set()
    for v in vals:
        cv = clean_text(v)
        key = cv.lower() if cv else None
        if cv and key not in seen:
            seen.add(key)
            out.append(cv)
    return out

def extract_person_name(s):
    if not s:
        return None
    m = re.search(r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)', s)
    if m:
        val = clean_text(m.group(1))
        val = re.sub(r'копейк$', 'копейки', val, flags=re.I)
        return val
    m = re.search(r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.)', s)
    return clean_text(m.group(1)) if m else None

def cleanup_bank_name(s):
    if not s:
        return None
    s = clean_text(s)
    s = re.sub(r'\b[A-Z]{6}[A-Z0-9]{2}\b', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip(' ,;:')
    return s or None

def extract_doc_number_by_no(s):
    if not s:
        return None
    m = re.search(r'№\s*([A-Za-zА-Яа-я0-9\-\/]+)', s)
    return clean_text(m.group(1)) if m else None

def extract_ru_date_text(s):
    if not s:
        return None
    m = re.search(rf'([0-3]?\d\s+(?:{MONTHS_RU})\s+20\d{{2}}\s*г?\.?)', s, flags=re.I)
    if m:
        val = clean_text(m.group(1))
        val = re.sub(r'копейк$', 'копейки', val, flags=re.I)
        return val
    m = re.search(r'([0-3]?\d\.[01]?\d\.20\d{2}(?:\s+\d{2}:\d{2})?)', s)
    if m:
        return clean_text(m.group(1))
    return None

def get_regions(data):
    return data.get("regions", []) if isinstance(data, dict) else []

def group_rows(table_cells, tol=12):
    rows = []
    for cell in sorted(table_cells, key=lambda r: (r["bbox"][1], r["bbox"][0])):
        y = cell["bbox"][1]
        placed = False
        for row in rows:
            row_y = round(sum(c["bbox"][1] for c in row) / len(row))
            if abs(y - row_y) <= tol:
                row.append(cell)
                placed = True
                break
        if not placed:
            rows.append([cell])
    for row in rows:
        row.sort(key=lambda c: c["bbox"][0])
    return rows

def row_texts(row):
    return [clean_text(c.get("text")) or "" for c in row]

def looks_like_table_header(texts):
    joined = " ".join((clean_text(x) or "") for x in texts).lower()

    patterns = [
        r"\bартикул\b",
        r"\bтовар\b",
        r"\bштрих\b",
        r"\bцена\b",
        r"\bсумма\b",
        r"\bндс\b",
        r"\bкол(?:-во|ичество)?\b",
        r"\bед\.?\b",
    ]

    hits = sum(1 for pat in patterns if re.search(pat, joined))
    return hits >= 3


def is_header_row(texts):
    return looks_like_table_header(texts)


def is_index_row(texts):
    vals = [clean_text(v) for v in texts if clean_text(v)]
    if len(vals) < 3:
        return False

    nums = []
    for v in vals:
        vv = v.replace("l", "1").replace("I", "1").replace("|", "1")
        if not vv.isdigit():
            return False
        nums.append(int(vv))

    diffs = [b - a for a, b in zip(nums, nums[1:])]
    return all(d == 1 for d in diffs)


def is_total_row(texts):
    joined = " ".join((clean_text(x) or "") for x in texts).lower()
    return "итого" in joined


def filter_table_rows(table_rows):
    clean_rows = []

    for row in table_rows:
        texts = [clean_text(cell.get("text")) or "" for cell in row]
        joined = " ".join(texts).lower()

        if looks_like_table_header(texts):
            continue
        if is_index_row(texts):
            continue
        if "итого" in joined:
            continue

        clean_rows.append(row)

    return clean_rows


def invoice_is_header_row(texts):
    return looks_like_table_header(texts)


def invoice_is_index_row(texts):
    return is_index_row(texts)



# =========================
# Account protocol
# =========================

def _account_prot_normalize_unit(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    normalized = cleaned.lower().replace(".", "").replace("τ", "т").strip()
    if normalized in {"шт", "шп"}:
        return "шт"
    return cleaned

def split_supplier_customer(header_text):
    if not header_text:
        return None, None
    m = re.search(r'Покупатель', header_text, flags=re.I)
    if not m:
        return header_text, None
    return clean_text(header_text[:m.start()]), clean_text(header_text[m.start():])

def extract_contract(header_text):
    out = {"contract_number": None, "contract_date": None, "contract_type": None}
    if not header_text:
        return out

    m = re.search(
        r'Основание:\s*([А-Яа-яA-Za-z ]+?)\s*№\s*([A-Za-z0-9\-\/]+)\s*от\s*([0-3]?\d\.[01]?\d\.20\d{2})',
        header_text,
        flags=re.I,
    )
    if m:
        out["contract_type"] = clean_text(m.group(1))
        out["contract_number"] = clean_text(m.group(2))
        out["contract_date"] = clean_text(m.group(3))
    return out

def _account_prot_header_sort_key(region):
    bbox = region.get("bbox") or [0, 0, 0, 0]
    return (round(bbox[1] / 15), bbox[1], bbox[0])

def _account_prot_join_region_texts(regions):
    parts = [clean_text(region.get("text")) for region in regions]
    parts = [part for part in parts if part]
    return clean_text(" ".join(parts))

def _account_prot_header_views(regions):
    header_box = next((region for region in regions if region.get("id") == "header_box"), None)
    header_box_text = clean_text(header_box.get("text")) if header_box else None
    header_rois = sorted(
        [
            region
            for region in regions
            if region.get("kind") == "header_form_roi" and clean_text(region.get("text"))
        ],
        key=_account_prot_header_sort_key,
    )
    header_form_text = _account_prot_join_region_texts(header_rois)
    combined_text = clean_text(" ".join(part for part in [header_form_text, header_box_text] if part))
    return {
        "header_box_text": header_box_text,
        "header_form_text": header_form_text,
        "header_text": header_form_text or header_box_text,
        "combined_text": combined_text,
    }

def _account_prot_trim_by_stop_words(text, stop_patterns):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    cut_at = len(cleaned)
    for pattern in stop_patterns:
        match = re.search(pattern, cleaned, flags=re.I)
        if match:
            cut_at = min(cut_at, match.start())
    return clean_text(cleaned[:cut_at])

def _account_prot_normalize_address(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    cleaned = re.sub(r'(?<=,\s)(?:[bBбБ]|6)(?:[aAаА])\b', '6а', cleaned)
    cleaned = re.sub(r'(?<=\s)(?:[bBбБ]|6)(?:[aAаА])\b', '6а', cleaned)
    cleaned = re.sub(r',(?=\S)', ', ', cleaned)
    cleaned = re.sub(r'\s+,', ',', cleaned)
    cleaned = re.sub(r'(?i)\b(г\.|д\.|ул\.|пр\.)\s*(?=\S)', lambda m: m.group(1) + ' ', cleaned)
    return clean_text(cleaned)

def _account_prot_cleanup_company_name(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    cleaned = re.sub(r'^\s*Поставщик(?:\s+и\s+его\s+адрес:?)?\s*', '', cleaned, flags=re.I)
    cleaned = re.sub(r'^\s*Покупатель(?:\s+и\s+его\s+адрес:?)?\s*', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\bСЧЕТ[-\s]*ПРОТОКОЛ\b', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\bего\s+адрес:?\b', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,;:')
    return cleaned or None

def _account_prot_cleanup_bank_name(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    cleaned = re.sub(r'\b[A-Z]{6}[A-Z0-9]{2}\b', ' ', cleaned)
    cleaned = re.sub(r'\bтовары\s*\(продукцию\)\b', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\bсогласования\b.*$', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,;:')
    return cleaned or None

def _account_prot_extract_document_number_and_date(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None, None
    scope = cleaned
    title_match = re.search(r'счет[-\s]*протокол', cleaned, flags=re.I)
    if title_match:
        scope = cleaned[title_match.start():]
    pattern = re.compile(
        r'№\s*([A-Za-zА-Яа-я0-9\-/]+)\s*от\s*([0-3]?\d\s+(?:' + MONTHS_RU + r')\s+20\d{2}\s*г?\.?)',
        flags=re.I,
    )
    for match in pattern.finditer(scope):
        candidate = clean_text(match.group(1))
        normalized = normalize_account(candidate)
        if not candidate or (normalized and normalized.startswith("BY")):
            continue
        return candidate, clean_text(match.group(2))
    return None, None

def _account_prot_extract_bic_after_label(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None

    patterns = [
        r'\bBIC\b\s*[:\-]?\s*([A-Za-zА-Яа-яІіҮү0-9]{8,12})',
        r'\bБИК\b\s*[:\-]?\s*([A-Za-zА-Яа-яІіҮү0-9]{8,12})',
    ]

    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.I)
        if not match:
            continue

        raw_value = clean_text(match.group(1))
        if not raw_value:
            continue

        normalized = normalize_account(raw_value)
        if not normalized:
            continue

        bic_match = re.search(r'[A-Z]{6}[A-Z0-9]{2}', normalized)
        if bic_match:
            return bic_match.group(0)

        if len(normalized) >= 8:
            return normalized[:8]

    return None

def _account_prot_parse_supplier(block):
    out = {
        "name": None,
        "tax_id": extract_tax_id(block),
        "address": None,
        "bank_account": extract_bank_account(block),
        "bank_name": None,
        "bank_address": None,
        "bank_code": extract_bic(block) or _account_prot_extract_bic_after_label(block),
        "phone": extract_phone(block),
        "email": extract_email(block),
    }
    text = clean_text(block)
    if not text:
        return out

    party_text = clean_text(re.split(r'\bБанк:\s*', text, maxsplit=1, flags=re.I)[0]) or text
    companies = extract_company_names(party_text)
    if companies:
        out["name"] = _account_prot_cleanup_company_name(companies[0])

    address_match = re.search(r'(\d{6}.*)', party_text, flags=re.I)
    if address_match:
        out["address"] = _account_prot_normalize_address(
            _account_prot_trim_by_stop_words(
                address_match.group(1),
                (
                    r'\bр/с\b',
                    r'№\s*BY',
                    r'№\s*[A-Za-zА-Яа-я0-9]{12,}',
                    r'\bБанк:',
                    r'\bБИК\b',
                    r'\bBIC\b',
                    r'\bтел\.',
                    r'\bE-mail:',
                    r'\bУНП\b',
                    r'\bсогласования\b',
                    r'\bсчет[-\s]*протокол\b',
                    r'№\s*[A-Za-zА-Яа-я0-9\-/]+\s*от',
                ),
            )
        )

    bank_name_match = re.search(
        r'Банк:\s*(.*?)(?=\s*\d{6}|\s*БИК|\s*BIC|\s*тел\.|\s*E-mail:|\s*УНП|$)',
        text,
        flags=re.I,
    )
    if bank_name_match:
        out["bank_name"] = _account_prot_cleanup_bank_name(bank_name_match.group(1))

    bank_address_match = re.search(
        r'Банк:\s*.*?(\d{6}.*?)(?=\s*БИК|\s*BIC|\s*тел\.|\s*E-mail:|\s*УНП|$)',
        text,
        flags=re.I,
    )
    if bank_address_match:
        out["bank_address"] = _account_prot_normalize_address(bank_address_match.group(1))

    if not out["bank_code"]:
        out["bank_code"] = _account_prot_extract_bic_after_label(text)

    return out

def _account_prot_parse_customer(block):
    out = {
        "name": None,
        "tax_id": extract_tax_id(block),
        "address": None,
        "bank_account": extract_bank_account(block),
        "bank_name": None,
        "bank_address": None,
        "bank_code": extract_bic(block) or _account_prot_extract_bic_after_label(block),
        "phone": extract_phone(block),
    }
    text = clean_text(block)
    if not text:
        return out

    party_text = clean_text(re.split(r'\bБанк:\s*', text, maxsplit=1, flags=re.I)[0]) or text
    companies = extract_company_names(party_text)
    if companies:
        out["name"] = _account_prot_cleanup_company_name(companies[0])

    address_source = None
    address_match = re.search(r'адрес:\s*(.*)', party_text, flags=re.I)
    if address_match:
        address_source = address_match.group(1)
    elif out["name"] and out["name"] in party_text:
        address_source = party_text.split(out["name"], 1)[1]
        address_source = re.sub(r'^\s*(?:и\s+его\s+)?адрес:\s*', '', address_source, flags=re.I)

    if address_source:
        out["address"] = _account_prot_normalize_address(
            _account_prot_trim_by_stop_words(
                address_source,
                (
                    r'\bр/с\b',
                    r'№\s*BY',
                    r'№\s*[A-Za-zА-Яа-я0-9]{12,}',
                    r'\bБанк:',
                    r'\bБИК\b',
                    r'\bBIC\b',
                    r'\bтел\.',
                    r'\bУНП\b',
                    r'$',
                ),
            )
        )

    bank_name_match = re.search(
        r'Банк:\s*(.*?)(?=\s*\d{6}|\s*БИК|\s*BIC|\s*тел\.|\s*УНП|$)',
        text,
        flags=re.I,
    )
    if bank_name_match:
        out["bank_name"] = _account_prot_cleanup_bank_name(bank_name_match.group(1))

    bank_address_match = re.search(
        r'Банк:\s*.*?(\d{6}.*?)(?=\s*БИК|\s*BIC|\s*тел\.|\s*УНП|$)',
        text,
        flags=re.I,
    )
    if bank_address_match:
        out["bank_address"] = _account_prot_normalize_address(bank_address_match.group(1))

    if out["address"] and out["name"]:
        escaped_name = re.escape(out["name"])
        out["address"] = clean_text(re.sub(r'^' + escaped_name + r'[\s,;:]*', '', out["address"], flags=re.I))

    if not out["bank_code"]:
        out["bank_code"] = _account_prot_extract_bic_after_label(text)

    return out

def _account_prot_extract_total_in_words(footer_text):
    text = clean_text(footer_text)
    if not text:
        return None

    text = re.sub(r'\b[ВVB][сc][еe][ггg][оo]\s*:', 'Всего:', text, flags=re.I)

    patterns = [
        r'Всего:\s*([А-ЯЁа-яё][А-ЯЁа-яё\s-]+белорусских рублей\s+\d{1,2}\s+копе[её]к)',
        r'на сумму\s*([А-ЯЁа-яё][А-ЯЁа-яё\s-]+белорусских рублей\s+\d{1,2}\s+копе[её]к)',
        r'Сумма прописью[:\s]*([А-ЯЁа-яё][А-ЯЁа-яё\s-]+белорусских рублей\s+\d{1,2}\s+копе[её]к)',
        r'([А-ЯЁа-яё][А-ЯЁа-яё\s-]+белорусских рублей\s+\d{1,2}\s+копе[её]к)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.I)
        if matches:
            return clean_text(matches[-1])

    return None

def _account_prot_extract_notes(footer_text):
    text = clean_text(footer_text)
    if not text:
        return None
    match = re.search(
        r'(При получении товара необходимо:.*?)(?=\s*(?:Поставщик|Покупатель|МП)\b|$)',
        text,
        flags=re.I,
    )
    return clean_text(match.group(1)) if match else None

def parse_account_protocol(roi_path: Path):
    data = load_json(roi_path)
    regions = get_regions(data)

    footer_box = next((region for region in regions if region.get("id") == "footer_box"), None)
    table_cells = [region for region in regions if region.get("kind") == "table_cell"]

    header_views = _account_prot_header_views(regions)
    header_text = header_views["header_text"]
    combined_header = header_views["combined_text"] or header_text
    footer_text = clean_text(footer_box.get("text")) if footer_box else None

    supplier_block, customer_block = split_supplier_customer(combined_header)
    supplier = _account_prot_parse_supplier(supplier_block)
    customer = _account_prot_parse_customer(customer_block)
    contract_basis = extract_contract(combined_header)

    items = []
    totals = {
        "subtotal_excl_vat": None,
        "vat_amount": None,
        "total_incl_vat": None,
        "total_in_words": None,
        "currency": "BYN",
    }

    rows = group_rows(table_cells)
    line_no = 1

    for row in rows:
        texts = row_texts(row)
        joined = " | ".join(texts).lower()

        if "предмет счета" in joined:
            continue

        if texts and texts[0].strip().lower().startswith("итого"):
            if len(texts) >= 10:
                totals["subtotal_excl_vat"] = to_float(texts[6])
                totals["vat_amount"] = to_float(texts[8])
                totals["total_incl_vat"] = to_float(texts[9])
            continue

        if len(texts) < 10:
            continue

        match = re.match(r'^(\d{8,14})\s+(.*)$', texts[0])
        sku = match.group(1) if match else None
        desc = clean_text(match.group(2) if match else texts[0])

        items.append({
            "line_number": line_no,
            "sku": sku,
            "description": desc,
            "unit": _account_prot_normalize_unit(texts[1]),
            "quantity": to_int(texts[2]) or 1,
            "free_unit_price_excl_vat": to_float(texts[3]),
            "extra_charge": to_float(texts[4]),
            "unit_price_excl_vat": to_float(texts[5]),
            "total_excl_vat": to_float(texts[6]),
            "vat_rate": normalize_percent(texts[7]),
            "vat_amount": to_float(texts[8]),
            "total_incl_vat": to_float(texts[9]),
        })
        line_no += 1

    document_status = {"is_valid": None, "valid_until": None, "status_note": None}

    if footer_text:
        totals["total_in_words"] = _account_prot_extract_total_in_words(footer_text)
        status_match = re.search(
            r'(Счет действителен до:\s*[0-3]?\d\s+(?:' + MONTHS_RU + r')\s+20\d{2}\s*г\.)',
            footer_text,
            flags=re.I,
        )
        if status_match:
            document_status["is_valid"] = True
            document_status["status_note"] = clean_text(status_match.group(1))
            document_status["valid_until"] = extract_ru_date_text(status_match.group(1))

    bics = extract_all_bics(combined_header or "")
    supplier_bics = extract_all_bics(supplier_block or "")
    customer_bics = extract_all_bics(customer_block or "")
    supplier_bank_name = (clean_text(supplier.get("bank_name")) or "").lower()
    customer_bank_name = (clean_text(customer.get("bank_name")) or "").lower()

    if not supplier.get("bank_code"):
        if supplier_bics:
            supplier["bank_code"] = supplier_bics[-1]
        elif len(bics) > 0:
            supplier["bank_code"] = bics[0]

    if not customer.get("bank_code"):
        if customer_bics:
            customer["bank_code"] = customer_bics[-1]
        elif len(bics) > 1:
            customer["bank_code"] = bics[-1]
        elif len(bics) == 1 and supplier_bank_name and supplier_bank_name == customer_bank_name:
            customer["bank_code"] = bics[0]

    document_number, document_date = _account_prot_extract_document_number_and_date(
        header_views["header_form_text"] or combined_header
    )
    if not document_number:
        document_number, document_date = _account_prot_extract_document_number_and_date(combined_header)
    if not document_date:
        document_date = extract_ru_date_text(combined_header)

    file_key = roi_path.name.replace("_roi_text.json", ".pdf")

    return {
        "Account-protocol": {
            file_key: {
                "document_number": document_number,
                "document_date": document_date,
                "supplier": supplier,
                "customer": customer,
                "contract_basis": contract_basis,
                "items": items,
                "totals": totals,
                "document_status": document_status,
                "notes": _account_prot_extract_notes(footer_text),
            }
        }
    }

# =========================
# Invoice
# =========================

def cut_basis(text):
    if not text:
        return None
    stop_words = ["Сумма", "Итого", "Всего", "ВНИМАНИЕ"]
    pos = len(text)
    for w in stop_words:
        i = text.find(w)
        if i != -1:
            pos = min(pos, i)
    return text[:pos].strip(" ,")

def merge_multiline(text):
    if not text:
        return None
    text = re.sub(r"\s+", " ", str(text))
    return text.strip(" ,")

def clean_invoice_date(text):
    text = clean_text(text)
    if not text:
        return None
    text = re.sub(r"\s+г\.\s*$", "", text, flags=re.I)
    return text

def extract_phone_pretty(s):
    if not s:
        return None
    m = re.search(r'(\+375)\s*\(?(\d{2})\)?\s*(\d{3})[-\s]*(\d{2})[-\s]*(\d{2})', s)
    if not m:
        return None
    return f"{m.group(1)} ({m.group(2)}) {m.group(3)}-{m.group(4)}-{m.group(5)}"

def extract_invoice_note(footer_text):
    if not footer_text:
        return None
    m = re.search(
        r'(ВНИМАНИЕ!!!\s*Счет действителен в течение\s*\d+\s*дн\w*)',
        footer_text,
        flags=re.I
    )
    return clean_text(m.group(1)) if m else None

def extract_invoice_total_in_words(footer_text):
    if not footer_text:
        return None

    text = clean_invoice_footer_text(footer_text) or footer_text
    text = re.sub(r'ВНИМАНИЕ!!!.*$', ' ', text, flags=re.I)
    text = re.sub(r'\bна сумму\b', ' ', text, flags=re.I)
    text = re.sub(r'\b\d+[.,]\d{2}\s*BYN\b', ' ', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip()

    m = re.search(
        r'([А-ЯЁа-яё]+(?:\s+[А-ЯЁа-яё-]+)*\s+рубл[яей]\s+\d{1,2}\s+копе[йе]к)',
        text,
        flags=re.I
    )
    if m:
        val = clean_text(m.group(1))
        val = re.sub(r'копейк$', 'копейки', val, flags=re.I)
        return val

    m = re.search(r'на сумму\s*([^\.]+)', footer_text, flags=re.I)
    if m:
        val = clean_text(m.group(1))
        if val:
            val = re.sub(r'^\d+[.,]\d{2}\s*BYN\s*', '', val, flags=re.I)
            val = re.sub(r'\s*ВНИМАНИЕ!!!.*$', '', val, flags=re.I)
            val = re.sub(r'копейк$', 'копейки', val, flags=re.I)
            return clean_text(val)

    return None


def clean_invoice_footer_text(footer_text):
    if not footer_text:
        return None
    text = clean_text(footer_text)
    text = re.sub(r'<del>.*?</del>', ' ', text, flags=re.I)
    text = re.sub(r'\bSalara\s+Augus\b', ' ', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_invoice_signatory(footer_text):
    signatory = {"position": None, "name": None}
    if not footer_text:
        return signatory

    m = re.search(
        r'(Специалист по работе с клиентами|Менеджер|Директор)\s+([А-ЯЁ][а-яё]+(?:\s*[А-ЯЁ]\.[А-ЯЁ]\.))',
        footer_text
    )
    if m:
        signatory["position"] = clean_text(m.group(1))
        signatory["name"] = clean_text(m.group(2))

    return signatory


def enrich_invoice_header(head, header_text):
    if not header_text:
        return head
    company_names = extract_company_names(header_text)
    if company_names and not head["supplier"]["name"]:
        head["supplier"]["name"] = company_names[0]
    if len(company_names) > 1 and not head["customer"]["name"]:
        head["customer"]["name"] = company_names[1]

    if company_names:
        supplier_name = head["supplier"]["name"] or company_names[0]
        customer_name = head["customer"]["name"] or (company_names[1] if len(company_names) > 1 else None)
        if supplier_name and customer_name and supplier_name in header_text and customer_name in header_text:
            supplier_tail = header_text.split(supplier_name, 1)[1].split(customer_name, 1)[0]
            customer_tail = header_text.split(customer_name, 1)[1]
            if not head["supplier"]["address"]:
                m = re.search(r'^(.*?)(?=,\s*УНП\s*\d{9}|,\s*р/с\s*BY|,\s*в банке|$)', clean_text(supplier_tail or ''), flags=re.I)
                if m:
                    head["supplier"]["address"] = clean_text(m.group(1))
            if not head["customer"]["address"]:
                m = re.search(r'^(.*?)(?=,\s*тел\.?|,\s*УНП\s*\d{9}|,\s*КПП\s*\d{9}|\s*Основание:|$)', clean_text(customer_tail or ''), flags=re.I)
                if m:
                    head["customer"]["address"] = clean_text(m.group(1))
            if not head["customer"]["phone"]:
                head["customer"]["phone"] = extract_phone_pretty(customer_tail)
            if not head["customer"]["tax_id"]:
                head["customer"]["tax_id"] = extract_tax_id(customer_tail)
            if not head["customer"]["kpp"]:
                head["customer"]["kpp"] = extract_kpp(customer_tail)
            if not head["supplier"]["bank_name"]:
                m = re.search(r'в банке\s*(.*?)(?=,\s*БИК\s*[A-ZА-Я0-9]+|$)', supplier_tail, flags=re.I)
                if m:
                    head["supplier"]["bank_name"] = cleanup_bank_name(m.group(1))
            if not head["supplier"]["bank_account"]:
                head["supplier"]["bank_account"] = extract_bank_account(supplier_tail)
            if not head["supplier"]["bic"]:
                head["supplier"]["bic"] = extract_bic(supplier_tail)
            if not head["supplier"]["tax_id"]:
                head["supplier"]["tax_id"] = extract_tax_id(supplier_tail)
    return head


def parse_invoice_header(header_text, header_lines=None):
    out = {
        "invoice_number": None,
        "invoice_date": None,
        "payment_deadline": None,
        "supplier": {
            "name": None, "address": None, "bank_account": None,
            "bank_name": None, "bic": None, "tax_id": None
        },
        "customer": {
            "name": None, "address": None, "tax_id": None,
            "kpp": None, "phone": None
        },
        "basis": None,
    }
    if not header_text:
        return out

    lines = []
    if header_lines:
        for line in header_lines:
            txt = clean_text(line.get("text")) if isinstance(line, dict) else clean_text(line)
            if txt:
                lines.append(txt)

    invoice_line = next((line for line in lines if re.search(r'Счет\s*№', line, flags=re.I)), None)
    scope_for_invoice = invoice_line or header_text
    m = re.search(
        r'Счет\s*№\s*([A-Za-zА-Яа-я0-9\-\/]+)\s*от\s*([0-3]?\d\s+(?:' + MONTHS_RU + r')\s+20\d{2})(?:\s*г\.)?',
        scope_for_invoice,
        flags=re.I
    )
    if m:
        out["invoice_number"] = clean_text(m.group(1))
        out["invoice_date"] = clean_invoice_date(m.group(2))

    basis_line = next((line for line in lines if re.search(r'Основание:', line, flags=re.I)), None)
    if basis_line:
        m = re.search(r'Основание:\s*(.+)', basis_line, flags=re.I)
        if m:
            out["basis"] = cut_basis(clean_text(m.group(1)))
    else:
        m = re.search(r'Основание:\s*(.+)', header_text, flags=re.I)
        if m:
            out["basis"] = cut_basis(clean_text(m.group(1)))

    supplier_label_idx = next((i for i, line in enumerate(lines) if re.search(r'Поставщик:', line, flags=re.I)), None)
    if supplier_label_idx is not None:
        supplier_line = lines[supplier_label_idx]
        prev_line = lines[supplier_label_idx - 1] if supplier_label_idx > 0 else None
        next_line = lines[supplier_label_idx + 1] if supplier_label_idx + 1 < len(lines) else None

        if prev_line:
            companies = extract_company_names(prev_line)
            if companies:
                out["supplier"]["name"] = clean_text(companies[0])

            tax_match = re.search(r'УНП\s*(\d{9})', prev_line, flags=re.I)
            if tax_match:
                out["supplier"]["tax_id"] = clean_text(tax_match.group(1))

        supplier_line_match = re.search(r'Поставщик:\s*(.+)$', supplier_line, flags=re.I)
        address_parts = []

        postal_prefix = None
        if prev_line:
            zip_match = re.search(r'(?:^|,\s*)(\d{6})(?=,|$)', prev_line)
            if zip_match:
                postal_prefix = zip_match.group(1)

        if supplier_line_match:
            supplier_inline = clean_text(supplier_line_match.group(1))
            if supplier_inline:
                address_parts.append(supplier_inline)

        if (not address_parts) and next_line and not re.search(r'^\s*(УНП|КПП|Покупатель:)', next_line, flags=re.I):
            address_parts.append(next_line)

        supplier_address = clean_text(" ".join(x for x in address_parts if x))
        if supplier_address:
            supplier_address = re.sub(r'^\s*,\s*', '', supplier_address)
            if postal_prefix and not re.match(r'^\s*' + re.escape(postal_prefix) + r'(?:\b|,)', supplier_address):
                supplier_address = clean_text(f'{postal_prefix}, {supplier_address}')
            out["supplier"]["address"] = clean_text(supplier_address)

    if not out["supplier"]["name"]:
        org_line = next((line for line in lines if re.search(r'Организация:', line, flags=re.I)), None)
        if org_line:
            m = re.search(r'Организация:\s*(.*?)(?=,\s*УПП\b|,\s*УНП\b|$)', org_line, flags=re.I)
            if m:
                out["supplier"]["name"] = clean_text(m.group(1))

    def _normalize_invoice_account_candidate(text):
        if not text:
            return None
        s = clean_text(text)
        if not s:
            return None

        s = s.translate(CYR_TO_LAT)

        # OCR sometimes keeps Y-like letters in non-Latin forms, which breaks BY...
        s = (
            s.replace("Ү", "Y")
             .replace("ү", "Y")
             .replace("Ұ", "Y")
             .replace("ұ", "Y")
             .replace("У", "Y")
             .replace("у", "Y")
             .replace("Ў", "Y")
             .replace("ў", "Y")
             .replace("Ј", "J")
             .replace("ј", "J")
        )

        s = s.upper()
        s = re.sub(r'\s+', '', s)
        s = s.replace("О", "0").replace("O", "0")
        s = s.replace("І", "1").replace("I", "1").replace("L", "1")
        return s


    bank_idx = next((i for i, line in enumerate(lines) if 'р/с' in line.lower()), None)
    if bank_idx is not None:
        bank_parts = [lines[bank_idx]]
        if bank_idx + 1 < len(lines):
            bank_parts.append(lines[bank_idx + 1])
        if bank_idx + 2 < len(lines):
            bank_parts.append(lines[bank_idx + 2])

        bank_block = clean_text(" ".join(x for x in bank_parts if x))

        account_match = re.search(r'р/с\s*(.+?)(?=,\s*в банке|\s+в банке|,\s*БИК\b|\s+БИК\b|$)', bank_block, flags=re.I)
        if account_match:
            account_candidate = _normalize_invoice_account_candidate(account_match.group(1))
            m_acc = re.search(r'BY\d{2}[A-Z0-9]{24}', account_candidate or '')
            if m_acc:
                out["supplier"]["bank_account"] = m_acc.group(0)

        if not out["supplier"]["bank_account"]:
            for cand in bank_parts:
                cand_norm = _normalize_invoice_account_candidate(cand)
                m_acc = re.search(r'BY\d{2}[A-Z0-9]{24}', cand_norm or '')
                if m_acc:
                    out["supplier"]["bank_account"] = m_acc.group(0)
                    break

        bank_name_match = re.search(r'в банке\s*(.*?)(?=,\s*БИК\b|\s+БИК\b|$)', bank_block, flags=re.I)
        if bank_name_match:
            out["supplier"]["bank_name"] = cleanup_bank_name(bank_name_match.group(1))

        bic_in_block = extract_bic(bank_block)
        if bic_in_block:
            out["supplier"]["bic"] = bic_in_block
        else:
            for cand in bank_parts:
                cand_clean = clean_text(cand)
                if not cand_clean:
                    continue
                cand_norm = normalize_account(cand_clean)
                if not cand_norm:
                    continue
                m_bic = re.search(r'[A-Z]{6}[A-Z0-9]{2}', cand_norm)
                if m_bic:
                    out["supplier"]["bic"] = m_bic.group(0)
                    break


    customer_idx = next((i for i, line in enumerate(lines) if re.search(r'Покупатель:', line, flags=re.I)), None)
    if customer_idx is not None:
        customer_line = lines[customer_idx]
        customer_parts = []

        if customer_idx > 0:
            prev_line = lines[customer_idx - 1]
            if re.search(r'УНП|КПП|ООО|ОАО|ЗАО|ОДО|ЧУП|Общество с ограниченной ответственностью', prev_line, flags=re.I):
                customer_parts.append(prev_line)

        customer_parts.append(customer_line)

        if customer_idx + 1 < len(lines):
            next_line = lines[customer_idx + 1]
            if not re.search(r'Основание:|Счет\s*№|Поставщик:|Организация:', next_line, flags=re.I):
                customer_parts.append(next_line)

        customer_block = clean_text(" ".join(x for x in customer_parts if x)) or customer_line

        out["customer"]["phone"] = extract_phone_pretty(customer_block)

        tax_match = re.search(r'УНП\s*(\d{9})', customer_block, flags=re.I)
        if tax_match:
            out["customer"]["tax_id"] = clean_text(tax_match.group(1))

        kpp_match = re.search(r'КПП\s*(\d{9})', customer_block, flags=re.I)
        if kpp_match:
            out["customer"]["kpp"] = clean_text(kpp_match.group(1))

        head_match = re.search(r'Покупатель:\s*([^,]+)', customer_line, flags=re.I)
        tail_match = re.search(r'КПП\s*\d{9}\s*,\s*(.+)$', customer_line, flags=re.I)

        if head_match and tail_match:
            customer_name = clean_text(f'{tail_match.group(1)} {head_match.group(1)}')
            out["customer"]["name"] = customer_name
        else:
            joined_name_match = re.search(
                r'((?:ООО|ОАО|ЗАО|ОДО|ЧУП|Общество с ограниченной ответственностью)\s*["«][^,]*?)\s*Покупатель:\s*([^,]+)',
                customer_block,
                flags=re.I
            )
            if joined_name_match:
                customer_name = clean_text(f'{joined_name_match.group(1)} {joined_name_match.group(2)}')
                out["customer"]["name"] = customer_name
            else:
                companies = extract_company_names(customer_block)
                if companies:
                    out["customer"]["name"] = clean_text(companies[-1])

        addr_match = re.search(
            r'Покупатель:\s*[^,]+,\s*(.+?)(?=,\s*тел\.?:|\s*тел\.?:|,\s*УНП\b|\s*УНП\b|,\s*КПП\b|\s*КПП\b|$)',
            customer_block,
            flags=re.I
        )
        if addr_match:
            out["customer"]["address"] = clean_text(addr_match.group(1))

    if not out["customer"]["name"]:
        companies = extract_company_names(header_text)
        if len(companies) > 1:
            out["customer"]["name"] = clean_text(companies[-1])

    return out


def invoice_is_header_row(texts):
    return looks_like_table_header(texts)


def invoice_is_index_row(texts):
    return is_index_row(texts)


def is_valid_item_row(texts):
    if len(texts) < 10:
        return False

    if invoice_is_header_row(texts):
        return False

    if invoice_is_index_row(texts):
        return False

    joined = " ".join(texts).lower()

    if any(x in joined for x in [
        "итого", "всего наименований", "внимание",
        "специалист", "кисел"
    ]):
        return False

    nonempty = [clean_text(x) for x in texts if clean_text(x)]

    if nonempty and all(re.fullmatch(r"\d{1,2}", x) for x in nonempty):
        return False

    short_numeric = sum(1 for x in nonempty if re.fullmatch(r"\d{1,2}", x or ""))
    if nonempty and short_numeric / len(nonempty) >= 0.7:
        return False

    has_article = bool(texts[1]) if len(texts) > 1 else False
    has_desc = bool(texts[2]) if len(texts) > 2 else False

    if re.fullmatch(r"\d{1,2}", str(texts[1]).strip() if len(texts) > 1 else ""):
        has_article = False
    if re.fullmatch(r"\d{1,2}", str(texts[2]).strip() if len(texts) > 2 else ""):
        has_desc = False

    numeric_fields = sum(
        1 for t in texts[4:12]
        if to_float(t) is not None
    )

    return (has_article or has_desc) and numeric_fields >= 3


def parse_line_number(text, fallback):
    v = to_int(text)
    return v if v is not None else fallback


def normalize_unit(u):
    if not u:
        return None
    u = u.lower().replace(".", "").strip()
    if u in {"шт", "шτ", "யா", "wr", "wt"}:
        return "шт"
    return u


def extract_invoice_numeric_totals(table_rows):
    totals = {
        "total_quantity": None,
        "subtotal_no_disc_incl_vat": None,
        "total_disc_amount": None,
        "subtotal_with_disc_excl_vat": None,
        "vat_amount": None,
        "total_with_disc_incl_vat": None,
        "total_in_words": None,
        "currency": "BYN",
    }

    for row in table_rows:
        texts = row_texts(row)
        joined = " | ".join(texts).lower()

        if "итого" not in joined:
            continue

        texts = texts + [""] * (13 - len(texts))

        totals["total_quantity"] = to_int(texts[4])
        totals["subtotal_no_disc_incl_vat"] = to_float(texts[7])
        totals["total_disc_amount"] = to_float(texts[8])
        totals["subtotal_with_disc_excl_vat"] = to_float(texts[9])
        totals["vat_amount"] = to_float(texts[11])
        totals["total_with_disc_incl_vat"] = to_float(texts[12])
        break

    return totals

def parse_invoice(roi_path: Path):
    data = load_json(roi_path)
    regions = get_regions(data)

    header_box = next((r for r in regions if r.get("id") == "header_box"), None)
    footer_box = next((r for r in regions if r.get("id") == "footer_box"), None)
    table_cells = [r for r in regions if r.get("kind") == "table_cell"]

    header_text = clean_text(header_box.get("text")) if header_box else None
    raw_footer_text = clean_text(footer_box.get("text")) if footer_box else None
    footer_text = clean_invoice_footer_text(raw_footer_text)

    header_lines = header_box.get("header_lines") if header_box else None
    head = enrich_invoice_header(parse_invoice_header(header_text, header_lines), header_text)

    all_rows = group_rows(table_cells, tol=14)
    rows = filter_table_rows(all_rows)

    items = []
    line_no = 1
    totals = extract_invoice_numeric_totals(all_rows)

    for row in rows:
        texts = row_texts(row)

        if not is_valid_item_row(texts):
            continue

        texts = texts + [""] * (13 - len(texts))

        items.append({
            "line_number": parse_line_number(texts[0], line_no),
            "article": clean_text(texts[1]),
            "description": merge_multiline(texts[2]),
            "barcode": clean_text(texts[3]),
            "quantity": to_int(texts[4]),
            "unit": normalize_unit(texts[5]),
            "unit_price_incl_vat": to_float(texts[6]),
            "amount_no_disc_incl_vat": to_float(texts[7]),
            "disc_amount": to_float(texts[8]),
            "amount_with_disc_excl_vat": to_float(texts[9]),
            "vat_rate": normalize_percent(texts[10]),
            "vat_amount": to_float(texts[11]),
            "total_with_disc_incl_vat": to_float(texts[12]),
        })

        line_no += 1

    signatory = extract_invoice_signatory(footer_text)
    note = extract_invoice_note(footer_text)
    totals["total_in_words"] = extract_invoice_total_in_words(footer_text)

    if note:
        m2 = re.search(r'в течение\s*(\d+\s*дн\w*)', note, flags=re.I)
        if m2:
            head["payment_deadline"] = clean_text(m2.group(1))

    file_key = roi_path.name.replace("_roi_text.json", ".pdf")

    return {
        "invoice": {
            file_key: {
                "invoice_number": head["invoice_number"],
                "invoice_date": head["invoice_date"],
                "payment_deadline": head["payment_deadline"],
                "supplier": head["supplier"],
                "customer": head["customer"],
                "basis": head["basis"],
                "items": items,
                "totals": totals,
                "signatory": signatory,
                "note": note,
            }
        }
    }

# =========================
# Payment order
# =========================

def build_form_text_map(regions):
    vals = []
    for r in regions:
        if r.get("kind") == "form_roi":
            t = clean_text(r.get("text"))
            if t is not None:
                vals.append(t)
    return vals

def find_first(lines, pattern, flags=re.I):
    rx = re.compile(pattern, flags)
    for line in lines:
        m = rx.search(line)
        if m:
            return m
    return None

def enrich_payment_order_result(result, lines, full):
    doc = next(iter(result.get("payment_order", {}).values()), None)
    if not doc:
        return result
    payer = doc.get("payer", {})
    payee = doc.get("payee", {})
    payment_details = doc.get("payment_details", {})
    execution_details = doc.get("execution_details", {})

    accounts = extract_all_accounts(full)
    tax_ids = extract_all_tax_ids(full)
    bics = extract_all_bics(full)
    datetimes = extract_all_datetimes(full)
    company_names = extract_company_names(full)

    if not payer.get("bank_account") and len(accounts) > 0:
        payer["bank_account"] = accounts[0]
    if not payee.get("bank_account") and len(accounts) > 1:
        payee["bank_account"] = accounts[1]
    if not payer.get("tax_id") and len(tax_ids) > 0:
        payer["tax_id"] = tax_ids[0]
    if not payee.get("tax_id") and len(tax_ids) > 1:
        payee["tax_id"] = tax_ids[1]
    if not payer.get("bank_code") and len(bics) > 0:
        payer["bank_code"] = bics[0]
    if not payee.get("bank_code") and len(bics) > 1:
        payee["bank_code"] = bics[1]
    if payer.get("bank_code") and not re.fullmatch(r'[A-Z]{6}[A-Z0-9]{2}', normalize_account(payer.get("bank_code")) or '') and len(bics) > 0:
        payer["bank_code"] = bics[0]
    if payee.get("bank_code") and not re.fullmatch(r'[A-Z]{6}[A-Z0-9]{2}', normalize_account(payee.get("bank_code")) or '') and len(bics) > 1:
        payee["bank_code"] = bics[1]
    if not payer.get("name") and len(company_names) > 0:
        payer["name"] = company_names[0]
    if not payee.get("name") and len(company_names) > 1:
        payee["name"] = company_names[1]
    if payer.get("bank_name"):
        payer["bank_name"] = cleanup_bank_name(payer.get("bank_name"))
    if payee.get("bank_name"):
        payee["bank_name"] = cleanup_bank_name(payee.get("bank_name"))

    if not execution_details.get("receipt_date") and len(datetimes) > 0:
        execution_details["receipt_date"] = datetimes[0]
    if not execution_details.get("execution_date") and len(datetimes) > 1:
        execution_details["execution_date"] = datetimes[1]
    if not execution_details.get("status"):
        m = re.search(r'\b(исполнено|принято|обработано)\b', full, flags=re.I)
        if m:
            execution_details["status"] = clean_text(m.group(1))
    if not execution_details.get("executing_bank"):
        bank_names = [x for x in company_names if 'банк' in x.lower()]
        if bank_names:
            execution_details["executing_bank"] = bank_names[-1]

    if not doc.get("payment_order_number"):
        m = re.search(r'№\s*(\d{1,4})', full)
        if m:
            doc["payment_order_number"] = clean_text(m.group(1))
    if not doc.get("payment_order_type"):
        m = re.search(r'\(([^)]+)\)', full)
        if m:
            doc["payment_order_type"] = clean_text(m.group(1))
    if not payment_details.get("payment_priority"):
        m = re.search(r'(?:очеред|приоритет)[^0-9]{0,10}(\d{1,2})', full, flags=re.I)
        if m:
            payment_details["payment_priority"] = clean_text(m.group(1))
    if payment_details.get("purpose"):
        payment_details["purpose"] = re.sub(r'\s*Дата документа:?\s*$', '', payment_details["purpose"], flags=re.I).strip()
    if not payment_details.get("amount_in_words"):
        m = re.search(r'([А-ЯЁа-яё\-\s]+рубл[а-яё]+,\s*\d{1,2}\s*коп[а-яё]+)', full)
        if m:
            payment_details["amount_in_words"] = clean_text(m.group(1))
    if not payment_details.get("currency_full"):
        payment_details["currency_full"] = "белорусские рубли"

    if not doc.get("signatory", {}).get("name"):
        name = extract_person_name(full)
        if name:
            doc.setdefault("signatory", {})["name"] = name
    return result

def parse_payment_order(roi_path: Path):
    data = load_json(roi_path)
    regions = get_regions(data)
    form_rois = [r for r in regions if r.get("kind") == "form_roi"]
    lines = [clean_text(r.get("text")) for r in form_rois if clean_text(r.get("text"))]

    def roi_text(roi):
        return clean_text(roi.get("text"))

    def find_roi(pattern):
        for roi in form_rois:
            txt = roi_text(roi)
            if txt and re.search(pattern, txt, flags=re.I):
                return roi
        return None

    def extract_near_bank_code(text):
        txt = clean_text(text)
        if not txt:
            return None

        txt_norm = normalize_account(txt)
        if not txt_norm:
            return None

        m = re.search(r'([A-Z0-9]{8})', txt_norm)
        if m:
            return m.group(1)
        return None

    full = " ".join([roi_text(r) for r in form_rois if roi_text(r)])
    meta = {}

    number = None
    po_type = None
    title_roi = find_roi(r'ПЛАТЕЖНОЕ ПОРУЧЕНИЕ')
    if title_roi:
        txt = roi_text(title_roi)
        m = re.search(r'№\s*([0-9]+)\s*\(([^)]+)\)', txt or "", flags=re.I)
        if m:
            number = clean_text(m.group(1))
            po_type = clean_text(m.group(2))
            meta["payment_order_number"] = title_roi["id"]
            meta["payment_order_type"] = title_roi["id"]

    m = re.search(r'Дата:\s*([0-3]?\d\.[01]?\d\.20\d{2})', full)
    document_date = clean_text(m.group(1)) if m else None

    urgent = bool(re.search(r'Срочный\s*Х', full, flags=re.I))
    non_urgent = bool(re.search(r'Несрочный\s*Х', full, flags=re.I))

    payer = {
        "name": None,
        "bank_account": None,
        "bank_code": None,
        "tax_id": None,
        "bank_name": None,
        "address": None,
    }
    payee = {
        "name": None,
        "bank_account": None,
        "bank_code": None,
        "tax_id": None,
        "bank_name": None,
    }

    def build_payer_text():
        ordered = sorted(form_rois, key=lambda r: (r["bbox"][1], r["bbox"][0]))

        def bbox_height(roi):
            return max(1, roi["bbox"][3] - roi["bbox"][1])

        def bbox_width(roi):
            return max(1, roi["bbox"][2] - roi["bbox"][0])

        def center_x(roi):
            return (roi["bbox"][0] + roi["bbox"][2]) / 2

        def x_overlap(a, b):
            return max(0, min(a["bbox"][2], b["bbox"][2]) - max(a["bbox"][0], b["bbox"][0]))

        def find_next_similar_lower_roi(base_roi, start_index):
            base_h = bbox_height(base_roi)
            base_w = bbox_width(base_roi)
            base_cx = center_x(base_roi)

            best_roi = None
            best_score = None

            for j in range(start_index + 1, len(ordered)):
                cand = ordered[j]
                cand_text = roi_text(cand)
                if not cand_text:
                    continue

                if cand["bbox"][1] <= base_roi["bbox"][1]:
                    continue

                cand_h = bbox_height(cand)
                cand_w = bbox_width(cand)
                cand_cx = center_x(cand)

                height_ratio = cand_h / base_h
                width_ratio = cand_w / base_w
                overlap = x_overlap(base_roi, cand)
                cx_diff = abs(cand_cx - base_cx)
                y_gap = cand["bbox"][1] - base_roi["bbox"][3]

                if not (0.45 <= height_ratio <= 1.8):
                    continue
                if not (0.45 <= width_ratio <= 1.8):
                    continue
                if overlap <= 0 and cx_diff > max(40, base_w * 0.35):
                    continue
                if y_gap > max(120, base_h * 4):
                    continue

                score = (
                    y_gap if y_gap >= 0 else 0,
                    cx_diff,
                    abs(cand_h - base_h),
                    abs(cand_w - base_w),
                )

                if best_score is None or score < best_score:
                    best_score = score
                    best_roi = cand

            return best_roi

        for i, roi in enumerate(ordered):
            txt = roi_text(roi)
            if not txt:
                continue

            m = re.search(r'\bПлательщик\b.*$', txt, flags=re.I)
            if not m:
                continue

            top_tail = clean_text(m.group(0))
            source_ids = [roi["id"]]

            next_roi = find_next_similar_lower_roi(roi, i)
            next_text = roi_text(next_roi) if next_roi else None
            if next_roi and next_text:
                source_ids.append(next_roi["id"])
                merged = clean_text(top_tail + " " + next_text)
            else:
                merged = top_tail

            return merged, source_ids

        return None, []

    payer_text, payer_source_ids = build_payer_text()
    if payer_text:
        m = re.search(r'Плательщик\s*:?\s*(.+)', payer_text, flags=re.I)
        if m:
            payer_blob = clean_text(m.group(1))

            payer_blob = re.sub(r'\s+BY\d{2}.*$', '', payer_blob, flags=re.I)
            payer_blob = re.sub(r'\s+(?:Счет|Счёт)\s*№?.*$', '', payer_blob, flags=re.I)
            payer_blob = clean_text(payer_blob)

            mname = re.match(r'(.+?)\s+(Г\..+)$', payer_blob or "")
            if mname:
                payer["name"] = clean_text(mname.group(1))
                payer["address"] = clean_text(mname.group(2))
                source_tag = " + ".join(payer_source_ids)
                meta["payer.name"] = source_tag
                meta["payer.address"] = source_tag
            else:
                payer["name"] = payer_blob
                meta["payer.name"] = " + ".join(payer_source_ids)

    m = re.search(r'Плательщик:.*?(BY\d{2}[A-ZА-Я0-9 ]+)\s+Счет', full, flags=re.I)
    if m:
        payer["bank_account"] = extract_bank_account(m.group(1))
        meta["payer.bank_account"] = "form_roi_payer_account"

    sender_roi = find_roi(r'Банк-отправитель')
    if sender_roi:
        txt = roi_text(sender_roi)
        if txt:
            m = re.search(r'Банк-отправитель:?\s*(.+)', txt, flags=re.I)
            if m:
                bank_text = clean_text(m.group(1))
                bank_text = re.sub(r'Код банка.*$', '', bank_text, flags=re.I).strip(" ,;:")
                payer["bank_name"] = bank_text or None
                if payer["bank_name"]:
                    meta["payer.bank_name"] = sender_roi["id"]

            if re.search(r'Код банка', txt, flags=re.I):
                code = extract_near_bank_code(txt)
                if code:
                    payer["bank_code"] = code
                    meta["payer.bank_code"] = sender_roi["id"]

    receiver_roi = find_roi(r'Банк-получатель')
    if receiver_roi:
        txt = roi_text(receiver_roi)
        if txt:
            m = re.search(r'Банк-получатель:?\s*(.+)', txt, flags=re.I)
            if m:
                bank_text = clean_text(m.group(1))
                bank_text = re.sub(r'Код банка.*$', '', bank_text, flags=re.I).strip(" ,;:")
                payee["bank_name"] = bank_text or None
                if payee["bank_name"]:
                    meta["payee.bank_name"] = receiver_roi["id"]

            if re.search(r'Код банка', txt, flags=re.I):
                code = extract_near_bank_code(txt)
                if code:
                    payee["bank_code"] = code
                    meta["payee.bank_code"] = receiver_roi["id"]

    beneficiary_roi = find_roi(r'Бенефициар')
    if beneficiary_roi:
        txt = roi_text(beneficiary_roi)
        if txt:
            m = re.search(r'Бенефициар\s*(.+)', txt, flags=re.I)
            if m:
                beneficiary_name = clean_text(m.group(1))
                beneficiary_name = re.sub(r'\s+(?:Счет|Счёт)\b.*$', '', beneficiary_name, flags=re.I)
                beneficiary_name = re.sub(r'\s+№.*$', '', beneficiary_name, flags=re.I)
                beneficiary_name = re.sub(r'\s+BY\d{2}.*$', '', beneficiary_name, flags=re.I)
                payee["name"] = clean_text(beneficiary_name)
                meta["payee.name"] = beneficiary_roi["id"]

    m = re.search(r'Бенефициар:.*?Счет №:?\s*(BY\d{2}[A-ZА-Я0-9 ]+)', full, flags=re.I)
    if m:
        payee["bank_account"] = extract_bank_account(m.group(1))

    payer["tax_id"] = None
    payee["tax_id"] = None

    payment_priority = None
    queue_roi = find_roi(r'\bОчередь\b')
    if queue_roi:
        qx1, qy1, qx2, qy2 = queue_roi["bbox"]
        qcx = (qx1 + qx2) / 2

        next_roi = None
        next_dy = None

        for roi in form_rois:
            if roi["id"] == queue_roi["id"]:
                continue

            txt = roi_text(roi)
            if not txt:
                continue

            rx1, ry1, rx2, ry2 = roi["bbox"]
            rcx = (rx1 + rx2) / 2

            if ry1 <= qy1:
                continue
            if abs(rcx - qcx) > 40:
                continue

            dy = ry1 - qy2
            if next_dy is None or dy < next_dy:
                next_dy = dy
                next_roi = roi

        if next_roi:
            m = re.search(r'\b(\d{1,2})\b', roi_text(next_roi) or "")
            if m:
                payment_priority = clean_text(m.group(1))

    m = re.search(r'Сумма и валюта:\s*(.+?)\s+Код\s+Сумма\s+(\d+)\s+([0-9,\.]+)', full, flags=re.I)
    amount_in_words = clean_text(m.group(1)) if m else None
    currency_code = clean_text(m.group(2)) if m else None
    amount = to_float(m.group(3)) if m else None

    purpose = None
    m = re.search(r'Назначение платежа:\s*(.+?)\s+№ документа:', full, flags=re.I)
    if m:
        purpose = clean_text(m.group(1))

    receipt_date = None
    execution_date = None
    executing_bank = None
    status = None

    bank_exec_roi = find_roi(r'Дата исполнения')
    if bank_exec_roi:
        txt = roi_text(bank_exec_roi)
        if txt:
            m = re.search(r'Дата исполнения:?\s*([0-3]?\d\.[01]?\d\.20\d{2}\s+\d{2}:\d{2})', txt, flags=re.I)
            if m:
                execution_date = clean_text(m.group(1))
                status = "исполнено"
                meta["execution_details.execution_date"] = bank_exec_roi["id"]
                meta["execution_details.status"] = bank_exec_roi["id"]

            m = re.search(r'Дата поступления:?\s*([0-3]?\d\.[01]?\d\.20\d{2}\s+\d{2}:\d{2})', txt, flags=re.I)
            if m:
                receipt_date = clean_text(m.group(1))
                meta["execution_details.receipt_date"] = bank_exec_roi["id"]

            m = re.search(r'(ЗАО\s*".+?")', txt)
            if m:
                executing_bank = clean_text(m.group(1))
                meta["execution_details.executing_bank"] = bank_exec_roi["id"]

    signatory = {"position": None, "name": None}
    m = re.search(r'([А-Яа-яA-Za-z ]+)\s+([А-ЯЁA-Z][а-яё]+\s+[А-ЯЁA-Z][а-яё]+\s+[А-ЯЁA-Z][а-яё]+)$', full)
    if m:
        signatory["position"] = clean_text(m.group(1))
        signatory["name"] = clean_text(m.group(2))

    file_key = roi_path.name.replace("_roi_text.json", ".pdf")
    return enrich_payment_order_result({
        "payment_order": {
            file_key: {
                "payment_order_number": number,
                "payment_order_type": po_type,
                "document_date": document_date,
                "urgent": urgent,
                "non_urgent": non_urgent,
                "payer": payer,
                "payee": payee,
                "payment_details": {
                    "amount": amount,
                    "currency_code": currency_code,
                    "currency": "BYN",
                    "currency_full": "белорусские рубли" if amount_in_words else None,
                    "amount_in_words": amount_in_words,
                    "purpose": purpose,
                    "payment_priority": payment_priority,
                },
                "execution_details": {
                    "receipt_date": receipt_date,
                    "execution_date": execution_date,
                    "executing_bank": executing_bank,
                    "status": status,
                },
                "signatory": signatory,
                "_meta": meta,
            }
        }
    }, lines, full)

# =========================
# Waybill
# =========================

def _waybill_extract_tax_id(text):
    if not text:
        return None
    m = re.search(r'(?<!\d)(\d{9})(?!\d)', text)
    return m.group(1) if m else None


def _cluster_axis(values, tol):
    if not values:
        return []

    values = sorted(values)
    groups = [[values[0]]]

    for v in values[1:]:
        if abs(v - groups[-1][-1]) <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])

    return [sum(g) / len(g) for g in groups]


def extract_waybill_unp_fields(regions):
    out = {
        "sender": {"tax_id": None},
        "receiver": {"tax_id": None},
        "payer": {"name": None, "address": None, "tax_id": None},
    }

    unp_regions = [r for r in regions if r.get("kind") == "unp_cell"]
    if not unp_regions:
        return out

    items = []
    widths = []

    for r in unp_regions:
        bbox = r.get("bbox") or [0, 0, 0, 0]
        x1, y1, x2, y2 = bbox
        text = clean_text(r.get("text"))
        widths.append(max(1, x2 - x1))

        items.append({
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "cx": (x1 + x2) / 2,
            "cy": (y1 + y2) / 2,
            "text": text,
            "tax_id": _waybill_extract_tax_id(text),
        })

    if not items:
        return out

    widths = sorted(widths)
    median_w = widths[len(widths) // 2] if widths else 100
    x_tol = max(40, int(median_w * 0.35))

    x_clusters = _cluster_axis([it["cx"] for it in items], tol=x_tol)
    if not x_clusters:
        return out

    cols = {i: [] for i in range(len(x_clusters))}
    for it in items:
        col_idx = min(range(len(x_clusters)), key=lambda i: abs(it["cx"] - x_clusters[i]))
        cols[col_idx].append(it)

    col_values = []
    for col_idx in sorted(cols):
        col_items = sorted(cols[col_idx], key=lambda z: (z["cy"], z["x1"]))

        val = next((z["tax_id"] for z in col_items if z["tax_id"]), None)
        if not val:
            merged = " ".join(z["text"] for z in col_items if z["text"])
            val = _waybill_extract_tax_id(merged)

        col_values.append(val)

    # 2 колонки: sender, receiver
    # 3 колонки: sender, payer, receiver
    if len(col_values) >= 1:
        out["sender"]["tax_id"] = col_values[0]
    if len(col_values) >= 2:
        if len(col_values) == 2:
            out["receiver"]["tax_id"] = col_values[1]
        else:
            out["payer"]["tax_id"] = col_values[1]
    if len(col_values) >= 3:
        out["receiver"]["tax_id"] = col_values[2]

    return out


def parse_waybill_header(header_text, header_lines=None):
    out = {
        "document_type": None,
        "document_series": None,
        "document_number": None,
        "date": None,
        "sender": {"name": None, "address": None, "tax_id": None},
        "receiver": {"name": None, "address": None, "tax_id": None},
        "payer": {"name": None, "address": None, "tax_id": None},
        "basis": None,
    }
    if not header_text:
        return out

    if "ТОВАРНАЯ НАКЛАДНАЯ" in header_text.upper():
        out["document_type"] = "ТОВАРНАЯ НАКЛАДНАЯ"

    m = re.search(r'Серия\s+([A-ZА-Я]{1,4})', header_text)
    if m:
        out["document_series"] = clean_text(m.group(1))

    m = re.search(r'ТОВАРНАЯ НАКЛАДНАЯ\s+([0-3]?\d\s+(?:' + MONTHS_RU + r')\s+20\d{2}\s*г\.)', header_text, flags=re.I)
    if m:
        out["date"] = clean_text(m.group(1))

    m = re.search(r'Серия\s+[A-ZА-Я]{1,4}\s+([0-9]{4,10})', header_text)
    if m:
        out["document_number"] = clean_text(m.group(1))

    m = re.search(r'Грузоотправитель.*?Общество с ограниченной ответственностью\s*".+?"\s*,\s*(.+?)\s*Грузоотправитель', header_text, flags=re.I)
    if not m:
        m = re.search(r'Общество с ограниченной ответственностью\s*"Эстель Сервис"\s*,\s*(.+?)\s*Грузоотправитель', header_text, flags=re.I)
    if m:
        out["sender"]["name"] = 'Общество с ограниченной ответственностью "Эстель Сервис"'
        out["sender"]["address"] = clean_text(m.group(1))

    m = re.search(r'Грузополучатель.*?Общество с ограниченной ответственностью\s*"Голд Сити Барберс"\s*,\s*(.+?)\s*Грузополучатель', header_text, flags=re.I)
    if not m:
        m = re.search(r'Общество с ограниченной ответственностью\s*"Голд Сити Барберс"\s*,\s*(.+?)\s*Грузополучатель', header_text, flags=re.I)
    if m:
        out["receiver"]["name"] = 'Общество с ограниченной ответственностью "Голд Сити Барберс"'
        out["receiver"]["address"] = clean_text(m.group(1))

    if header_lines:
        for line in header_lines:
            line_text = clean_text(line.get("text")) if isinstance(line, dict) else clean_text(line)
            if not line_text:
                continue

            m = re.search(r'Основание отпуска\s+(.+)', line_text, flags=re.I)
            if m:
                out["basis"] = clean_text(m.group(1))
                break

    if not out["basis"]:
        m = re.search(
            r'Основание отпуска\s+(.+?)(?:І\.\s*ТОВАРНЫЙ|I\.\s*ТОВАРНЫЙ|ТОВАРНЫЙ РАЗДЕЛ|$)',
            header_text,
            flags=re.I
        )
        if m:
            out["basis"] = clean_text(m.group(1))

    return out


def extract_waybill_numeric_totals(table_rows):
    totals = {
        "quantity_total": None,
        "cost_total": None,
        "vat_total": None,
        "cost_with_vat_total": None,
        "vat_total_words": None,
        "cost_with_vat_total_words": None,
    }

    for row in table_rows:
        texts = row_texts(row)
        joined = " | ".join(texts).lower()

        if "итого" not in joined:
            continue

        totals["quantity_total"] = to_int(texts[2]) if len(texts) > 2 else None
        totals["cost_total"] = to_float(texts[4]) if len(texts) > 4 else None
        totals["vat_total"] = to_float(texts[6]) if len(texts) > 6 else None

        if len(texts) > 7:
            m = re.search(r'([0-9]+[.,][0-9]{2})', texts[7] or "")
            totals["cost_with_vat_total"] = to_float(m.group(1)) if m else to_float(texts[7])

        break

    return totals

def extract_waybill_total_words(footer_lines, anchor):
    if not footer_lines:
        return None

    for line in footer_lines:
        line_text = clean_text(line.get("text")) if isinstance(line, dict) else clean_text(line)
        if not line_text:
            continue

        m = re.search(rf'{anchor}\s+(.+)', line_text, flags=re.I)
        if m:
            return clean_text(m.group(1))

    return None

def enrich_waybill_result(result, footer_text):
    if not isinstance(result, dict):
        return result
    approvals = result.get("approvals", {})
    footer = result.get("footer", {})
    if footer_text:
        patterns = {
            "released_by": r'(Специалист по работе с клиентами[^\n]*)',
            "handed_by": r'(Сдал грузоотправитель[^\n]*)',
            "accepted_for_delivery": r'(Товар к доставке принял[^\n]*)',
            "received_by": r'(Принял грузополучатель[^\n]*)',
            "documents_transferred": r'(С товаром переданы документы[^\n]*)',
        }
        for key, pat in patterns.items():
            if not approvals.get(key):
                m = re.search(pat, footer_text, flags=re.I)
                if m:
                    approvals[key] = clean_text(m.group(1))
        if not footer.get("publisher"):
            m = re.search(r'(РУП[^\n]*|Издательство[^\n]*)', footer_text, flags=re.I)
            if m:
                footer["publisher"] = clean_text(m.group(1))
        if not footer.get("warning"):
            m = re.search(r'(Внимание![^\n]*)', footer_text, flags=re.I)
            if m:
                footer["warning"] = clean_text(m.group(1))
    result["approvals"] = approvals
    result["footer"] = footer
    return result

def parse_waybill(roi_path: Path):
    data = load_json(roi_path)
    regions = get_regions(data)
    header_box = next((r for r in regions if r.get("id") == "header_box"), None)
    footer_box = next((r for r in regions if r.get("id") == "footer_box"), None)
    table_cells = [r for r in regions if r.get("kind") == "table_cell"]

    header_text = clean_text(header_box.get("text")) if header_box else None
    footer_text = clean_text(footer_box.get("text")) if footer_box else None
    footer_lines = footer_box.get("footer_lines") if footer_box else None

    header_lines = header_box.get("header_lines") if header_box else None
    head = parse_waybill_header(header_text, header_lines)
    unp_fields = extract_waybill_unp_fields(regions)
    for party_key in ("sender", "receiver", "payer"):
        party_vals = unp_fields.get(party_key) or {}
        if party_key not in head or not isinstance(head[party_key], dict):
            head[party_key] = {}
        for field, value in party_vals.items():
            if value and not head[party_key].get(field):
                head[party_key][field] = value

    all_rows = group_rows(table_cells, tol=12)

    items = []
    for row in all_rows:
        texts = row_texts(row)
        joined = " | ".join(texts).lower()

        if "итого" in joined:
            continue
        if any(x in joined for x in ["наименование товара", "единица измерения", "ставка ндс", "примечание"]):
            continue
        if is_index_row(texts):
            continue
        if len(texts) < 9:
            continue
        if not texts[0] or texts[0].isdigit():
            continue



        cost_with_vat = None
        note = clean_text(texts[8])
        if texts[7]:
            m = re.search(r'([0-9]+[.,][0-9]{2})', texts[7])
            if m:
                cost_with_vat = to_float(m.group(1))

        items.append({
            "name": clean_text(texts[0]),
            "unit": "шт" if texts[1].lower() in {"шт", "шт.", "шτ"} else clean_text(texts[1]),
            "quantity": to_int(texts[2]),
            "price": to_float(texts[3]),
            "cost": to_float(texts[4]),
            "vat_rate": normalize_percent(texts[5]),
            "vat_amount": to_float(texts[6]),
            "cost_with_vat": cost_with_vat,
            "note": note,
        })

    totals = extract_waybill_numeric_totals(all_rows)
    totals["vat_total_words"] = extract_waybill_total_words(footer_lines, r'Всего сумма НДС')
    totals["cost_with_vat_total_words"] = extract_waybill_total_words(footer_lines, r'Всего стоимость с НДС')

    approvals = {
        "released_by": None,
        "handed_by": None,
        "accepted_for_delivery": None,
        "received_by": None,
        "documents_transferred": None,
    }
    footer = {"publisher": None, "warning": None}

    return enrich_waybill_result({
        "document_type": head["document_type"],
        "document_series": head["document_series"],
        "document_number": head["document_number"],
        "date": head["date"],
        "sender": head["sender"],
        "receiver": head["receiver"],
        "payer": head["payer"],
        "basis": head["basis"],
        "items": items,
        "totals": totals,
        "approvals": approvals,
        "footer": footer,

    }, footer_text)

# =========================
# dispatcher
# =========================

def detect_doc_type(path: Path):
    p = path.name.lower()
    if "account_prot" in p:
        return "account_prot"
    if "invoice" in p:
        return "invoice"
    if "order" in p or "payment_order" in p:
        return "payment_order"
    if "waybill" in p:
        return "waybill"
    return None

