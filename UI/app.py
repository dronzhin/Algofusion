import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime, timedelta

# Настройка страницы на широкий режим
st.set_page_config(page_title="File Processor Dashboard", layout="wide")

# ==========================================
# ИНИЦИАЛИЗАЦИЯ SESSION STATE
# ==========================================
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'main'
if 'editing_file_index' not in st.session_state:
    st.session_state.editing_file_index = None
if 'json_data' not in st.session_state:
    st.session_state.json_data = {}
if 'export_pending' not in st.session_state:
    st.session_state.export_pending = None
if 'export_logs' not in st.session_state:
    st.session_state.export_logs = []
if 'filter_date' not in st.session_state:
    st.session_state.filter_date = None
if 'filter_accuracy_type' not in st.session_state:
    st.session_state.filter_accuracy_type = 'manual'
if 'filter_accuracy_manual' not in st.session_state:
    st.session_state.filter_accuracy_manual = 100
if 'filter_reset_counter' not in st.session_state:
    st.session_state.filter_reset_counter = 0

# Исходные данные (шаблон) - ДАТЫ РАСПРЕДЕЛЕНЫ ПО 2025 И 2026 ГОДАМ
INITIAL_FILE_DATA = {
    "Дата": [
        # 2025 год
        "15.01.2025 10:00", "22.01.2025 14:30", "05.02.2025 09:15",
        "18.02.2025 11:45", "03.03.2025 16:20", "21.03.2025 08:00",
        "10.04.2025 13:10", "28.04.2025 10:55", "12.05.2025 15:30",
        "30.05.2025 09:40", "14.06.2025 11:00", "25.06.2025 14:15",
        # 2026 год
        "08.01.2026 10:30", "19.01.2026 13:45", "02.02.2026 09:00",
        "17.02.2026 15:20", "05.03.2026 11:30", "22.03.2026 16:00"
    ],
    "Имя файла": [
        "invoice_001.pdf", "contract_A23.docx", "nakladnaya_789.pdf",
        "schet_456.pdf", "unknown_scan.jpg", "dogovor_B12.pdf",
        "invoice_002.pdf", "contract_A24.docx", "nakladnaya_790.pdf",
        "schet_457.pdf", "unknown_scan2.jpg", "dogovor_B13.pdf",
        "invoice_003.pdf", "contract_A25.docx", "nakladnaya_791.pdf",
        "schet_458.pdf", "unknown_scan3.jpg", "dogovor_B14.pdf"
    ],
    "Статус": [
        "🟢 Экспортирован в 1С", "🟡 Обработка", "🟢 Экспортирован в 1С",
        "🔴 Требует правки", "🔵 Новый", "🟢 Экспортирован в 1С",
        "🟢 Экспортирован в 1С", "🟡 Обработка", "🔴 Требует правки",
        "🔵 Новый", "🟢 Экспортирован в 1С", "🟡 Обработка",
        "🔴 Требует правки", "🔵 Новый", "🟣 Поправлен",
        "🟡 Обработка", "🔴 Требует правки", "🔵 Новый"
    ],
    "Тип файла": [
        "Счет", "Договор", "Товарная накладная",
        "Счет", "Не определен", "Договор",
        "Счет", "Договор", "Товарная накладная",
        "Счет", "Не определен", "Договор",
        "Счет", "Договор", "Товарная накладная",
        "Счет", "Не определен", "Договор"
    ],
    "Метрики": [
        "98%", "95%", "99%", "82%", "45%", "97%",
        "96%", "94%", "88%", "75%", "99%", "93%",
        "85%", "70%", "98%", "91%", "89%", "65%"
    ],
    "Экспорт в 1С": ["✅", "⏳", "✅", "❌", "⏸️", "✅",
                     "✅", "⏳", "❌", "⏸️", "✅", "⏳",
                     "❌", "⏸️", "✅", "⏳", "❌", "⏸️"]
}

if 'file_data' not in st.session_state:
    st.session_state.file_data = {k: v[:] for k, v in INITIAL_FILE_DATA.items()}

# ==========================================
# ДЕФОЛТНЫЙ JSON ДЛЯ РЕДАКТИРОВАНИЯ
# ==========================================
DEFAULT_JSON = {
    "document_id": "DOC-2023-001",
    "document_type": "invoice",
    "supplier_name": "ООО Ромашка",
    "supplier_inn": "1234567890",
    "total_amount": "15000.00",
    "currency": "RUB",
    "date": "2023-10-15",
    "items": [
        {"name": "Товар 1", "quantity": "10", "price": "1000.00"},
        {"name": "Товар 2", "quantity": "5", "price": "1000.00"}
    ],
    "confidence_score": "92",
    "classification": "Счет"
}


# ==========================================
# ФУНКЦИИ НАВИГАЦИИ
# ==========================================
def go_to_edit_page(file_index):
    st.session_state.current_page = 'edit'
    st.session_state.editing_file_index = file_index
    st.session_state.json_data = DEFAULT_JSON.copy()


def go_to_main_page():
    st.session_state.current_page = 'main'
    st.session_state.editing_file_index = None


# ==========================================
# ФУНКЦИЯ ДОБАВЛЕНИЯ ЛОГА
# ==========================================
def add_log(status, message):
    timestamp = datetime.now().strftime("%H:%M")
    st.session_state.export_logs.append({
        "time": timestamp,
        "status": status,
        "msg": message
    })
    if len(st.session_state.export_logs) > 20:
        st.session_state.export_logs = st.session_state.export_logs[-20:]


# ==========================================
# ФУНКЦИЯ ЭКСПОРТА В 1С
# ==========================================
def export_to_1c(file_index, confirm=False):
    file_name = st.session_state.file_data["Имя файла"][file_index]
    status = st.session_state.file_data["Статус"][file_index]

    if "Экспортирован" in status and not confirm:
        st.session_state.export_pending = file_index
        return

    if "Экспортирован" in status and confirm:
        add_log("ОК", f"Повторный экспорт файла {file_name} в 1С")
        st.session_state.export_pending = None
        return

    add_log("ОК", f"Начат экспорт файла {file_name} в 1С...")
    time.sleep(0.3)

    st.session_state.file_data["Статус"][file_index] = "🟢 Экспортирован в 1С"
    st.session_state.file_data["Экспорт в 1С"][file_index] = "✅"

    add_log("ОК", f"Файл {file_name} успешно экспортирован в 1С")
    st.session_state.export_pending = None


# ==========================================
# ФУНКЦИЯ ФИЛЬТРАЦИИ ДАННЫХ
# ==========================================
def filter_file_data(file_data, filter_date, accuracy_type, accuracy_manual, sidebar_accuracy):
    """Фильтрует данные по дате и точности (точность <= порога)"""
    num_rows = len(file_data["Имя файла"])
    filtered_indices = []

    # Определяем порог точности
    if accuracy_type == 'sidebar':
        if sidebar_accuracy == "Высокая точность (>98%)":
            accuracy_threshold = 98
        elif sidebar_accuracy == "Средняя точность (>95%)":
            accuracy_threshold = 95
        else:
            accuracy_threshold = 90
    else:
        accuracy_threshold = accuracy_manual

    for idx in range(num_rows):
        include = True

        # Фильтр по дате
        if filter_date is not None:
            file_date_str = file_data["Дата"][idx].split(" ")[0]
            try:
                file_date = datetime.strptime(file_date_str, "%d.%m.%Y")
                if file_date.date() != filter_date:
                    include = False
            except:
                pass

        # Фильтр по точности (показываем файлы с точностью <= порога)
        # Если порог 100%, пропускаем все файлы (фильтр отключен)
        if include and accuracy_threshold < 100:
            try:
                metric_val = int(file_data["Метрики"][idx].replace('%', ''))
                if metric_val > accuracy_threshold:
                    include = False
            except:
                pass

        if include:
            filtered_indices.append(idx)

    return filtered_indices


# ==========================================
# СТРАНИЦА РЕДАКТИРОВАНИЯ JSON
# ==========================================
def edit_page():
    st.title("✏️ Редактирование файла")

    file_index = st.session_state.editing_file_index
    file_name = st.session_state.file_data["Имя файла"][file_index]

    st.info(f"📄 Редактирование файла: **{file_name}**")
    st.subheader("📋 Данные документа")

    edited_values = {}

    def render_json_editor(data, prefix=""):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                with st.expander(f"📁 {key}", expanded=False):
                    render_json_editor(value, full_key)
            elif isinstance(value, list):
                with st.expander(f"📦 {key} (список)", expanded=False):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            with st.container(border=True):
                                st.markdown(f"**Элемент {i + 1}**")
                                render_json_editor(item, f"{full_key}[{i}]")
                        else:
                            edited_values[f"{full_key}[{i}]"] = st.text_input(
                                f"{full_key}[{i}]", value=str(item), key=f"input_{full_key}_{i}"
                            )
            else:
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.markdown(f"**{key}**")
                with col2:
                    edited_values[full_key] = st.text_input(
                        f"edit_{full_key}", value=str(value), key=f"txt_{full_key}", label_visibility="collapsed"
                    )

    render_json_editor(st.session_state.json_data)

    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💾 Сохранить", use_container_width=True, type="primary"):
            add_log("ОК", f"Файл {file_name} отредактирован пользователем")
            add_log("ОК", f"Статус файла {file_name} изменен на 'Поправлен'")

            st.session_state.file_data["Статус"][file_index] = "🟣 Поправлен"
            st.success("✅ Данные сохранены! Статус файла изменен на 'Поправлен'")
            st.balloons()
            go_to_main_page()
            st.rerun()
    with col2:
        if st.button("❌ Отмена", use_container_width=True):
            add_log("ERROR", f"Редактирование файла {file_name} отменено пользователем")
            st.warning("⚠️ Изменения не сохранены")
            go_to_main_page()
            st.rerun()
    with col3:
        if st.button("🔄 Сбросить", use_container_width=True):
            st.session_state.json_data = DEFAULT_JSON.copy()
            st.info("🔄 JSON сброшен к значениям по умолчанию")
            st.rerun()

    if st.button("← Вернуться на главную страницу"):
        go_to_main_page()
        st.rerun()


# ==========================================
# ГЛАВНАЯ СТРАНИЦА
# ==========================================
def main_page():
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

    st.title("📂 Панель мониторинга обработки файлов")

    col_process, col_stats = st.columns(2)

    # ==========================================
    # 1. ОКНО ПРОЦЕССА ОБРАБОТКИ
    # ==========================================
    with col_process:
        st.subheader("⚙️ Процесс обработки")

        log_container = st.container(border=True)

        with log_container:
            def render_log_line(timestamp, status, message):
                if status == "ОК":
                    color = "#28a745"
                    badge = "✅"
                else:
                    color = "#dc3545"
                    badge = "❌"

                html = f"""
                <div style="font-family: monospace; margin-bottom: 6px; font-size: 13px; border-bottom: 1px solid #f0f0f0; padding-bottom: 4px;">
                    <span style="color: #888;">{timestamp}</span> 
                    <span style="color: {color}; font-weight: bold;">{badge} {status}</span> 
                    <span style="color: #333;">{message}</span>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)

            system_logs = [
                {"time": "18:35", "status": "ОК", "msg": "получен новый ХХХ.pdf"},
                {"time": "18:35", "status": "ОК",
                 "msg": "предобработка ХХХ.pdf: определено 16 документов: 1, 2, 3...16"},
                {"time": "18:35", "status": "ОК", "msg": "(1) точность распознания ХХХ 92%"},
                {"time": "18:35", "status": "ОК", "msg": "(1) уверенность классификации ХХХ 98%"},
                {"time": "18:35", "status": "ОК", "msg": "(1) Статус: передан в 1С"},
                {"time": "18:35", "status": "ОК", "msg": "(2) точность распознания ХХХ 92%"},
                {"time": "18:35", "status": "ERROR", "msg": "(2) уверенность классификации ХХХ 80%"},
                {"time": "18:35", "status": "ERROR", "msg": "(2) Статус: ошибка классификации"},
            ]

            for log in system_logs:
                render_log_line(log["time"], log["status"], log["msg"])

            for log in st.session_state.export_logs:
                render_log_line(log["time"], log["status"], log["msg"])

    # ==========================================
    # 2. ОКНО СТАТИСТИКИ
    # ==========================================
    with col_stats:
        st.subheader("📊 Текущая статистика")
        m1, m2, m3 = st.columns(3)
        m1.metric(label="Всего файлов", value="1,240", delta="+12")
        m2.metric(label="Обработано", value="850", delta="+5")
        m3.metric(label="Ошибки", value="12", delta="-2", delta_color="inverse")
        chart_data = pd.DataFrame({'Час': range(0, 10), 'Файлов/час': [10, 15, 20, 25, 30, 35, 40, 45, 50, 55]})
        st.line_chart(chart_data.set_index('Час'))

    st.divider()

    # ==========================================
    # ФИЛЬТРЫ ПЕРЕД РЕЕСТРОМ ФАЙЛОВ
    # ==========================================
    st.subheader("📄 Реестр файлов")

    # Контейнер для фильтров
    filter_container = st.container(border=True)

    with filter_container:
        st.markdown("### 🔍 Фильтры")

        filter_col1, filter_col2, filter_col3 = st.columns(3)

        # Уникальные ключи для всех виджетов на основе счётчика сброса
        reset_counter = st.session_state.filter_reset_counter
        date_input_key = f"filter_date_input_{reset_counter}"
        radio_key = f"accuracy_type_radio_{reset_counter}"
        slider_key = f"accuracy_slider_{reset_counter}"

        # Фильтр по дате
        with filter_col1:
            st.markdown("**📅 Фильтр по дате**")
            filter_date = st.date_input(
                "Выберите дату",
                value=st.session_state.filter_date,
                key=date_input_key,
                help="Оставьте пустым для отображения всех дат"
            )
            st.session_state.filter_date = filter_date

        # Тип фильтра точности
        with filter_col2:
            st.markdown("**🎯 Источник точности**")
            radio_index = 0 if st.session_state.filter_accuracy_type == 'sidebar' else 1
            accuracy_type = st.radio(
                "Источник значения",
                ["Установленные значения", "Ручной ввод"],
                index=radio_index,
                key=radio_key,
                horizontal=True
            )
            st.session_state.filter_accuracy_type = 'sidebar' if accuracy_type == "Установленные значения" else 'manual'

        # Фильтр по точности
        with filter_col3:
            st.markdown("**📊 Максимальная точность**")
            if st.session_state.filter_accuracy_type == 'sidebar':
                sidebar_acc = st.session_state.get('sidebar_accuracy', 'Средняя точность (>95%)')
                if sidebar_acc == "Высокая точность (>98%)":
                    threshold = 98
                elif sidebar_acc == "Средняя точность (>95%)":
                    threshold = 95
                else:
                    threshold = 90
                st.info(f"≤{threshold}% (из настроек)")
                st.session_state.filter_accuracy_manual = threshold
            else:
                accuracy_manual = st.slider(
                    "Максимальный процент",
                    min_value=0,
                    max_value=100,
                    value=st.session_state.filter_accuracy_manual,
                    key=slider_key
                )
                st.session_state.filter_accuracy_manual = accuracy_manual
                st.markdown(f"≤**{accuracy_manual}%**")

        # Кнопки управления фильтрами
        filter_btn_col1, filter_btn_col2 = st.columns(2)
        with filter_btn_col1:
            if st.button("🔄 Сбросить фильтры", use_container_width=True, key="reset_filters_btn"):
                st.session_state.filter_reset_counter += 1
                st.session_state.filter_date = None
                st.session_state.filter_accuracy_manual = 100
                st.session_state.filter_accuracy_type = 'manual'
                st.rerun()

        # Отображение активных фильтров
        active_filters = []
        if st.session_state.filter_date is not None:
            active_filters.append(f"📅 Дата: {st.session_state.filter_date.strftime('%d.%m.%Y')}")

        if st.session_state.filter_accuracy_manual < 100:
            if st.session_state.filter_accuracy_type == 'sidebar':
                sidebar_acc = st.session_state.get('sidebar_accuracy', 'Средняя точность (>95%)')
                if sidebar_acc == "Высокая точность (>98%)":
                    threshold = 98
                elif sidebar_acc == "Средняя точность (>95%)":
                    threshold = 95
                else:
                    threshold = 90
                active_filters.append(f"🎯 Точность: ≤{threshold}%")
            else:
                active_filters.append(f"🎯 Точность: ≤{st.session_state.filter_accuracy_manual}%")

        if active_filters:
            st.success("✅ Активные фильтры: " + " | ".join(active_filters))
        else:
            st.info("ℹ️ Фильтры не применены — отображаются все файлы")

    # ==========================================
    # ПРИМЕНЕНИЕ ФИЛЬТРОВ
    # ==========================================
    sidebar_accuracy = st.session_state.get('sidebar_accuracy', 'Средняя точность (>95%)')
    filtered_indices = filter_file_data(
        st.session_state.file_data,
        st.session_state.filter_date,
        st.session_state.filter_accuracy_type,
        st.session_state.filter_accuracy_manual,
        sidebar_accuracy
    )

    st.markdown(f"**Найдено файлов:** {len(filtered_indices)} из {len(st.session_state.file_data['Имя файла'])}")

    # ==========================================
    # РЕЕСТР ФАЙЛОВ (ОТОБРАЖЕНИЕ ОТФИЛЬТРОВАННЫХ ДАННЫХ)
    # ==========================================
    header_cols = st.columns([2, 2.5, 2, 1.5, 1.5, 1.5, 1.5, 1.5, 2])
    headers = ["Дата", "Имя файла", "Статус", "Тип файла", "Метрики", "Файл", "Правка", "XML", "Экспорт в 1С"]
    for col, header in zip(header_cols, headers):
        col.markdown(f"**{header}**")

    st.divider()

    file_data = st.session_state.file_data

    for idx in filtered_indices:
        cols = st.columns([2, 2.5, 2, 1.5, 1.5, 1.5, 1.5, 1.5, 2])

        # Дата
        cols[0].markdown(f"<span style='color: #666; font-size: 13px;'>{file_data['Дата'][idx]}</span>",
                         unsafe_allow_html=True)

        # Имя файла
        cols[1].markdown(f"📄 {file_data['Имя файла'][idx]}")

        # Статус (с цветом)
        status = file_data['Статус'][idx]
        status_color = "#155724" if "Экспортирован" in status else \
            "#856404" if "Обработка" in status else \
                "#721c24" if "Требует правки" in status else \
                    "#004085" if "Новый" in status else \
                        "#5a3d7a" if "Поправлен" in status else "#333"
        cols[2].markdown(f"<span style='color: {status_color};'>{status}</span>", unsafe_allow_html=True)

        # Тип файла
        cols[3].markdown(file_data['Тип файла'][idx])

        # Метрики (с цветом)
        try:
            metric_val = int(file_data['Метрики'][idx].replace('%', ''))
            metric_color = "#155724" if metric_val >= 95 else "#856404" if metric_val >= 80 else "#721c24"
            cols[4].markdown(
                f"<span style='color: {metric_color}; font-weight: bold;'>{file_data['Метрики'][idx]}</span>",
                unsafe_allow_html=True)
        except:
            cols[4].markdown(file_data['Метрики'][idx])

        # Файл (ссылка-заглушка)
        cols[5].markdown("📄 [Открыть](#)")

        # Правка (АКТИВНАЯ КНОПКА)
        if cols[6].button("✏️ Править", key=f"edit_btn_{idx}", use_container_width=True):
            go_to_edit_page(idx)
            st.rerun()

        # XML (ссылка-заглушка)
        cols[7].markdown("📥 [Скачать](#)")

        # ЭКСПОРТ В 1С
        is_exported = "Экспортирован" in file_data['Статус'][idx]

        if st.session_state.export_pending == idx:
            cols[8].warning(f"⚠️ Файл уже экспортирован. Повторить?")
            confirm_col, cancel_col = cols[8].columns(2)
            with confirm_col:
                if st.button("✅ Да", key=f"confirm_export_{idx}", use_container_width=True):
                    export_to_1c(idx, confirm=True)
                    st.rerun()
            with cancel_col:
                if st.button("❌ Нет", key=f"cancel_export_{idx}", use_container_width=True):
                    st.session_state.export_pending = None
                    st.rerun()
        else:
            if is_exported:
                if cols[8].button("📤 Экспортирован", key=f"export_btn_{idx}", use_container_width=True):
                    export_to_1c(idx)
                    st.rerun()
            else:
                if cols[8].button("📤 Экспортировать", key=f"export_btn_{idx}", use_container_width=True,
                                  type="primary"):
                    export_to_1c(idx)
                    st.rerun()

        st.divider()

    # Если ничего не найдено
    if len(filtered_indices) == 0:
        st.warning("⚠️ По выбранным фильтрам файлы не найдены. Попробуйте изменить параметры фильтрации.")

    st.caption(
        "📌 Таблица доступна только для просмотра. Для редактирования данных используйте кнопку «Править» в соответствующей строке.")

    with st.expander("ℹ️ Описание статусов и действий"):
        st.markdown("""
        ### Статусы файлов:
        - 🟢 **Экспортирован в 1С** — файл успешно обработан и передан в систему
        - 🟡 **Обработка** — файл находится в процессе обработки
        - 🔴 **Требует правки** — обнаружены ошибки, требуется ручное вмешательство
        - 🔵 **Новый** — файл загружен, ожидает начала обработки
        - 🟣 **Поправлен** — файл был отредактирован пользователем

        ### Фильтры:
        - **Дата** — фильтрация по конкретной дате загрузки файла
        - **Точность** — максимальный процент уверенности распознавания
          - *Установленные значения* — использует значение из боковой панели (Высокая ≤98%, Средняя ≤95%, Низкая ≤90%)
          - *Ручной ввод* — позволяет задать произвольное значение от 0 до 100%
          - *100%* — показать все файлы (фильтр отключен)

        ### Действия:
        - **Файл** — открытие исходного файла для просмотра
        - **Править** — переход на страницу редактирования JSON
        - **XML** — скачивание сгенерированного XML файла
        - **Экспортировать** — отправка файла в 1С
        """)


# ==========================================
# МАРШРУТИЗАЦИЯ
# ==========================================
if st.session_state.current_page == 'main':
    main_page()
elif st.session_state.current_page == 'edit':
    edit_page()