import streamlit as st
from StreamlitLogic.file_info import render_file_info
from StreamlitLogic.binary_image import render_binary_image
from StreamlitLogic.parameters import render_parameters  # Импорт новой вкладки

# Заголовок всего приложения
st.set_page_config(page_title="Мой OCR-анализатор", layout="wide")
st.title("🚀 Многофункциональный анализ файлов")

# Создаём вкладки (теперь три вкладки)
tab1, tab2, tab3 = st.tabs([
    "Информация о файле",
    "Бинарное изображение",
    "Параметры"  # Новая вкладка для настройки порога
])

with tab1:
    render_file_info()

with tab2:
    render_binary_image()

with tab3:
    render_parameters()