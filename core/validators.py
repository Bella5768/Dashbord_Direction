import os
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

ALLOWED_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.ppt', '.pptx', '.odt', '.ods', '.odp',
    '.png', '.jpg', '.jpeg', '.gif', '.webp',
    '.txt', '.csv', '.zip',
}

DANGEROUS_MIMES = {
    'text/html', 'text/javascript', 'application/javascript',
    'application/x-php', 'application/x-httpd-php',
    'image/svg+xml',
}


def validate_safe_file(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            _("Type de fichier non autorisé (%(ext)s). Extensions acceptées : %(allowed)s.") % {
                'ext': ext or _("sans extension"),
                'allowed': ', '.join(sorted(ALLOWED_EXTENSIONS)),
            }
        )
    # Reject dangerous MIME types detected from file content
    mime = getattr(file, 'content_type', None)
    if mime and mime.split(';')[0].strip() in DANGEROUS_MIMES:
        raise ValidationError(_("Ce type de fichier n'est pas autorisé pour des raisons de sécurité."))
