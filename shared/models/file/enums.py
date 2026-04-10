# shared/models/file/enums.py
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
import re


class FileType(str, Enum):
    IMAGE = "image"
    PDF = "pdf"
    DOCUMENT = "document"
    TEXT = "text"
    UNKNOWN = "unknown"


class FileStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    EXPORTED = "exported"
    FAILED = "failed"


_VALID_STATUSES = [s.value for s in FileStatus]


class ExportStatus(str, Enum):
    PENDING = "pending"
    EXPORTING = "exporting"
    SUCCESS = "success"
    FAILED = "failed"


# =============================================================================
# 🔹 DocumentType: выносим служебные словари ЗА пределы класса
# =============================================================================

# Маппинг value → человекочитаемая метка
_DOCUMENT_TYPE_LABELS: Dict[str, str] = {
    "contract": "Договор",
    "invoice": "Счет",
    "invoice_protocol": "Счет-протокол",
    "waybill": "Товарная накладная",
    "payment": "Платёжное поручение",
    "order": "Приказ / Распоряжение",
    "unknown": "Неизвестно"
}

# Маппинг всех известных вариантов → канонические члены Enum
# 🔹 Важно: определяем ПОСЛЕ объявления класса DocumentType, чтобы члены уже существовали
_DOCUMENT_TYPE_PARSE_MAP: Dict[str, "DocumentType"] = {}  # заполним ниже


class DocumentType(str, Enum):
    CONTRACT = "contract"
    INVOICE = "invoice"
    INVOICE_PROTOCOL = "invoice_protocol"
    WAYBILL = "waybill"
    PAYMENT = "payment"  # 🔹 НОВОЕ: Платёжное поручение
    ORDER = "order"  # 🔹 НОВОЕ: Приказ / Распоряжение
    UNKNOWN = "unknown"  # 🔹 ЕДИНСТВЕННЫЙ fallback-тип

    @property
    def label(self) -> str:
        return _DOCUMENT_TYPE_LABELS.get(self.value, self.value)

    @classmethod
    def get_all_for_ui(cls) -> List[Dict[str, str]]:
        return [{"value": v.value, "label": v.label} for v in cls]

    @classmethod
    def safe_parse(cls, value: Optional[str]) -> Optional["DocumentType"]:
        """
        Безопасный парсинг строки в DocumentType.
        Нормализует вход и ищет в маппинге, возвращает UNKNOWN при неудаче.
        """
        if not value or not value.strip():
            return None

        # 🔹 Шаг 1: Жёсткая нормализация
        normalized = value.strip().lower().replace("ё", "е")
        # Пробелы, дефисы, табуляции → одинарное "_"
        normalized = re.sub(r"[\s\-]+", "_", normalized)
        # Множественные "__" → "_", убираем крайние
        normalized = re.sub(r"_+", "_", normalized).strip("_")

        # 🔹 Шаг 2: Поиск в маппинге
        return _DOCUMENT_TYPE_PARSE_MAP.get(normalized, cls.UNKNOWN)


# =============================================================================
# 🔹 Заполняем _DOCUMENT_TYPE_PARSE_MAP ПОСЛЕ создания класса DocumentType
# =============================================================================
_DOCUMENT_TYPE_PARSE_MAP.update({
    # === Английские каноничные ===
    "contract": DocumentType.CONTRACT,
    "invoice": DocumentType.INVOICE,
    "invoice_protocol": DocumentType.INVOICE_PROTOCOL,
    "waybill": DocumentType.WAYBILL,
    "payment": DocumentType.PAYMENT,
    "order": DocumentType.ORDER,
    "unknown": DocumentType.UNKNOWN,

    # === Русские (после нормализации) ===
    "договор": DocumentType.CONTRACT,
    "счет": DocumentType.INVOICE,
    "счёт": DocumentType.INVOICE,
    "счет_протокол": DocumentType.INVOICE_PROTOCOL,
    "счёт_протокол": DocumentType.INVOICE_PROTOCOL,
    "товарная_накладная": DocumentType.WAYBILL,
    "накладная": DocumentType.WAYBILL,
    "платёжное_поручение": DocumentType.PAYMENT,
    "платежное_поручение": DocumentType.PAYMENT,
    "платежка": DocumentType.PAYMENT,
    "платёжка": DocumentType.PAYMENT,
    "приказ": DocumentType.ORDER,
    "распоряжение": DocumentType.ORDER,
    "заказ": DocumentType.ORDER,  # Часто используется как синоним
    "неизвестно": DocumentType.UNKNOWN,
    "другое": DocumentType.UNKNOWN,  # 🔹 "Другое" → UNKNOWN

    # === Сокращения / опечатки / варианты ===
    "сч_протокол": DocumentType.INVOICE_PROTOCOL,
    "т_накладная": DocumentType.WAYBILL,
    "тов_накладная": DocumentType.WAYBILL,
    "пл_поручение": DocumentType.PAYMENT,
    "плат_поруч": DocumentType.PAYMENT,
    "приказ_по_орг": DocumentType.ORDER,
})


@dataclass
class ExportConfig:
    enabled: bool = False
    mode: str = "manual"
    format: str = "1c_xml"
    endpoint: str = ""
    batch_size: int = 10
    retry_count: int = 3


# =============================================================================
# 🔹 Unit-тесты для быстрой проверки (запуск: python -m shared.models.file.enums)
# =============================================================================
if __name__ == "__main__":
    # Проверка типов служебных словарей
    assert isinstance(_DOCUMENT_TYPE_PARSE_MAP, dict), "_PARSE_MAP должен быть dict!"
    assert hasattr(_DOCUMENT_TYPE_PARSE_MAP, "get"), "_PARSE_MAP должен иметь метод .get()"

    # Проверка парсинга
    assert DocumentType.safe_parse("договор") == DocumentType.CONTRACT
    assert DocumentType.safe_parse("ПЛАТЁЖКА") == DocumentType.PAYMENT
    assert DocumentType.safe_parse("счёт-протокол") == DocumentType.INVOICE_PROTOCOL
    assert DocumentType.safe_parse("неизвестный_тип") == DocumentType.UNKNOWN
    assert DocumentType.safe_parse(None) is None
    assert DocumentType.safe_parse("") is None

    # Проверка label
    assert DocumentType.CONTRACT.label == "Договор"
    assert DocumentType.UNKNOWN.label == "Неизвестно"

    # Проверка UI-метода
    ui_list = DocumentType.get_all_for_ui()
    assert all("value" in item and "label" in item for item in ui_list)

    print("✅ Все проверки DocumentType пройдены успешно")