"""Shared UI constants for the operator interface."""

MODULES_ORDER = [
    "cleaner",
    "layout",
    "ocr",
    "parser",
    "normalizer",
    "reconcile",
    "final_json",
]

MODULE_LABELS = {
    "cleaner": "Очистка",
    "layout": "Разметка",
    "ocr": "OCR",
    "parser": "Извлечение",
    "normalizer": "Нормализация",
    "reconcile": "Проверка сумм",
    "final_json": "Финальный JSON",
}

FILE_STATUS_CONFIG = {
    "uploaded": {
        "emoji": "•",
        "label": "Загружен",
        "color": "#375B7A",
        "bg": "#DDE9F2",
    },
    "processing": {
        "emoji": "•",
        "label": "В обработке",
        "color": "#8A5A20",
        "bg": "#F4E7CB",
    },
    "completed": {
        "emoji": "•",
        "label": "Готов",
        "color": "#2F6B55",
        "bg": "#DCEBE3",
    },
    "failed": {
        "emoji": "•",
        "label": "Ошибка",
        "color": "#8B3D34",
        "bg": "#F3DDDA",
    },
    "exported": {
        "emoji": "•",
        "label": "Выгружен",
        "color": "#5C4B7C",
        "bg": "#E7E1F1",
    },
}

EXPORT_STATUS_CONFIG = {
    "pending": {"emoji": "•", "label": "Ожидает"},
    "exporting": {"emoji": "•", "label": "Выгружается"},
    "success": {"emoji": "•", "label": "Успешно"},
    "failed": {"emoji": "•", "label": "Ошибка"},
}

LOG_STATUS_CONFIG = {
    "OK": {"emoji": "[OK]", "color": "#2F6B55"},
    "ERROR": {"emoji": "[ERR]", "color": "#8B3D34"},
    "WARNING": {"emoji": "[WARN]", "color": "#8A5A20"},
    "INFO": {"emoji": "[INFO]", "color": "#5E5A52"},
}

UI_CONFIG = {
    "max_files_display": 100,
    "max_logs_display": 12,
    "max_processing_display": 8,
    "datetime_format_short": "%d.%m.%Y %H:%M",
    "datetime_format_full": "%d.%m.%Y %H:%M:%S",
}

REDIS_CHANNELS = {
    "events": "files:events",
    "export": "1c:export",
}

REDIS_QUEUES = {
    "cleaner": "files:cleaner",
    "layout": "files:layout",
    "ocr": "files:ocr",
    "parser": "files:parser",
    "normalizer": "files:normalizer",
    "reconcile": "files:reconcile",
    "final_json": "files:final_json",
}
