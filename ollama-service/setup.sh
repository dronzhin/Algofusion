#!/bin/bash
set -e

echo "🚀 Запуск Ollama OCR сервиса..."

# 1. Остановить старый контейнер (если существует)
docker stop ollama-ocr 2>/dev/null || true
docker rm ollama-ocr 2>/dev/null || true

# 2. Запустить контейнер
docker run -d \
  --name ollama-ocr \
  --gpus all \
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