"""
Django settings for dashboard_csig project.
"""

from pathlib import Path
import os
import socket
from django.utils.translation import gettext_lazy as _
from urllib.parse import urlparse, parse_qsl

BASE_DIR = Path(__file__).resolve().parent.parent

env_path = BASE_DIR / '.env'
if env_path.exists():
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() in ('1', 'true', 'yes', 'on')

def _local_addresses():
    addresses = set()
    try:
        addresses.add(socket.gethostbyname(socket.gethostname()))
    except OSError:
        pass
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(('169.254.169.254', 80))
            addresses.add(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass
    return addresses


ALLOWED_HOSTS = [h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

# L'ALB envoie son health check avec Host=<IP privee de la tache>:<port>. Cette IP change a
# chaque remplacement de tache, on ne peut donc pas la figer dans la task definition. Elle est
# ajoutee au demarrage, le temps de vie de la tache.
ALLOWED_HOSTS += [ip for ip in _local_addresses() if ip not in ALLOWED_HOSTS]

# Permet l'affichage des previews de documents dans des iframes du même domaine
X_FRAME_OPTIONS = 'SAMEORIGIN'

SITE_URL = os.getenv('SITE_URL', 'http://localhost:8000')

CSRF_TRUSTED_ORIGINS = [
    'http://localhost',
    'http://127.0.0.1',
    'http://localhost:*',
    'http://127.0.0.1:*',
]

_extra_csrf = [o.strip() for o in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]
if _extra_csrf:
    CSRF_TRUSTED_ORIGINS += _extra_csrf

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'storages',
    'channels',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'dashboard_csig.middleware.ExceptionHandlingMiddleware',
]

ROOT_URLCONF = 'dashboard_csig.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'dashboard_csig.wsgi.application'
ASGI_APPLICATION = 'dashboard_csig.asgi.application'

# Channel layer : InMemory en dev, Redis en prod (REDIS_URL=redis://...)
_redis_url = os.getenv('REDIS_URL', '')
if _redis_url:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [_redis_url]},
        }
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }

# Database Configuration
# Priority: PostgreSQL (DATABASE_URL, ex. Amazon RDS) > SQLite
_database_url = os.getenv('DATABASE_URL', '')
if _database_url:
    # PostgreSQL (primary choice)
    tmpPostgres = urlparse(_database_url)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': tmpPostgres.path.replace('/', ''),
            'USER': tmpPostgres.username,
            'PASSWORD': tmpPostgres.password,
            'HOST': tmpPostgres.hostname,
            'PORT': tmpPostgres.port or 5432,
            'OPTIONS': dict(parse_qsl(tmpPostgres.query)),
        }
    }
else:
    # SQLite (development fallback)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

SESSION_COOKIE_AGE = 3600 * 8
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

if not DEBUG:
    # TLS et HSTS pilotés par variable. Défauts = mode sûr (1), titres du domaine
    # et du certificat ACM en place sur l'ALB. On ne passe à 0 que pour une
    # recette temporaire derrière un ALB en HTTP seul : sans cela
    # SECURE_SSL_REDIRECT renvoie une boucle de 301 et les cookies "Secure" ne
    # sont jamais renvoyés par le navigateur, donc la connexion est impossible.
    _ssl_on = os.getenv('DJANGO_SECURE_SSL', '1').lower() in ('1', 'true', 'yes', 'on')
    _hsts_on = os.getenv('DJANGO_HSTS', '1').lower() in ('1', 'true', 'yes', 'on')
    SESSION_COOKIE_SECURE = _ssl_on
    CSRF_COOKIE_SECURE = _ssl_on
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = _ssl_on
    # Le healthcheck ALB attaque le conteneur en HTTP sur /healthz/ et n'envoie
    # pas X-Forwarded-Proto : sans exemption, SecurityMiddleware le renverrait
    # en 301 alors que le matcher de la target group exige 200, et la tâche ne
    # deviendrait jamais healthy.
    # Django 4.2 (django/middleware/security.py:22) applique un lstrip("/") sur
    # le path AVANT de tester le pattern : il faut donc "^healthz/" et non
    # "^/healthz/".
    SECURE_REDIRECT_EXEMPT = [r'^healthz/']
    SECURE_HSTS_SECONDS = 31536000 if _hsts_on else 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _hsts_on
    SECURE_HSTS_PRELOAD = _hsts_on

LANGUAGE_CODE = 'fr'

LANGUAGES = [
    ('fr', _('Fran\u00e7ais')),
    ('en', _('English')),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

TIME_ZONE = 'Africa/Conakry'

# Authentication
LOGIN_URL = 'core:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'core:login'
AUTH_USER_MODEL = 'core.User'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Amazon S3 + CloudFront media storage (replace Cloudinary)
if os.getenv('AWS_STORAGE_BUCKET_NAME'):
    # Credentials AWS : optionnelles. Absentes => boto3 utilise sa chaîne par
    # défaut (rôle de tâche ECS sur Fargate, profil local, métadonnées).
    # Ne jamais les définir en chaîne vide : django-storages les passerait
    # explicitement au client S3 et invaliderait le rôle de tâche ECS.
    _aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID') or ''
    _aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY') or ''
    if _aws_access_key_id and _aws_secret_access_key:
        AWS_ACCESS_KEY_ID = _aws_access_key_id
        AWS_SECRET_ACCESS_KEY = _aws_secret_access_key
    AWS_S3_REGION = os.getenv('AWS_S3_REGION', os.getenv('AWS_REGION', 'us-east-1'))
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False
    # URLs CloudFront (ou S3 direct si non renseigné)
    _cloudfront_domain = os.getenv('AWS_CLOUDFRONT_DOMAIN', '')
    if _cloudfront_domain:
        AWS_S3_CUSTOM_DOMAIN = _cloudfront_domain.rstrip('/')
    else:
        AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION}.amazonaws.com'

    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3.S3Storage',
            'OPTIONS': {},
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
else:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email Configuration
# Priorité : Amazon SES (API) → SendGrid → SMTP Outlook/Gmail
# SES est choisi dès que AWS_SES_REGION est défini : les credentials peuvent
# venir du rôle de tâche ECS (chaîne boto3 par défaut), pas seulement de l'env.
if os.getenv('AWS_SES_REGION'):
    EMAIL_BACKEND = 'core.email_backend.SESBackend'
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@csig.edu.gn')
elif os.getenv('SENDGRID_API_KEY'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.sendgrid.net'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = 'apikey'
    EMAIL_HOST_PASSWORD = os.getenv('SENDGRID_API_KEY')
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@csig.edu.gn')
else:
    EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'core.email_backend.OutlookSMTPBackend')
    EMAIL_LOCAL_HOSTNAME = os.getenv('EMAIL_LOCAL_HOSTNAME', 'csig.edu.gn')
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.office365.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('1', 'true', 'yes', 'on')
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'support@csig.edu.gn')
