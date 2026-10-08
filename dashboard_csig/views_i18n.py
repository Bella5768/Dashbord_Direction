"""Surcharge de ``set_language`` pour persister la langue sur le profil.

La vue Django ``set_language`` n'écrit que le cookie de langue. Pour rendre le
choix durable par compte (et permettre les emails par destinataire), on
enregistre aussi la préférence dans ``UserProfile.language``.
"""
from django.utils.translation import check_for_language
from django.views.i18n import set_language as django_set_language

from core.models import UserProfile


def set_language(request):
    response = django_set_language(request)

    lang = request.POST.get('language')
    user = getattr(request, 'user', None)
    if lang and user is not None and user.is_authenticated and check_for_language(lang):
        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            profile = None
        if profile is not None and profile.language != lang:
            profile.language = lang
            profile.save(update_fields=['language'])

    return response
