# ---- Image de build (compilation des traductions + collectstatic) ----
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Outils système minimaux
RUN apt-get update && apt-get install -y --no-install-recommends \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 60 -r requirements.txt

# Code applicatif
COPY . .

# Compiler les traductions (locale/*.po → .mo) et les fichiers statiques
RUN mkdir -p locale && python manage.py compilemessages -l fr -l en --ignore=static || true
RUN SECRET_KEY=dummy python manage.py collectstatic --noinput

# ---- Image d'exécution ----
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=dashboard_csig.settings \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Récupérer les dépendances installées depuis l'image builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Lancer daphne (ASGI : HTTP + WebSocket) — port par défaut AWS ECS (8080)
EXPOSE 8080

# Migrations + démarrage (les migrations peuvent être désactivées via SKIP_MIGRATE=1)
CMD ["/app/docker-entrypoint.sh"]