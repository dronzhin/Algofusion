# ui/pages/main_page.py
"""
Главная страница приложения
"""
import streamlit as st
from typing import Any, List, Dict
from utils import setup_logger
from ui.components.log_viewer import render_log_viewer
from ui.components.stats_panel import render_stats_panel
from ui.components.filter_panel import render_filter_panel
from ui.components.file_row import render_file_row

logger = setup_logger("ui.pages.main_page")


def render_main_page(state: Any) -> None:
    """
    Рендерит главную страницу мониторинга.

    Args:
        state: Объект состояния приложения
    """
    logger.info("Рендеринг главной страницы")

    # Боковая панель
    _render_sidebar(state)

    st.title("📂 Панель мониторинга обработки файлов")

    # Верхние блоки: Процесс и Статистика
    col_process, col_stats = st.columns(2)

    with col_process:
        _render_process_block(state)

    with col_stats:
        _render_stats_block(state)

    st.divider()

    # Реестр файлов
    st.subheader("📄 Реестр файлов")
    _render_file_registry(state)


def _render_sidebar(state: Any) -> None:
    """Рендерит боковую панель настроек"""
    with st.sidebar:
        st.header("⚙️ Настройки обработки")

        accuracy_level = st.selectbox(
            "Уровень точности распознавания",
            ["Высокая точность (>98%)", "Средняя точность (>95%)", "Низкая точность (>90%)"],
            key="sidebar_accuracy"
        )

        st.divider()
        st.info(f"🎯 Активный режим: {accuracy_level}")
        st.toggle("Автоматическая отправка в 1С", value=True)
        st.caption("Изменение настроек применится к новым файлам.")

        logger.debug(f"Настройки сайдбара: точность={accuracy_level}")


def _render_process_block(state: Any) -> None:
    """Рендерит блок процесса обработки"""
    st.subheader("⚙️ Процесс обработки")

    # Системные логи (пример)
    system_logs = [
        {"time": "18:35", "status": "ОК", "msg": "получен новый ХХХ.pdf"},
        {"time": "18:35", "status": "ОК", "msg": "предобработка ХХХ.pdf: определено 16 документов"},
        {"time": "18:35", "status": "ERROR", "msg": "(2) уверенность классификации ХХХ 80%"},
    ]

    # Объединяем с логами экспорта из состояния
    all_logs = system_logs + state.export_logs
    render_log_viewer(all_logs, "📋 Журнал событий")


def _render_stats_block(state: Any) -> None:
    """Рендерит блок статистики"""
    import pandas as pd

    stats = {
        "total": "1,240",
        "total_delta": "+12",
        "processed": "850",
        "processed_delta": "+5",
        "errors": "12",
        "errors_delta": "-2",
        "chart_data": pd.DataFrame({
            'Час': range(0, 10),
            'Файлов/час': [10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
        }).set_index('Час')
    }

    render_stats_panel(stats)


def _render_file_registry(state: Any) -> None:
    """Рендерит реестр файлов"""
    # Применяем фильтры
    filter_date, accuracy_threshold, accuracy_type = render_filter_panel(state)

    filtered_indices = _apply_filters(state.file_data, filter_date, accuracy_threshold)

    st.markdown(f"**Найдено файлов:** {len(filtered_indices)} из {len(state.file_data.get('Имя файла', []))}")

    # Заголовки таблицы
    headers = ["Дата", "Имя файла", "Статус", "Тип файла", "Метрики", "Файл", "Правка", "XML", "Экспорт в 1С"]
    header_cols = st.columns([2, 2.5, 2, 1.5, 1.5, 1.5, 1.5, 1.5, 2])

    for col, header in zip(header_cols, headers):
        col.markdown(f"**{header}**")

    st.divider()

    # Строки файлов
    for idx in filtered_indices:
        file_data = {key: state.file_data[key][idx] for key in state.file_data.keys()}
        cols = st.columns([2, 2.5, 2, 1.5, 1.5, 1.5, 1.5, 1.5, 2])

        render_file_row(file_data, idx, state, cols)
        st.divider()

    if len(filtered_indices) == 0:
        st.warning("⚠️ По выбранным фильтрам файлы не найдены.")


def _apply_filters(file_data: Dict, filter_date, accuracy_threshold: int) -> List[int]:
    """Применяет фильтры к данным и возвращает индексы подходящих файлов"""
    num_rows = len(file_data.get("Имя файла", []))
    filtered_indices = []

    for idx in range(num_rows):
        include = True

        # Фильтр по дате
        if filter_date is not None:
            try:
                file_date_str = file_data["Дата"][idx].split(" ")[0]
                from datetime import datetime
                file_date = datetime.strptime(file_date_str, "%d.%m.%Y").date()
                if file_date != filter_date:
                    include = False
            except Exception as e:
                logger.warning(f"Ошибка парсинга даты для индекса {idx}: {e}")

        # Фильтр по точности
        if include and accuracy_threshold < 100:
            try:
                metric_val = int(file_data["Метрики"][idx].replace('%', ''))
                if metric_val > accuracy_threshold:
                    include = False
            except Exception as e:
                logger.warning(f"Ошибка парсинга метрики для индекса {idx}: {e}")

        if include:
            filtered_indices.append(idx)

    logger.debug(f"Фильтрация: найдено {len(filtered_indices)} из {num_rows}")
    return filtered_indices