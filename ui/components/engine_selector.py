# ui/components/engine_selector.py
"""
Компонент: Выбор OCR и LLM движков с мгновенным применением через Redis.
🔹 Вертикальная компоновка для узкого сайдбара.
"""

import streamlit as st
import httpx
from datetime import datetime, timezone
from typing import List, Dict

from shared.utils.logger import setup_logger

logger = setup_logger("ui.components.engine_selector")

OCR_ENGINES = {
    "tesseract": "🔤 Tesseract (быстро, оффлайн)",
    "easyocr": "🧠 EasyOCR (качество, мультиязычный)",
    "surya": "⚡ Surya (современный, быстрый)",
    "glm": "🤖 GLM-OCR (премиум, контекстный)",
}


@st.cache_data(ttl=300)
def get_ollama_models(ollama_endpoint: str) -> List[Dict[str, str]]:
    """Получает список моделей из Ollama API."""
    try:
        url = f"{ollama_endpoint.rstrip('/')}/api/tags"
        with httpx.Client(timeout=10) as client:
            response = client.get(url)
            response.raise_for_status()
            models = response.json().get("models", [])
            return [{"name": m["name"], "size": m.get("size", 0)} for m in models]
    except Exception as e:
        logger.warning(f"⚠️ Не удалось получить модели из Ollama: {e}")
        return []


def _publish_settings_update(session, settings: Dict[str, str], channel: str) -> None:
    """Публикует обновление настроек в Redis для мгновенного применения."""
    try:
        event = {
            "type": "settings_updated",
            "settings": settings,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "ui"
        }
        session.redis_client.publish_event(channel, event)
        logger.info(f"✅ Настройки опубликованы в {channel}: {settings}")
    except Exception as e:
        logger.error(f"❌ Ошибка публикации настроек: {e}")


def render_engine_selector(session, key_prefix: str = "main") -> None:
    """
    Рендерит панель выбора OCR и LLM движков.
    🔹 Вертикальная компоновка для узкого сайдбара.
    """
    with st.expander("⚙️ Настройки обработки", expanded=False):

        # ====================================================================
        # 🔹 Блок 1: Выбор OCR-движка
        # ====================================================================
        st.subheader("🔤 OCR движок")

        current_ocr = session.get_filter(f"{key_prefix}_ocr_engine", ["tesseract"])[0]

        ocr_choice = st.selectbox(
            "Движок",
            options=list(OCR_ENGINES.keys()),
            format_func=lambda x: OCR_ENGINES[x],
            index=list(OCR_ENGINES.keys()).index(current_ocr) if current_ocr in OCR_ENGINES else 0,
            key=f"{key_prefix}_ocr_select",
            label_visibility="collapsed"  # ← Скрываем дублирующую метку
        )

        if ocr_choice != current_ocr:
            session.set_filter(f"{key_prefix}_ocr_engine", [ocr_choice])
            _publish_settings_update(
                session,
                {"ocr_engine": ocr_choice},
                channel="config:ocr:updates"
            )
            st.toast(f"✅ OCR: {OCR_ENGINES[ocr_choice]}", icon="🔄")
            session.invalidate_cache()

        # Языки (компактно)
        ocr_langs = session.get_filter(f"{key_prefix}_ocr_langs", ["rus", "eng"])
        available_langs = ["rus", "eng", "deu", "fra", "spa", "ita", "por", "chi_sim", "jpn"]
        selected_langs = st.multiselect(
            "Языки",
            options=available_langs,
            default=ocr_langs,
            key=f"{key_prefix}_ocr_langs",
            label_visibility="collapsed",
            placeholder="Выберите языки..."  # ← Подсказка вместо заголовка
        )
        if selected_langs != ocr_langs:
            session.set_filter(f"{key_prefix}_ocr_langs", selected_langs)
            _publish_settings_update(
                session,
                {"ocr_langs": selected_langs},
                channel="config:ocr:updates"
            )
            st.toast(f"✅ Языки: {', '.join(selected_langs)}", icon="🌐")
            session.invalidate_cache()

        st.divider()  # ← Визуальный разделитель

        # ====================================================================
        # 🔹 Блок 2: Выбор LLM-моделей из Ollama
        # ====================================================================
        st.subheader("🤖 LLM модели (Ollama)")

        ollama_endpoint = getattr(session.settings, "llm_endpoint", "http://ollama:11434")
        ollama_models = get_ollama_models(ollama_endpoint)
        model_names = [m["name"] for m in ollama_models] if ollama_models else ["qwen2.5:1.5b", "qwen2.5:7b",
                                                                                "llama3.1:8b"]

        current_classifier = session.get_filter(f"{key_prefix}_llm_classifier", ["qwen2.5:1.5b"])[0]
        current_extractor = session.get_filter(f"{key_prefix}_llm_extractor", ["qwen2.5:7b"])[0]

        # Модель для классификации
        st.caption("📋 Классификация документа")
        classifier_choice = st.selectbox(
            "Модель",
            options=model_names,
            index=model_names.index(current_classifier) if current_classifier in model_names else 0,
            key=f"{key_prefix}_llm_classifier",
            label_visibility="collapsed",
            help="Лёгкая модель для определения типа документа"
        )
        if classifier_choice != current_classifier:
            session.set_filter(f"{key_prefix}_llm_classifier", [classifier_choice])
            _publish_settings_update(
                session,
                {"llm_classifier_model": classifier_choice},
                channel="config:llm:updates"
            )
            st.toast(f"✅ Классификация: {classifier_choice}", icon="🎯")
            session.invalidate_cache()

        # Модель для экстракции
        st.caption("📝 Извлечение данных")
        extractor_choice = st.selectbox(
            "Модель",
            options=model_names,
            index=model_names.index(current_extractor) if current_extractor in model_names else 0,
            key=f"{key_prefix}_llm_extractor",
            label_visibility="collapsed",
            help="Мощная модель для извлечения структурированных данных"
        )
        if extractor_choice != current_extractor:
            session.set_filter(f"{key_prefix}_llm_extractor", [extractor_choice])
            _publish_settings_update(
                session,
                {"llm_extractor_model": extractor_choice},
                channel="config:llm:updates"
            )
            st.toast(f"✅ Экстракция: {extractor_choice}", icon="📤")
            session.invalidate_cache()

        # Кнопка обновления списка моделей
        st.divider()
        if st.button("🔄 Обновить список моделей", key=f"{key_prefix}_refresh_ollama", type="secondary",
                     use_container_width=True):
            get_ollama_models.clear()
            st.rerun()

        # Статус подключения к Ollama
        if ollama_models:
            st.success(f"✅ Ollama: {len(ollama_models)} моделей доступно")
        else:
            st.warning(f"⚠️ Нет подключения к {ollama_endpoint.split('://')[-1]}", icon="⚠️")


def get_selected_engines(session, key_prefix: str = "main") -> Dict[str, str]:
    """Возвращает текущие настройки движков."""
    return {
        "ocr_engine": session.get_filter(f"{key_prefix}_ocr_engine", ["tesseract"])[0],
        "ocr_langs": session.get_filter(f"{key_prefix}_ocr_langs", ["rus", "eng"]),
        "llm_classifier": session.get_filter(f"{key_prefix}_llm_classifier", ["qwen2.5:1.5b"])[0],
        "llm_extractor": session.get_filter(f"{key_prefix}_llm_extractor", ["qwen2.5:7b"])[0],
    }