# workers/LLM/src/llm/converter.py
"""
Конвертер JSON → XML для экспорта в 1С.
Аналогично другим компонентам LLM
"""

from pathlib import Path
from typing import Dict, Any, Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom

from shared.utils.logger import setup_logger
from shared.models.file import FileJob
from core.services.file_service import FileService
from workers.LLM.src.llm.base import ConverterEngine

logger = setup_logger("workers.llm.llm.converter")


class XmlConverter(ConverterEngine):
    """Конвертер данных в XML-формат для 1С."""

    name = "xml_converter"

    def __init__(self, config: dict):
        super().__init__(config)
        self.encoding = config.get("xml_encoding", "utf-8")
        self.indent = config.get("xml_indent", "  ")

    def convert(self, data: Dict[str, Any], doc_type: str) -> str:
        """Конвертирует данные в XML-строку."""
        # Создаём корневой элемент
        root = ET.Element("Document", {
            "type": doc_type,
            "version": "1.0",
        })

        # Рекурсивно добавляем данные
        self._add_to_xml(root, data)

        # Форматируем и сериализуем
        xml_str = minidom.parseString(ET.tostring(root, encoding=self.encoding)) \
            .toprettyxml(indent=self.indent, encoding=self.encoding)

        return xml_str.decode(self.encoding)

    def convert_to_file(
        self,
        data: Dict[str, Any],
        doc_type: str,
        job: FileJob,
        file_service: FileService
    ) -> Optional[Path]:
        """Конвертирует и сохраняет в файл."""
        xml_content = self.convert(data, doc_type)

        output_dir = Path(file_service.base_dir) / job.file_id / "export"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{Path(job.original_filename).stem}_1c.xml"

        with open(output_path, "w", encoding=self.encoding) as f:
            f.write(xml_content)

        return output_path

    def _add_to_xml(self, parent: ET.Element, data: Any, key: Optional[str] = None) -> None:
        """Рекурсивно добавляет данные в XML-элемент."""
        if isinstance(data, dict):
            for k, v in data.items():
                if k.startswith("_"):  # Пропускаем служебные поля
                    continue
                tag_name = self._to_xml_tag(k)
                child = ET.SubElement(parent, tag_name)
                self._add_to_xml(child, v)
        elif isinstance(data, list):
            for item in data:
                item_elem = ET.SubElement(parent, "item")
                self._add_to_xml(item_elem, item)
        else:
            parent.text = str(data) if data is not None else ""

    def _to_xml_tag(self, name: str) -> str:
        """Конвертирует имя поля в XML-тег (PascalCase для 1С)."""
        # Пример: "contract_number" → "ContractNumber"
        parts = name.split("_")
        return "".join(part.capitalize() for part in parts if part)