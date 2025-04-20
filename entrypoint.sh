#!/bin/bash
set -e

echo "🔍 Проверка зависимостей Playwright..."
playwright install-deps || echo "⚠️ Не удалось установить все зависимости Playwright (возможно уже установлены)"
playwright install chromium || echo "⚠️ Не удалось установить Chromium (возможно уже установлен)"

# Миграции и статика
echo "📦 Применяем миграции..."
python manage.py migrate --noinput

echo "🎨 Собираем статику..."
python manage.py collectstatic --noinput --clear || echo "⚠️ Не удалось собрать статику"

# Запуск Gunicorn с увеличенным таймаутом
echo "🚀 Запускаем сервер..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers 2 \
    --timeout 120 \
    --log-level debug


##!/bin/bash
#set -e
## Проверка зависимостей Playwright
#echo "🔍 Проверка зависимостей Playwright..."
#
#if ! command -v playwright &>/dev/null; then
#  echo "❌ Playwright не установлен"
#else
#  echo "🔍 Проверка зависимостей Playwright..."
#  playwright install-deps || echo "⚠️ Не удалось установить все зависимости Playwright"
#  playwright install chromium || echo "⚠️ Не удалось установить Chromium"
#fi
#
## Миграции и статика
#echo "📦 Применяем миграции..."
#python manage.py migrate --noinput
#
#echo "🎨 Собираем статику..."
#python manage.py collectstatic --noinput --clear
#
## Запуск Gunicorn с увеличенным таймаутом
#echo "🚀 Запускаем сервер..."
#exec gunicorn config.wsgi:application \
#    --bind 0.0.0.0:${PORT:-8080} \
#    --workers 2 \
#    --timeout 120 \
#    --log-level debug