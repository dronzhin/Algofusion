# ui/utils/json_editor_utils.py
"""
Утилиты для редактора JSON от LLM.
🔹 Полная поддержка компактного режима и русских меток
🔹 Убрано дублирование заголовков для вложенных структур
🔹 Корректная работа со списками объектов
"""

import json
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
from shared.utils.logger import setup_logger
from ui.config.field_labels import get_field_label

logger = setup_logger("ui.utils.json_editor_utils")


def init_edit_state(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Инициализирует плоское состояние редактирования (включая списки объектов)."""
    state = {}
    if not isinstance(data, dict):
        return state

    for key, value in data.items():
        if key.startswith("_"):
            continue

        full_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            state.update(init_edit_state(value, full_key))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                item_key = f"{full_key}[{i}]"
                if isinstance(item, dict):
                    state.update(init_edit_state(item, item_key))
                else:
                    state[item_key] = item
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
    """Рекурсивно рендерит поля для редактирования с русскими метками."""
    if current_depth >= max_depth or not isinstance(data, dict):
        return

    for key, value in data.items():
        if key.startswith("_"):
            continue

        field_key = f"{prefix}.{key}" if prefix else key
        display_label = get_field_label(key, prefix)

        # 🔹 КОНТЕЙНЕРЫ: только Expander (без дублирующего заголовка)
        if isinstance(value, dict) and value:
            expander_label = f"▼ {display_label}" if compact else f"📁 {display_label}"
            with st.expander(expander_label, expanded=False):
                render_editable_fields(
                    value, field_key, file_id, session_state,
                    compact=compact, max_depth=max_depth, current_depth=current_depth + 1
                )

        elif isinstance(value, dict):
            st.markdown(f"**{display_label}**")
            st.caption("📭 Пустой объект")

        elif isinstance(value, list):
            _render_list_editor(field_key, value, session_state, compact=compact)

        # 🔹 ЛИСТЬЯ: Заголовок + Поле ввода
        else:
            if compact:
                st.markdown(f"**{display_label}**", help=f"🔑 `{field_key}`")
            else:
                st.markdown(f"### {display_label}")
            _render_value_editor(field_key, display_label, value, session_state, compact=compact)

        # Разделитель только для элементов верхнего уровня в компактном режиме
        if compact and current_depth == 0:
            st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)


def _render_value_editor(field_key: str, display_name: str, value: Any, session_state: Any, compact: bool = False) -> None:
    """Рендерит поле ввода для простого значения."""
    edit_state = session_state.get("llm_edit_state", {})
    current_value = edit_state.get(field_key, value)
    label_vis = "collapsed" if compact else "visible"
    widget_key = f"fld_{field_key}"

    if isinstance(value, bool):
        new_value = st.checkbox(display_name, value=bool(current_value), key=widget_key, label_visibility=label_vis)
    elif isinstance(value, (int, float)):
        step = 0.01 if isinstance(value, float) else 1
        fmt = "%.2f" if isinstance(value, float) else "%d"
        try:
            init_val = float(current_value) if isinstance(value, float) else int(current_value)
        except (ValueError, TypeError):
            init_val = 0.0 if isinstance(value, float) else 0
        new_value = st.number_input(display_name, value=init_val, step=step, format=fmt, key=widget_key, label_visibility=label_vis)
    elif isinstance(value, str) and len(str(value)) > 100:
        new_value = st.text_area(display_name, value=str(current_value), height=60 if compact else 80, key=widget_key, label_visibility=label_vis)
    else:
        new_value = st.text_input(display_name, value=str(current_value) if current_value is not None else "", key=widget_key, label_visibility=label_vis, placeholder="введите...")

    if "llm_edit_state" not in session_state:
        session_state["llm_edit_state"] = {}
    session_state["llm_edit_state"][field_key] = new_value


def _render_list_editor(field_key: str, value: List, session_state: Any, compact: bool = False) -> None:
    """Рендерит редактор для списка (поддерживает вложенные dict)."""
    if not value:
        st.caption("📭 Пустой список")
        return

    list_name = field_key.split(".")[-1]
    list_label = get_field_label(list_name, ".".join(field_key.split(".")[:-1]))

    with st.expander(f"📋 {list_label} ({len(value)} элем.)", expanded=False):
        for idx, item in enumerate(value):
            item_key = f"{field_key}[{idx}]"
            st.markdown(f"**Элемент {idx + 1}**")
            if isinstance(item, dict):
                render_editable_fields(item, item_key, "", session_state, compact=compact, current_depth=1)
            else:
                _render_value_editor(item_key, f"[{idx}]", item, session_state, compact=compact)
            st.divider()


def collect_edited_values(original_data: Dict[str, Any], edited_state: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Восстанавливает вложенную JSON-структуру из плоского dict."""
    result = {}
    for key, original_value in original_data.items():
        if key.startswith("_"):
            result[key] = original_value
            continue

        full_key = f"{prefix}.{key}" if prefix else key

        if isinstance(original_value, dict):
            result[key] = collect_edited_values(original_value, edited_state, full_key)
        elif isinstance(original_value, list):
            new_list = []
            for i, orig_item in enumerate(original_value):
                item_key = f"{full_key}[{i}]"
                if isinstance(orig_item, dict):
                    new_list.append(collect_edited_values(orig_item, edited_state, item_key))
                else:
                    val = edited_state.get(item_key, orig_item)
                    try: val = type(orig_item)(val)
                    except: val = orig_item
                    new_list.append(val)
            result[key] = new_list
        else:
            if full_key in edited_state:
                val = edited_state[full_key]
                try:
                    if isinstance(original_value, bool): result[key] = bool(val)
                    elif isinstance(original_value, int): result[key] = int(val)
                    elif isinstance(original_value, float): result[key] = float(val)
                    else: result[key] = str(val)
                except: result[key] = original_value
            else:
                result[key] = original_value
    return result


def handle_llm_json_save(file_id: str, json_file: Path, updated_data: Dict[str, Any], redis_client) -> bool:
    """Сохраняет изменения в файл и Redis."""
    try:
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(updated_data, f, ensure_ascii=False, indent=2)

        file_status = redis_client.get_file_status(file_id)
        if file_status:
            file_status.setdefault("metadata", {})
            file_status["metadata"]["llm_data_edited"] = True
            file_status["metadata"]["llm_edited_at"] = datetime.now(timezone.utc).isoformat()
            redis_client.set_file_status(file_id, file_status)

        redis_client.publish_event("files:events", {
            "type": "llm_data_edited",
            "file_id": file_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения: {e}", exc_info=True)
        return False