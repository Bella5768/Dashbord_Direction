import logging
import traceback
from django.utils import translation
from django.utils.translation import gettext as _
from django.http import JsonResponse, HttpResponseBadRequest
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, IntegrityError
from django.conf import settings

from core.models import UserProfile

logger = logging.getLogger(__name__)


class EnsureUserProfileMiddleware:
    """Répare à la volée les utilisateurs dont le profil a été supprimé.

    Le signal create_user_profile ne crée le profil qu'à la création de
    l'utilisateur : une suppression manuelle (SQL/admin) laissait ~110 accès
    `request.user.profile.*` lever RelatedObjectDoesNotExist → 500 sur la
    majorité des pages. Le profil est recréé ici (défauts vides) avant la vue.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated:
            try:
                user.profile
            except UserProfile.DoesNotExist:
                try:
                    UserProfile.objects.get_or_create(user=user)
                except IntegrityError:
                    # Course : deux requêtes simultanées ont recréé le profil.
                    pass
        return self.get_response(request)


class UserLanguageMiddleware:
    """Aligne la langue de la requête sur la préférence du profil utilisateur.

    Depuis Django 4.0, la langue est résolue depuis le cookie / Accept-Language.
    Pour un utilisateur authentifié, ``UserProfile.language`` fait foi : on
    l'active avant la vue (l'interface ET les emails rendus pendant la requête
    en héritent) et on réaligne le cookie pour la cohérence.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = None
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            try:
                lang = user.profile.language
            except UserProfile.DoesNotExist:
                lang = None

        valid = {code for code, _name in settings.LANGUAGES}
        if lang in valid and translation.get_language() != lang:
            translation.activate(lang)
            request.LANGUAGE_CODE = lang

        response = self.get_response(request)

        if lang in valid:
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                lang,
                max_age=settings.LANGUAGE_COOKIE_AGE,
                path=settings.LANGUAGE_COOKIE_PATH,
                domain=settings.LANGUAGE_COOKIE_DOMAIN,
                samesite='Lax',
            )
        return response


class ExceptionHandlingMiddleware:
    """Global exception handling middleware for user-friendly error responses."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        return self.get_response(request)
    
    def process_exception(self, request, exception):
        # Skip WebSocket connections - they use different protocol
        if request.path.startswith('/ws/'):
            return None
        
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
