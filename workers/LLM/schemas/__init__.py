# workers/LLM/schemas/__init__.py
"""
Реестр схем для разных типов документов.
"""

from typing import Optional
from workers.LLM.schemas.base import SchemaRegistry
from workers.LLM.schemas import dogovor, schet, tovarnaya_nakladnaya, schet_protokol, generic

SCHEMA_REGISTRY = {
    "dogovor": dogovor.DogovorSchema(),
    "schet": schet.SchetSchema(),
    "tovarnaya_nakladnaya": tovarnaya_nakladnaya.NakladnayaSchema(),
    "schet_protokol": schet_protokol.SchetProtokolSchema(),
    "unknown": generic.GenericSchema(),
}


def get_schema_for_type(doc_type: str) -> Optional[SchemaRegistry]:
    """Возвращает схему для типа документа."""
    return SCHEMA_REGISTRY.get(doc_type, SCHEMA_REGISTRY["unknown"])


def get_all_supported_types() -> list[str]:
    """Возвращает список поддерживаемых типов."""
    return list(SCHEMA_REGISTRY.keys())


__all__ = ["get_schema_for_type", "get_all_supported_types", "SchemaRegistry"]