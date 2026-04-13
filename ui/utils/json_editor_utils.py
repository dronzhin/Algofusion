# ui/utils/json_editor_utils.py
"""
Утилиты для редактора JSON от LLM.
"""

import json
from typing import Dict, Any
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
from shared.utils.logger import setup_logger

logger = setup_logger("ui.utils.json_editor_utils")


def init_edit_state(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Инициализирует состояние редактирования: плоский dict."""
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
        data: Dict[str, Any],
        prefix: str,
        file_id: str,
        session_state,
        level: int = 0
) -> None:
    """Рекурсивно рендерит поля для редактирования."""
    indent = "  " * level

    for key, value in data.items():
        if key.startswith("_"):
            continue

        full_key = f"{prefix}.{key}" if prefix else key
        widget_key = f"edit_{file_id}_{full_key}"

        if isinstance(value, dict) and value:
            with st.expander(f"{indent}📦 {key}", expanded=(level == 0)):
                render_editable_fields(value, full_key, file_id, session_state, level + 1)
        elif isinstance(value, dict):
            st.markdown(f"{indent}**{key}**")
            st.caption(f"{indent}📭 Пустой объект")
        else:
            st.markdown(f"{indent}**{key}**")
            state_key = f"llm_edit_{file_id}"
            current_value = session_state.get(state_key, {}).get(full_key, value)

            if isinstance(value, bool):
                new_value = st.checkbox("Значение", value=bool(current_value), key=widget_key,
                                        label_visibility="collapsed")
            elif isinstance(value, int):
                new_value = st.number_input("Значение", value=int(current_value) if str(current_value).isdigit() else 0,
                                            step=1, key=widget_key, label_visibility="collapsed")
            elif isinstance(value, float):
                new_value = st.number_input("Значение", value=float(current_value) if current_value else 0.0, step=0.01,
                                            format="%.2f", key=widget_key, label_visibility="collapsed")
            elif isinstance(value, list):
                json_str = json.dumps(current_value, ensure_ascii=False) if current_value else "[]"
                new_value = st.text_area("Значение (список)", value=json_str, height=80, key=widget_key,
                                         label_visibility="collapsed")
            else:
                str_value = str(current_value) if current_value is not None else ""
                new_value = st.text_input("Значение", value=str_value, key=widget_key, label_visibility="collapsed",
                                          placeholder="введите значение...")

            if state_key not in session_state:
                session_state[state_key] = {}
            session_state[state_key][full_key] = new_value
            st.divider()


def collect_edited_values(
        original_data: Dict[str, Any],
        edited_state: Dict[str, Any],
        prefix: str = ""
        ) -> Dict[str, Any]:
    """Восстанавливает вложенную структуру из плоского dict."""
    result = {}
    for key, original_value in original_data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if key.startswith("_"):
            result[key] = original_value
        elif isinstance(original_value, dict):
            result[key] = collect_edited_values(original_value, edited_state, full_key)
        else:
            if full_key in edited_state:
                edited_value = edited_state[full_key]
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

        file_status = redis_client.get_file_status(file_id)
        if file_status:
            if "metadata" not in file_status:
                file_status["metadata"] = {}
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
