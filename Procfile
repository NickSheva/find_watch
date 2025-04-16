web: gunicorn config.wsgi --workers=2 --bind=0.0.0.0:$PORT --timeout 120
release: python manage.py migrate --no-input
worker: python manage.py rqworker  # только если используете RQ