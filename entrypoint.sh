#!/bin/sh

set -e  # Остановить скрипт при любой ошибке

echo "📦 Применяем миграции..."
python manage.py migrate --noinput

echo "🎨 Собираем статику..."
python manage.py collectstatic --noinput --clear

echo "🔄 Проверка установки Playwright..."
playwright install-deps || echo "⚠️ Не удалось установить зависимости Playwright"

echo "🚀 Запускаем Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers 3 \
    --timeout 120 \
    --log-level debug