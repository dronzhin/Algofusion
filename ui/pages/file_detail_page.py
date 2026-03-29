"""
РЎС‚СЂР°РЅРёС†Р° РґРµС‚Р°Р»РµР№ С„Р°Р№Р»Р°.
РСЃРїРѕР»СЊР·СѓРµС‚ С†РµРЅС‚СЂР°Р»РёР·РѕРІР°РЅРЅС‹Рµ СѓС‚РёР»РёС‚С‹ РёР· ui/utils/* РґР»СЏ СѓСЃС‚СЂР°РЅРµРЅРёСЏ РґСѓР±Р»РёСЂРѕРІР°РЅРёСЏ.
"""

# ============================================================================
# РРњРџРћР РўР«
# ============================================================================

import streamlit as st
import json  # в†ђ Р”РћР‘РђР’Р›Р•РќРћ: С‚СЂРµР±СѓРµС‚СЃСЏ РґР»СЏ json.dumps
from typing import Dict, Any, Optional
from datetime import datetime, timezone  # в†ђ Р”РћР‘РђР’Р›Р•РќРћ: С‚СЂРµР±СѓРµС‚СЃСЏ РґР»СЏ datetime.now(timezone.utc)

from shared.utils.logger import setup_logger
from shared.models.file import FileJob, FileStatus, ExportStatus
from ui.utils.constants import MODULES_ORDER, FILE_STATUS_CONFIG, EXPORT_STATUS_CONFIG, UI_CONFIG
from ui.utils.formatters import (
    format_datetime_full,
    format_file_size_human,
    render_status_badge,
    render_export_status_badge,
    calculate_module_progress,
)
from ui.utils.components import (
    error_handler,
    render_section_header,
    render_action_button,
    render_empty_state,
)
from ui.utils.redis_helpers import (
    safe_get_all_files,
    safe_update_file_status,
    push_job_to_queue,
    safe_get_file_status,
)

logger = setup_logger("ui.pages.file_detail_page")


# ============================================================================
# РћРЎРќРћР’РќРђРЇ Р¤РЈРќРљР¦РРЇ
# ============================================================================

def render_file_detail_page(session_state) -> None:
    """
    Р РµРЅРґРµСЂРёС‚ СЃС‚СЂР°РЅРёС†Сѓ РґРµС‚Р°Р»РµР№ С„Р°Р№Р»Р°.

    Args:
        session_state: Р­РєР·РµРјРїР»СЏСЂ SessionState РґР»СЏ РЅР°РІРёРіР°С†РёРё Рё РґР°РЅРЅС‹С…
    """
    with error_handler("file_detail_page", "РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё РґРµС‚Р°Р»РµР№ С„Р°Р№Р»Р°"):
        file_index = session_state.editing_file_index
        redis_client = session_state.redis_client
        file_service = session_state.file_service

        # Р’Р°Р»РёРґР°С†РёСЏ РІС…РѕРґРЅС‹С… РґР°РЅРЅС‹С…
        if file_index is None or not redis_client:
            st.error("вќЊ Р¤Р°Р№Р» РЅРµ РІС‹Р±СЂР°РЅ")
            _render_back_button(session_state)
            return

        files = safe_get_all_files(redis_client)
        if file_index is None or file_index >= len(files):
            st.error("вќЊ Р¤Р°Р№Р» РЅРµ РЅР°Р№РґРµРЅ")
            _render_back_button(session_state)
            return

        file_data = files[file_index]
        file_id = file_data.get("file_id")

        logger.info(f"Р РµРЅРґРµСЂРёРЅРі РґРµС‚Р°Р»РµР№ С„Р°Р№Р»Р°: {file_id}")

        # Р—Р°РіРѕР»РѕРІРѕРє Рё РЅР°РІРёРіР°С†РёСЏ
        st.title("рџ“‹ Р”РµС‚Р°Р»Рё С„Р°Р№Р»Р°")
        _render_back_button(session_state)
        st.divider()

        # РћСЃРЅРѕРІРЅР°СЏ РёРЅС„РѕСЂРјР°С†РёСЏ (3 РєРѕР»РѕРЅРєРё)
        col1, col2, col3 = st.columns(3)

        with col1:
            _render_file_info_col(file_data)

        with col2:
            _render_status_col(file_data)  # в†ђ РРЎРџР РђР’Р›Р•РќРћ: file_data

        with col3:
            _render_export_col(file_data)  # в†ђ РРЎРџР РђР’Р›Р•РќРћ: file_data

        st.divider()

        # РџСЂРѕРіСЂРµСЃСЃ РїРѕ РјРѕРґСѓР»СЏРј
        render_section_header("рџ“€ РџСЂРѕРіСЂРµСЃСЃ РѕР±СЂР°Р±РѕС‚РєРё")
        _render_module_progress(file_data)

        st.divider()

        # РСЃС‚РѕСЂРёСЏ РѕР±СЂР°Р±РѕС‚РєРё
        render_section_header("рџ“њ РСЃС‚РѕСЂРёСЏ РѕР±СЂР°Р±РѕС‚РєРё")
        _render_history(file_data)

        st.divider()

        # Р¤Р°Р№Р»С‹ РІ СЃС‚СЂСѓРєС‚СѓСЂРµ
        render_section_header("рџ“‚ Р¤Р°Р№Р»С‹ РІ СЃС‚СЂСѓРєС‚СѓСЂРµ")
        _render_file_structure(file_id, file_service)

        st.divider()

        # Р”РµР№СЃС‚РІРёСЏ
        render_section_header("вљЎ Р”РµР№СЃС‚РІРёСЏ")
        _render_actions(file_id, file_data, redis_client)


# ============================================================================
# Р’РЎРџРћРњРћР“РђРўР•Р›Р¬РќР«Р• Р¤РЈРќРљР¦РР
# ============================================================================

def _render_back_button(session_state) -> None:
    """РљРЅРѕРїРєР° РІРѕР·РІСЂР°С‚Р° Рє СЂРµРµСЃС‚СЂСѓ."""
    if st.button("в†ђ Р’РµСЂРЅСѓС‚СЊСЃСЏ Рє СЂРµРµСЃС‚СЂСѓ", key="back_to_list"):
        session_state.current_page = "main"
        session_state.editing_file_index = None
        st.rerun()


def _render_file_info_col(file_data: Dict[str, Any]) -> None:
    """Р РµРЅРґРµСЂРёС‚ РєРѕР»РѕРЅРєСѓ СЃ РѕСЃРЅРѕРІРЅРѕР№ РёРЅС„РѕСЂРјР°С†РёРµР№ Рѕ С„Р°Р№Р»Рµ."""
    st.markdown("### рџ“Ѓ РћСЃРЅРѕРІРЅР°СЏ РёРЅС„РѕСЂРјР°С†РёСЏ")
    st.markdown(f"**ID:** `{file_data.get('file_id', 'unknown')}`")
    st.markdown(f"**РРјСЏ:** {file_data.get('original_filename', 'Unknown')}")
    st.markdown(f"**РўРёРї:** `{file_data.get('file_type', 'unknown')}`")
    st.markdown(f"**Р Р°Р·РјРµСЂ:** {format_file_size_human(file_data.get('file_size', 0))}")

    # Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ РјРµС‚Р°РґР°РЅРЅС‹Рµ РµСЃР»Рё РµСЃС‚СЊ
    metadata = file_data.get('metadata', {})
    if metadata:
        with st.expander("рџ“¦ РњРµС‚Р°РґР°РЅРЅС‹Рµ", expanded=False):
            for key, value in metadata.items():
                st.markdown(f"**{key}:** {value}")


def _render_status_col(file_data: Dict[str, Any]) -> None:  # в†ђ РРЎРџР РђР’Р›Р•РќРћ: file_data: Dict
    """Р РµРЅРґРµСЂРёС‚ РєРѕР»РѕРЅРєСѓ СЃРѕ СЃС‚Р°С‚СѓСЃРѕРј РѕР±СЂР°Р±РѕС‚РєРё."""
    st.markdown("### рџ“Љ РЎС‚Р°С‚СѓСЃ РѕР±СЂР°Р±РѕС‚РєРё")

    status = file_data.get("status", "unknown")
    # в†ђ FIX: unsafe_allow_html=True РґР»СЏ СЂРµРЅРґРµСЂРёРЅРіР° С†РІРµС‚РЅС‹С… Р±РµР№РґР¶РµР№
    st.markdown(f"**РЎС‚Р°С‚СѓСЃ:** {render_status_badge(status)}", unsafe_allow_html=True)

    current_module = file_data.get("current_module")
    module_display = f"`{current_module}`" if current_module else "вЂ”"
    st.markdown(f"**РњРѕРґСѓР»СЊ:** {module_display}")

    st.markdown(f"**РЎРѕР·РґР°РЅ:** {format_datetime_full(file_data.get('created_at'))}")
    st.markdown(f"**РћР±РЅРѕРІР»С‘РЅ:** {format_datetime_full(file_data.get('updated_at'))}")

    retry_count = file_data.get("retry_count", 0)
    max_retries = file_data.get("max_retries", 3)
    if retry_count > 0:
        st.caption(f"рџ”„ РџРѕРїС‹С‚РєРё: {retry_count}/{max_retries}")


def _render_export_col(file_data: Dict[str, Any]) -> None:  # в†ђ РРЎРџР РђР’Р›Р•РќРћ: file_data: Dict
    """Р РµРЅРґРµСЂРёС‚ РєРѕР»РѕРЅРєСѓ СЃРѕ СЃС‚Р°С‚СѓСЃРѕРј СЌРєСЃРїРѕСЂС‚Р° РІ 1РЎ."""
    st.markdown("### рџ“¤ Р­РєСЃРїРѕСЂС‚ РІ 1РЎ")

    export_status = file_data.get("export_status", "pending")
    # в†ђ FIX: unsafe_allow_html=True
    st.markdown(f"**РЎС‚Р°С‚СѓСЃ:** {render_export_status_badge(export_status)}", unsafe_allow_html=True)

    st.markdown(f"**РџРѕРїС‹С‚РѕРє:** {file_data.get('export_attempts', 0)}")

    export_error = file_data.get("export_error")
    if export_error:
        st.error(f"вќЊ {export_error}")

    exported_at = file_data.get("exported_at")
    if exported_at:
        st.caption(f"вњ… Р­РєСЃРїРѕСЂС‚РёСЂРѕРІР°РЅ: {format_datetime_full(exported_at)}")

    doc_id = file_data.get("document_1c_id")
    if doc_id:
        st.caption(f"рџ†” Р”РѕРєСѓРјРµРЅС‚ 1РЎ: `{doc_id}`")


def _render_module_progress(file_data: Dict[str, Any]) -> None:
    """
    Р РµРЅРґРµСЂРёС‚ РїСЂРѕРіСЂРµСЃСЃ РїРѕ РјРѕРґСѓР»СЏРј РѕР±СЂР°Р±РѕС‚РєРё.
    РСЃРїРѕР»СЊР·СѓРµС‚ РѕР±С‰СѓСЋ С„СѓРЅРєС†РёСЋ calculate_module_progress РёР· utils.
    """
    completed = set(file_data.get("completed_modules", []))
    current = file_data.get("current_module")

    progress, status_texts = calculate_module_progress(completed, current)

    st.progress(progress / 100)
    st.caption(" | ".join(status_texts))

    # Р”РµС‚Р°Р»Рё РїРѕ РєР°Р¶РґРѕРјСѓ РјРѕРґСѓР»СЋ
    with st.expander("рџ”Ќ Р”РµС‚Р°Р»Рё РїРѕ РјРѕРґСѓР»СЏРј", expanded=False):
        for module in MODULES_ORDER:
            if module in completed:
                st.markdown(f"вњ… **{module}** вЂ” Р·Р°РІРµСЂС€С‘РЅ")
            elif current == module:
                st.markdown(f"рџ”„ **{module}** вЂ” РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ")
            else:
                st.markdown(f"вЏі **{module}** вЂ” РѕР¶РёРґР°РµС‚")


def _render_history(file_data: Dict[str, Any]) -> None:
    """Р РµРЅРґРµСЂРёС‚ РёСЃС‚РѕСЂРёСЋ РѕР±СЂР°Р±РѕС‚РєРё С„Р°Р№Р»Р°."""
    history = file_data.get("history", [])

    if not history:
        render_empty_state("РСЃС‚РѕСЂРёСЏ РїСѓСЃС‚Р° вЂ” РѕР±СЂР°Р±РѕС‚РєР° РµС‰С‘ РЅРµ РЅР°С‡РёРЅР°Р»Р°СЃСЊ")
        return

    # РџРѕРєР°Р·С‹РІР°РµРј РїРѕСЃР»РµРґРЅРёРµ Р·Р°РїРёСЃРё СЃ СѓС‡С‘С‚РѕРј Р»РёРјРёС‚Р°
    display_limit = UI_CONFIG["max_logs_display"]
    for record in reversed(history[-display_limit:]):
        _render_history_record(record)


def _render_history_record(record: Dict[str, Any]) -> None:
    """Р РµРЅРґРµСЂРёС‚ РѕРґРЅСѓ Р·Р°РїРёСЃСЊ РёСЃС‚РѕСЂРёРё."""
    timestamp = format_datetime_full(record.get("timestamp"))
    module = record.get("module", "unknown")
    action = record.get("action", "unknown")
    success = record.get("success", False)
    error = record.get("error")
    duration = record.get("duration_seconds")

    emoji = "вњ…" if success else "вќЊ"
    duration_str = f" ({duration:.2f}СЃ)" if duration else ""

    st.markdown(f"{emoji} **{timestamp}** вЂ” `{module}`: {action}{duration_str}")

    if error:
        st.caption(f"рџ”ґ РћС€РёР±РєР°: {error}")


def _render_file_structure(file_id: str, file_service) -> None:
    """Р РµРЅРґРµСЂРёС‚ СЃС‚СЂСѓРєС‚СѓСЂСѓ С„Р°Р№Р»РѕРІ РЅР° РґРёСЃРєРµ."""
    if not file_service:
        render_empty_state("вљ пёЏ FileService РЅРµ РґРѕСЃС‚СѓРїРµРЅ")
        return

    with error_handler("file_structure", "РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ СЃС‚СЂСѓРєС‚СѓСЂС‹ С„Р°Р№Р»РѕРІ"):
        file_info = file_service.get_file_info(file_id, file_data.get("original_filename"), file_data.get("storage_dir"))

        if not file_info:
            render_empty_state("вљ пёЏ РРЅС„РѕСЂРјР°С†РёСЏ Рѕ С„Р°Р№Р»Рµ РЅРµ РЅР°Р№РґРµРЅР° РЅР° РґРёСЃРєРµ")
            return

        directories = file_info.get("directories", {})
        if not directories:
            render_empty_state("рџ“­ РџР°РїРєРё РїСѓСЃС‚С‹Рµ")
            return

        for folder, info in directories.items():
            file_count = info.get("file_count", 0)
            with st.expander(f"рџ“Ѓ {folder} ({file_count} С„Р°Р№Р»РѕРІ)", expanded=False):
                st.caption(f"рџ“Ќ `{info.get('path', '')}`")

                files = info.get("files", [])
                if files:
                    for filename in files[:20]:  # Р›РёРјРёС‚ РЅР° РѕС‚РѕР±СЂР°Р¶РµРЅРёРµ
                        st.markdown(f"рџ“„ `{filename}`")
                    if len(files) > 20:
                        st.caption(f"... Рё РµС‰С‘ {len(files) - 20} С„Р°Р№Р»РѕРІ")
                else:
                    st.caption("рџ“­ РџСѓСЃС‚Рѕ")


def _render_actions(file_id: str, file_data: Dict[str, Any], redis_client) -> None:
    """Р РµРЅРґРµСЂРёС‚ РєРЅРѕРїРєРё РґРµР№СЃС‚РІРёР№ СЃ С„Р°Р№Р»РѕРј."""
    col1, col2, col3 = st.columns(3)

    with col1:
        _render_retry_button(file_id, file_data, redis_client)

    with col2:
        _render_export_button(file_id, file_data, redis_client)

    with col3:
        _render_delete_button(file_id, redis_client)


def _render_retry_button(file_id: str, file_data: Dict[str, Any], redis_client) -> None:
    """РљРЅРѕРїРєР° РїРµСЂРµР·Р°РїСѓСЃРєР° РѕР±СЂР°Р±РѕС‚РєРё."""
    status = file_data.get("status", "")
    disabled = status in ["processing", "exporting"]

    if render_action_button(
            "рџ”„ РџРµСЂРµР·Р°РїСѓСЃС‚РёС‚СЊ",
            key=f"retry_{file_id}",
            disabled=disabled,
            help="РЎР±СЂРѕСЃРёС‚СЊ РїСЂРѕРіСЂРµСЃСЃ Рё РЅР°С‡Р°С‚СЊ РѕР±СЂР°Р±РѕС‚РєСѓ Р·Р°РЅРѕРІРѕ" if not disabled else "Р¤Р°Р№Р» СѓР¶Рµ РѕР±СЂР°Р±Р°С‚С‹РІР°РµС‚СЃСЏ"
    ):
        _handle_retry_action(file_id, file_data, redis_client)


def _handle_retry_action(
        file_id: str,
        file_data: Dict[str, Any],  # в†ђ РРЎРџР РђР’Р›Р•РќРћ: file_data: Dict[str, Any]
        redis_client: Any
) -> None:
    """РћР±СЂР°Р±РѕС‚С‡РёРє РґРµР№СЃС‚РІРёСЏ РїРµСЂРµР·Р°РїСѓСЃРєР°."""
    try:
        # в†ђ FIX: РџРѕР»СѓС‡Р°РµРј С‚РµРєСѓС‰РµРµ РІСЂРµРјСЏ РѕРґРёРЅ СЂР°Р·
        retry_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        updates = {
            "status": FileStatus.PROCESSING.value,
            "current_module": "preprocess",
            "completed_modules": [],
            "retry_count": file_data.get("retry_count", 0) + 1,
            "errors": file_data.get("errors", []) + [f"Retry initiated at {retry_timestamp}"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        job_data = {**file_data, **updates}

        # в†ђ FIX: РЎРµСЂРёР°Р»РёР·СѓРµРј Рё РїР°СЂСЃРёРј С‡РµСЂРµР· from_payload РґР»СЏ РєРѕРЅРІРµСЂС‚Р°С†РёРё СЃС‚СЂРѕРє РІ Enum
        payload = json.dumps(job_data, ensure_ascii=False)
        job = FileJob.from_payload(payload)

        if push_job_to_queue(redis_client, "preprocess", job.to_payload(), priority=10):
            st.success("вњ… РћР±СЂР°Р±РѕС‚РєР° РїРµСЂРµР·Р°РїСѓС‰РµРЅР° СЃ РІС‹СЃРѕРєРёРј РїСЂРёРѕСЂРёС‚РµС‚РѕРј")
            st.rerun()
        else:
            st.error("вќЊ РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ Р·Р°РґР°С‡Сѓ РІ РѕС‡РµСЂРµРґСЊ")

    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РїРµСЂРµР·Р°РїСѓСЃРєРµ РѕР±СЂР°Р±РѕС‚РєРё {file_id}: {e}", exc_info=True)
        st.error(f"вќЊ РћС€РёР±РєР°: {e}")


def _render_export_button(file_id: str, file_data: Dict[str, Any], redis_client) -> None:
    """РљРЅРѕРїРєР° СЌРєСЃРїРѕСЂС‚Р° РІ 1РЎ."""
    export_status = file_data.get("export_status", "")
    file_status = file_data.get("status", "")

    # Р‘Р»РѕРєРёСЂСѓРµРј РµСЃР»Рё: СѓР¶Рµ СЌРєСЃРїРѕСЂС‚РёСЂРѕРІР°РЅ, РІ РїСЂРѕС†РµСЃСЃРµ СЌРєСЃРїРѕСЂС‚Р°, РёР»Рё С„Р°Р№Р» РЅРµ Р·Р°РІРµСЂС€С‘РЅ
    disabled = (
            export_status == ExportStatus.SUCCESS.value or
            export_status == ExportStatus.EXPORTING.value or
            file_status != FileStatus.COMPLETED.value
    )

    help_text = "РћС‚РїСЂР°РІРёС‚СЊ С„Р°Р№Р» РЅР° СЌРєСЃРїРѕСЂС‚ РІ 1РЎ"
    if export_status == ExportStatus.SUCCESS.value:
        help_text = "вњ… РЈР¶Рµ СЌРєСЃРїРѕСЂС‚РёСЂРѕРІР°РЅ"
    elif file_status != FileStatus.COMPLETED.value:
        help_text = "вЏі РЎРЅР°С‡Р°Р»Р° Р·Р°РІРµСЂС€РёС‚Рµ РѕР±СЂР°Р±РѕС‚РєСѓ С„Р°Р№Р»Р°"

    if render_action_button(
            "рџ“¤ Р­РєСЃРїРѕСЂС‚ РІ 1РЎ",
            key=f"export_{file_id}",
            disabled=disabled,
            help=help_text
    ):
        _handle_export_action(file_id, file_data, redis_client)


def _handle_export_action(
        file_id: str,
        file_data: Dict[str, Any],  # в†ђ РРЎРџР РђР’Р›Р•РќРћ: file_data: Dict[str, Any]
        redis_client: Any
) -> None:
    """РћР±СЂР°Р±РѕС‚С‡РёРє РґРµР№СЃС‚РІРёСЏ СЌРєСЃРїРѕСЂС‚Р°."""
    try:
        updates = {
            "export_status": ExportStatus.EXPORTING.value,
            "export_attempts": file_data.get("export_attempts", 0) + 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if not safe_update_file_status(redis_client, file_id, updates):
            st.error("вќЊ РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ СЃС‚Р°С‚СѓСЃ СЌРєСЃРїРѕСЂС‚Р°")
            return

        # в†ђ FIX: РЎРѕР·РґР°С‘Рј Job С‡РµСЂРµР· from_payload
        job_data = {**file_data, **updates}
        payload = json.dumps(job_data, ensure_ascii=False)  # в†ђ FIX: Р±С‹Р»Рѕ ensure_allow_ascii
        job = FileJob.from_payload(payload)

        if push_job_to_queue(redis_client, "export", job.to_payload(), priority=5):
            st.success("вњ… Р­РєСЃРїРѕСЂС‚ Р·Р°РїСѓС‰РµРЅ")
            st.rerun()
        else:
            st.error("вќЊ РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ Р·Р°РґР°С‡Сѓ СЌРєСЃРїРѕСЂС‚Р° РІ РѕС‡РµСЂРµРґСЊ")

    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё Р·Р°РїСѓСЃРєРµ СЌРєСЃРїРѕСЂС‚Р° {file_id}: {e}", exc_info=True)
        st.error(f"вќЊ РћС€РёР±РєР°: {e}")


def _render_delete_button(file_id: str, redis_client) -> None:
    """РљРЅРѕРїРєР° СѓРґР°Р»РµРЅРёСЏ С„Р°Р№Р»Р° СЃ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµРј."""
    if render_action_button(
            "рџ—‘пёЏ РЈРґР°Р»РёС‚СЊ",
            key=f"delete_{file_id}",
            type="secondary",
            help="вљ пёЏ Р‘РµР·РІРѕР·РІСЂР°С‚РЅРѕ СѓРґР°Р»РёС‚СЊ С„Р°Р№Р» Рё РІСЃРµ Р°СЂС‚РµС„Р°РєС‚С‹"
    ):
        # РџРѕРєР°Р·С‹РІР°РµРј РјРѕРґР°Р»СЊРЅРѕРµ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ
        st.warning("вљ пёЏ РџРѕРґС‚РІРµСЂРґРёС‚Рµ СѓРґР°Р»РµРЅРёРµ")
        col_yes, col_no = st.columns(2)

        with col_yes:
            if st.button("вњ… Р”Р°, СѓРґР°Р»РёС‚СЊ", key=f"confirm_delete_{file_id}", type="primary"):
                _handle_delete_action(file_id, redis_client)

        with col_no:
            if st.button("вќЊ РћС‚РјРµРЅР°", key=f"cancel_delete_{file_id}"):
                st.rerun()


def _handle_delete_action(file_id: str, redis_client) -> None:
    """РћР±СЂР°Р±РѕС‚С‡РёРє РґРµР№СЃС‚РІРёСЏ СѓРґР°Р»РµРЅРёСЏ."""
    try:
        # РЈРґР°Р»СЏРµРј СЃС‚Р°С‚СѓСЃ РёР· Redis
        if redis_client.delete_file_status(file_id):
            st.success("вњ… Р¤Р°Р№Р» СѓРґР°Р»С‘РЅ РёР· СЂРµРµСЃС‚СЂР°")
            # Р’РѕР·РІСЂР°С‰Р°РµРј Рє СЃРїРёСЃРєСѓ
            st.session_state.current_page = "main"
            st.session_state.editing_file_index = None
            st.rerun()
        else:
            st.error("вќЊ РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ С„Р°Р№Р»")

    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё СѓРґР°Р»РµРЅРёРё С„Р°Р№Р»Р° {file_id}: {e}", exc_info=True)
        st.error(f"вќЊ РћС€РёР±РєР°: {e}")