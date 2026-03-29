"""Main operator dashboard page."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st

from shared.utils.logger import setup_logger
from ui.cache import CacheManager, get_files_from_redis_cached
from ui.state import SessionState
from ui.utils.constants import FILE_STATUS_CONFIG, MODULE_LABELS, MODULES_ORDER
from ui.utils.formatters import format_datetime_short, render_status_badge_safe

logger = setup_logger("ui.pages.main_page")

_KEY_AUTO_REFRESH = "_af_auto_refresh"
_KEY_REFRESH_INTERVAL = "_af_refresh_interval"
_KEY_LAST_REFRESH = "_af_last_refresh"
_KEY_CACHE_BUSTER = "_af_cache_buster"
_KEY_STATUS_FILTER = "_af_status_filter"
_KEY_SEARCH = "_af_search"
_KEY_DOC_TYPE = "_af_doc_type"


def render_main_page(session: SessionState) -> None:
    logger.info("Rendering main dashboard")
    _run_auto_refresh(session)

    redis_client = session.redis_client
    if not redis_client:
        st.error("Redis client is not available.")
        return

    _render_sidebar(session, redis_client)

    cache_key = st.session_state.get(_KEY_CACHE_BUSTER, "v1")
    raw_files = get_files_from_redis_cached(redis_client, _cache_key=cache_key)
    files = _prepare_files(raw_files)

    _render_dashboard_header(files)
    _render_kpi_filters(files)
    filtered_files = _filter_files(files)

    main_col, side_col = st.columns([3.6, 1.4], gap="large")
    with main_col:
        _render_documents_table(filtered_files, session)
    with side_col:
        _render_live_activity(session)
        _render_system_status(session, files)

    session.update_refresh_time()


def _run_auto_refresh(session: SessionState) -> None:
    enabled = st.session_state.get(_KEY_AUTO_REFRESH, True)
    if not enabled:
        return

    interval = float(st.session_state.get(_KEY_REFRESH_INTERVAL, 15))
    last = float(st.session_state.get(_KEY_LAST_REFRESH, 0.0))
    now = time.time()

    if now - last >= interval:
        st.session_state[_KEY_LAST_REFRESH] = now
        st.session_state[_KEY_CACHE_BUSTER] = f"v{now}"
        CacheManager.clear_data_cache()
        st.rerun()


def _prepare_files(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prepared = []
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["_index"] = index
        row["_doc_type"] = _infer_document_type(row)
        row["_display_stage"] = _display_stage(row)
        row["_display_status"] = row.get("status", "uploaded")
        prepared.append(row)

    prepared.sort(key=lambda x: _sort_key(x), reverse=True)
    return prepared


def _sort_key(file_data: Dict[str, Any]) -> str:
    return (
        file_data.get("updated_at")
        or file_data.get("created_at")
        or ""
    )


def _infer_document_type(file_data: Dict[str, Any]) -> str:
    filename = str(file_data.get("original_filename", "")).lower()
    if "invoice" in filename:
        return "Счет"
    if "payment" in filename:
        return "Платежное поручение"
    if "waybill" in filename:
        return "ТТН"
    if "account" in filename or "prot" in filename:
        return "Счет-протокол"
    return "Документ"


def _display_stage(file_data: Dict[str, Any]) -> str:
    status = file_data.get("status")
    current = file_data.get("current_module")
    completed = set(file_data.get("completed_modules", []))

    if status == "failed":
        return "Ошибка"
    if status == "exported":
        return "Выгружен в 1С"
    if status == "completed":
        return "Готов"
    if current:
        return MODULE_LABELS.get(current, current)
    if completed:
        last_module = next((m for m in reversed(MODULES_ORDER) if m in completed), None)
        if last_module:
            return MODULE_LABELS.get(last_module, last_module)
    return "Ожидает"


def _render_dashboard_header(files: List[Dict[str, Any]]) -> None:
    st.markdown("## Реестр документов")
    left, right = st.columns([3, 1])
    with left:
        st.caption("Загрузка, проверка и подготовка документов к выгрузке в 1С.")
    with right:
        st.caption(f"Документов в системе: {len(files)}")


def _render_kpi_filters(files: List[Dict[str, Any]]) -> None:
    stats = {
        "Все": len(files),
        "В обработке": sum(1 for f in files if f.get("status") == "processing"),
        "Требуют внимания": sum(1 for f in files if f.get("status") == "failed"),
        "Готовы": sum(1 for f in files if f.get("status") == "completed"),
        "Выгружены": sum(1 for f in files if f.get("status") == "exported"),
    }

    cols = st.columns(len(stats), gap="small")
    status_targets = {
        "Все": "all",
        "В обработке": "processing",
        "Требуют внимания": "failed",
        "Готовы": "completed",
        "Выгружены": "exported",
    }
    active_status = st.session_state.get(_KEY_STATUS_FILTER, "all")
    for col, (label, value) in zip(cols, stats.items()):
        with col:
            is_active = active_status == status_targets[label]
            button_label = f"{label}\n{value}"
            if st.button(button_label, key=f"kpi_{label}", use_container_width=True, type="primary" if is_active else "secondary"):
                st.session_state[_KEY_STATUS_FILTER] = status_targets[label]
                st.rerun()

    filter_col1, filter_col2, filter_col3 = st.columns([2.4, 1.4, 1], gap="small")
    with filter_col1:
        st.text_input(
            "Поиск",
            key=_KEY_SEARCH,
            placeholder="Имя файла, номер, тип документа",
            label_visibility="collapsed",
        )
    with filter_col2:
        all_doc_types = sorted({f["_doc_type"] for f in files})
        selected = st.selectbox(
            "Тип документа",
            ["Все"] + all_doc_types,
            key=_KEY_DOC_TYPE,
            label_visibility="collapsed",
        )
        if not selected:
            st.session_state[_KEY_DOC_TYPE] = "Все"
    with filter_col3:
        if st.button("Обновить", use_container_width=True):
            CacheManager.clear_data_cache()
            st.session_state[_KEY_CACHE_BUSTER] = f"v{time.time()}"
            st.rerun()


def _filter_files(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    search = st.session_state.get(_KEY_SEARCH, "").strip().lower()
    status_filter = st.session_state.get(_KEY_STATUS_FILTER, "all")
    doc_type = st.session_state.get(_KEY_DOC_TYPE, "Все")

    filtered = []
    for file_data in files:
        if status_filter != "all" and file_data.get("status") != status_filter:
            continue
        if doc_type not in (None, "", "Все") and file_data["_doc_type"] != doc_type:
            continue
        haystack = " ".join(
            [
                str(file_data.get("original_filename", "")),
                str(file_data.get("_doc_type", "")),
                str(file_data.get("current_module", "")),
                str(file_data.get("file_id", "")),
            ]
        ).lower()
        if search and search not in haystack:
            continue
        filtered.append(file_data)
    return filtered


def _render_documents_table(files: List[Dict[str, Any]], session: SessionState) -> None:
    st.markdown("### Документы")
    if not files:
        st.info("По текущим фильтрам документы не найдены.")
        return

    header = st.columns([3.0, 1.4, 1.6, 1.2, 1.4, 0.8], gap="small")
    labels = ["Файл", "Тип", "Этап", "Статус", "Обновлен", ""]
    for col, label in zip(header, labels):
        col.caption(label)

    for file_data in files:
        with st.container(border=True):
            cols = st.columns([3.0, 1.4, 1.6, 1.2, 1.4, 0.8], gap="small")
            cols[0].markdown(
                f"**{file_data.get('original_filename', 'Без имени')}**\n\n`{str(file_data.get('file_id', ''))[:8]}`"
            )
            cols[1].markdown(file_data["_doc_type"])
            cols[2].markdown(file_data["_display_stage"])
            render_status_badge_safe(file_data["_display_status"], cols[3])
            cols[4].markdown(format_datetime_short(file_data.get("updated_at") or file_data.get("created_at")))
            if cols[5].button("Открыть", key=f"open_{file_data.get('file_id')}", use_container_width=True):
                session.current_page = "detail"
                session.editing_file_index = file_data["_index"]
                st.rerun()


def _render_live_activity(session: SessionState) -> None:
    st.markdown("### Живой журнал")
    logs = list(reversed(session.get_logs(limit=8)))
    if not logs:
        st.caption("События появятся после загрузки и обработки документов.")
        return

    for record in logs:
        with st.container(border=True):
            st.caption(record.get("time", "--:--:--"))
            st.markdown(record.get("msg", ""))


def _render_system_status(session: SessionState, files: List[Dict[str, Any]]) -> None:
    st.markdown("### Система")
    redis_ok = "Да" if session.redis_client else "Нет"
    in_progress = sum(1 for f in files if f.get("status") == "processing")
    failed = sum(1 for f in files if f.get("status") == "failed")
    st.markdown(f"**Redis:** {redis_ok}")
    st.markdown(f"**В обработке:** {in_progress}")
    st.markdown(f"**Ошибки:** {failed}")
    st.markdown(f"**Автообновление:** {'Включено' if st.session_state.get(_KEY_AUTO_REFRESH, True) else 'Выключено'}")
    if session.last_refresh:
        st.caption(f"Последнее обновление: {session.last_refresh.strftime('%H:%M:%S')}")


def _render_sidebar(session: SessionState, redis_client: Any) -> None:
    with st.sidebar:
        st.markdown("### Панель")
        enabled = st.toggle("Автообновление", value=st.session_state.get(_KEY_AUTO_REFRESH, True))
        st.session_state[_KEY_AUTO_REFRESH] = enabled

        interval = st.slider(
            "Интервал, сек",
            min_value=5,
            max_value=60,
            value=int(st.session_state.get(_KEY_REFRESH_INTERVAL, 15)),
        )
        st.session_state[_KEY_REFRESH_INTERVAL] = float(interval)

        st.markdown("---")
        st.markdown("### Быстрые фильтры")
        if st.button("Все документы", use_container_width=True):
            st.session_state[_KEY_STATUS_FILTER] = "all"
            st.rerun()
        if st.button("Только ошибки", use_container_width=True):
            st.session_state[_KEY_STATUS_FILTER] = "failed"
            st.rerun()
        if st.button("Только в обработке", use_container_width=True):
            st.session_state[_KEY_STATUS_FILTER] = "processing"
            st.rerun()

        st.markdown("---")
        try:
            redis_client.client.ping()
            st.success("Redis подключен")
        except Exception:
            st.error("Redis недоступен")
