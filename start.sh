#!/bin/bash
exec gunicorn config.wsgi --bind 0.0.0.0:8080 --workers 3