"""
Схема для документа типа "Договор".
"""

from typing import Dict, Any, List
from workers.LLM.schemas.base import SchemaRegistry


class DogovorSchema(SchemaRegistry):
    """Схема извлечения данных из договора."""

    doc_type = "dogovor"
    description = "Договор/контракт: номера, даты, стороны, суммы"

    def get_json_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "contract_number": {"type": "string", "description": "Номер договора"},
                "contract_date": {"type": "string", "description": "Дата договора (ДД.ММ.ГГГГ)"},
                "party_1": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "inn": {"type": "string"},
                        "kpp": {"type": "string"},
                    },
                    "required": ["name"]
                },
                "party_2": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "inn": {"type": "string"},
                    },
                    "required": ["name"]
                },
                "subject": {"type": "string"},
                "amount": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "currency": {"type": "string"},
                    }
                },
            },
            "required": ["contract_number", "contract_date", "party_1", "party_2"]
        }

    def get_extraction_fields(self) -> List[str]:
        return ["contract_number", "contract_date", "party_1", "party_2", "subject"]

    def get_prompt_hints(self) -> str:
        return """
Формат вывода:
- Даты: ДД.ММ.ГГГГ
- Суммы: число + валюта отдельно
- ИНН/KPP: только цифры
- Не найдено → null
"""