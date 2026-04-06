# ui/components/classification_badge.py

import streamlit as st
from typing import Optional
from ui.utils.formatters import render_status_badge_safe


def render_classification_info(
        file_data: dict,
        container=None
) -> None:
    """
    Отображает информацию о классификации документа.

    Показывает:
    - Тип документа (если определён)
    - Источник классификации (LLM / пользователь)
    - Уверенность (если от LLM)
    - Кнопку "Изменить" если классификация от LLM с низкой уверенностью
    """
    container = container or st

    # Извлекаем данные о классификации
    doc_type = file_data.get("metadata", {}).get("document_type") or file_data.get("llm_classification_type")
    confidence = file_data.get("metadata", {}).get("classification_confidence") or file_data.get(
        "llm_classification_confidence")
    source = file_data.get("metadata", {}).get("classification_source") or file_data.get("active_classification_source")
    pending = file_data.get("classification_pending", False)

    if not doc_type:
        container.caption("⏳ Классификация не выполнена")
        return

    # Определяем визуальное оформление
    if source == "user":
        badge_color = "#155724"  # зелёный — доверенный источник
        badge_bg = "#d4edda"
        source_label = "👤 Пользователь"
        confidence_display = ""
    elif source == "llm":
        if confidence and confidence >= 0.85:
            badge_color = "#155724"
            badge_bg = "#d4edda"
        elif confidence and confidence >= 0.6:
            badge_color = "#856404"
            badge_bg = "#fff3cd"
        else:
            badge_color = "#721c24"
            badge_bg = "#f8d7da"

        source_label = "🤖 LLM"
        confidence_display = f" ({confidence:.0%})" if confidence else ""
    else:
        badge_color = "#6c757d"
        badge_bg = "#e9ecef"
        source_label = "❓ Неизвестно"
        confidence_display = ""

    # Рендеринг бейджа
    badge_html = f"""
    <span style="
        background-color: {badge_bg};
        color: {badge_color};
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 11px;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    ">
        {doc_type}{confidence_display}
        <span style="opacity: 0.7; font-weight: 400; font-size: 10px;">{source_label}</span>
    </span>
    """
    container.markdown(badge_html, unsafe_allow_html=True)

    # Кнопка изменения если классификация от LLM с низкой уверенностью или pending
    if (source == "llm" and confidence and confidence < 0.85) or pending:
        if container.button("✏️ Изменить тип", key=f"edit_class_{file_data.get('file_id')}"):
            # Показываем модальное окно выбора типа
            _show_classification_editor(file_data, container)


def _show_classification_editor(file_data: dict, container) -> None:
    """Модальное окно для изменения типа документа."""
    from core.services.redis_client import get_redis_client
    import json
    from datetime import datetime, timezone

    file_id = file_data.get("file_id")
    current_type = file_data.get("metadata", {}).get("document_type") or file_data.get("llm_classification_type")
    allowed_types = ["dogovor", "schet", "tovarnaya_nakladnaya", "schet_protokol", "unknown"]

    with container.form(key=f"classify_form_{file_id}"):
        st.caption("📋 Выберите тип документа:")
        selected = st.selectbox(
            "Тип документа",
            options=allowed_types,
            index=allowed_types.index(current_type) if current_type in allowed_types else 0,
            label_visibility="collapsed"
        )
        comment = st.text_input("Комментарий (опционально)", placeholder="Почему этот тип?")

        submitted = st.form_submit_button("✅ Подтвердить")

        if submitted:
            # Отправляем ответ в Redis
            redis = get_redis_client()
            response = {
                "type": "llm_classification_response",
                "version": "1.0",
                "file_id": file_id,
                "document_type": selected,
                "user_comment": comment or None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            redis.publish("ui:llm_responses", json.dumps(response, ensure_ascii=False))

            # Обновляем UI
            st.success(f"✅ Тип изменён на: {selected}")
            st.rerun()