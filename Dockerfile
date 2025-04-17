# Используем образ с подходящей версией GLIBC (Debian 12)
FROM python:3.12-bookworm as builder

# Устанавливаем зависимости системы
RUN apt-get update && \
    apt-get install -y \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости Playwright
RUN apt-get update && \
    apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libwayland-client0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости Python
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Устанавливаем Playwright и браузеры
RUN pip install playwright && \
    playwright install && \
    playwright install-deps

# Копируем весь проект
COPY . .

# Собираем статические файлы
RUN python manage.py collectstatic --noinput

# Финальный образ
FROM python:3.12-slim-bookworm

WORKDIR /app

# Копируем Python зависимости
COPY --from=builder /root/.local /root/.local
COPY --from=builder /app .

# Копируем Playwright
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Устанавливаем runtime зависимости для Playwright
RUN apt-get update && \
    apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libwayland-client0 \
    && rm -rf /var/lib/apt/lists/*

# Добавляем .local/bin в PATH
ENV PATH=/root/.local/bin:$PATH
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# Порт, который будет слушать приложение
EXPOSE 8080

# Команда для запуска
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8080", "--workers", "3"]