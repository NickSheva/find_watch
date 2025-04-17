FROM python:3.11-slim-bookworm

WORKDIR /app

# Установка uv как обычного pip-пакета
RUN pip install uv

COPY pyproject.toml .

# Установка с флагом --system
RUN uv pip install --system -e .

COPY . .

EXPOSE 8080
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8080"]