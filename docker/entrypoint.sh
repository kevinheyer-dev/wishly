#!/usr/bin/env bash
# Prepares the database before the web server starts; worker and beat skip this (WISHLY_SKIP_MIGRATE).
set -Eeuo pipefail

if [[ -z "${WISHLY_SKIP_MIGRATE:-}" ]]; then
  python manage.py migrate --noinput
  if [[ -n "${DJANGO_SUPERUSER_USERNAME:-}" && -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]]; then
    # Only creates the account once; an existing one is left alone
    python manage.py createsuperuser --noinput 2>/dev/null || true
  fi
fi

exec "$@"
