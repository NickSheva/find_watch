#!/bin/bash
web: gunicorn config.wsgi --daemon
release: python manage.py migrate --no-input
rq worker --with-scheduler