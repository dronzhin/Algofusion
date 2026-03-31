# ui/components/stats_panel.py
"""
Компонент: Панель статистики.
Вертикальное отображение с детализацией по этапам обработки.
"""

import streamlit as st
from typing import Dict, Any, List

from shared.utils.logger import setup_logger
from ui.utils.components import render_metric_card

logger = setup_logger("ui.components.stats_panel")


def render_stats_panel(
        stats: Dict[str, Any],
        show_progress: bool = True,
        vertical: bool = True  # ← Параметр: вертикальный режим
) -> None:
    """
    Отображает статистику обработки файлов.

    Категории:
    - 📥 Загружено
    - 🔧 Предобработка
    - 🔤 OCR
    - 🧠 LLM
    - ⏳ Ожидают экспорта
    - 📤 Экспортировано в 1С
    """

    # 🔹 Формируем данные для отображения
    stats_items: List[Dict[str, Any]] = [
        {
            "label": "📥 Загружено",
            "value": stats.get("uploaded", 0),
            "help": "Файлы, ожидающие обработки",
            "color": "normal"
        },
        {
            "label": "🔧 Предобработка",
            "value": stats.get("preprocessing", 0),
            "help": "Файлы в процессе бинаризации/поворота",
            "color": "normal"
        },
        {
            "label": "🔤 OCR",
            "value": stats.get("ocr", 0),
            "help": "Файлы в процессе распознавания текста",
            "color": "normal"
        },
        {
            "label": "🧠 LLM",
            "value": stats.get("llm", 0),
            "help": "Файлы в процессе анализа через LLM",
            "color": "normal"
        },
        {
            "label": "⏳ Ожидают экспорта",
            "value": stats.get("pending_export", 0),
            "help": "Обработанные файлы, ожидающие экспорта в 1С",
            "color": "inverse"
        },
        {
            "label": "📤 Экспортировано в 1С",
            "value": stats.get("exported", 0),
            "help": "Файлы, успешно экспортированные в 1С",
            "color": "normal"
        },
        {
            "label": "❌ Ошибки",
            "value": stats.get("failed", 0),
            "help": "Файлы, обработка которых завершилась с ошибкой",
            "color": "inverse"
        },
    ]

    # 🔹 Режим отображения
    if vertical:
        _render_vertical_stats(stats_items, show_progress)
    else:
        _render_horizontal_stats(stats_items, show_progress)


def _render_vertical_stats(items: List[Dict[str, Any]], show_progress: bool) -> None:
    """
    Вертикальное отображение статистики (одна колонка) с цветовой индикацией.
    Название и значение — в одну строку, шрифт увеличен на 50%.
    """

    # 🔹 Цветовая схема для категорий (ключевые слова для поиска в label)
    color_map = {
        "Загружено": "#17a2b8",  # cyan
        "Предобработка": "#6610f2",  # purple
        "OCR": "#fd7e14",  # orange
        "LLM": "#e83e8c",  # pink
        "Ожидают": "#6c757d",  # gray
        "Экспортировано": "#28a745",  # green
        "Ошибки": "#dc3545",  # red
    }

    with st.container(border=True):
        st.markdown("##### 📊 Статистика обработки")

        for item in items:
            # 🔹 Определяем цвет по метке (поиск ключевого слова)
            label_key = next((k for k in color_map if k in item["label"]), None)
            value_color = color_map.get(label_key, "#1f77b4")  # fallback: синий

            # 🔹 Увеличиваем шрифт на 50%: 13px → 20px (label), 20px → 30px (value)
            # 🔹 Название и значение — в одну строку через flexbox
            st.markdown(f"""
            <div style="
                margin-bottom: 10px;
                padding: 6px 10px;
                border-radius: 4px;
                background-color: #f8f9fa;
                border-left: 4px solid {value_color};
                display: flex;
                justify-content: space-between;
                align-items: center;
            ">
                <div style="
                    font-size: 20px;
                    font-weight: 600;
                    color: #333;
                    flex: 1;
                ">
                    {item['label']}
                </div>
                <div style="
                    font-size: 30px;
                    font-weight: 700;
                    color: {value_color};
                    min-width: 60px;
                    text-align: right;
                ">
                    {item['value']}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Прогресс-бар успешности (если включён)
        if show_progress:
            st.divider()
            success_rate = _calculate_success_rate(items)

            # Цвет прогресс-бара в зависимости от успешности
            progress_color = "#28a745" if success_rate >= 90 else "#ffc107" if success_rate >= 70 else "#dc3545"

            st.markdown(f"""
            <div style="
                font-size: 16px;
                font-weight: 600;
                color: {progress_color};
                margin-bottom: 6px;
            ">
                ✨ Успешность обработки: {success_rate}%
            </div>
            """, unsafe_allow_html=True)

            st.progress(success_rate / 100)


def _render_horizontal_stats(items: List[Dict[str, Any]], show_progress: bool) -> None:
    """Горизонтальное отображение (старый режим, для совместимости)."""

    # Группируем элементы по 3 в ряд
    cols = st.columns(3)

    for idx, item in enumerate(items):
        col = cols[idx % 3]
        with col:
            render_metric_card(
                label=item["label"],
                value=item["value"],
                help=item.get("help"),
                delta_color=item.get("color", "normal")
            )

    # Прогресс-бар
    if show_progress:
        st.divider()
        success_rate = _calculate_success_rate(items)
        st.progress(success_rate / 100)
        st.caption(f"✨ Успешность: {success_rate}%")


def _calculate_success_rate(items: List[Dict[str, Any]]) -> float:
    """
    Рассчитывает процент успешной обработки.

    Формула: экспортировано / (экспортировано + ошибки) * 100
    """
    exported = next((i["value"] for i in items if "Экспортировано" in i["label"]), 0)
    failed = next((i["value"] for i in items if "Ошибки" in i["label"]), 0)

    total = exported + failed
    if total == 0:
        return 100.0  # Нет завершённых = 100% успешности

    return round((exported / total) * 100, 1)