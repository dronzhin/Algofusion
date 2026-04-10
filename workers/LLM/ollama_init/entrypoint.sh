#!/bin/sh
set -e
MODELS="${OLLAMA_MODELS:-qwen2.5:1.5b,qwen2.5:7b}"
echo "🚀 Ollama Entry Point: запуск инициализации..."
echo "📦 Ожидаемые модели: $MODELS"
echo "🔄 Запуск ollama serve..."
/bin/ollama serve &
SERVE_PID=$!
echo "⏳ Ожидание готовности сервера..."
for i in $(seq 1 120); do
    if /bin/ollama list >/dev/null 2>&1; then
        echo "✅ Сервер Ollama готов (попытка $i)"
        break
    fi
    sleep 1
done
echo "🔍 Проверка моделей..."
for model in $(echo $MODELS | tr ',' ' '); do
    echo "----------------------------------------"
    echo "📦 Модель: $model"
    if /bin/ollama list 2>/dev/null | grep -q "^$model "; then
        echo "✅ Уже загружена: $model"
    else
        echo "⬇️  Начинаю загрузку $model (прогресс ниже):"
        /bin/ollama pull "$model"
        echo "✅ Загрузка завершена: $model"
    fi
done
echo "----------------------------------------"
echo "🎉 Все модели готовы! Возврат управления основному процессу..."
wait $SERVE_PID
