FROM python:3.11-slim-bookworm

# Установка переменных окружения
ENV PIP_ROOT_USER_ACTION=ignore \
    DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSER_TYPE=chromium \
    PLAYWRIGHT_TIMEOUT=60000

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Базовые зависимости
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libdbus-1-3 libexpat1 libxcb1 \
    # Дополнительные зависимости
    fonts-liberation libappindicator3-1 libxtst6 lsb-release xdg-utils \
    fonts-freefont-ttf fonts-noto fonts-noto-cjk \
    # Утилиты
    wget curl gnupg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Обновление pip
RUN pip install --upgrade pip

# Установка зависимостей проекта
WORKDIR /app

# Сначала копируем только requirements.txt для кэширования
COPY requirements.txt .
#RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Установка Playwright
#RUN pip install playwright==1.40.0 && \
#    playwright install chromium && \
#    playwright install-deps
RUN pip install playwright==1.40.0 && \
    playwright install --with-deps chromium && \
    playwright install chromium


# Копируем остальные файлы
COPY . .

# Сборка статики Django
RUN python manage.py collectstatic --noinput || echo "⚠️ Сборка статики пропущена"

# Настройка entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Порт для Railway
ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
## Установка pip и uv
#RUN pip install --upgrade pip && pip install --no-cache-dir uv
#
## Копирование зависимостей
#COPY pyproject.toml .
#
## Установка Python-зависимостей
#RUN uv pip install --system -e .
#
## Установка Playwright + браузеров
#RUN uv pip install --system playwright && \
#    playwright install --with-deps
#
## Сборка статики (если не требуется — не упадёт)
#RUN python manage.py collectstatic --noinput || echo "Static files collection skipped"
#
## Порт для приложения
## Устанавливаем Python зависимости
#WORKDIR /app
#
## Копируем код
#COPY . /app
#COPY . .
#ENV PYTHONPATH=/app
## Устанавливаем переменные окружения
#ENV PORT=8080
#ENV PYTHONUNBUFFERED=1
#
### Собираем статику
##RUN python manage.py collectstatic --noinput
#
## Команда запуска
##CMD gunicorn --bind 0.0.0.0:$PORT your_app.wsgi:application
##CMD ["/bin/bash", "-c", "gunicorn run:app –bind 0.0.0.0:$PORT"]
#CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "3", "config.wsgi:application"]
##CMD ["gunicorn", "--bind", "0.0.0.0:${PORT:-8080}", "--workers", "3", "--timeout", "60", "config.wsgi:application"]