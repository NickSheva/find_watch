#!/bin/bash
set -e
# Проверка зависимостей Playwright
echo "🔍 Проверка зависимостей Playwright..."

playwright install-deps || echo "⚠️ Предупреждение: не удалось установить все зависимости Playwright"
playwright install chromium "⚠️ Предупреждение: не удалось установить chromium"

# Миграции и статика
echo "📦 Применяем миграции..."
python manage.py migrate --noinput

echo "🎨 Собираем статику..."
python manage.py collectstatic --noinput --clear

# Запуск Gunicorn с увеличенным таймаутом
echo "🚀 Запускаем сервер..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers 2 \
    --timeout 120 \
    --log-level debug