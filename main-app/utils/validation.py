from typing import Any, Dict, List, Union


class ValidationError(Exception):
    """Кастомное исключение для ошибок валидации"""
    pass


def validate_threshold(value: Any) -> int:
    """
    Валидация порога для бинаризации
    """
    try:
        threshold = int(value)
        if not 0 <= threshold <= 255:
            raise ValidationError("Порог должен быть в диапазоне от 0 до 255")
        return threshold
    except (ValueError, TypeError):
        raise ValidationError("Порог должен быть целым числом")


def validate_line_detection_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Валидация параметров детекции линий
    """
    validated = {}

    # Минимальная длина линии
    min_line_length = params.get("min_line_length", 50)
    try:
        min_line_length = int(min_line_length)
        if min_line_length < 10:
            min_line_length = 10
        elif min_line_length > 500:
            min_line_length = 500
        validated["min_line_length"] = min_line_length
    except (ValueError, TypeError):
        validated["min_line_length"] = 50

    # Максимальный разрыв
    max_line_gap = params.get("max_line_gap", 20)
    try:
        max_line_gap = int(max_line_gap)
        if max_line_gap < 1:
            max_line_gap = 1
        elif max_line_gap > 100:
            max_line_gap = 100
        validated["max_line_gap"] = max_line_gap
    except (ValueError, TypeError):
        validated["max_line_gap"] = 20

    # Использование морфологии
    validated["use_morphology"] = bool(params.get("use_morphology", True))

    return validated


def validate_rotation_angle(angle: Any) -> float:
    """
    Валидация угла поворота
    """
    try:
        angle = float(angle)
        if angle < -360 or angle > 360:
            raise ValidationError("Угол поворота должен быть в диапазоне от -360 до 360 градусов")
        return angle
    except (ValueError, TypeError):
        raise ValidationError("Угол поворота должен быть числом")


def validate_file_upload(file_info: Dict[str, Any]) -> None:
    """
    Полная валидация загруженного файла
    """
    if not file_info:
        raise ValidationError("Файл не загружен")

    # Проверка размера
    max_size = 50 * 1024 * 1024  # 50MB
    if file_info.get("size", 0) > max_size:
        raise ValidationError(f"Файл слишком большой (максимум {max_size // (1024 * 1024)}MB)")

    # Проверка типа
    supported_types = [
        "image/jpeg", "image/jpg", "image/png", "image/bmp", "image/gif",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]

    file_type = file_info.get("type", "")
    file_ext = file_info.get("ext", "").lower()

    if file_type not in supported_types and file_ext not in [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".pdf", ".docx"]:
        raise ValidationError(f"Неподдерживаемый тип файла: {file_type} ({file_ext})")

    # Проверка содержимого
    file_bytes = file_info.get("bytes", b"")
    if not file_bytes or len(file_bytes) == 0:
        raise ValidationError("Файл пустой")