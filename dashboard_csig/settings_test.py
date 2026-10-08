"""Settings de la suite de tests : SQLite en mémoire.

La base de développement (.env DATABASE_URL) est une instance Neon distante
(us-east-2) : chaque requête des tests paierait l'aller-retour réseau (une
suite de ~100 pages a dépassé 5 min sur ce chemin). Les tests smoke valident
le rendu des pages et la logique applicative, pas le moteur PostgreSQL ;
les migrations ont aussi été appliquées avec succès sur PostgreSQL
(base de test test_neondb, 0001 → 0004).

Usage : python manage.py test core --settings=dashboard_csig.settings_test
"""

from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Sans collectstatic récent, le manifeste whitenoise est stale en local
# (fonts/inter/inter.css absent) et chaque {% static %} lèverait une
# ValueError. Les tests ne valident pas les URL de fichiers hachés.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}
