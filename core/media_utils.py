"""Helpers pour la migration Cloudinary → Amazon S3 + CloudFront.

Les anciennes URLs Cloudinary stockées en base utilisent le flag
``/upload/fl_attachment/`` pour forcer le téléchargement. Les nouvelles URLs
S3/CloudFront n'ont pas ce flag : on génère une URL presignée courte avec
``response-content-disposition=attachment``.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def aws_session(region=None):
    """Retourne une session boto3.

    N'utilise les clés d'environnement que si elles sont réellement définies,
    sinon laisse boto3 résoudre les credentials via sa chaîne par défaut
    (task role ECS sur Fargate, profil local, métadonnées d'instance).
    """
    import boto3

    kwargs = {}
    access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', '') or ''
    secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', '') or ''
    if access_key and secret_key:
        kwargs['aws_access_key_id'] = access_key
        kwargs['aws_secret_access_key'] = secret_key
    kwargs['region_name'] = (
        region
        or getattr(settings, 'AWS_S3_REGION', '') or getattr(settings, 'AWS_REGION', '')
        or 'us-east-1'
    )
    return boto3.Session(**kwargs)


def is_s3_url(url):
    """Détecte si une URL de fichier est hébergée sur S3/CloudFront."""
    if not url:
        return False
    lower = url.lower()
    if 'res.cloudinary.com' in lower:
        return False
    if 'amazonaws.com' in lower or 'cloudfront.net' in lower:
        return True
    custom = getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', '') or ''
    host = custom.rstrip('/').split('://')[-1].split('/')[0] if custom else ''
    return bool(host and host in lower)


def _s3_key_from_url(url):
    """Extrait la clé S3 d'une URL publique S3/CloudFront, ou None."""
    if not url:
        return None
    bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '') or ''
    region = getattr(settings, 'AWS_S3_REGION', '') or getattr(settings, 'AWS_REGION', '') or 'us-east-1'
    custom = getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', '') or ''
    host = custom.rstrip('/').split('://')[-1].split('/')[0] if custom else ''
    key = ''
    if host and host in url:
        key = url.split(host, 1)[-1].lstrip('/')
    else:
        for prefix in (
            f'{bucket}.s3.{region}.amazonaws.com/',
            f'{bucket}.s3.amazonaws.com/',
        ):
            if bucket and prefix in url:
                key = url.split(prefix, 1)[-1]
                break
    if not key:
        return None
    return key.split('?', 1)[0]


def _presign_get(key, params=None):
    """Génère une URL S3 présignée courte (5 min) pour un objet."""
    region = getattr(settings, 'AWS_S3_REGION', '') or getattr(settings, 'AWS_REGION', '') or 'us-east-1'
    session = aws_session(region=region)
    return session.client('s3').generate_presigned_url(
        'get_object',
        Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': key, **(params or {})},
        ExpiresIn=300,
    )


def presigned_inline_url(url):
    """URL presignée courte pour l'affichage inline d'un fichier S3/CloudFront.

    L'accès reste ainsi conditionné à la vue Django authentifiée (le bucket est
    privé) : l'URL brute stockée en base n'est jamais servie directement.
    Renvoie l'URL d'origine telle quelle si ce n'est pas un fichier S3.
    """
    if not is_s3_url(url):
        return url
    try:
        key = _s3_key_from_url(url)
        if not key:
            return url
        return _presign_get(key)
    except Exception as e:
        logger.warning("presigned_inline_url: impossible de presigner %s: %s", url, e)
        return url


def force_download_url(url, filename=''):
    """Retourne une URL qui force le téléchargement.

    - URL Cloudinary : conserve ``/upload/fl_attachment/``.
    - URL S3/CloudFront : URL presignée courte avec
      ``response-content-disposition=attachment``.
    """
    if not url:
        return url
    if not is_s3_url(url):
        return url.replace('/upload/', '/upload/fl_attachment/')

    from django.utils.encoding import iri_to_uri

    try:
        key = _s3_key_from_url(url)
        if not key:
            return url
        disposition = f'attachment; filename="{filename}"' if filename else 'attachment'
        return _presign_get(key, {'ResponseContentDisposition': iri_to_uri(disposition)})
    except Exception as e:
        logger.warning("force_download_url: impossible de presigner %s: %s", url, e)
        return url