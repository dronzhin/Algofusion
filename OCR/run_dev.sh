#!/bin/bash
# run_dev.sh — запуск сервера в режиме разработки с автоматической перезагрузкой

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Активация виртуального окружения
source venv/bin/activate

echo "🚀 Запуск OCR сервера в режиме разработки..."
echo "   📁 Отслеживаемые директории: app.py, models/, utils/"
echo "   🌐 http://localhost:8000"
echo "   📚 Документация: http://localhost:8000/docs"
echo ""

# Запуск uvicorn с автоматической перезагрузкой
uvicorn app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --reload-dir ./models \
  --reload-dir ./utils \
  --log-level info \
  --access-log