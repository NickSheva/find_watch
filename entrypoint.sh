#!/bin/sh

echo "Применяем миграции..."
python manage.py migrate --noinput

echo "Собираем статику..."
python manage.py collectstatic --noinput --clear || echo "Пропущена сборка статики"

echo "Запускаем Gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:"${PORT:-8080}" --workers 3

# Для gunicorn (если используешь в проде):
# gunicorn config.wsgi:application --bind 0.0.0.0:8080