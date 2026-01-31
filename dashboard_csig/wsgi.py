"""
WSGI config for dashboard_csig project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard_csig.settings')

application = get_wsgi_application()
