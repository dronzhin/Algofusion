# core/services/filter_service.py
from typing import List, Optional
from datetime import date
from core.models import FileRecord


class FilterService:
    """Инкапсуляция логики фильтрации"""

    @staticmethod
    def apply_filters(
            records: List[FileRecord],
            filter_date: Optional[date] = None,
            accuracy_threshold: int = 100
    ) -> List[FileRecord]:
        """Применяет фильтры к списку записей"""
        result = records

        if filter_date:
            result = [r for r in result if r.parsed_date and r.parsed_date.date() == filter_date]

        if accuracy_threshold < 100:
            result = [
                r for r in result
                if r.metric_value is not None and r.metric_value <= accuracy_threshold
            ]

        return result

    @staticmethod
    def get_accuracy_threshold(
            accuracy_type: str,
            sidebar_value: str,
            manual_value: int
    ) -> int:
        """Вычисляет порог точности из настроек"""
        if accuracy_type == "sidebar":
            mapping = {
                "Высокая точность (>98%)": 98,
                "Средняя точность (>95%)": 95,
                "Низкая точность (>90%)": 90
            }
            return mapping.get(sidebar_value, 95)
        return manual_value