# ui/utils/constants.py
"""
Централизованные константы для UI.
Устраняет дублирование строк по всему коду.
"""

# Порядок модулей обработки
MODULES_ORDER = ["preprocess", "ocr", "llm", "export"]

# Конфигурация статусов файлов
FILE_STATUS_CONFIG = {
    "uploaded": {"emoji": "🔵", "label": "Загружен", "color": "#004085", "bg": "#cce5ff"},
    "processing": {"emoji": "🟡", "label": "В обработке", "color": "#856404", "bg": "#fff3cd"},
    "completed": {"emoji": "🟢", "label": "Завершён", "color": "#155724", "bg": "#d4edda"},
    "failed": {"emoji": "🔴", "label": "Ошибка", "color": "#721c24", "bg": "#f8d7da"},
    "exported": {"emoji": "🟣", "label": "Экспортирован", "color": "#5a3d7a", "bg": "#e2d5f1"},
}

# Конфигурация статусов экспорта
EXPORT_STATUS_CONFIG = {
    "pending": {"emoji": "⏳", "label": "Ожидает"},
    "exporting": {"emoji": "🔄", "label": "Экспортируется"},
    "success": {"emoji": "✅", "label": "Успешно"},
    "failed": {"emoji": "❌", "label": "Ошибка"},
}

# Конфигурация логов
LOG_STATUS_CONFIG = {
    "OK": {"emoji": "✅", "color": "#28a745"},
    "ERROR": {"emoji": "❌", "color": "#dc3545"},
    "WARNING": {"emoji": "⚠️", "color": "#ffc107"},
    "INFO": {"emoji": "ℹ️", "color": "#6c757d"},
}

# Настройки отображения
UI_CONFIG = {
    "max_files_display": 50,      # Макс. файлов в списке
    "max_logs_display": 20,       # Макс. логов в просмотрщике
    "max_processing_display": 10, # Макс. файлов в прогрессе
    "datetime_format_short": "%Y-%m-%d %H:%M",
    "datetime_format_full": "%Y-%m-%d %H:%M:%S",
}

# Redis каналы и очереди (для консистентности с бэкендом)
REDIS_CHANNELS = {
    "events": "files:events",
    "export": "1c:export",
}

REDIS_QUEUES = {
    "preprocess": "files:preprocess",
    "ocr": "files:ocr",
    "llm": "files:llm",
    "export": "files:export",
}