# Используем официальный образ Python с Debian Bullseye (более стабильная версия)
FROM python:3.11-slim-bullseye as builder

# Устанавливаем системные зависимости для Playwright
RUN apt-get update && \
    apt-get install -y \
    wget \
    unzip \
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
COPY requirements.txt .
RUN pip install --user -r requirements.txt
RUN pip install playwright && \
    playwright install && \
    playwright install-deps

COPY . .

# Финальный образ
FROM python:3.11-slim-bullseye
WORKDIR /app

# Копируем только необходимое
COPY --from=builder /root/.local /root/.local
COPY --from=builder /app /app
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Минимальные runtime зависимости
RUN apt-get update && \
    apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH=/root/.local/bin:$PATH
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8080", "--workers", "3"]