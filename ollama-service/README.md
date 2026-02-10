# Ollama OCR Service

Локальный сервис распознавания текста на базе Ollama с предзагруженными специализированными моделями.

---

## 📁 Структура проекта

```
ollama-service/
├── README.md               # Документация по запуску и использованию
└── setup.sh                # Опциональный скрипт для первоначальной настройки
```
---

## 🚀 Быстрый старт

```bash
# 1. Запустить контейнер
docker run -d \
  --name ollama-ocr \
  --restart unless-stopped \
  -p 8003:11434 \
  -v ollama_/root/.ollama \
  ollama/ollama:0.3.12

# 2. Дождаться готовности (~15 сек)
sleep 15

# 3. Загрузить модели (однократно, 5-15 минут)
docker exec ollama-ocr ollama pull glm-ocr:latest
docker exec ollama-ocr ollama pull deepseek-ocr:latest
```

---

## `setup.sh` (опционально, для удобства)

```bash
#!/bin/bash
set -e

echo "🚀 Запуск Ollama OCR сервиса..."

# 1. Остановить старый контейнер (если существует)
docker stop ollama-ocr 2>/dev/null || true
docker rm ollama-ocr 2>/dev/null || true

# 2. Запустить контейнер
docker run -d \
  --name ollama-ocr \
  --restart unless-stopped \
  -p 8003:11434 \
  -v ollama_/root/.ollama \
  ollama/ollama:latest

echo "⏳ Ожидание полной готовности сервера (до 60 сек)..."
START_TIME=$(date +%s)
while true; do
  if curl -s http://localhost:8003/api/tags >/dev/null 2>&1; then
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    echo "✅ Сервер готов через ${ELAPSED} секунд"
    break
  fi
  sleep 2
  echo -n "."
  CURRENT_TIME=$(date +%s)
  if [ $((CURRENT_TIME - START_TIME)) -gt 60 ]; then
    echo ""
    echo "❌ Таймаут ожидания сервера (60 сек)"
    exit 1
  fi
done
echo ""

# 3. Загрузить модели с явной проверкой
echo "⬇️  Загрузка модели glm-ocr:latest..."
if ! docker exec ollama-ocr ollama pull glm-ocr:latest 2>&1 | tee /tmp/pull_glm.log; then
  echo "❌ Ошибка загрузки glm-ocr. Проверьте лог: /tmp/pull_glm.log"
  exit 1
fi

echo "⬇️  Загрузка модели deepseek-ocr:latest..."
if ! docker exec ollama-ocr ollama pull deepseek-ocr:latest 2>&1 | tee /tmp/pull_deepseek.log; then
  echo "❌ Ошибка загрузки deepseek-ocr. Проверьте лог: /tmp/pull_deepseek.log"
  exit 1
fi

# 4. Финальная проверка
echo ""
echo "🔍 Проверка загруженных моделей:"
docker exec ollama-ocr ollama list

echo ""
echo "✅ Готово! Сервис доступен на http://localhost:8003"
echo ""
echo "Тестовый запрос:"
echo 'curl http://localhost:8003/api/generate -d '\''{"model": "glm-ocr:latest", "prompt": "test", "stream": false}'\'''
```

Запуск:
```bash
chmod +x setup.sh
./setup.sh
```
---

## 🔍 Проверка работоспособности

```bash
# Проверить доступность API
curl http://localhost:8003/api/tags

# Убедиться, что модели загружены
curl -s http://localhost:8003/api/tags | jq '.models[].name'
# Ожидаемый вывод:
# "glm-ocr:latest"
# "deepseek-ocr:latest"
```

---

## 🖼️ Примеры использования

### Пример 1: Распознавание слова "привет"

#### Шаг 1: Подготовка изображения

Создайте простое изображение с текстом "привет" (например, в Paint или через Python):

```python
# generate_hello.py
from PIL import Image, ImageDraw, ImageFont

# Создаём белое изображение 200x80
img = Image.new('RGB', (200, 80), color='white')
draw = ImageDraw.Draw(img)

# Рисуем текст "привет" чёрным цветом
try:
    font = ImageFont.truetype("DejaVuSans.ttf", 36)
except:
    font = ImageFont.load_default()

draw.text((20, 20), "привет", fill='black', font=font)

# Сохраняем и конвертируем в base64
import base64
from io import BytesIO

buffer = BytesIO()
img.save(buffer, format="PNG")
base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
print(base64_image)
```

Запустите скрипт и сохраните полученный base64-код.

#### Шаг 2: Отправка запроса к Ollama

```bash
# Сохраните base64 изображения в переменную (пример сокращён для читаемости)
BASE64_IMAGE="iVBORw0KGgoAAAANSUhEUgAAAMgAAABQCAIAAA..."

# Отправка запроса к модели glm-ocr
curl http://localhost:8003/api/generate -d '{
  "model": "glm-ocr:latest",
  "prompt": "Extract all text from the image",
  "stream": false,
  "images": ["'"$BASE64_IMAGE"'"]
}'
```

#### Ожидаемый ответ:

```json
{
  "model": "glm-ocr:latest",
  "created_at": "2026-02-10T12:34:56.789Z",
  "response": "привет",
  "done": true,
  "context": [...],
  "total_duration": 1234567890,
  "load_duration": 123456789,
  "prompt_eval_count": 5,
  "eval_count": 12,
  "eval_duration": 987654321
}
```

Ключевое поле — `"response"` содержит распознанный текст: **`привет`** ✅

---

### Пример 2: Распознавание через Python (для интеграции)

```python
import requests
import base64

def ocr_image(image_path: str, model: str = "glm-ocr:latest") -> str:
    """Распознать текст с изображения через локальный Ollama"""
    
    # Чтение и кодирование изображения
    with open(image_path, "rb") as f:
        base64_image = base64.b64encode(f.read()).decode('utf-8')
    
    # Запрос к Ollama
    response = requests.post(
        "http://localhost:8003/api/generate",
        json={
            "model": model,
            "prompt": "Extract all text preserving structure",
            "stream": False,
            "images": [base64_image]
        },
        timeout=120
    )
    response.raise_for_status()
    
    return response.json()["response"].strip()

# Использование
text = ocr_image("hello.png")
print(f"Распознанный текст: {text}")
# Вывод: Распознанный текст: привет
```

---

## 💡 Особенности

| Параметр | Значение |
|----------|----------|
| **Модели** | `glm-ocr:latest` (0.9B, быстрая), `deepseek-ocr:latest` (1.3B, точная) |
| **Персистентность** | Модели сохраняются между перезапусками благодаря `-v ollama_data` |
| **Первый запуск** | Загрузка моделей занимает 5-15 минут (зависит от скорости интернета) |
| **Последующие запуски** | Контейнер стартует за < 2 секунд |
| **Порт** | Сервис доступен на `http://localhost:8003` |
| **API** | Совместим с официальным [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md) |

---

## 🛠️ Управление контейнером

```bash
# Остановить контейнер
docker stop ollama-ocr

# Перезапустить
docker restart ollama-ocr

# Посмотреть логи
docker logs -f ollama-ocr

# Загрузить новую модель
docker exec ollama-ocr ollama pull имя-модели:тег

# Проверить занятый объём (модели хранятся в томе)
docker system df -v | grep ollama_data

# Полная очистка (удалить контейнер И данные моделей)
docker stop ollama-ocr
docker rm ollama-ocr
docker volume rm ollama_data
```

---

## 📊 Сравнение моделей

| Модель | Параметры | Скорость | Точность | Рекомендация |
|--------|-----------|----------|----------|--------------|
| **glm-ocr** | 0.9B | ⚡ Быстрая | ✅ Хорошая | Простые документы, сканы, рукописный текст |
| **deepseek-ocr** | 1.3B | 🐢 Умеренная | 🌟 Высокая | Сложные документы, таблицы, мелкий шрифт |

---

## ❓ Частые вопросы

**Вопрос:** Что делать, если `docker exec ollama-ocr ollama pull` зависает?  
**Ответ:** Дождитесь завершения загрузки (модели весят 1-2 ГБ). Проверьте прогресс через `docker logs ollama-ocr`.

**Вопрос:** Можно ли использовать другие порты?  
**Ответ:** Да, измените проброс: `-p 9000:11434` → сервис будет доступен на `http://localhost:9000`.

**Вопрос:** Как обновить модели до новых версий?  
**Ответ:** Выполните повторную загрузку: `docker exec ollama-ocr ollama pull glm-ocr:latest`.

---