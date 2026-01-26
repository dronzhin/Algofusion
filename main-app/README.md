
# OCR-анализатор: Полное руководство по запуску и настройке

**Версия приложения:** 1.2.0
**Последнее обновление:** 26 января 2026 г.

---

## 📋 Описание проекта

Приложение для анализа и обработки файлов с использованием OCR, ML и LLM-модулей. Поддерживает:
- OCR (EasyOCR)
- Интеграцию с LLM (Llama3.2, Mistral)
- Многофункциональный UI на Streamlit
- Логирование и мониторинг

---

## 🛠 Предварительные требования

   - **Docker** (для контейнеризации) 
- **Git** (для управления версиями)

---

## 🏗 Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/dronzhin/algofusion.git
cd algofusion
```

### 2. Создание виртуального окружения

```bash
python -m venv venv
source venv/bin/activate  # Linux/MacOS
# или
venv\Scripts\activate     # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Установка системных зависимостей

**Для Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y pandoc libgl1-mesa-glx libglib2.0-0
```

**Для CentOS/RHEL:**
```bash
sudo yum install -y pandoc mesa-libGL libglib2.0
```

**Для Windows:**
Установите [Pandoc](https://pandoc.org/installing.html) и добавьте в PATH.

---

## 🚀 Варианты запуска

### ▶️ Базовый запуск

```bash
streamlit run app.py
```

**По умолчанию:**
- Порт: 8501
- Уровень логирования: DEBUG
- Файл логов: `./logs/app.log`
- API URL: `http://localhost:8000`

Приложение будет доступно по адресу: [http://localhost:8501](http://localhost:8501)

---

### 🔌 Запуск с настройкой порта

**Через параметры Streamlit:**
```bash
streamlit run app.py --server.port 8502
```

**Через переменные окружения:**
```bash
export PORT=8502
streamlit run app.py
```
> **Важно:** При изменении порта через переменную окружения `PORT`, Streamlit автоматически использует это значение.

---

### 📊 Режимы логирования

Приложение поддерживает уровни логирования:
- `DEBUG` — подробная отладочная информация
- `INFO` — основная информация
- `WARNING` — предупреждения
- `ERROR` — ошибки
- `CRITICAL` — критические ошибки

**Примеры запуска:**
```bash
LOG_LEVEL=INFO streamlit run app.py
LOG_LEVEL=ERROR LOG_FILE=./logs/error.log streamlit run app.py
```

**Настройка файлов логов:**
```bash
LOG_FILE=./logs/custom.log LOG_LEVEL=WARNING streamlit run app.py
```

---

### ⚙️ Конфигурация API

**Базовая настройка:**
```bash
API_URL="http://api.example.com" API_KEY="your_key" streamlit run app.py
```

**Комплексная конфигурация:**
```bash
API_URL="http://api.example.com" \
API_KEY="your_key" \
API_TIMEOUT=30 \
streamlit run app.py
```

---

## 🏭 Production-запуск

**Рекомендуемые настройки для Streamlit:**
| Параметр                | Описание               | Значение для production |
|-------------------------|------------------------|-------------------------|
| `--server.port`         | Порт сервера           | 80 или 443              |
| `--server.address`      | Адрес прослушивания    | 0.0.0.0                 |
| `--server.enableCORS`   | Включение CORS         | false                   |
| `--server.enableXsrfProtection` | Защита от XSRF  | true                    |
| `--browser.serverAddress` | Адрес для браузера   | your-domain.com         |

**Пример запуска:**
```bash
streamlit run app.py \
  --server.port=80 \
  --server.address=0.0.0.0 \
  --server.enableCORS=false \
  --server.enableXsrfProtection=true
```

---

## 🐳 Запуск в Docker

### 1. Создание Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV LOG_LEVEL=INFO \
    LOG_FILE=./logs/app.log \
    PORT=8000

EXPOSE 8000

CMD ["streamlit", "run", "app.py", "--server.port=8000", "--server.address=0.0.0.0"]
```

### 2. Сборка и запуск образа

```bash
docker build -t ocr-analyzer .
docker run -p 8000:8000 -v \$(pwd)/logs:/app/logs ocr-analyzer
```

### 3. Docker Compose

```yaml
version: '3.12'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs
    environment:
      - LOG_LEVEL=INFO
      - LOG_FILE=./logs/app.log
      - PORT=8000
    restart: unless-stopped
```

**Запуск:**
```bash
docker-compose up -d
```

---

## 🧪 Примеры конфигураций

### 1. Локальная разработка (максимальная детализация)
```bash
LOG_LEVEL=DEBUG streamlit run app.py
```

### 2. Тестовое окружение
```bash
LOG_LEVEL=INFO \
LOG_FILE=./logs/test.log \
API_URL="http://test-api.example.com" \
streamlit run app.py
```

### 3. Production-окружение
```bash
LOG_LEVEL=WARNING \
LOG_FILE=./logs/prod.log \
API_URL="https://api.example.com" \
API_KEY="prod_key" \
streamlit run app.py \
  --server.port=80 \
  --server.address=0.0.0.0 \
  --server.enableCORS=false
```

### 4. Локальный production-тест
```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## 🚨 Устранение неполадок

### 1. Проблемы с запуском

**Симптом:** Ошибка импорта библиотек
```bash
pip install -r requirements.txt --force-reinstall
```

**Симптом:** Ошибка доступа к порту
```bash
lsof -i :8501  # Проверка занятости порта
kill -9 <PID>  # Освобождение порта
```

### 2. Проблемы с логированием

**Симптом:** Логи не записываются в файл
```bash
mkdir -p logs && touch logs/app.log
chmod 777 logs/app.log
```

**Симптом:** Слишком много логов
```bash
LOG_LEVEL=WARNING streamlit run app.py
```

### 3. Проблемы с API

**Симптом:** Ошибки подключения к API
```bash
curl -v http://api.example.com/health
```

**Симптом:** Неправильные параметры API
```bash
export API_URL="https://correct-api.example.com"
export API_KEY="correct_key"
```

### 4. Просмотр логов в реальном времени
```bash
tail -f logs/app.log
# или для Docker
docker logs -f <container_id>
```

---
**Автор:** Дмитрий Ронжин
**GitHub:** [github.com/dronzhin](https://github.com/dronzhin)
**Версия:** 1.2.0
