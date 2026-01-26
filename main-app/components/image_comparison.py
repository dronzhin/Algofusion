# components/image_comparison.py
import streamlit as st
from PIL import Image
from io import BytesIO
import logging

# Создаём логгер для этого модуля
logger = logging.getLogger(f"app.{__name__}")

class ImageComparisonComponent:
    """
    Компонент для отображения двух изображений рядом для сравнения.
    """

    @staticmethod
    def render(
        image1_bytes: bytes,
        image2_bytes: bytes,
        label1: str = "Изображение 1",
        label2: str = "Изображение 2",
        caption: str = "### Сравнение изображений"
    ):
        """
        Отображает два изображения рядом.

        Args:
            image1_bytes (bytes): Байты первого изображения.
            image2_bytes (bytes): Байты второго изображения.
            label1 (str): Надпись над первым изображением.
            label2 (str): Надпись над вторым изображением.
            caption (str): Заголовок для блока сравнения.
        """
        st.markdown(caption)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**{label1}**")
            try:
                img1 = Image.open(BytesIO(image1_bytes))
                st.image(img1, width='stretch')
                logger.debug("Первое изображение успешно отображено")
            except Exception as e:
                logger.error(f"Ошибка отображения первого изображения: {e}")
                st.error(f"Ошибка отображения {label1}: {e}")

        with col2:
            st.markdown(f"**{label2}**")
            try:
                img2 = Image.open(BytesIO(image2_bytes))
                st.image(img2, width='stretch')
                logger.debug("Второе изображение успешно отображено")
            except Exception as e:
                logger.error(f"Ошибка отображения второго изображения: {e}")
                st.error(f"Ошибка отображения {label2}: {e}")
