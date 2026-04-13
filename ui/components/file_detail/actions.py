# ui/components/file_detail/actions.py
import json, streamlit as st
from typing import Dict, Any
from datetime import datetime, timezone
from shared.models.file import FileJob, FileStatus, ExportStatus
from ui.utils.components import render_action_button
from ui.utils.redis_helpers import safe_update_file_status, push_job_to_queue

def render_actions_section(file_id: str, file_data: Dict[str, Any], redis_client: Any) -> None:
    col1, col2, col3 = st.columns(3)
    with col1: _render_retry_button(file_id, file_data, redis_client)
    with col2: _render_export_button(file_id, file_data, redis_client)
    with col3: _render_delete_button(file_id, redis_client)

def _render_retry_button(file_id: str, file_data: Dict[str, Any], redis_client: Any) -> None:
    if render_action_button("🔄 Перезапустить", key=f"retry_{file_id}", disabled=file_data.get("status") in ["processing", "exporting"]):
        updates = {"status": FileStatus.PROCESSING.value, "current_module": "preprocess", "completed_modules": [], "retry_count": file_data.get("retry_count", 0) + 1, "updated_at": datetime.now(timezone.utc).isoformat()}
        job = FileJob.from_payload(json.dumps({**file_data, **updates}, ensure_ascii=False))
        if push_job_to_queue(redis_client, "preprocess", job.to_payload(), priority=10):
            st.success("✅ Перезапущено"); st.rerun()

def _render_export_button(file_id: str, file_data: Dict[str, Any], redis_client: Any) -> None:
    disabled = file_data.get("export_status") in [ExportStatus.SUCCESS.value, ExportStatus.EXPORTING.value] or file_data.get("status") != FileStatus.COMPLETED.value
    if render_action_button("📤 Экспорт в 1С", key=f"export_{file_id}", disabled=disabled):
        updates = {"export_status": ExportStatus.EXPORTING.value, "export_attempts": file_data.get("export_attempts", 0) + 1, "updated_at": datetime.now(timezone.utc).isoformat()}
        if safe_update_file_status(redis_client, file_id, updates):
            job = FileJob.from_payload(json.dumps({**file_data, **updates}, ensure_ascii=False))
            if push_job_to_queue(redis_client, "export", job.to_payload(), priority=5):
                st.success("✅ Экспорт запущен"); st.rerun()

def _render_delete_button(file_id: str, redis_client: Any) -> None:
    if render_action_button("🗑️ Удалить", key=f"delete_{file_id}", type="secondary"):
        if st.button("✅ Да, удалить", key=f"confirm_{file_id}"):
            if redis_client.delete_file_status(file_id):
                st.success("✅ Удалён"); st.session_state.update({"current_page": "main", "editing_file_index": None}); st.rerun()