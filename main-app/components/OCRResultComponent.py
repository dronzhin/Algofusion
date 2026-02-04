# components/OCRResultComponent.py
"""
Компонент для отображения результатов распознавания текста
Интегрируется с существующим интерфейсом
"""

import streamlit as st
from typing import Dict, Any
from utils import get_file_icon


def render_ocr_result(result: Dict[str, Any], original_filename: str):
    """
    Отображение результата распознавания текста с оригинальным документом

    Args:
        result: результат от сервера OCR
        original_filename: имя исходного файла
    """

    # Две колонки: слева оригинал, справа результат
    col1, col2 = st.columns([1, 1], gap="medium")

    with col1:
        st.markdown("### 📄 Исходный документ")
        _render_original_document()

    with col2:
        st.markdown("### ✅ Результат распознавания")
        _render_text_result(result)

    # Общая информация под колонками
    st.markdown("---")
    _render_summary(result, original_filename)

    # Уверенность и время обработки
    if result.get("confidence") is not None:
        _render_confidence(result)

    if result.get("timing"):
        _render_timing_info(result["timing"])

    # Кнопки скачивания
    _render_download_buttons(result, original_filename)


def _render_original_document():
    """Отображение оригинального документа как на других страницах"""
    shared_file = st.session_state.get("shared_file")
    if not shared_file:
        st.info("Исходный файл недоступен")
        return

    from .FilePreviewComponent import FilePreviewComponent
    FilePreviewComponent.render(
        file_bytes=shared_file["bytes"],
        file_type=shared_file["type"],
        file_name=shared_file["name"],
        file_ext=shared_file["ext"],
        title=None,
        show_meta=False
    )


def _render_text_result(result: Dict[str, Any]):
    """Отображение распознанного текста"""
    if result.get("file_type") == "pdf":
        _render_pdf_text(result)
    else:
        text = result.get("text", "").strip()
        if text:
            st.text_area(
                "Распознанный текст",
                value=text,
                height=300,
                key="ocr_result_text"
            )
        else:
            st.warning("⚠️ Текст не был распознан")


def _render_pdf_text(result: Dict[str, Any]):
    """Отображение текста многостраничного PDF"""
    pages = result.get("pages", [])
    if not pages:
        st.warning("⚠️ Страницы не были распознаны")
        return

    # Выбор страницы
    page_numbers = [p["page_number"] for p in pages if p.get("text")]
    if not page_numbers:
        st.warning("⚠️ Ни одна страница не содержит распознанного текста")
        return

    selected_page = st.selectbox(
        "Выберите страницу:",
        options=page_numbers,
        format_func=lambda x: f"Страница {x}",
        key="ocr_page_selector"
    )

    # Поиск выбранной страницы
    page_data = next((p for p in pages if p.get("page_number") == selected_page), None)
    if page_data and page_data.get("text"):
        st.text_area(
            f"Страница {selected_page}",
            value=page_data["text"].strip(),
            height=300,
            key=f"ocr_page_{selected_page}"
        )

        # Уверенность для страницы
        if page_data.get("confidence") is not None:
            _render_page_confidence(page_data["confidence"], selected_page)


def _render_summary(result: Dict[str, Any], filename: str):
    """Краткая сводка по распознаванию"""
    with st.expander("📊 Сводка распознавания", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Модель", result.get("model", "N/A"))

        with col2:
            file_type = result.get("file_type", "N/A").upper()
            st.metric("Тип", file_type)

        with col3:
            if result.get("file_type") == "pdf":
                st.metric("Страниц", result.get("total_pages", 0))
            else:
                status = result.get("status", "N/A")
                st.metric("Статус", status)


def _render_confidence(result: Dict[str, Any]):
    """Отображение общей уверенности"""
    confidence = result.get("confidence", 0)
    color, icon, level = _get_confidence_style(confidence)

    st.markdown(
        f"""
        <div style='padding: 15px; border-left: 5px solid {color}; background-color: #f8f9fa; border-radius: 5px; margin: 10px 0;'>
            <h4>{icon} Уверенность распознавания: {confidence:.2f}</h4>
            <p><strong>Уровень:</strong> {level}</p>
            <p style='font-size: 14px; color: #666; margin-top: 5px;'>
                <em>Рекомендация: {_get_confidence_recommendation(confidence)}</em>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )


def _render_page_confidence(confidence: float, page_num: int):
    """Уверенность для отдельной страницы PDF"""
    color, icon, level = _get_confidence_style(confidence)

    st.markdown(
        f"<small style='color: {color};'>{icon} Страница {page_num}: {level} ({confidence:.2f})</small>",
        unsafe_allow_html=True
    )


def _get_confidence_style(confidence: float):
    """Определение стиля для индикатора уверенности"""
    if confidence >= 0.85:
        return "#28a745", "✅", "Высокая"
    elif confidence >= 0.70:
        return "#ffc107", "⚠️", "Средняя"
    else:
        return "#dc3545", "❌", "Низкая"


def _get_confidence_recommendation(confidence: float) -> str:
    """Рекомендация на основе уровня уверенности"""
    if confidence >= 0.85:
        return "Результат можно использовать без дополнительной проверки"
    elif confidence >= 0.70:
        return "Рекомендуется проверить критичные поля (суммы, даты, номера)"
    else:
        return "Обязательна полная ручная проверка документа"


def _render_timing_info(timing: Dict[str, Any]):
    """Отображение времени обработки"""
    with st.expander("⏱️ Время обработки", expanded=False):
        total = timing.get("total_seconds", 0)
        inference = timing.get("inference_seconds", 0)

        st.markdown(f"**Общее время:** {total:.2f} сек")
        if inference:
            st.markdown(f"**Время инференса:** {inference:.2f} сек")

        # Для многостраничных документов
        pages_timing = timing.get("pages", [])
        if pages_timing:
            st.markdown("**По страницам:**")
            for i, t in enumerate(pages_timing, 1):
                st.markdown(f"- Страница {i}: {t:.2f} сек")


def _render_download_buttons(result: Dict[str, Any], filename: str):
    """Кнопки для скачивания результатов"""
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        # Скачать текстовый результат
        text_content = _get_text_for_download(result)
        if text_content:
            st.download_button(
                "📥 Скачать текст (TXT)",
                data=text_content.encode('utf-8'),
                file_name=_generate_filename(filename, "txt"),
                mime="text/plain",
                key="download_ocr_txt"
            )

    with col2:
        # Скачать полные данные в JSON
        import json
        json_content = json.dumps(result, ensure_ascii=False, indent=2)
        st.download_button(
            "📥 Скачать данные (JSON)",
            data=json_content.encode('utf-8'),
            file_name=_generate_filename(filename, "json"),
            mime="application/json",
            key="download_ocr_json"
        )


def _get_text_for_download(result: Dict[str, Any]) -> str:
    """Получение текста для скачивания"""
    if result.get("file_type") == "pdf":
        return result.get("combined_text", "")
    else:
        return result.get("text", "")


def _generate_filename(original: str, ext: str) -> str:
    """Генерация имени файла для скачивания"""
    import re
    clean_name = re.sub(r'[^\w\-_\.]', '_', original.split('.')[0])
    return f"ocr_{clean_name}.{ext}"


def show_server_unavailable(server_name: str, server_url: str, port: int):
    """
    Отображение сообщения о недоступности сервера
    """
    st.error(f"❌ Сервер {server_name} недоступен")

    st.markdown(f"""
    **Проверьте следующее:**

    1. **Запущен ли сервер распознавания?**
       ```bash
       cd ~/Algofusion/OCR
       python app.py
       ```

    2. **Доступен ли сервер по адресу `{server_url}`?**
       ```bash
       curl {server_url}/models
       ```

    3. **Не занят ли порт {port} другим приложением?**
       ```bash
       lsof -i :{port}
       ```
    """)

    if st.button("🔄 Проверить подключение снова", key="retry_ocr_connection"):
        st.rerun()


def show_model_selection(models_info: Dict[str, Any]) -> str:
    """
    Отображение выбора модели с описанием
    Возвращает выбранное имя модели
    """
    st.markdown("### 🧠 Выбор модели распознавания")

    available = models_info.get("available_models", [])
    loaded = models_info.get("loaded_models", [])

    if not available:
        st.warning("⚠️ Не удалось загрузить список моделей")
        return "glm-ocr"

    # Описания моделей
    model_info = {
        "glm-ocr": {
            "name": "GLM-OCR (0.9B)",
            "desc": "⚡ Быстрая и лёгкая модель для простых документов",
            "use_case": "Простые текстовые документы, быстрая обработка"
        },
        "deepseek-ocr": {
            "name": "DeepSeek-OCR (1.3B)",
            "desc": "📝 Базовая модель для общего распознавания текста",
            "use_case": "Общее распознавание, документы со сложным форматированием"
        },
        "deepseek-ocr2": {
            "name": "DeepSeek-OCR 2 (3B)",
            "desc": "📊 Лучшая модель для таблиц и структурированных документов",
            "use_case": "Таблицы, финансовые документы, формы с полями"
        },
        "paddleocr-vl-1.5": {
            "name": "PaddleOCR-VL-1.5 (0.9B)",
            "desc": "🌐 Специализация на многоязычных документах",
            "use_case": "Китайский, японский, корейский текст"
        }
    }

    # Формирование опций выбора
    options = []
    for model in available:
        info = model_info.get(model, {})
        status = "✅ Загружена" if model in loaded else "⏳ Загрузится при первом использовании"
        options.append(f"{info.get('name', model)} — {status}")

    selected_idx = st.selectbox(
        "Выберите модель:",
        options=options,
        index=0,
        help="Выберите модель в зависимости от типа документа"
    )

    # Извлечение имени модели из выбранной опции
    selected_model = available[options.index(selected_idx)]

    # Отображение подробной информации
    with st.expander("ℹ️ Подробнее о модели", expanded=False):
        info = model_info.get(selected_model, {})
        st.markdown(f"""
        **{info.get('name', selected_model)}**

        {info.get('desc', '')}

        **Рекомендуется для:**
        {info.get('use_case', 'Общее распознавание текста')}

        {"✅ Модель уже загружена в память" if selected_model in loaded else "⏳ Модель будет загружена при первом использовании (займёт 5-30 сек)"}
        """)

    return selected_model