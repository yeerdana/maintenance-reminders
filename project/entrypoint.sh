#!/bin/sh
set -e

# Only the web service migrates (RUN_MIGRATIONS=1); celery and beat wait for it to be healthy.
if [ "$RUN_MIGRATIONS" = "1" ]; then
    python manage.py migrate --no-input
    # Optional first admin user for the demo; ignored if it already exists.
    if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
        python manage.py createsuperuser --no-input || true
    fi
fi

exec "$@"
