web: gunicorn config.wsgi --workers 2 --bind 0.0.0.0:$PORT
worker: python manage.py rqworker  # если используете фоновые задачи (опционально)