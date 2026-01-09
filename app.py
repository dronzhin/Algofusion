import streamlit as st

st.title("📄 Информация о загруженном файле")

uploaded_file = st.file_uploader("Загрузите файл", accept_multiple_files=False)

if uploaded_file is not None:
    file_name = uploaded_file.name
    file_size = uploaded_file.size
    file_type = uploaded_file.type if uploaded_file.type else "Неизвестен"

    st.subheader("Информация о файле:")
    st.write(f"**Имя файла:** `{file_name}`")
    st.write(f"**Размер:** {file_size} байт ({file_size / 1024:.2f} КБ)")
    st.write(f"**MIME-тип:** `{file_type}`")

    if file_type.startswith("text/") or file_name.endswith((".txt", ".csv", ".log")):
        try:
            content = uploaded_file.getvalue().decode("utf-8")[:500]
            st.text_area("Первые 500 символов содержимого:", content, height=150)
        except UnicodeDecodeError:
            st.info("Файл не является текстовым (не удалось декодировать как UTF-8).")
else:
    st.info("Пожалуйста, загрузите файл.")