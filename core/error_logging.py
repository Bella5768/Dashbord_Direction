"""Error logging utilities for consistent error tracking and debugging."""
import logging
import traceback
from django.conf import settings
from django.utils import timezone
from typing import Optional, Dict, Any
from django.contrib.auth.models import User


logger = logging.getLogger(__name__)


class ErrorLogger:
    """Centralized error logging with context and user information."""
    
    @staticmethod
    def log_exception(
        exception: Exception,
        context: Optional[Dict[str, Any]] = None,
        user: Optional[User] = None,
        level: str = 'error'
    ) -> None:
        """Log an exception with full context."""
        log_func = getattr(logger, level.lower(), logger.error)
        
        log_data = {
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'timestamp': timezone.now().isoformat(),
        }
        
        if user and user.is_authenticated:
            log_data['user_id'] = user.id
            log_data['username'] = user.username
        
        if context:
            log_data['context'] = context
        
        log_func(
            f"{log_data['exception_type']}: {log_data['exception_message']}",
            extra=log_data,
            exc_info=True
        )
    
    @staticmethod
    def log_validation_error(
        field: str,
        message: str,
        user: Optional[User] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log validation errors specifically."""
        log_data = {
            'error_type': 'validation_error',
            'field': field,
            'message': message,
            'timestamp': timezone.now().isoformat(),
        }
        
        if user and user.is_authenticated:
            log_data['user_id'] = user.id
            log_data['username'] = user.username
        
        if context:
            log_data['context'] = context
        
        logger.warning(f"Validation error on {field}: {message}", extra=log_data)
    
    @staticmethod
    def log_permission_denied(
        action: str,
        resource: str,
        user: Optional[User] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log permission denied events."""
        log_data = {
            'error_type': 'permission_denied',
            'action': action,
            'resource': resource,
            'timestamp': timezone.now().isoformat(),
        }
        
        if user and user.is_authenticated:
            log_data['user_id'] = user.id
            log_data['username'] = user.username
        
        if context:
            log_data['context'] = context
        
        logger.warning(f"Permission denied: {action} on {resource}", extra=log_data)
    
    @staticmethod
    def log_database_error(
        operation: str,
        table: str,
        exception: Exception,
        user: Optional[User] = None
    ) -> None:
        """Log database errors specifically."""
        log_data = {
            'error_type': 'database_error',
            'operation': operation,
            'table': table,
            'exception_message': str(exception),
            'timestamp': timezone.now().isoformat(),
        }
        
        if user and user.is_authenticated:
            log_data['user_id'] = user.id
            log_data['username'] = user.username
        
        logger.error(f"Database error during {operation} on {table}", extra=log_data, exc_info=True)
    
    @staticmethod
    def log_api_error(
        endpoint: str,
        method: str,
        error_code: str,
        message: str,
        user: Optional[User] = None,
        status_code: int = 400
    ) -> None:
        """Log API errors for monitoring."""
        log_data = {
            'error_type': 'api_error',
            'endpoint': endpoint,
            'method': method,
            'error_code': error_code,
            'message': message,
            'status_code': status_code,
            'timestamp': timezone.now().isoformat(),
        }
        
        if user and user.is_authenticated:
            log_data['user_id'] = user.id
            log_data['username'] = user.username
        
        logger.warning(f"API error: {method} {endpoint} - {error_code}", extra=log_data)


def safe_execute(
    func,
    default_return=None,
    log_error: bool = True,
    error_message: str = None,
    context: Dict[str, Any] = None
):
    """Safely execute a function with error handling and logging.
    
    Args:
        func: Function to execute
        default_return: Value to return on error
        log_error: Whether to log errors
        error_message: Custom error message for logging
        context: Additional context for error logging
    
    Returns:
        Function result or default_return on error
    """
    try:
        return func()
    except Exception as e:
        if log_error:
            ErrorLogger.log_exception(
                e,
                context=context or {},
                error_message=error_message
            )
        return default_return
