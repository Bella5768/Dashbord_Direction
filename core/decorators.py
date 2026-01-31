from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Decorator to check if user has required role."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('core:login')
            
            if not hasattr(request.user, 'profile'):
                messages.error(request, "Votre profil n'est pas configuré.")
                return redirect('core:login')
            
            user_role = request.user.profile.role
            if user_role not in roles and 'admin' not in roles:
                if user_role != 'admin':
                    messages.error(request, "Vous n'avez pas les permissions nécessaires.")
                    return redirect('core:dashboard')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def permission_required(permission_method):
    """Decorator to check specific permission."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('core:login')
            
            if not hasattr(request.user, 'profile'):
                messages.error(request, "Votre profil n'est pas configuré.")
                return redirect('core:login')
            
            # Check if user has the required permission
            profile = request.user.profile
            has_permission = getattr(profile, permission_method, lambda: False)()
            
            if not has_permission and not profile.is_admin():
                messages.error(request, "Vous n'avez pas les permissions nécessaires pour cette action.")
                return redirect('core:dashboard')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
