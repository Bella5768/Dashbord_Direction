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
RUN mkdir -p locale && DJANGO_SECRET_KEY=dummy python manage.py compilemessages -l fr -l en --ignore=static || true
RUN DJANGO_SECRET_KEY=dummy python manage.py collectstatic --noinput

# ---- Image d'exécution ----
FROM python:3.13-slim

# postgresql-client : psql/pg_dump uniquement pour les tâches ECS ponctuelles
# d'import ou de sauvegarde (la base est en sous-réseaux privés, donc
# inaccessible depuis le poste de l'opérateur). Aucun service n'expose ces outils.
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=dashboard_csig.settings

WORKDIR /app

# Récupérer les dépendances installées depuis l'image builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# pip n'est pas nécessaire à l'exécution (~8 Mo) : toute modification de
# dépendance se fait dans requirements.txt puis par un rebuild de l'image.
RUN rm -rf /usr/local/lib/python3.13/site-packages/pip* \
    /usr/local/lib/python3.13/site-packages/wheel* \
    /usr/local/bin/pip*

# Code applicatif + statiques déjà collectés par le builder (indispensable :
# .dockerignore exclut staticfiles/, un simple "COPY . ." ne les apporterait pas,
# et le manifest manquante fait échouer chaque page en production)
COPY --from=builder /app /app

# Port HTTP/WebSocket exposé par Daphne (ASGI)
EXPOSE 8080

# Point d'entrée + démarrage Daphne (ASGI : HTTP + WebSocket), port AWS ECS (8080)
# CMD vide => ECS peut remplacer la commande (run-task --command "python
# manage.py create_admin") sans être ignoré par l'ENTRYPOINT.
ENTRYPOINT ["/app/docker-entrypoint.sh"]