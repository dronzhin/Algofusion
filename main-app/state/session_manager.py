# state/session_manager.py
import streamlit as st
import logging
from typing import Any, Optional, Dict, List

# Создаём логгер для этого модуля
logger = logging.getLogger(f"app.{__name__}")


class SessionManager:
    """
    Централизованный менеджер для работы с session_state
    Обеспечивает типизацию и валидацию данных
    """

    # Ключи для session_state
    SHARED_FILE = "shared_file"
    BINARY_RESULTS = "binary_results"
    ROTATION_RESULTS = "rotation_results"
    OCR_RESULTS = "ocr_results"  # ← НОВЫЙ КЛЮЧ ДЛЯ РЕЗУЛЬТАТОВ РАСПОЗНАВАНИЯ
    LAST_UPLOADED_FILE = "last_uploaded_file"
    SHOW_LINE_STATE = "show_line_state"
    SESSION_INITIALIZED = "_session_initialized"

    @classmethod
    def get_shared_file(cls) -> Optional[Dict[str, Any]]:
        """Получить текущий файл из сессии"""
        file = st.session_state.get(cls.SHARED_FILE)
        logger.debug(f"Получен файл из сессии: {'да' if file else 'нет'}")
        return file

    @classmethod
    def set_shared_file(cls, file_info: Dict[str, Any]):
        """Сохранить файл в сессию"""
        try:
            st.session_state[cls.SHARED_FILE] = file_info
            st.session_state[cls.LAST_UPLOADED_FILE] = file_info["name"]
            logger.info(f"Файл сохранён в сессию: {file_info.get('name', 'без имени')}")
        except KeyError as e:
            logger.error(f"Ошибка при сохранении файла: отсутствует ключ {e}")
            raise ValueError(f"Некорректная структура file_info: {e}")

    @classmethod
    def clear_shared_file(cls):
        """Очистить файл из сессии"""
        removed = []
        if cls.SHARED_FILE in st.session_state:
            del st.session_state[cls.SHARED_FILE]
            removed.append(cls.SHARED_FILE)
        if cls.LAST_UPLOADED_FILE in st.session_state:
            del st.session_state[cls.LAST_UPLOADED_FILE]
            removed.append(cls.LAST_UPLOADED_FILE)
        if removed:
            logger.info(f"Удалены ключи из сессии: {removed}")
        else:
            logger.debug("Попытка очистки файла: файл не был загружен")

    @classmethod
    def get_binary_results(cls) -> Optional[Dict[str, Any]]:
        """Получить результаты бинарной конвертации"""
        results = st.session_state.get(cls.BINARY_RESULTS)
        logger.debug(f"Получены бинарные результаты: {'да' if results else 'нет'}")
        return results

    @classmethod
    def set_binary_results(cls, images: List[bytes], threshold: int, original_filename: str,
                           original_page_num: int = 0):
        """
        Сохранить результаты бинарной конвертации

        Args:
            images: список байтов бинарных изображений (обычно одно для одной страницы)
            threshold: использованный порог бинаризации
            original_filename: имя исходного файла
            original_page_num: номер исходной страницы (0-indexed, для многостраничных документов)
        """
        st.session_state[cls.BINARY_RESULTS] = {
            "images": images,
            "threshold": threshold,
            "original_filename": original_filename,
            "original_page_num": original_page_num
        }
        logger.info(
            f"Бинарные результаты сохранены: файл={original_filename}, "
            f"порог={threshold}, изображений={len(images)}, страница={original_page_num}"
        )

    @classmethod
    def clear_binary_results(cls):
        """Очистить результаты бинарной конвертации"""
        if cls.BINARY_RESULTS in st.session_state:
            del st.session_state[cls.BINARY_RESULTS]
            logger.info("Бинарные результаты удалены из сессии")
        else:
            logger.debug("Попытка очистки бинарных результатов: данные отсутствуют")

    @classmethod
    def get_rotation_results(cls) -> Optional[Dict[str, Any]]:
        """Получить результаты выравнивания изображения"""
        results = st.session_state.get(cls.ROTATION_RESULTS)
        logger.debug(f"Получены результаты выравнивания: {'да' if results else 'нет'}")
        return results

    @classmethod
    def set_rotation_results(cls, results: Dict[str, Any]):
        """Сохранить результаты выравнивания изображения"""
        st.session_state[cls.ROTATION_RESULTS] = results
        angle = results.get("rotation_angle", results.get("angle", "неизвестно"))
        logger.info(f"Результаты выравнивания сохранены: угол={angle}°")

    @classmethod
    def clear_rotation_results(cls):
        """Очистить результаты выравнивания изображения"""
        if cls.ROTATION_RESULTS in st.session_state:
            del st.session_state[cls.ROTATION_RESULTS]
            logger.info("Результаты выравнивания удалены из сессии")
        else:
            logger.debug("Попытка очистки результатов выравнивания: данные отсутствуют")

    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С РЕЗУЛЬТАТАМИ РАСПОЗНАВАНИЯ ТЕКСТА ====================

    @classmethod
    def get_ocr_results(cls) -> Optional[Dict[str, Any]]:
        """
        Получить результаты распознавания текста (OCR)

        Returns:
            Словарь с результатами распознавания или None, если результаты отсутствуют

        Пример результата:
            {
                "model": "glm-ocr",
                "prompt": "Extract all text",
                "file_type": "pdf",
                "total_pages": 3,
                "pages": [...],
                "combined_text": "...",
                "confidence": 0.87,
                "confidence_per_page": [0.92, 0.78, 0.85],
                "status": "success",
                "timing": {...},
                "request_id": "req_12345"
            }
        """
        results = st.session_state.get(cls.OCR_RESULTS)
        logger.debug(f"Получены результаты распознавания: {'да' if results else 'нет'}")
        return results

    @classmethod
    def set_ocr_results(cls, results: Dict[str, Any]):
        """
        Сохранить результаты распознавания текста (OCR)

        Args:
            results: словарь с результатами от сервера распознавания

        Пример структуры результатов см. в описании get_ocr_results()
        """
        st.session_state[cls.OCR_RESULTS] = results

        # Логирование ключевой информации
        model = results.get("model", "неизвестно")
        file_type = results.get("file_type", "неизвестно")
        status = results.get("status", "неизвестно")
        confidence = results.get("confidence")
        pages = results.get("total_pages", 1) if file_type == "pdf" else 1

        log_msg = f"Результаты распознавания сохранены: модель={model}, тип={file_type}, статус={status}"
        if confidence is not None:
            log_msg += f", уверенность={confidence:.2f}"
        if file_type == "pdf":
            log_msg += f", страниц={pages}"

        logger.info(log_msg)

    @classmethod
    def clear_ocr_results(cls):
        """Очистить результаты распознавания текста (OCR)"""
        if cls.OCR_RESULTS in st.session_state:
            del st.session_state[cls.OCR_RESULTS]
            logger.info("Результаты распознавания удалены из сессии")
        else:
            logger.debug("Попытка очистки результатов распознавания: данные отсутствуют")

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    @classmethod
    def get_show_line_state(cls) -> bool:
        """Получить состояние чекбокса показа линии"""
        state = st.session_state.get(cls.SHOW_LINE_STATE, False)
        logger.debug(f"Состояние 'показать линию': {state}")
        return state

    @classmethod
    def set_show_line_state(cls, value: bool):
        """Установить состояние чекбокса показа линии"""
        st.session_state[cls.SHOW_LINE_STATE] = value
        logger.info(f"Состояние 'показать линию' установлено: {value}")

    # ==================== ИНИЦИАЛИЗАЦИЯ И ОЧИСТКА ====================

    @classmethod
    def initialize_session(cls):
        """Инициализация session_state — только один раз за сессию"""
        if st.session_state.get(cls.SESSION_INITIALIZED):
            return  # Уже инициализировано — выходим

        defaults = {
            cls.SHARED_FILE: None,
            cls.BINARY_RESULTS: None,
            cls.ROTATION_RESULTS: None,
            cls.OCR_RESULTS: None,  # ← ДОБАВЛЕНО
            cls.LAST_UPLOADED_FILE: None,
            cls.SHOW_LINE_STATE: False
        }

        for key, default_value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
                logger.debug(f"Установлено значение по умолчанию для '{key}': {default_value}")

        # Устанавливаем флаг инициализации
        st.session_state[cls.SESSION_INITIALIZED] = True
        logger.info("Сессия инициализирована")

    @classmethod
    def clear_all_results(cls):
        """
        Очистить ВСЕ результаты обработки (бинаризация, выравнивание, распознавание)
        Не очищает сам файл — только результаты его обработки
        """
        logger.info("Очистка всех результатов обработки")
        cls.clear_binary_results()
        cls.clear_rotation_results()
        cls.clear_ocr_results()  # ← ДОБАВЛЕНО
        cls.set_show_line_state(False)