#!/bin/sh
set -e

case "$1" in
  web)
    python manage.py migrate --noinput
    if [ "${DJANGO_DEBUG}" = "true" ]; then
      exec python manage.py runserver 0.0.0.0:8000
    fi
    exec gunicorn config.wsgi:application --bind 0.0.0.0:8000
    ;;
  worker)
    exec celery -A config worker --loglevel=info
    ;;
  *)
    exec "$@"
    ;;
esac
