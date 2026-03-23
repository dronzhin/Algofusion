# ui/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY ui/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код в образ
COPY shared/ ./shared/
COPY core/ ./core/
COPY ui/ ./ui/

# Настройка окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true

# Порт Streamlit
EXPOSE 8501

# Запуск
CMD ["streamlit", "run", "ui/app.py"]