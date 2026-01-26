# 🖼️ Image Processing API

**Сервис для обработки изображений: бинаризация и выравнивание по горизонтальным линиям.**

![Image Processing API](https://via.placeholder.com/800x400?text=Image+Processing+API)

## 📋 Содержание
- [Требования](#-требования)
- [Установка](#-установка)
- [Базовый запуск](#-базовый-запуск)
- [Запуск с настройкой порта](#-запуск-с-настройкой-порта)
- [Режимы логирования](#-режимы-логирования)
- [API Документация](#-api-документация)
- [Production-запуск](#-production-запуск)
- [Запуск в Docker](#-запуск-в-docker)
- [Примеры конфигураций](#-примеры-конфигураций)
- [Устранение неполадок](#-устранение-неполадок)

## ⚙️ Требования

- **Python 3.9+**
- **FastAPI 0.95+**
- **Uvicorn 0.20+**
- **Библиотеки:** opencv-python, numpy, pillow, PyMuPDF, python-multipart
- **Системные зависимости:** 
  - Linux: `libgl1 libsm6 poppler-utils`
  - macOS: `poppler`
  - Windows: [Visual C++ Redistributable](https://aka.ms/vs/16/release/vc_redist.x64.exe)

## 📦 Установка

### 1. Клонирование репозитория
```bash
git clone https://github.com/yourusername/image-processing-api.git
cd image-processing-api

### 2. Создание виртуального окружения
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate    # Windows
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Установка системных зависимостей
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y libgl1 libsm6 poppler-utils

# macOS
brew install poppler

# Windows (через Chocolatey)
choco install poppler
```

## ▶️ Базовый запуск

```bash
uvicorn main:app --reload
```

**По умолчанию:**
- Порт: `8000`
- Уровень логирования: `INFO`
- Автоматическая перезагрузка: `включена` (только для разработки)
- CORS: `разрешены все источники`

Сервис будет доступен по адресу: `http://localhost:8000`

Документация Swagger UI: `http://localhost:8000/docs`  
Документация ReDoc: `http://localhost:8000/redoc`

## 🔌 Запуск с настройкой порта

### Изменение порта через параметры Uvicorn
```bash
# Запуск на порту 8080
uvicorn main:app --port 8080

# Запуск с указанием хоста и порта
uvicorn main:app --host 0.0.0.0 --port 9000

# Production-запуск без перезагрузки
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Изменение порта через переменные окружения
```bash
# Linux/Mac
PORT=8080 uvicorn main:app --host 0.0.0.0

# Windows (PowerShell)
$env:PORT=8080; uvicorn main:app --host 0.0.0.0
```

## 📊 Режимы логирования

Сервис поддерживает следующие уровни логирования:
- `DEBUG` - подробная отладочная информация
- `INFO` - основная информация о работе приложения (по умолчанию)
- `WARNING` - предупреждения
- `ERROR` - ошибки
- `CRITICAL` - критические ошибки

### Примеры запуска с разными уровнями логирования

```bash
# Режим отладки (максимальная детализация)
LOG_LEVEL=DEBUG uvicorn main:app --reload

# Production-режим (только важные события)
LOG_LEVEL=WARNING uvicorn main:app --host 0.0.0.0 --port 8000

# Отключение логов (только ошибки)
LOG_LEVEL=ERROR uvicorn main:app --host 0.0.0.0 --port 8000
```

## 📡 API Документация

### Доступные эндпоинты

| Эндпоинт | Метод | Описание | Параметры |
|----------|-------|----------|-----------|
| `/` | `GET` | Корневой эндпоинт | - |
| `/health` | `GET` | Проверка здоровья сервиса | - |
| `/convert` | `POST` | Конвертация в бинарный формат | `file`, `threshold` (0-255) |
| `/rotate` | `POST` | Выравнивание по горизонтальной линии | `file`, `min_line_length`, `max_line_gap`, `use_morphology` |

### Примеры запросов

#### Конвертация в бинарный формат
```bash
curl -X 'POST' \
  'http://localhost:8000/convert' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@/path/to/image.jpg' \
  -F 'threshold=128'
```

#### Выравнивание изображения
```bash
curl -X 'POST' \
  'http://localhost:8000/rotate' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@/path/to/document.pdf' \
  -F 'min_line_length=50' \
  -F 'max_line_gap=20' \
  -F 'use_morphology=true'
```

#### Проверка здоровья
```bash
curl http://localhost:8000/health
```

### Примеры ответов

#### Успешный ответ (конвертация)
```json
{
  "success": true,
  "original_filename": "document.pdf",
  "binary_images": [
    "base64_encoded_image_1",
    "base64_encoded_image_2"
  ],
  "threshold": 128,
  "page_count": 2
}
```

#### Успешный ответ (выравнивание)
```json
{
  "success": true,
  "original_filename": "scan.jpg",
  "rotated_image_base64": "base64_encoded_image",
  "rotation_angle": -2.35,
  "line_info": {
    "start": [100, 200],
    "end": [500, 205],
    "length": 400.12,
    "detected_angle": -2.35
  }
}
```

#### Ошибка обработки
```json
{
  "success": false,
  "error": "Неподдерживаемый формат файла",
  "error_type": "ValueError",
  "timestamp": 1677892345.123
}
```

## 🏭 Production-запуск

Для production-окружения рекомендуется использовать следующие настройки:

```bash
# Production-запуск с оптимизированными настройками
LOG_LEVEL=WARNING \
UVICORN_WORKERS=4 \
UVICORN_TIMEOUT=60 \
uvicorn main:app \
  --host 0.0.0.0 \
  --port 80 \
  --workers $UVICORN_WORKERS \
  --timeout-keep-alive $UVICORN_TIMEOUT
```

### Production-настройки Uvicorn
| Параметр | Описание | Рекомендуемое значение |
|----------|----------|------------------------|
| `--workers` | Количество worker процессов | `2 * CPU cores + 1` |
| `--timeout-keep-alive` | Таймаут для keep-alive соединений | `60` секунд |
| `--limit-concurrency` | Максимальное количество одновременных соединений | `100` |
| `--backlog` | Размер очереди соединений | `2048` |

## 🐳 Запуск в Docker

### 1. Создание Dockerfile
```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 libsm6 poppler-utils && \
    rm -rf /var/lib/apt/lists/*

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4"]
```

### 2. Сборка и запуск образа

```bash
# Сборка образа
docker build -t image-processing-api:latest .

# Запуск с базовыми настройками
docker run -d -p 8000:8000 --name image-api image-processing-api:latest

# Запуск с кастомным портом
docker run -d -p 8080:8000 --name image-api image-processing-api:latest

# Запуск с production-настройками
docker run -d \
  -p 80:8000 \
  -e LOG_LEVEL=WARNING \
  -e UVICORN_WORKERS=4 \
  --name image-api-prod \
  image-processing-api:latest
```

### 3. Docker Compose (для комплексного развертывания)

```yaml
# docker-compose.yml
version: '3.8'

services:
  image-api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs
    environment:
      - LOG_LEVEL=WARNING
      - UVICORN_WORKERS=4
      - UVICORN_TIMEOUT=60
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - api-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - image-api
    networks:
      - api-network

networks:
  api-network:
    driver: bridge
```

Запуск:
```bash
docker-compose up -d
```

## 🧪 Примеры конфигураций

### 1. Локальная разработка (максимальная детализация)
```bash
LOG_LEVEL=DEBUG \
uvicorn main:app --reload --port 8000
```

### 2. Тестовое окружение
```bash
LOG_LEVEL=INFO \
UVICORN_WORKERS=2 \
uvicorn main:app --host 0.0.0.0 --port 8080 --workers $UVICORN_WORKERS
```

### 3. Production-окружение
```bash
LOG_LEVEL=WARNING \
UVICORN_WORKERS=8 \
UVICORN_TIMEOUT=120 \
MAX_UPLOAD_SIZE=50MB \
uvicorn main:app \
  --host 0.0.0.0 \
  --port 80 \
  --workers $UVICORN_WORKERS \
  --timeout-keep-alive $UVICORN_TIMEOUT \
  --limit-concurrency 200
```

### 4. Локальный production-тест
```bash
# Имитация production-настроек на локальной машине
LOG_LEVEL=INFO \
UVICORN_WORKERS=4 \
uvicorn main:app --host 0.0.0.0 --port 8000 --workers $UVICORN_WORKERS
```

## 🚨 Устранение неполадок

### 1. Проблемы с запуском

**Симптом:** Сервис не запускается, ошибка импорта библиотек
```bash
# Решение: переустановка зависимостей
pip install --force-reinstall -r requirements.txt
```

**Симптом:** Ошибка доступа к порту
```bash
# Решение: проверка занятых портов и выбор свободного
sudo lsof -i :8000  # Linux/Mac
# или
netstat -ano | findstr 8000  # Windows

# Запуск на другом порту
uvicorn main:app --port 8001
```

### 2. Проблемы с обработкой изображений

**Симптом:** Ошибки при обработке PDF файлов
```bash
# Решение: проверка установки poppler
pdfinfo --version  # Linux/Mac
# Если не установлен:
sudo apt-get install poppler-utils  # Ubuntu/Debian
brew install poppler                # macOS
```

**Симптом:** Ошибки OpenCV (например, "libGL.so.1 not found")
```bash
# Linux решение:
sudo apt-get install libgl1 libsm6

# macOS решение:
brew install opencv
```

### 3. Проблемы с памятью

**Симптом:** Сервис падает при обработке больших файлов
```bash
# Решение: ограничение размера загрузки
MAX_UPLOAD_SIZE=20MB uvicorn main:app --port 8000
```

**Симптом:** Высокое потребление памяти
```bash
# Решение: уменьшение количества worker'ов
UVICORN_WORKERS=2 uvicorn main:app --port 8000
```

### 4. Просмотр логов в реальном времени

```bash
# Linux/Mac
tail -f ./logs/app.log

# Windows (PowerShell)
Get-Content ./logs/app.log -Wait

# В Docker-контейнере
docker logs -f image-api
```

### 5. Проверка доступности эндпоинтов

```bash
# Проверка корневого эндпоинта
curl http://localhost:8000/

# Проверка здоровья
curl http://localhost:8000/health

# Проверка документации
curl http://localhost:8000/docs
```

---

**Версия API:** 1.0.0  
**Последнее обновление:** 26 января 2026 г.  
