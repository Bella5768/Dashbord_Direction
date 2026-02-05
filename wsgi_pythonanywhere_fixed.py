import os
import sys

path = '/home/dgdashbord/Dashbord_Direction'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'dashboard_csig.settings'

# Django prod
os.environ.setdefault('DJANGO_DEBUG', 'False')
os.environ.setdefault('DJANGO_ALLOWED_HOSTS', 'dgdashbord.pythonanywhere.com')
os.environ.setdefault('DJANGO_CSRF_TRUSTED_ORIGINS', 'https://dgdashbord.pythonanywhere.com')
os.environ.setdefault('DJANGO_SECRET_KEY', 'CHANGE_ME_STRONG_SECRET')

# UTILISER SQLITE (pas de MySQL)
# Les variables MySQL sont commentées pour forcer l'utilisation de SQLite
# os.environ.setdefault('MYSQL_HOST', 'dgdashbord.mysql.pythonanywhere-services.com')
# os.environ.setdefault('MYSQL_PORT', '3306')
# os.environ.setdefault('MYSQL_DATABASE', 'dgdashbord$NOM_DB')
# os.environ.setdefault('MYSQL_USER', 'dgdashbord')
# os.environ.setdefault('MYSQL_PASSWORD', 'TON_MYSQL_PASSWORD')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
