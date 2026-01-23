# components/settings_panel.py
import streamlit as st
import logging
from typing import Dict, Any
from config import Config
from utils import validate_line_detection_params

# Создаём логгер для этого модуля
logger = logging.getLogger(f"app.{__name__}")

class SettingsPanel:
    """
    Компонент для отображения и управления настройками
    """

    @staticmethod
    def render_binary_settings(default_threshold: int = None) -> int:
        """
        Отобразить настройки для бинаризации
        """
        if default_threshold is None:
            default_threshold = Config.DEFAULT_BINARY_THRESHOLD

        logger.debug(f"Рендеринг настроек бинаризации (дефолт: {default_threshold})")
        st.markdown("### ⚙️ Настройки бинаризации")

        col1, col2 = st.columns([2, 1])

        with col1:
            threshold = st.number_input(
                "Порог бинаризации (0-255)",
                min_value=0,
                max_value=255,
                value=default_threshold,
                step=1,
                help="Значение яркости: выше порога → белый, ниже → черный"
            )

        with col2:
            st.markdown("**Рекомендации:**")
            st.markdown("- Документы: 120-150")
            st.markdown("- Чертежи: 80-100")
            st.markdown("- Фото с текстом: 180-200")

        logger.info(f"Выбран порог бинаризации: {threshold}")
        return threshold

    @staticmethod
    def render_rotation_settings(default_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Отобразить настройки для выравнивания изображения
        """
        logger.debug("Рендеринг настроек детекции линий")
        st.markdown("### ⚙️ Настройки детекции линий")

        if default_params is None:
            default_params = Config.get_rotation_default_params()
            logger.debug("Используются параметры по умолчанию из конфигурации")

        with st.expander("Настройки детекции линий", expanded=True):
            col1, col2 = st.columns(2)

            with col1:
                min_line_length = st.slider(
                    "Минимальная длина линии (пиксели)",
                    min_value=10,
                    max_value=500,
                    value=default_params["min_line_length"],
                    step=10,
                    key="min_line_length_slider"
                )

            with col2:
                max_line_gap = st.slider(
                    "Максимальный разрыв в линии (пиксели)",
                    min_value=1,
                    max_value=100,
                    value=default_params["max_line_gap"],
                    step=1,
                    key="max_line_gap_slider"
                )

            use_morphology = st.checkbox(
                "Применить морфологические операции для улучшения линий",
                value=default_params["use_morphology"],
                key="use_morphology_checkbox"
            )

            st.info("Морфологические операции помогают соединить разорванные линии и удалить шум")

        params = {
            "min_line_length": min_line_length,
            "max_line_gap": max_line_gap,
            "use_morphology": use_morphology
        }

        try:
            validated_params = validate_line_detection_params(params)
            logger.info(f"Параметры детекции линий успешно валидированы: {validated_params}")
            return validated_params
        except Exception as e:
            logger.error(f"Ошибка валидации параметров детекции линий: {e}", exc_info=True)
            st.error("Некорректные параметры детекции линий. Используются значения по умолчанию.")
            return Config.get_rotation_default_params()