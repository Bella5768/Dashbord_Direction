#!/usr/bin/env bash
# Point d'entrée du conteneur (ECS Fargate).
# Applique les migrations puis démarre daphne (HTTP + WebSocket).
set -e

if [ "$SKIP_MIGRATE" != "1" ] && [ -z "$DJANGO_ADMIN_SKIP_MIGRATE" ]; then
    echo "[entrypoint] migration des schemas..."
    python manage.py migrate --noinput
fi

PORT="${PORT:-8080}"
echo "[entrypoint] daphne sur le port ${PORT}"

exec daphne -b 0.0.0.0 -p "${PORT}" dashboard_csig.asgi:application