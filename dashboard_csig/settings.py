"""
Django settings for dashboard_csig project.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-csig-dashboard-2025-change-this-in-production')

DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('1', 'true', 'yes', 'on')

ALLOWED_HOSTS = [h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

CSRF_TRUSTED_ORIGINS = [
    'http://localhost',
    'http://127.0.0.1',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://127.0.0.1:49870',
    'http://127.0.0.1:56509',
    'http://127.0.0.1:50239',
    'http://127.0.0.1:9000',
    'http://127.0.0.1:65073',
    'https://*.pythonanywhere.com',
]

_extra_csrf = [o.strip() for o in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]
if _extra_csrf:
    CSRF_TRUSTED_ORIGINS += _extra_csrf

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'dashboard_csig.wsgi.application'

if os.getenv('MYSQL_HOST'):
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

LANGUAGE_CODE = 'fr-fr'

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

# Email Configuration (Outlook/Office365 - CSIG)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.office365.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = 'support@csig.edu.gn'
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = 'support@csig.edu.gn'
SERVER_EMAIL = 'support@csig.edu.gn'
