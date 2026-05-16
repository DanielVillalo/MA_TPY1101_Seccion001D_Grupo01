#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Crear superusuario automáticamente si está definido
if [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py createsuperuser \
    --noinput \
    --username "$DJANGO_SUPERUSER_USERNAME" \
    --email "$DJANGO_SUPERUSER_EMAIL" || true
fi