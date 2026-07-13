import logging
import traceback
from django.utils.translation import gettext as _
from django.http import JsonResponse, HttpResponseBadRequest
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError
from django.conf import settings

logger = logging.getLogger(__name__)


class ExceptionHandlingMiddleware:
    """Global exception handling middleware for user-friendly error responses."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        return self.get_response(request)
    
    def process_exception(self, request, exception):
        # Don't handle if response is already set
        if hasattr(exception, 'status_code'):
            return None
        
        # Log the exception
        logger.error(
            f"Exception in {request.path}: {str(exception)}",
            exc_info=True,
            extra={
                'path': request.path,
                'method': request.method,
                'user': str(request.user) if request.user.is_authenticated else 'Anonymous',
            }
        )
        
        # Handle different exception types
        if isinstance(exception, PermissionDenied):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'permission_denied',
                    'message': _("Vous n'avez pas la permission d'effectuer cette action."),
                    'code': 'PERMISSION_DENIED'
                }, status=403)
            return None  # Let Django handle PermissionDenied normally
        
        elif isinstance(exception, ValidationError):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'validation_error',
                    'message': str(exception),
                    'code': 'VALIDATION_ERROR'
                }, status=400)
            return None
        
        elif isinstance(exception, DatabaseError):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'database_error',
                    'message': _("Une erreur de base de données s'est produite. Veuillez réessayer."),
                    'code': 'DATABASE_ERROR'
                }, status=500)
            return None
        
        # Generic exception handling
        if settings.DEBUG:
            # In debug mode, show full error for development
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'server_error',
                    'message': str(exception),
                    'traceback': traceback.format_exc(),
                    'code': 'SERVER_ERROR'
                }, status=500)
            return None
        
        # In production, show user-friendly message
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'server_error',
                'message': _("Une erreur inattendue s'est produite. L'équipe technique a été notifiée."),
                'code': 'SERVER_ERROR'
            }, status=500)
        
        return None
