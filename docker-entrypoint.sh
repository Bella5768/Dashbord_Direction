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

# --proxy-headers : fait confiance aux en-têtes X-Forwarded-* de l'ALB
# (IP client réelle + schéma https derrière le reverse proxy).
exec daphne -b 0.0.0.0 -p "${PORT}" --proxy-headers dashboard_csig.asgi:application