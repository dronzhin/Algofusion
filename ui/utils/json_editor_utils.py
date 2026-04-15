"""
Утилиты для редактора JSON от LLM.
✅ Визуально улучшенный интерфейс + отслеживание изменений + быстрый сброс
✅ Полный функционал сохранён: вложенность, списки, сохранение, Redis, compact_mode
"""

import json
import streamlit as st
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime, timezone
from shared.utils.logger import setup_logger

try:
    from ui.config.field_labels import get_field_label
except ImportError:
    def get_field_label(key: str, prefix: str = "") -> str:
        return key.replace("_", " ").capitalize()

logger = setup_logger("ui.utils.json_editor_utils")

# =============================================================================
# 🔹 СТИЛИ: Современный, чистый UI для Streamlit
# =============================================================================
_EDITOR_CSS = """
<style>
.json-editor-card {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 6px 0;
    border: 1px solid #e9ecef;
    transition: all 0.2s ease;
}
.json-editor-card:hover {
    border-color: #ced4da;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04);
}
.json-modified {
    background: #e8f5e9 !important;
    border-color: #81c784 !important;
}
.json-field-label {
    font-weight: 600;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.json-reset-btn {
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 4px;
    color: #6c757d;
    font-size: 12px;
}
.json-reset-btn:hover {
    background: #e9ecef;
    color: #212529;
}
.stExpander {
    border-radius: 8px !important;
    background: #f8f9fa !important;
}
</style>
"""


def _inject_css():
    if "json_css_injected" not in st.session_state:
        st.markdown(_EDITOR_CSS, unsafe_allow_html=True)
        st.session_state.json_css_injected = True


# =============================================================================
# 🔹 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================
def _get_type_icon(value: Any) -> str:
    if isinstance(value, bool): return "✅"
    if isinstance(value, int): return "🔢"
    if isinstance(value, float): return "📊"
    if isinstance(value, list): return "📋"
    if isinstance(value, dict): return "📁"
    return "📝"


def _render_reset_button(field_key: str, original_value: Any, session_state: Any) -> None:
    edit_state = session_state.get("llm_edit_state", {})
    current = edit_state.get(field_key, original_value)
    is_modified = current != original_value and not (current is None and original_value == "")

    if is_modified:
        st.markdown(
            f'<button class="json-reset-btn" title="Сбросить к оригиналу" '
            f'onclick="document.querySelector(\'[data-key=\"{field_key}\"]\').dispatchEvent(new Event(\'change\'))">↺</button>',
            unsafe_allow_html=True
        )
        # Streamlit-альтернатива без JS:
        if st.button("↺", key=f"reset_{field_key}", help="Сбросить к оригиналу", use_container_width=False):
            if "llm_edit_state" in session_state:
                session_state["llm_edit_state"][field_key] = original_value
                st.rerun()


def _is_field_modified(field_key: str, original_value: Any, session_state: Any) -> bool:
    current = session_state.get("llm_edit_state", {}).get(field_key, original_value)
    if isinstance(original_value, (int, float, bool)):
        return current != original_value
    return str(current) != str(original_value)


# =============================================================================
# 🔹 ОСНОВНАЯ ЛОГИКА (ФУНКЦИОНАЛ ПОЛНОСТЬЮ СОХРАНЁН)
# =============================================================================
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
    _inject_css()
    if current_depth >= max_depth or not isinstance(data, dict):
        return

    for key, value in data.items():
        if key.startswith("_"):
            continue

        field_key = f"{prefix}.{key}" if prefix else key
        display_label = get_field_label(key, prefix)
        icon = _get_type_icon(value)

        if isinstance(value, dict):
            if value:
                exp_label = f"{icon} {display_label}"
                with st.expander(exp_label, expanded=False):
                    render_editable_fields(
                        value, field_key, file_id, session_state,
                        compact=compact, max_depth=max_depth, current_depth=current_depth + 1
                    )
            else:
                st.markdown(f"**{icon} {display_label}**")
                st.caption("📭 Пустой объект")

        elif isinstance(value, list):
            _render_list_editor(field_key, value, session_state, compact=compact)

        else:
            modified = _is_field_modified(field_key, value, session_state)
            card_class = "json-editor-card json-modified" if modified and current_depth == 0 else "json-editor-card"

            with st.container():
                st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

                # Заголовок + иконка + сброс
                col_title, col_reset = st.columns([4, 1])
                with col_title:
                    st.markdown(f'<div class="json-field-label">{icon} {display_label}</div>', unsafe_allow_html=True)
                with col_reset:
                    _render_reset_button(field_key, value, session_state)

                # Виджет ввода
                _render_value_editor(field_key, display_label, value, session_state, compact=compact)

                st.markdown('</div>', unsafe_allow_html=True)


def _render_value_editor(
        field_key: str,
        display_name: str,
        value: Any,
        session_state: Any,
        compact: bool = False
) -> None:
    current_value = session_state.get("llm_edit_state", {}).get(field_key, value)
    help_text = f"🔑 `{field_key}`"
    label_vis = "collapsed" if compact else "visible"

    if isinstance(value, bool):
        new_val = st.checkbox(display_name, value=bool(current_value), key=f"chk_{field_key}", help=help_text)
    elif isinstance(value, int):
        try:
            init_val = int(current_value)
        except:
            init_val = 0
        new_val = st.number_input(display_name, value=init_val, step=1, key=f"num_{field_key}", help=help_text,
                                  label_visibility=label_vis)
    elif isinstance(value, float):
        try:
            init_val = float(current_value)
        except:
            init_val = 0.0
        new_val = st.number_input(display_name, value=init_val, step=0.01, format="%.2f", key=f"num_{field_key}",
                                  help=help_text, label_visibility=label_vis)
    elif isinstance(value, list):
        json_str = json.dumps(current_value, ensure_ascii=False) if current_value else "[]"
        new_val = st.text_area(display_name, value=json_str, height=60 if compact else 100, key=f"txt_{field_key}",
                               help=help_text, label_visibility=label_vis)
    else:
        str_val = str(current_value) if current_value is not None else ""
        new_val = st.text_input(display_name, value=str_val, key=f"inp_{field_key}", help=help_text,
                                label_visibility=label_vis, placeholder="введите значение...")

    if "llm_edit_state" not in session_state:
        session_state["llm_edit_state"] = {}
    session_state["llm_edit_state"][field_key] = new_val


def _render_list_editor(field_key: str, value: List, session_state: Any, compact: bool = False) -> None:
    if not value:
        st.caption("📭 Пустой список")
        return

    list_name = field_key.split(".")[-1].split("[")[0]
    list_label = get_field_label(list_name, ".".join(field_key.split(".")[:-1]))

    with st.expander(f"📋 {list_label} ({len(value)} элем.)", expanded=False):
        for idx, item in enumerate(value):
            item_key = f"{field_key}[{idx}]"
            if isinstance(item, dict):
                st.markdown(f"**Элемент {idx + 1}**")
                render_editable_fields(item, item_key, "", session_state, compact=compact, current_depth=1)
            else:
                _render_value_editor(item_key, f"[{idx + 1}]", item, session_state, compact=compact)
            st.divider()


def collect_edited_values(original_data: Dict[str, Any], edited_state: Dict[str, Any], prefix: str = "") -> Dict[
    str, Any]:
    """Восстанавливает вложенную JSON-структуру из плоского dict."""
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
            try:
                if isinstance(original_value, bool):
                    result[key] = bool(edited_value)
                elif isinstance(original_value, int):
                    result[key] = int(edited_value)
                elif isinstance(original_value, float):
                    result[key] = float(edited_value)
                elif isinstance(original_value, list):
                    result[key] = json.loads(edited_value)
                else:
                    result[key] = str(edited_value)
            except Exception:
                result[key] = original_value
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