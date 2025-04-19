#!/bin/sh

set -e  # Остановить скрипт при любой ошибке

echo "📦 Применяем миграции..."
python manage.py migrate --noinput

echo "🎨 Собираем статику..."
python manage.py collectstatic --noinput --clear || echo "⚠️ Сборка статики пропущена"

echo "🚀 Запускаем Gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 3

##!/bin/sh
#
#echo "Устанавливаем браузеры Playwright..."
#playwright install --with-deps
#
#echo "Применяем миграции..."
#python manage.py migrate --noinput
#
#echo "Собираем статику..."
#python manage.py collectstatic --noinput --clear || echo "Пропущена сборка статики"
#
#echo "Запускаем Gunicorn..."
#exec gunicorn config.wsgi:application --bind 0.0.0.0:"${PORT:-8080}" --workers 3

# Для gunicorn (если используешь в проде):
# gunicorn config.wsgi:application --bind 0.0.0.0:8080