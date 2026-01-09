import streamlit as st

def render_file_info():
    st.subheader("📄 Анализ файла")
    uploaded = st.file_uploader("Загрузите файл", key="file_info_uploader")
    if uploaded:
        st.write(f"Имя: {uploaded.name}")
        st.write(f"Размер: {uploaded.size} байт")