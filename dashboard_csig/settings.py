"""
Django settings for dashboard_csig project.
"""

from pathlib import Path
import os
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

ALLOWED_HOSTS = [h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

# Permet l'affichage des previews de documents dans des iframes du même domaine
X_FRAME_OPTIONS = 'SAMEORIGIN'

SITE_URL = os.getenv('SITE_URL', 'http://localhost:8000')

CSRF_TRUSTED_ORIGINS = [
    'http://localhost',
    'http://127.0.0.1',
    'http://localhost:*',
    'http://127.0.0.1:*',
    'https://*.pythonanywhere.com',
    'https://dgdashbord.pythonanywhere.com',
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
# Priority: Neon PostgreSQL (DATABASE_URL) > MySQL > SQLite
_database_url = os.getenv('DATABASE_URL', '')
if _database_url:
    # Neon PostgreSQL (primary choice)
    tmpPostgres = urlparse(_database_url)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': tmpPostgres.path.replace('/', ''),
            'USER': tmpPostgres.username,
            'PASSWORD': tmpPostgres.password,
            'HOST': tmpPostgres.hostname,
            'PORT': 5432,
            'OPTIONS': dict(parse_qsl(tmpPostgres.query)),
        }
    }
elif os.getenv('MYSQL_HOST'):
    # MySQL (fallback option)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('MYSQL_DATABASE', ''),
            'USER': os.getenv('MYSQL_USER', ''),
            'PASSWORD': os.getenv('MYSQL_PASSWORD', ''),
            'HOST': os.getenv('MYSQL_HOST', ''),
            'PORT': os.getenv('MYSQL_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
            },
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
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

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

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email Configuration
# Use SendGrid if API key is configured, otherwise fallback to Outlook SMTP
if os.getenv('SENDGRID_API_KEY'):
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
