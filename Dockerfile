# Базовый образ Python
FROM python:3.11-slim-bookworm

# Избегаем предупреждений pip при запуске от root
ENV PIP_ROOT_USER_ACTION=ignore

# Установка системных библиотек Playwright + утилит
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgirepository-1.0-1 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libgdk-pixbuf2.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxcb1 \
    libxkbcommon0 \
    libasound2 \
    libatspi2.0-0 \
    libexpat1 \
    wget \
    curl \
    gnupg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Установка pip и uv
RUN pip install --upgrade pip && pip install --no-cache-dir uv

# Установка рабочей директории
WORKDIR /app

# Копирование зависимостей
COPY pyproject.toml .

# Установка Python-зависимостей
RUN uv pip install --system -e .

# Установка Playwright + браузеров
RUN uv pip install --system playwright && \
    playwright install --with-deps

# Копирование оставшихся файлов проекта
COPY . .

# Сборка статики (если не требуется — не упадёт)
RUN python manage.py collectstatic --noinput || echo "Static files collection skipped"

# Порт для приложения
#ENV PORT=8080
#EXPOSE $PORT

# Используйте один из вариантов CMD:
#CMD bash -c "python manage.py runserver 0.0.0.0:${PORT}"
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8080", "--workers", "3"]
#CMD ["sh", "-c", "gunicorn config.wsgi --bind 0.0.0.0:${PORT:-8080} --workers 3"]