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
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        region = getattr(settings, 'AWS_S3_REGION', '') or getattr(settings, 'AWS_REGION', '') or 'us-east-1'
        session = aws_session(region=region)
        # Extraire la clé S3 depuis l'URL publique
        custom = getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', '') or ''
        host = custom.rstrip('/').split('://')[-1].split('/')[0] if custom else ''
        key = ''
        if host and host in url:
            key = url.split(host, 1)[-1].lstrip('/')
        else:
            prefix = f'{bucket}.s3.{region}.amazonaws.com/'
            if prefix in url:
                key = url.split(prefix, 1)[-1]
            elif f'{bucket}.s3.amazonaws.com/' in url:
                key = url.split(f'{bucket}.s3.amazonaws.com/', 1)[-1]
            else:
                return url
        key = key.split('?', 1)[0]

        disposition = f'attachment; filename="{filename}"' if filename else 'attachment'
        return session.client('s3').generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': key,
                'ResponseContentDisposition': iri_to_uri(disposition),
            },
            ExpiresIn=300,
        )
    except Exception as e:
        logger.warning("force_download_url: impossible de presigner %s: %s", url, e)
        return url