"""
URL configuration for dashboard_csig project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.i18n import JavaScriptCatalog
from django.db import connection
from django.db.utils import OperationalError

from dashboard_csig.views_i18n import set_language

def healthz(request):
    """Healthcheck pour l'ALB/ECS.
    Répond 200 + JSON si la base répond, 503 sinon (aucune écriture DB)."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except OperationalError:
        return JsonResponse({'status': 'error', 'database': 'down'}, status=503)
    return JsonResponse({'status': 'ok', 'database': 'up'})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/setlang/', set_language, name='set_language'),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    path('healthz/', healthz, name='healthz'),
    path('', include('core.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
