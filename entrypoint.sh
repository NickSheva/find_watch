#!/bin/bash
set -e

# Проверка зависимостей Playwright
echo "🔍 Проверяем зависимости Playwright..."
playwright install-deps || echo "⚠️ Предупреждение: не удалось установить все зависимости Playwright"

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
    --log-level info \
    --access-logfile -