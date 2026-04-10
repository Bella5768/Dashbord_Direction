from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware


class DevCsrfTrustedOriginsMiddleware:
    """
    In DEBUG mode, automatically trust all localhost/127.0.0.1 origins
    regardless of port, to support dev proxies.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG:
            origin = request.META.get('HTTP_ORIGIN', '')
            if origin and any(origin.startswith(prefix) for prefix in (
                'http://127.0.0.1',
                'http://localhost',
            )):
                if origin not in settings.CSRF_TRUSTED_ORIGINS:
                    settings.CSRF_TRUSTED_ORIGINS.append(origin)
        return self.get_response(request)
