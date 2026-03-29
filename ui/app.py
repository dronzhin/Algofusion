"""Streamlit entrypoint for the document processing UI."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

st.set_page_config(
    page_title="Algofusion",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="expanded",
)

from shared.config.settings import get_settings
from shared.utils.logger import setup_logger
from ui.cache import CacheManager, get_redis_client_cached
from ui.pages.file_detail_page import render_file_detail_page
from ui.pages.main_page import render_main_page
from ui.state import SessionState, get_session_state

logger = setup_logger("ui.app")


def _inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --af-bg: #f5f1e8;
            --af-card: #fffdf8;
            --af-border: #ddd4c4;
            --af-text: #2f2b26;
            --af-muted: #736b63;
            --af-primary: #486f67;
            --af-primary-2: #c46a3a;
            --af-ok: #2f6b55;
            --af-warn: #8a5a20;
            --af-bad: #8b3d34;
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(196,106,58,0.08), transparent 22%),
                radial-gradient(circle at left top, rgba(72,111,103,0.10), transparent 26%),
                var(--af-bg);
            color: var(--af-text);
        }

        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2rem;
        }

        section[data-testid="stSidebar"] {
            background: rgba(255, 253, 248, 0.82);
            border-right: 1px solid var(--af-border);
        }

        div[data-testid="stMetric"] {
            background: var(--af-card);
            border: 1px solid var(--af-border);
            border-radius: 16px;
            padding: 0.9rem 1rem;
        }

        div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button {
            border-radius: 12px;
            border: 1px solid var(--af-border);
            background: var(--af-card);
            color: var(--af-text);
            font-weight: 600;
        }

        div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button[kind="primary"] {
            background: var(--af-primary-2);
            color: white;
            border-color: var(--af-primary-2);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }

        .stTabs [data-baseweb="tab"] {
            background: rgba(255,253,248,0.8);
            border: 1px solid var(--af-border);
            border-radius: 12px;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .stTabs [aria-selected="true"] {
            background: white;
            border-color: var(--af-primary);
            color: var(--af-primary);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _process_redis_events(session: SessionState) -> None:
    try:
        redis_client = session.redis_client
        if not redis_client:
            return

        if session.pubsub is None:
            session.pubsub = redis_client.subscribe(["files:events", "1c:export"])

        message = session.pubsub.get_message(timeout=0.1)
        if not message or message["type"] != "message":
            return

        import json

        event = json.loads(message["data"])
        event_type = event.get("type", event.get("event", "unknown"))

        if event_type == "file_uploaded":
            session.add_log("OK", f"Новый файл: {event.get('filename')}")
            CacheManager.clear_data_cache()
        elif event_type == "module_completed":
            session.add_log("OK", f"Этап завершен: {event.get('module')}")
            CacheManager.clear_data_cache()
        elif event_type == "file_error":
            session.add_log("ERROR", f"Ошибка: {event.get('error')}")
        elif event_type == "export_completed":
            session.add_log("OK", "Выгрузка в 1С завершена")
            CacheManager.clear_data_cache()
    except Exception as exc:
        logger.warning("Redis event processing failed: %s", exc)


def _render_shell_header(session: SessionState) -> None:
    left, right = st.columns([4, 1], gap="large")
    with left:
        st.markdown("## Algofusion")
        st.caption("Сервис распознавания, проверки и подготовки документов к выгрузке в 1С.")
    with right:
        if session.last_refresh:
            st.caption(f"Обновлено: {session.last_refresh.strftime('%H:%M:%S')}")


def _render_footer() -> None:
    st.divider()
    left, right = st.columns([4, 1])
    with left:
        st.caption("Algofusion operator workspace")
    with right:
        if st.button("Очистить кэш", use_container_width=True):
            CacheManager.clear_all()
            st.rerun()


def main() -> None:
    logger.info("UI started")
    _inject_theme()

    session = get_session_state()
    if session.redis_client is None:
        session.redis_client = get_redis_client_cached()

    settings = get_settings()
    session.settings = settings

    from core.services.file_service import FileService

    if session.file_service is None:
        session.file_service = FileService(settings.shared_files_path)

    _process_redis_events(session)
    _render_shell_header(session)

    try:
        if session.current_page == "detail":
            render_file_detail_page(session)
        else:
            render_main_page(session)
    except Exception as exc:
        logger.error("UI rendering failed: %s", exc, exc_info=True)
        st.error(f"Ошибка интерфейса: {exc}")

    _render_footer()


if __name__ == "__main__":
    main()
