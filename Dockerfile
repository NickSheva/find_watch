FROM python:3.11-slim-bookworm

# Установка всех зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Основные зависимости
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libdbus-1-3 libexpat1 libxcb1 \
    # Дополнительные зависимости
    fonts-liberation libappindicator3-1 libxtst6 lsb-release xdg-utils \
    # Очистка
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Установка и обновление pip
RUN pip install --upgrade pip

# Установка зависимостей проекта
WORKDIR /app

# Сначала копируем только requirements для кэширования
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Установка Playwright с конкретной версией
RUN pip install playwright==1.40.0 && \
    playwright install chromium && \
    playwright install-deps

# Копируем остальные файлы
COPY . .

# Копируем entrypoint и делаем его исполняемым
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Railway использует этот порт
ENV PORT=8080
EXPOSE 8080

# Запускаем entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]