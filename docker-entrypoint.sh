#!/usr/bin/env bash
# Point d'entrée du conteneur (ECS Fargate).
# - Sans argument : applique les migrations puis démarre daphne (HTTP + WebSocket).
# - Avec arguments : les exécute tels quels (tâche ECS ponctuelle :
#   run-task --command "python manage.py create_admin").
set -e

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

if [ "$SKIP_MIGRATE" != "1" ] && [ -z "$DJANGO_ADMIN_SKIP_MIGRATE" ]; then
    ATTEMPTS="${MIGRATE_ATTEMPTS:-12}"
    echo "[entrypoint] migration des schemas (tentatives max : ${ATTEMPTS})..."
    n=1
    until python manage.py migrate --noinput; do
        if [ "$n" -ge "$ATTEMPTS" ]; then
            echo "[entrypoint] migration impossible apres ${ATTEMPTS} tentatives - abandon"
            exit 1
        fi
        n=$((n + 1))
        echo "[entrypoint] base pas encore disponible, nouvel essai dans 5s (${n}/${ATTEMPTS})..."
        sleep 5
    done
fi

PORT="${PORT:-8080}"
echo "[entrypoint] daphne sur le port ${PORT}"

# --proxy-headers : fait confiance aux en-têtes X-Forwarded-* de l'ALB
# (IP client réelle + schéma https derrière le reverse proxy).
exec daphne -b 0.0.0.0 -p "${PORT}" --proxy-headers dashboard_csig.asgi:application