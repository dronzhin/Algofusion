import streamlit as st
# from paddleocr import PaddleOCR  # если установлен

def render_ocr():
    st.subheader("🔍 OCR-распознавание")
    img = st.file_uploader("Загрузите изображение", type=["png", "jpg"], key="ocr_uploader")
    if img:
        st.image(img, caption="Загруженное изображение", width=300)
        # Здесь можно вызвать OCR-модель
        st.info("OCR-логика будет здесь")