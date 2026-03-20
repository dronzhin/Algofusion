# core/services/export_service.py
import time
from core.state import AppState
from core.models import FileRecord


class ExportService:
    """Логика экспорта в 1С"""

    @staticmethod
    def export_file(state: AppState, file_index: int, confirm: bool = False) -> bool:
        """Выполняет экспорт файла с обработкой повторных попыток"""
        record = FileRecord(**{k: state.file_data[k][file_index] for k in FileRecord.__fields__})

        # Проверка повторного экспорта
        if "Экспортирован" in record.status and not confirm:
            state.export_pending = file_index
            return False

        if "Экспортирован" in record.status and confirm:
            state.add_log("ОК", f"Повторный экспорт файла {record.filename} в 1С")
            state.export_pending = None
            return True

        # Имитация экспорта
        state.add_log("ОК", f"Начат экспорт файла {record.filename} в 1С...")
        time.sleep(0.3)  # В реальности — вызов API

        # Обновление состояния
        state.file_data["Статус"][file_index] = FileStatus.EXPORTED.value
        state.file_data["Экспорт в 1С"][file_index] = "✅"
        state.add_log("ОК", f"Файл {record.filename} успешно экспортирован в 1С")
        state.export_pending = None

        return True