"""
Утилиты для редактора JSON от LLM.
🔹 Единая реализация с поддержкой компактного режима
🔹 Русские метки полей через ui.config.field_labels
"""

import json
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
from shared.utils.logger import setup_logger

# 🔹 Импорт русских меток
from ui.config.field_labels import get_field_label

logger = setup_logger("ui.utils.json_editor_utils")


def init_edit_state(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Инициализирует плоское состояние редактирования."""
    state = {}
    for key, value in data.items():
        if key.startswith("_"):
            continue
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            state.update(init_edit_state(value, full_key))
        else:
            state[full_key] = value
    return state


def render_editable_fields(
    data: Any,
    prefix: str,
    file_id: str,
    session_state: Any,
    compact: bool = False,
    max_depth: int = 5,
    current_depth: int = 0
) -> None:
    """
    Рекурсивно рендерит поля для редактирования.
    🔹 Поддержка компактного режима
    🔹 Русские метки через get_field_label()
    """
    if current_depth >= max_depth:
        return

    if not isinstance(data, dict):
        return

    for key, value in data.items():
        if key.startswith("_"):
            continue

        field_key = f"{prefix}.{key}" if prefix else key

        # 🔹 Получаем русское название (или оригинал)
        try:
            display_label = get_field_label(key, prefix)
        except ImportError:
            display_label = key.replace("_", " ").capitalize()

        # 🔹 Заголовок поля
        if compact:
            st.markdown(f"**{display_label}**", help=f"🔑 `{field_key}`")
        else:
            st.markdown(f"### {display_label}")

        if isinstance(value, dict) and value:
            expander_label = f"▼ {display_label}" if compact else f"📁 {display_label}"
            with st.expander(expander_label, expanded=False):
                render_editable_fields(
                    value, field_key, file_id, session_state,
                    compact=compact, max_depth=max_depth, current_depth=current_depth + 1
                )
        elif isinstance(value, dict):
            st.caption("📭 Пустой объект")
        elif isinstance(value, list):
            _render_list_editor(field_key, value, session_state, compact=compact)
        else:
            _render_value_editor(field_key, display_label, value, session_state, compact=compact)

        if compact and current_depth == 0:
            st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid #eee;'>",
                        unsafe_allow_html=True)


def _render_value_editor(
    field_key: str,
    display_name: str,
    value: Any,
    session_state: Any,
    compact: bool = False
) -> None:
    """Рендерит поле ввода для простого значения."""
    state_key = f"edit_{field_key}"
    current_value = session_state.get(state_key, value)
    label_vis = "collapsed" if compact else "visible"

    if isinstance(value, bool):
        new_value = st.checkbox(
            display_name, value=bool(current_value),
            key=f"chk_{field_key}", label_visibility=label_vis
        )
    elif isinstance(value, int):
        new_value = st.number_input(
            display_name, value=int(current_value) if str(current_value).isdigit() else 0,
            step=1, key=f"num_{field_key}", label_visibility=label_vis
        )
    elif isinstance(value, float):
        try:
            val = float(current_value)
        except (ValueError, TypeError):
            val = 0.0
        new_value = st.number_input(
            display_name, value=val, step=0.01, format="%.2f",
            key=f"num_{field_key}", label_visibility=label_vis
        )
    elif isinstance(value, list):
        json_str = json.dumps(current_value, ensure_ascii=False) if current_value else "[]"
        new_value = st.text_area(
            display_name, value=json_str, height=60 if compact else 80,
            key=f"txt_{field_key}", label_visibility=label_vis
        )
    else:
        str_value = str(current_value) if current_value is not None else ""
        new_value = st.text_input(
            display_name, value=str_value,
            key=f"inp_{field_key}", label_visibility=label_vis,
            placeholder="введите..."
        )

    # Сохраняем в состояние
    if "llm_edit_state" not in session_state:
        session_state["llm_edit_state"] = {}
    session_state["llm_edit_state"][field_key] = new_value


def _render_list_editor(
    field_key: str,
    value: List,
    session_state: Any,
    compact: bool = False
) -> None:
    """Рендерит редактор для списка."""
    if not value:
        st.caption("📭 Пустой список")
        return

    for idx, item in enumerate(value):
        item_key = f"{field_key}[{idx}]"
        label = f"[{idx}]" if compact else f"📦 Элемент {idx}"

        if isinstance(item, (dict, list)):
            st.caption(f"{label}: {type(item).__name__} (редактирование отключено)")
        else:
            _render_value_editor(item_key, label, item, session_state, compact=compact)


def collect_edited_values(
    original_data: Dict[str, Any],
    edited_state: Dict[str, Any],
    prefix: str = ""
) -> Dict[str, Any]:
    """Восстанавливает вложенную структуру из плоского dict."""
    result = {}
    for key, original_value in original_data.items():
        if key.startswith("_"):
            result[key] = original_value
            continue

        full_key = f"{prefix}.{key}" if prefix else key

        if isinstance(original_value, dict):
            result[key] = collect_edited_values(original_value, edited_state, full_key)
        elif full_key in edited_state:
            edited_value = edited_state[full_key]
            # 🔹 Конвертация типов
            if isinstance(original_value, bool):
                result[key] = bool(edited_value)
            elif isinstance(original_value, int):
                result[key] = int(edited_value) if str(edited_value).isdigit() else original_value
            elif isinstance(original_value, float):
                try:
                    result[key] = float(edited_value)
                except ValueError:
                    result[key] = original_value
            elif isinstance(original_value, list):
                try:
                    result[key] = json.loads(edited_value)
                except json.JSONDecodeError:
                    result[key] = original_value
            else:
                result[key] = str(edited_value)
        else:
            result[key] = original_value
    return result


def handle_llm_json_save(
    file_id: str,
    json_file: Path,
    updated_data: Dict[str, Any],
    redis_client
) -> bool:
    """Сохраняет изменения в файл и Redis."""
    try:
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(updated_data, f, ensure_ascii=False, indent=2)

        # Обновляем метаданные в Redis
        file_status = redis_client.get_file_status(file_id)
        if file_status:
            file_status.setdefault("metadata", {})
            file_status["metadata"]["llm_data_edited"] = True
            file_status["metadata"]["llm_edited_at"] = datetime.now(timezone.utc).isoformat()
            redis_client.set_file_status(file_id, file_status)

        # Публикуем событие
        redis_client.publish_event("files:events", {
            "type": "llm_data_edited",
            "file_id": file_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения: {e}", exc_info=True)
        return False