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


class DocumentType(str, Enum):
    CONTRACT = "contract"
    INVOICE = "invoice"
    INVOICE_PROTOCOL = "invoice_protocol"
    WAYBILL = "waybill"
    PAYMENT = "payment"  # 🔹 НОВОЕ: Платёжное поручение
    ORDER = "order"  # 🔹 НОВОЕ: Приказ / Распоряжение
    UNKNOWN = "unknown"  # 🔹 ЕДИНСТВЕННЫЙ fallback-тип

    _LABELS = {
        "contract": "Договор",
        "invoice": "Счет",
        "invoice_protocol": "Счет-протокол",
        "waybill": "Товарная накладная",
        "payment": "Платёжное поручение",
        "order": "Приказ / Распоряжение",
        "unknown": "Неизвестно"
    }

    # Маппинг всех известных вариантов → канонические Enum
    _PARSE_MAP: Dict[str, "DocumentType"] = {
        # Английские каноничные
        "contract": CONTRACT,
        "invoice": INVOICE,
        "invoice_protocol": INVOICE_PROTOCOL,
        "waybill": WAYBILL,
        "payment": PAYMENT,
        "order": ORDER,
        "unknown": UNKNOWN,

        # Русские (после нормализации)
        "договор": CONTRACT,
        "счет": INVOICE,
        "счёт": INVOICE,
        "счет_протокол": INVOICE_PROTOCOL,
        "счёт_протокол": INVOICE_PROTOCOL,
        "товарная_накладная": WAYBILL,
        "накладная": WAYBILL,
        "платёжное_поручение": PAYMENT,
        "платежное_поручение": PAYMENT,
        "платежка": PAYMENT,
        "платёжка": PAYMENT,
        "приказ": ORDER,
        "распоряжение": ORDER,
        "заказ": ORDER,  # Часто используется как синоним приказа/распоряжения
        "неизвестно": UNKNOWN,
        "другое": UNKNOWN,  # 🔹 "Другое" теперь маппится на UNKNOWN

        # Сокращения/опечатки
        "сч_протокол": INVOICE_PROTOCOL,
        "т_накладная": WAYBILL,
        "тов_накладная": WAYBILL,
        "пл_поручение": PAYMENT,
        "плат_поруч": PAYMENT,
        "приказ_по_орг": ORDER,
    }

    @property
    def label(self) -> str:
        return self._LABELS.get(self.value, self.value)

    @classmethod
    def get_all_for_ui(cls) -> List[Dict[str, str]]:
        return [{"value": v.value, "label": v.label} for v in cls]

    @classmethod
    def safe_parse(cls, value: Optional[str]) -> Optional["DocumentType"]:
        if not value or not value.strip():
            return None

        # 🔹 Шаг 1: Жёсткая нормализация
        normalized = value.strip().lower().replace("ё", "е")
        # Пробелы, дефисы, табуляции → одинарное "_"
        normalized = re.sub(r"[\s\-]+", "_", normalized)
        # Множественные "__" → "_", убираем крайние
        normalized = re.sub(r"_+", "_", normalized).strip("_")

        # 🔹 Шаг 2: Поиск в маппинге
        return cls._PARSE_MAP.get(normalized, cls.UNKNOWN)


@dataclass
class ExportConfig:
    enabled: bool = False
    mode: str = "manual"
    format: str = "1c_xml"
    endpoint: str = ""
    batch_size: int = 10
    retry_count: int = 3