FROM python:3.11-slim-bookworm

# Установка переменных окружения
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_ROOT_USER_ACTION=ignore \
    PLAYWRIGHT_BROWSER_TYPE=chromium \
    PLAYWRIGHT_TIMEOUT=60000 \
    PATH="/root/.local/bin:$PATH"

# Установка системных зависимостей (одним слоем)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Базовые зависимости для Playwright
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libdbus-1-3 libexpat1 libxcb1 \
    # Дополнительные зависимости
    fonts-liberation fonts-freefont-ttf fonts-noto fonts-noto-cjk \
    libappindicator3-1 libxtst6 xdg-utils \
    # Утилиты
    curl ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Установка uv pip (альтернатива pip с кэшированием)
RUN pip install --no-cache-dir uv && \
    uv pip install --upgrade pip

# Рабочая директория
WORKDIR /app

# Копирование и установка зависимостей (с кэшированием)
COPY pyproject.toml requirements.txt ./
RUN uv pip install --no-cache-dir -r requirements.txt && \
    uv pip install playwright==1.40.0 && \
    playwright install --with-deps chromium

# Копирование остальных файлов
COPY . .

# Сборка статики Django (если используется)
RUN python manage.py collectstatic --noinput 2>/dev/null || echo "ℹ️ Сборка статики пропущена"

# Настройка entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Порт для Railway
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