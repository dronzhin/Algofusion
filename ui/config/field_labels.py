"""
Словарь русскоязычных меток для полей JSON-редактора.
🔹 Покрывает все типы документов: invoice, invoice_protocol, order, payment, waybill, unknown
🔹 Приоритет: полный путь > короткий ключ > авто-форматирование
"""

FIELD_LABELS_RU = {
    # === Общие поля документа ===
    "document_type": "Тип документа",
    "source_file": "Исходный файл",
    "document_number": "Номер документа",
    "document_date": "Дата документа",
    "currency": "Валюта",
    "notes": "Примечания",
    "contract_basis": "Основание (договор/заказ/счёт)",
    "basis": "Основание издания",
    "order_title": "Тема / Заголовок документа",
    "total_amount": "Общая сумма",

    # === Стороны (поставщик/покупатель/плательщик/получатель) ===
    "parties": "👥 Стороны документа",
    "supplier": "🏢 Поставщик / Отправитель",
    "customer": "👤 Покупатель / Получатель",
    "payer": "💸 Плательщик",
    "payee": "🏦 Получатель платежа",

    # === Реквизиты организаций ===
    "name": "Наименование организации / ФИО",
    "address": "Юридический / Фактический адрес",
    "tax_id": "УНП / ИНН",
    "account": "Расчётный счёт (IBAN)",
    "bank": "Наименование банка",
    "bank_id": "БИК / Код банка",
    "unp": "УНП",
    "city": "Город",

    # === Организация и персонал (для приказов/распоряжений) ===
    "organization": "🏢 Организация-издатель",
    "employees": "👥 Сотрудники / Исполнители",
    "full_name": "ФИО сотрудника",
    "position": "Должность",
    "action": "Поручение / Действие",
    "signatory": "✍️ Подписант",

    # === Платёжные реквизиты ===
    "payment_details": "💳 Детали платежа",
    "amount": "Сумма (числом)",
    "purpose": "Назначение платежа",

    # === Позиции / Товары и услуги ===
    "items": "📦 Позиции / Товары и услуги",
    "description": "Наименование / Описание",
    "unit": "Единица измерения",
    "quantity": "Количество",
    "unit_price": "Цена за единицу",
    "unit_price_incl_vat": "Цена за ед. (с НДС)",
    "amount_no_disc_incl_vat": "Сумма без скидки (с НДС)",
    "disc_amount": "Сумма скидки",
    "amount_with_disc_excl_vat": "Сумма со скидкой (без НДС)",
    "vat_rate": "Ставка НДС, %",
    "vat_amount": "Сумма НДС",
    "total_incl_vat": "Итого с НДС",

    # === Итоговые блоки ===
    "totals": "💰 Итоговые суммы",
    "total_quantity": "Общее количество мест",
    "total_excl_vat": "Всего без НДС",
    "total_in_words": "Сумма прописью",

    # 🔹 ПОЛНЫЕ ПУТИ (приоритет над короткими ключами для вложенных полей)
    # Поставщик
    "parties.supplier.name": "Поставщик: Наименование",
    "parties.supplier.address": "Поставщик: Адрес",
    "parties.supplier.tax_id": "Поставщик: УНП/ИНН",
    # Покупатель
    "parties.customer.name": "Покупатель: Наименование",
    "parties.customer.address": "Покупатель: Адрес",
    "parties.customer.tax_id": "Покупатель: УНП/ИНН",
    # Плательщик
    "parties.payer.name": "Плательщик: Наименование",
    "parties.payer.account": "Плательщик: Расчётный счёт",
    "parties.payer.bank": "Плательщик: Банк",
    "parties.payer.tax_id": "Плательщик: УНП/ИНН",
    "parties.payer.bank_id": "Плательщик: БИК",
    # Получатель
    "parties.payee.name": "Получатель: Наименование",
    "parties.payee.account": "Получатель: Расчётный счёт",
    "parties.payee.bank": "Получатель: Банк",
    "parties.payee.tax_id": "Получатель: УНП/ИНН",
    "parties.payee.bank_id": "Получатель: БИК",
    # Организация
    "organization.name": "Организация: Наименование",
    "organization.unp": "Организация: УНП",
    "organization.city": "Организация: Город",
    # Подписант
    "signatory.name": "Подписант: ФИО",
    "signatory.position": "Подписант: Должность",
    # Платёж
    "payment_details.amount": "Платёж: Сумма",
    "payment_details.currency": "Платёж: Валюта",
    "payment_details.purpose": "Платёж: Назначение",
    # Итоги
    "totals.vat_amount": "Итог: Всего НДС",
    "totals.total_incl_vat": "Итог: Всего к оплате (с НДС)",
    "totals.total_excl_vat": "Итог: Всего без НДС",
    "totals.total_quantity": "Итог: Общее количество",
    "totals.total_in_words": "Итог: Сумма прописью",
    "totals.currency": "Итог: Валюта итога",
}


def get_field_label(key: str, prefix: str = "") -> str:
    """
    Получает русское название поля.

    Приоритет поиска:
    1. Полный путь (prefix.key) → для точного соответствия вложенным полям
    2. Короткий ключ (key) → для универсальных полей
    3. Авто-форматирование → fallback, если перевода нет
    """
    full_path = f"{prefix}.{key}" if prefix else key

    # 1. Точный путь
    if full_path in FIELD_LABELS_RU:
        return FIELD_LABELS_RU[full_path]

    # 2. Универсальный ключ
    if key in FIELD_LABELS_RU:
        return FIELD_LABELS_RU[key]

    # 3. Fallback: заменяем _ на пробел, капитализируем
    return key.replace("_", " ").capitalize()