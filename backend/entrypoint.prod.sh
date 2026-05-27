#!/bin/sh
set -eu

uv run python manage.py migrate --settings=config.settings.prod
uv run python manage.py collectstatic --noinput --settings=config.settings.prod

exec uv run gunicorn config.wsgi:application \
  --bind 0.0.0.0:8009 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -

