"""Utility functions for standardized API responses and error handling."""
from django.http import JsonResponse
from django.utils.translation import gettext as _
from typing import Dict, Any, Optional


# Error codes for consistent client-side handling
class ErrorCodes:
    """Standard error codes for API responses."""
    PERMISSION_DENIED = 'PERMISSION_DENIED'
    VALIDATION_ERROR = 'VALIDATION_ERROR'
    DATABASE_ERROR = 'DATABASE_ERROR'
    SERVER_ERROR = 'SERVER_ERROR'
    NOT_FOUND = 'NOT_FOUND'
    INVALID_INPUT = 'INVALID_INPUT'
    RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED'
    AUTHENTICATION_ERROR = 'AUTHENTICATION_ERROR'
    FILE_ERROR = 'FILE_ERROR'
    NETWORK_ERROR = 'NETWORK_ERROR'


def api_success(data: Any = None, message: str = None, status: int = 200) -> JsonResponse:
    """Standard success response format."""
    response_data = {
        'success': True,
        'data': data if data is not None else {},
    }
    if message:
        response_data['message'] = message
    return JsonResponse(response_data, status=status)


def api_error(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    status: int = 400
) -> JsonResponse:
    """Standard error response format."""
    response_data = {
        'success': False,
        'error': error_code,
        'message': message,
    }
    if details:
        response_data['details'] = details
    return JsonResponse(response_data, status=status)


def api_validation_error(message: str, field_errors: Optional[Dict[str, str]] = None) -> JsonResponse:
    """Validation error response with optional field-level errors."""
    return api_error(
        ErrorCodes.VALIDATION_ERROR,
        message,
        details={'field_errors': field_errors} if field_errors else None,
        status=400
    )


def api_permission_denied(message: str = None) -> JsonResponse:
    """Permission denied error response."""
    return api_error(
        ErrorCodes.PERMISSION_DENIED,
        message or _("Vous n'avez pas la permission d'effectuer cette action."),
        status=403
    )


def api_not_found(resource: str = None) -> JsonResponse:
    """Not found error response."""
    message = _("Ressource introuvable.") if not resource else _("%(resource)s introuvable.") % {'resource': resource}
    return api_error(ErrorCodes.NOT_FOUND, message, status=404)


def api_server_error(message: str = None, debug_info: str = None) -> JsonResponse:
    """Server error response."""
    response_data = {
        'success': False,
        'error': ErrorCodes.SERVER_ERROR,
        'message': message or _("Une erreur inattendue s'est produite."),
    }
    if debug_info:
        response_data['debug_info'] = debug_info
    return JsonResponse(response_data, status=500)


def api_invalid_input(message: str, field: str = None) -> JsonResponse:
    """Invalid input error response."""
    details = {'field': field} if field else None
    return api_error(ErrorCodes.INVALID_INPUT, message, details=details, status=400)
