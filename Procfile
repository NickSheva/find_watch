web: gunicorn config.wsgi --workers 3 --bind 0.0.0.0:$PORT --timeout 120
release: python manage.py migrate --no-input