import copy
import re

VISUAL_QUOTES_REPLACEMENTS = []


def clean_spaces(s: str) -> str:
    s = str(s).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_generic_text(value):
    if value is None:
        return None

    s = clean_spaces(value)
    if not s:
        return None

    for src, dst in VISUAL_QUOTES_REPLACEMENTS:
        s = s.replace(src, dst)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    s = re.sub(r"([,.;:])(\S)", r"\1 \2", s)
    s = re.sub(r"\s+", " ", s).strip(" ,.;:")
    return s or None


def normalize_money_words_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    s = re.sub(r"\bР С”Р С•Р С—Р ВµР в„–Р С”\b", "Р С”Р С•Р С—Р ВµР в„–Р С”Р С‘", s, flags=re.I)
    s = re.sub(r"(?<=\d)\s*РЎР‚РЎС“Р В±\b\.?", " РЎР‚РЎС“Р В±.", s, flags=re.I)
    s = re.sub(r"(?<=\d)\s*Р С”Р С•Р С—\b\.?", " Р С”Р С•Р С—.", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" ,.;:")
    return s or None


def reconcile_document_amounts(doc_type, payload, tol=0.02):
    """
    doc_type: "invoice" | "waybill" | "account_prot"
    payload: РІРЅСѓС‚СЂРµРЅРЅРёР№ dict РґРѕРєСѓРјРµРЅС‚Р°, РіРґРµ РµСЃС‚СЊ items / totals

    РќРёС‡РµРіРѕ РЅРµ РїРµСЂРµР·Р°РїРёСЃС‹РІР°РµС‚, РµСЃР»Рё Р·РЅР°С‡РµРЅРёРµ СѓР¶Рµ РёР·РІР»РµС‡РµРЅРѕ.
    Р’РѕСЃСЃС‚Р°РЅР°РІР»РёРІР°РµС‚ С‚РѕР»СЊРєРѕ РїСѓСЃС‚С‹Рµ numeric-РїРѕР»СЏ.
    РњРѕР¶РµС‚ РёСЃРїСЂР°РІР»СЏС‚СЊ СѓР¶Рµ РёР·РІР»РµС‡С‘РЅРЅРѕРµ С‡РёСЃР»Рѕ С‚РѕР»СЊРєРѕ РµСЃР»Рё:
    - РµСЃС‚СЊ РјРёРЅРёРјСѓРј 2 РЅРµР·Р°РІРёСЃРёРјС‹Рµ СЃРѕРІРјРµСЃС‚РёРјС‹Рµ РѕРїРѕСЂС‹
    - РѕРїРѕСЂС‹ СЃРѕРіР»Р°СЃРѕРІР°РЅС‹ РјРµР¶РґСѓ СЃРѕР±РѕР№
    - С‚РµРєСѓС‰РµРµ Р·РЅР°С‡РµРЅРёРµ РїРѕС…РѕР¶Рµ РЅР° С‚РёРїРёС‡РЅСѓСЋ OCR-РѕС€РёР±РєСѓ РјР°СЃС€С‚Р°Р±Р° (46.50 -> 4650)
    """

    def is_missing(v):
        if v is None:
            return True
        if isinstance(v, str) and not v.strip():
            return True
        return False

    def as_num(v):
        if is_missing(v):
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(",", ".")
        s = re.sub(r"[^\d.\-%\-]", "", s)
        if not s:
            return None
        try:
            if s.endswith("%"):
                return float(s[:-1])
            return float(s)
        except:
            return None

    def as_rate(v):
        x = as_num(v)
        if x is None:
            return None
        return x / 100.0 if x > 1 else x

    def norm_num(v):
        if v is None:
            return None
        x = round(float(v), 2)
        return int(x) if x.is_integer() else x

    def close_enough(a, b):
        a = as_num(a)
        b = as_num(b)
        if a is None or b is None:
            return False
        return abs(a - b) <= tol

    def rubles_part(v):
        x = as_num(v)
        if x is None:
            return None
        return int(x)

    def non_negative(v):
        x = as_num(v)
        return x is not None and x >= 0

    def set_missing_numeric(obj, field, value, source, scope, row_idx=None):
        if value is None:
            return
        if not is_missing(obj.get(field)):
            return
        obj[field] = norm_num(value)
        record = {
            "scope": scope,
            "field": field,
            "value": obj[field],
            "source": source,
            "kind": "derived",
        }
        if row_idx is not None:
            record["row_index"] = row_idx
        changes.append(record)

    def set_corrected_numeric(obj, field, old_value, new_value, source, scope, row_idx=None, support_count=None):
        if new_value is None:
            return
        obj[field] = norm_num(new_value)
        record = {
            "scope": scope,
            "field": field,
            "value": obj[field],
            "previous_value": norm_num(old_value),
            "source": source,
            "kind": "corrected",
        }
        if support_count is not None:
            record["support_count"] = support_count
        if row_idx is not None:
            record["row_index"] = row_idx
        changes.append(record)

    def add_warning(field, extracted, derived, scope, row_idx=None, source=None):
        record = {
            "scope": scope,
            "field": field,
            "extracted": extracted,
            "derived": norm_num(derived),
        }
        if source:
            record["source"] = source
        if row_idx is not None:
            record["row_index"] = row_idx
        warnings.append(record)

    def sum_item_field(items, field):
        vals = [as_num(x.get(field)) for x in items if isinstance(x, dict)]
        vals = [v for v in vals if v is not None]
        if not vals:
            return None
        return norm_num(sum(vals))

    def consensus_from_supports(supports, min_count=2):
        good = []
        for label, value in supports:
            num = as_num(value)
            if num is None:
                continue
            good.append((label, num))

        if len(good) < min_count:
            return None, []

        best_value = None
        best_labels = []

        for i, (label_i, value_i) in enumerate(good):
            labels = [label_i]
            values = [value_i]

            for j, (label_j, value_j) in enumerate(good):
                if i == j:
                    continue
                if close_enough(value_i, value_j):
                    labels.append(label_j)
                    values.append(value_j)

            uniq_labels = []
            for lbl in labels:
                if lbl not in uniq_labels:
                    uniq_labels.append(lbl)

            if len(uniq_labels) >= min_count and len(uniq_labels) > len(best_labels):
                best_labels = uniq_labels
                best_value = sum(values) / len(values)

        if len(best_labels) < min_count:
            return None, []

        return norm_num(best_value), best_labels

    def looks_like_decimal_shift(raw_value, target_value):
        raw = as_num(raw_value)
        target = as_num(target_value)
        if raw is None or target is None:
            return False
        if close_enough(raw, target):
            return False

        for factor in (10, 100, 1000):
            if close_enough(raw / factor, target):
                return True
            if close_enough(raw * factor, target):
                return True

        return False

    def try_correct_numeric(obj, field, supports, scope, row_idx=None):
        current = as_num(obj.get(field))
        if current is None:
            return False

        target, labels = consensus_from_supports(supports, min_count=2)
        if target is None:
            return False

        if close_enough(current, target):
            return False

        if not looks_like_decimal_shift(current, target):
            return False

        set_corrected_numeric(
            obj,
            field,
            current,
            target,
            " & ".join(labels),
            scope,
            row_idx=row_idx,
            support_count=len(labels),
        )
        return True

    def parse_ru_number_words(text):
        if not text:
            return None

        units = {
            "РЅРѕР»СЊ": 0,
            "РѕРґРёРЅ": 1, "РѕРґРЅР°": 1, "РѕРґРЅРѕ": 1,
            "РґРІР°": 2, "РґРІРµ": 2,
            "С‚СЂРё": 3,
            "С‡РµС‚С‹СЂРµ": 4,
            "РїСЏС‚СЊ": 5,
            "С€РµСЃС‚СЊ": 6,
            "СЃРµРјСЊ": 7,
            "РІРѕСЃРµРјСЊ": 8,
            "РґРµРІСЏС‚СЊ": 9,
        }
        teens = {
            "РґРµСЃСЏС‚СЊ": 10,
            "РѕРґРёРЅРЅР°РґС†Р°С‚СЊ": 11,
            "РґРІРµРЅР°РґС†Р°С‚СЊ": 12,
            "С‚СЂРёРЅР°РґС†Р°С‚СЊ": 13,
            "С‡РµС‚С‹СЂРЅР°РґС†Р°С‚СЊ": 14,
            "РїСЏС‚РЅР°РґС†Р°С‚СЊ": 15,
            "С€РµСЃС‚РЅР°РґС†Р°С‚СЊ": 16,
            "СЃРµРјРЅР°РґС†Р°С‚СЊ": 17,
            "РІРѕСЃРµРјРЅР°РґС†Р°С‚СЊ": 18,
            "РґРµРІСЏС‚РЅР°РґС†Р°С‚СЊ": 19,
        }
        tens = {
            "РґРІР°РґС†Р°С‚СЊ": 20,
            "С‚СЂРёРґС†Р°С‚СЊ": 30,
            "СЃРѕСЂРѕРє": 40,
            "РїСЏС‚СЊРґРµСЃСЏС‚": 50,
            "С€РµСЃС‚СЊРґРµСЃСЏС‚": 60,
            "СЃРµРјСЊРґРµСЃСЏС‚": 70,
            "РІРѕСЃРµРјСЊРґРµСЃСЏС‚": 80,
            "РґРµРІСЏРЅРѕСЃС‚Рѕ": 90,
        }
        hundreds = {
            "СЃС‚Рѕ": 100,
            "РґРІРµСЃС‚Рё": 200,
            "С‚СЂРёСЃС‚Р°": 300,
            "С‡РµС‚С‹СЂРµСЃС‚Р°": 400,
            "РїСЏС‚СЊСЃРѕС‚": 500,
            "С€РµСЃС‚СЊСЃРѕС‚": 600,
            "СЃРµРјСЊСЃРѕС‚": 700,
            "РІРѕСЃРµРјСЊСЃРѕС‚": 800,
            "РґРµРІСЏС‚СЊСЃРѕС‚": 900,
        }
        scales = {
            "С‚С‹СЃСЏС‡Р°": 1000, "С‚С‹СЃСЏС‡Рё": 1000, "С‚С‹СЃСЏС‡": 1000,
            "РјРёР»Р»РёРѕРЅ": 1000000, "РјРёР»Р»РёРѕРЅР°": 1000000, "РјРёР»Р»РёРѕРЅРѕРІ": 1000000,
            "РјРёР»Р»РёР°СЂРґ": 1000000000, "РјРёР»Р»РёР°СЂРґР°": 1000000000, "РјРёР»Р»РёР°СЂРґРѕРІ": 1000000000,
        }

        s = str(text).lower().replace("С‘", "Рµ").replace("-", " ")
        tokens = re.findall(r"[Р°-СЏ]+", s)

        if not tokens:
            return None

        total = 0
        group = 0
        seen = False

        for token in tokens:
            if token in hundreds:
                group += hundreds[token]
                seen = True
            elif token in teens:
                group += teens[token]
                seen = True
            elif token in tens:
                group += tens[token]
                seen = True
            elif token in units:
                group += units[token]
                seen = True
            elif token in scales:
                mul = scales[token]
                if group == 0:
                    group = 1
                total += group * mul
                group = 0
                seen = True

        total += group
        return total if seen else None

    def parse_money_words_amount(value):
        s = normalize_money_words_text(value) or normalize_generic_text(value)
        if not s:
            return None

        s_low = s.lower().replace("С‘", "Рµ")

        start_match = re.search(
            r"(РЅРѕР»СЊ|РѕРґРёРЅ|РѕРґРЅР°|РѕРґРЅРѕ|РґРІР°|РґРІРµ|С‚СЂРё|С‡РµС‚С‹СЂРµ|РїСЏС‚СЊ|С€РµСЃС‚СЊ|СЃРµРјСЊ|РІРѕСЃРµРјСЊ|РґРµРІСЏС‚СЊ|"
            r"РґРµСЃСЏС‚СЊ|РѕРґРёРЅРЅР°РґС†Р°С‚СЊ|РґРІРµРЅР°РґС†Р°С‚СЊ|С‚СЂРёРЅР°РґС†Р°С‚СЊ|С‡РµС‚С‹СЂРЅР°РґС†Р°С‚СЊ|РїСЏС‚РЅР°РґС†Р°С‚СЊ|"
            r"С€РµСЃС‚РЅР°РґС†Р°С‚СЊ|СЃРµРјРЅР°РґС†Р°С‚СЊ|РІРѕСЃРµРјРЅР°РґС†Р°С‚СЊ|РґРµРІСЏС‚РЅР°РґС†Р°С‚СЊ|РґРІР°РґС†Р°С‚СЊ|С‚СЂРёРґС†Р°С‚СЊ|"
            r"СЃРѕСЂРѕРє|РїСЏС‚СЊРґРµСЃСЏС‚|С€РµСЃС‚СЊРґРµСЃСЏС‚|СЃРµРјСЊРґРµСЃСЏС‚|РІРѕСЃРµРјСЊРґРµСЃСЏС‚|РґРµРІСЏРЅРѕСЃС‚Рѕ|СЃС‚Рѕ|РґРІРµСЃС‚Рё|"
            r"С‚СЂРёСЃС‚Р°|С‡РµС‚С‹СЂРµСЃС‚Р°|РїСЏС‚СЊСЃРѕС‚|С€РµСЃС‚СЊСЃРѕС‚|СЃРµРјСЊСЃРѕС‚|РІРѕСЃРµРјСЊСЃРѕС‚|РґРµРІСЏС‚СЊСЃРѕС‚)",
            s_low,
            flags=re.I,
        )
        if start_match:
            s = s[start_match.start():]
            s_low = s.lower().replace("С‘", "Рµ")

        kop_match = re.search(r"(\d{1,2})\s*РєРѕРї(?:\.|Рµ[Р№Рµ]Рє|РµР№РєРё|РµРµРє)?", s_low, flags=re.I)
        kop = int(kop_match.group(1)) if kop_match else 0

        rub_match = re.search(r"(.+?)\s+(?:Р±РµР»РѕСЂСѓСЃСЃРєРёС…\s+)?СЂСѓР±Р»[СЏРµР№]", s_low, flags=re.I)
        rub_text = rub_match.group(1) if rub_match else s_low

        rubles = parse_ru_number_words(rub_text)
        if rubles is None:
            return None

        if kop < 0 or kop > 99:
            kop = 0

        return norm_num(rubles + kop / 100.0)

    items = payload.get("items")
    totals = payload.get("totals")

    changes = []
    warnings = []

    if not isinstance(items, list):
        items = []
    if not isinstance(totals, dict):
        totals = {}
        payload["totals"] = totals

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        if doc_type == "invoice":
            q = as_num(item.get("quantity"))
            unit_price_incl_vat = as_num(item.get("unit_price_incl_vat"))
            amount_no_disc_incl_vat = as_num(item.get("amount_no_disc_incl_vat"))
            disc_amount = as_num(item.get("disc_amount"))
            amount_with_disc_excl_vat = as_num(item.get("amount_with_disc_excl_vat"))
            vat_amount = as_num(item.get("vat_amount"))
            total_with_disc_incl_vat = as_num(item.get("total_with_disc_incl_vat"))

            try_correct_numeric(
                item,
                "total_with_disc_incl_vat",
                [
                    ("amount_with_disc_excl_vat + vat_amount",
                     (amount_with_disc_excl_vat + vat_amount)
                     if non_negative(amount_with_disc_excl_vat) and non_negative(vat_amount) else None),
                    ("quantity * unit_price_incl_vat (discount blank/0)",
                     (q * unit_price_incl_vat)
                     if non_negative(q) and non_negative(unit_price_incl_vat) and (disc_amount is None or close_enough(disc_amount, 0))
                     else None),
                ],
                "item",
                idx,
            )

            q = as_num(item.get("quantity"))
            unit_price_incl_vat = as_num(item.get("unit_price_incl_vat"))
            amount_no_disc_incl_vat = as_num(item.get("amount_no_disc_incl_vat"))
            disc_amount = as_num(item.get("disc_amount"))
            amount_with_disc_excl_vat = as_num(item.get("amount_with_disc_excl_vat"))
            vat_amount = as_num(item.get("vat_amount"))
            total_with_disc_incl_vat = as_num(item.get("total_with_disc_incl_vat"))

            if amount_no_disc_incl_vat is None and non_negative(q) and non_negative(unit_price_incl_vat):
                amount_no_disc_incl_vat = q * unit_price_incl_vat
                set_missing_numeric(
                    item,
                    "amount_no_disc_incl_vat",
                    amount_no_disc_incl_vat,
                    "quantity * unit_price_incl_vat",
                    "item",
                    idx,
                )

            if (
                vat_amount is None
                and total_with_disc_incl_vat is not None
                and amount_with_disc_excl_vat is not None
                and total_with_disc_incl_vat >= amount_with_disc_excl_vat >= 0
            ):
                vat_amount = total_with_disc_incl_vat - amount_with_disc_excl_vat
                set_missing_numeric(
                    item,
                    "vat_amount",
                    vat_amount,
                    "total_with_disc_incl_vat - amount_with_disc_excl_vat",
                    "item",
                    idx,
                )

            if total_with_disc_incl_vat is None and non_negative(amount_with_disc_excl_vat) and non_negative(vat_amount):
                total_with_disc_incl_vat = amount_with_disc_excl_vat + vat_amount
                set_missing_numeric(
                    item,
                    "total_with_disc_incl_vat",
                    total_with_disc_incl_vat,
                    "amount_with_disc_excl_vat + vat_amount",
                    "item",
                    idx,
                )

        elif doc_type == "waybill":
            q = as_num(item.get("quantity"))
            price = as_num(item.get("price"))
            cost = as_num(item.get("cost"))
            vat_amount = as_num(item.get("vat_amount"))
            cost_with_vat = as_num(item.get("cost_with_vat"))
            vat_rate = as_rate(item.get("vat_rate"))

            try_correct_numeric(
                item,
                "cost",
                [
                    ("quantity * price", (q * price) if non_negative(q) and non_negative(price) else None),
                    ("cost_with_vat - vat_amount",
                     (cost_with_vat - vat_amount)
                     if cost_with_vat is not None and vat_amount is not None and cost_with_vat >= vat_amount >= 0
                     else None),
                ],
                "item",
                idx,
            )

            try_correct_numeric(
                item,
                "vat_amount",
                [
                    ("cost_with_vat - cost",
                     (cost_with_vat - cost)
                     if cost_with_vat is not None and cost is not None and cost_with_vat >= cost >= 0
                     else None),
                    ("cost * vat_rate",
                     (cost * vat_rate)
                     if non_negative(cost) and vat_rate is not None and vat_rate >= 0
                     else None),
                ],
                "item",
                idx,
            )

            q = as_num(item.get("quantity"))
            price = as_num(item.get("price"))
            cost = as_num(item.get("cost"))
            vat_amount = as_num(item.get("vat_amount"))
            cost_with_vat = as_num(item.get("cost_with_vat"))

            if cost is None and non_negative(q) and non_negative(price):
                cost = q * price
                set_missing_numeric(item, "cost", cost, "quantity * price", "item", idx)

            if (
                vat_amount is None
                and cost_with_vat is not None
                and cost is not None
                and cost_with_vat >= cost >= 0
            ):
                vat_amount = cost_with_vat - cost
                set_missing_numeric(item, "vat_amount", vat_amount, "cost_with_vat - cost", "item", idx)

            if cost_with_vat is None and non_negative(cost) and non_negative(vat_amount):
                cost_with_vat = cost + vat_amount
                set_missing_numeric(item, "cost_with_vat", cost_with_vat, "cost + vat_amount", "item", idx)

        elif doc_type == "account_prot":
            q = as_num(item.get("quantity"))
            free_unit_price_excl_vat = as_num(item.get("free_unit_price_excl_vat"))
            extra_charge = as_num(item.get("extra_charge"))
            unit_price_excl_vat = as_num(item.get("unit_price_excl_vat"))
            total_excl_vat = as_num(item.get("total_excl_vat"))
            vat_amount = as_num(item.get("vat_amount"))
            total_incl_vat = as_num(item.get("total_incl_vat"))
            vat_rate = as_rate(item.get("vat_rate"))

            try_correct_numeric(
                item,
                "total_excl_vat",
                [
                    ("quantity * unit_price_excl_vat",
                     (q * unit_price_excl_vat)
                     if non_negative(q) and non_negative(unit_price_excl_vat)
                     else None),
                    ("total_incl_vat - vat_amount",
                     (total_incl_vat - vat_amount)
                     if total_incl_vat is not None and vat_amount is not None and total_incl_vat >= vat_amount >= 0
                     else None),
                ],
                "item",
                idx,
            )

            try_correct_numeric(
                item,
                "unit_price_excl_vat",
                [
                    ("free_unit_price_excl_vat + extra_charge",
                     (free_unit_price_excl_vat + extra_charge)
                     if non_negative(free_unit_price_excl_vat) and non_negative(extra_charge)
                     else None),
                    ("total_excl_vat / quantity",
                     (total_excl_vat / q)
                     if non_negative(total_excl_vat) and non_negative(q) and q > 0
                     else None),
                ],
                "item",
                idx,
            )

            try_correct_numeric(
                item,
                "vat_amount",
                [
                    ("total_incl_vat - total_excl_vat",
                     (total_incl_vat - total_excl_vat)
                     if total_incl_vat is not None and total_excl_vat is not None and total_incl_vat >= total_excl_vat >= 0
                     else None),
                    ("total_excl_vat * vat_rate",
                     (total_excl_vat * vat_rate)
                     if non_negative(total_excl_vat) and vat_rate is not None and vat_rate >= 0
                     else None),
                ],
                "item",
                idx,
            )

            q = as_num(item.get("quantity"))
            free_unit_price_excl_vat = as_num(item.get("free_unit_price_excl_vat"))
            extra_charge = as_num(item.get("extra_charge"))
            unit_price_excl_vat = as_num(item.get("unit_price_excl_vat"))
            total_excl_vat = as_num(item.get("total_excl_vat"))
            vat_amount = as_num(item.get("vat_amount"))
            total_incl_vat = as_num(item.get("total_incl_vat"))

            if unit_price_excl_vat is None and non_negative(free_unit_price_excl_vat) and non_negative(extra_charge):
                unit_price_excl_vat = free_unit_price_excl_vat + extra_charge
                set_missing_numeric(
                    item,
                    "unit_price_excl_vat",
                    unit_price_excl_vat,
                    "free_unit_price_excl_vat + extra_charge",
                    "item",
                    idx,
                )

            if total_excl_vat is None and non_negative(q) and non_negative(unit_price_excl_vat):
                total_excl_vat = q * unit_price_excl_vat
                set_missing_numeric(
                    item,
                    "total_excl_vat",
                    total_excl_vat,
                    "quantity * unit_price_excl_vat",
                    "item",
                    idx,
                )

            if (
                vat_amount is None
                and total_incl_vat is not None
                and total_excl_vat is not None
                and total_incl_vat >= total_excl_vat >= 0
            ):
                vat_amount = total_incl_vat - total_excl_vat
                set_missing_numeric(
                    item,
                    "vat_amount",
                    vat_amount,
                    "total_incl_vat - total_excl_vat",
                    "item",
                    idx,
                )

            if total_incl_vat is None and non_negative(total_excl_vat) and non_negative(vat_amount):
                total_incl_vat = total_excl_vat + vat_amount
                set_missing_numeric(
                    item,
                    "total_incl_vat",
                    total_incl_vat,
                    "total_excl_vat + vat_amount",
                    "item",
                    idx,
                )

    if doc_type == "invoice":
        total_map = {
            "total_quantity": "quantity",
            "subtotal_no_disc_incl_vat": "amount_no_disc_incl_vat",
            "subtotal_with_disc_excl_vat": "amount_with_disc_excl_vat",
            "vat_amount": "vat_amount",
            "total_with_disc_incl_vat": "total_with_disc_incl_vat",
        }
        words_total_map = {
            "total_in_words": "total_with_disc_incl_vat",
        }

    elif doc_type == "waybill":
        total_map = {
            "quantity_total": "quantity",
            "cost_total": "cost",
            "vat_total": "vat_amount",
            "cost_with_vat_total": "cost_with_vat",
        }
        words_total_map = {
            "vat_total_words": "vat_total",
            "cost_with_vat_total_words": "cost_with_vat_total",
        }

    elif doc_type == "account_prot":
        total_map = {
            "subtotal_excl_vat": "total_excl_vat",
            "vat_amount": "vat_amount",
            "total_incl_vat": "total_incl_vat",
        }
        words_total_map = {
            "total_in_words": "total_incl_vat",
        }

    else:
        total_map = {}
        words_total_map = {}

    for total_field, item_field in total_map.items():
        derived = sum_item_field(items, item_field)
        extracted = totals.get(total_field)

        if is_missing(extracted):
            if derived is not None and derived >= 0:
                set_missing_numeric(totals, total_field, derived, f"sum(items.{item_field})", "totals")
        elif derived is not None and not close_enough(extracted, derived):
            add_warning(total_field, extracted, derived, "totals", source=f"sum(items.{item_field})")

    for words_field, numeric_field in words_total_map.items():
        words_text = totals.get(words_field)
        parsed_amount = parse_money_words_amount(words_text)
        if parsed_amount is None:
            continue

        extracted = totals.get(numeric_field)

        if is_missing(extracted):
            if parsed_amount >= 0:
                set_missing_numeric(totals, numeric_field, parsed_amount, f"parsed({words_field})", "totals")
            continue

        if not close_enough(extracted, parsed_amount):
            extracted_rub = rubles_part(extracted)
            parsed_rub = rubles_part(parsed_amount)

            if extracted_rub is not None and parsed_rub is not None and extracted_rub == parsed_rub:
                continue

            add_warning(numeric_field, extracted, parsed_amount, "totals", source=f"parsed({words_field})")

    payload["_reconciliation"] = {
        "changes": changes,
        "warnings": warnings,
    }

    return payload




def build_pred_reconciled(pred_normalized):
    pred_reconciled = copy.deepcopy(pred_normalized)

    for doc_type, docs in pred_reconciled.items():
        if not isinstance(docs, dict):
            continue

        for file_key, payload in docs.items():
            if not isinstance(payload, dict):
                continue

            if doc_type in {"invoice", "waybill", "Account-protocol"}:
                reconcile_type = {
                    "invoice": "invoice",
                    "waybill": "waybill",
                    "Account-protocol": "account_prot",
                }[doc_type]

                reconcile_document_amounts(reconcile_type, payload)

    return pred_reconciled
