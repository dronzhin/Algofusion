import streamlit as st
from StreamlitLogic.file_info import render_file_info
from StreamlitLogic.ocr_processor import render_ocr

# Заголовок всего приложения
st.set_page_config(page_title="Мой OCR-анализатор", layout="wide")
st.title("🚀 Многофункциональный анализ файлов")

# Навигация (можно через sidebar, tabs или selectbox)
option = st.sidebar.selectbox(
    "Выберите функцию:",
    ["Информация о файле", "OCR-распознавание"]
)

if option == "Информация о файле":
    render_file_info()
elif option == "OCR-распознавание":
    render_ocr()