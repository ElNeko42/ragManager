#!/bin/sh
set -e

case "$1" in
  web)
    python manage.py migrate --noinput
    case "${DJANGO_SETTINGS_MODULE}" in
      *.dev)
        exec python manage.py runserver 0.0.0.0:8000
        ;;
      *)
        python manage.py collectstatic --noinput
        exec gunicorn config.wsgi:application -c gunicorn.conf.py
        ;;
    esac
    ;;
  worker)
    exec celery -A config worker --loglevel=info
    ;;
  *)
    exec "$@"
    ;;
esac
