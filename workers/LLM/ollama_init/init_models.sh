#!/bin/sh
set -e

MODELS="${OLLAMA_MODELS:-qwen2.5:1.5b,gemma2:2b,phi3:mini-3.8b,qwen2.5:7b,llama3.1:8b}"

echo "🔄 Ollama init: загрузка моделей [$MODELS]"

# 🔹 Запускаем сервер в фоне
/bin/ollama serve &
SERVER_PID=$!

# 🔹 Ждём готовности (до 60 сек)
for i in $(seq 1 60); do
    if ollama list >/dev/null 2>&1; then
        echo "✅ Сервер готов"
        break
    fi
    echo "⏳ Ожидание... ($i/60)"
    sleep 1
done

# 🔹 Загружаем модели
for model in $(echo $MODELS | tr ',' ' '); do
    echo "⏳ Проверка: $model"
    if ! ollama list 2>/dev/null | grep -q "$model"; then
        echo "⬇️  Загрузка: $model"
        ollama pull "$model"
        echo "✅ Загружено: $model"
    else
        echo "✅ Уже есть: $model"
    fi
done

echo "🎉 Все модели готовы, возврат в форегроунд..."
wait $SERVER_PID