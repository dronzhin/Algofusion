import streamlit as st
from typing import Dict, Any
from utils.validation import validate_line_detection_params


class SettingsPanel:
    """
    Компонент для отображения и управления настройками
    """

    @staticmethod
    def render_binary_settings(default_threshold: int = 128) -> int:
        """
        Отобразить настройки для бинаризации
        """
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

        return threshold

    @staticmethod
    def render_rotation_settings(default_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Отобразить настройки для выравнивания изображения
        """
        st.markdown("### ⚙️ Настройки детекции линий")

        if default_params is None:
            default_params = {
                "min_line_length": 50,
                "max_line_gap": 20,
                "use_morphology": True
            }

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

        # Валидация параметров
        return validate_line_detection_params(params)

    @staticmethod
    def render_file_preview_settings(file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Отобразить настройки для предпросмотра файла
        """
        settings = {
            "show_metadata": True,
            "show_page_selector": True
        }

        if file_info.get("is_pdf", False):
            settings["dpi"] = st.slider(
                "DPI для отображения PDF",
                min_value=72,
                max_value=300,
                value=150,
                step=15,
                help="Чем выше DPI, тем лучше качество, но дольше загрузка"
            )

        if file_info.get("is_docx", False):
            settings["paragraphs_per_page"] = st.slider(
                "Параграфов на страницу",
                min_value=10,
                max_value=100,
                value=30,
                step=5
            )

        return settings