#!/usr/bin/env bash
# Met à jour les fichiers .po/.mo dans l'environnement virtuel
set -e

cd "$(dirname "$0")"

# Active l'environnement virtuel
source venv/Scripts/activate

# Extrait les nouvelles chaînes traduisibles
python manage.py makemessages -l en -l fr --no-obsolete

# Compile les .po en .mo
python manage.py compilemessages

echo "Traductions mises à jour."
