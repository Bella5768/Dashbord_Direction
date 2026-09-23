"""Backends d'envoi d'email.

- ``FixedHostnameSMTPBackend``: backend SMTP qui force un local_hostname
  valide (EMAIL_LOCAL_HOSTNAME). Certains serveurs SMTP (Gmail, Outlook…)
  rejettent la connexion si le client envoie un EHLO avec le hostname réel de
  la machine (invalide, avec virgule, sans domaine…). Ce backend force un FQDN
  fixe pour la commande EHLO, indépendamment du réseau ou du WiFi utilisé.
- ``SESBackend``: backend utilisant l'API Amazon SES (send_raw_email).
  Gère le HTML, les images inline CID (logo) et les pièces jointes (PDF)
  tels quels, car le message MIME complet de Django est envoyé.
"""

import logging
import smtplib

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPBackend
from django.core.mail import EmailMessage, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _local_hostname():
    return getattr(settings, 'EMAIL_LOCAL_HOSTNAME', '') or 'csig.edu.gn'


class _FixedHostnameSMTP(smtplib.SMTP):
    def __init__(self, host='', port=0, local_hostname=None, *args, **kwargs):
        super().__init__(host, port, _local_hostname(), *args, **kwargs)


class _FixedHostnameSMTP_SSL(smtplib.SMTP_SSL):
    def __init__(self, host='', port=0, local_hostname=None, *args, **kwargs):
        super().__init__(host, port, _local_hostname(), *args, **kwargs)


class OutlookSMTPBackend(DjangoSMTPBackend):
    """Alias conservé pour compatibilité .env existants."""
    @property
    def connection_class(self):
        return _FixedHostnameSMTP_SSL if self.use_ssl else _FixedHostnameSMTP


class FixedHostnameSMTPBackend(DjangoSMTPBackend):
    """Backend SMTP avec EHLO hostname fixe — fonctionne avec Gmail, Outlook, etc."""
    @property
    def connection_class(self):
        return _FixedHostnameSMTP_SSL if self.use_ssl else _FixedHostnameSMTP


class SESBackend(BaseEmailBackend):
    """Backend d'envoi d'email via Amazon SES (boto3 ``send_raw_email``).

    Le message MIME complet construit par Django (texte, HTML, images inline
    CID, pièces jointes) est envoyé tel quel à SES. Configuration via les
    variables d'environnement ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``
    et ``AWS_SES_REGION``.
    """

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not getattr(settings, 'AWS_ACCESS_KEY_ID', '') or not getattr(settings, 'AWS_SECRET_ACCESS_KEY', ''):
            if not self.fail_silently:
                raise ValueError("Envoyer un email avec SESBackend nécessite que "
                                 "AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY soient définis.")
            return 0
        sent = 0
        for message in email_messages:
            if self._send_message(message):
                sent += 1
        return sent

    def _send_message(self, message):
        import boto3
        session = boto3.Session(
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', ''),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', ''),
            region_name=getattr(settings, 'AWS_SES_REGION', getattr(settings, 'AWS_REGION', 'us-east-1')),
        )
        client = session.client('ses')
        raw = message.message().as_bytes()
        try:
            client.send_raw_email(
                Source=message.from_email,
                Destinations=list(message.to) + list(message.cc),
                RawMessage={'Data': raw},
            )
            return True
        except Exception:
            if not self.fail_silently:
                raise
            return False


def send_email(
    subject,
    message,
    recipient_list,
    from_email=None,
    html_message=None,
    fail_silently=False
):
    """
    Envoie un email simple.
    
    Args:
        subject: Sujet de l'email
        message: Corps du message (texte)
        recipient_list: Liste des destinataires
        from_email: Expéditeur (optionnel, utilise DEFAULT_FROM_EMAIL par défaut)
        html_message: Version HTML du message (optionnel)
        fail_silently: Si True, ne lève pas d'exception en cas d'erreur
    
    Returns:
        Nombre d'emails envoyés avec succès
    """
    return send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=recipient_list,
        html_message=html_message,
        fail_silently=fail_silently
    )


def send_html_email(
    subject,
    template_name,
    context,
    recipient_list,
    from_email=None,
    fail_silently=False
):
    """
    Envoie un email HTML à partir d'un template Django.
    
    Args:
        subject: Sujet de l'email
        template_name: Chemin du template Django (ex: 'emails/welcome.html')
        context: Contexte pour le template
        recipient_list: Liste des destinataires
        from_email: Expéditeur (optionnel)
        fail_silently: Si True, ne lève pas d'exception en cas d'erreur
    
    Returns:
        Nombre d'emails envoyés avec succès
    """
    html_content = render_to_string(template_name, context)
    text_content = strip_tags(html_content)
    
    return send_mail(
        subject=subject,
        message=text_content,
        from_email=from_email,
        recipient_list=recipient_list,
        html_message=html_content,
        fail_silently=fail_silently
    )


def send_email_with_attachments(
    subject,
    message,
    recipient_list,
    attachments=None,
    from_email=None,
    html_message=None,
    fail_silently=False
):
    """
    Envoie un email avec des pièces jointes.
    
    Args:
        subject: Sujet de l'email
        message: Corps du message (texte)
        recipient_list: Liste des destinataires
        attachments: Liste de tuples (filename, content, mimetype) ou de chemins de fichiers
        from_email: Expéditeur (optionnel)
        html_message: Version HTML du message (optionnel)
        fail_silently: Si True, ne lève pas d'exception en cas d'erreur
    
    Returns:
        Nombre d'emails envoyés avec succès
    """
    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=from_email,
        to=recipient_list
    )
    
    if html_message:
        email.content_subtype = 'html'
        email.body = html_message
    
    if attachments:
        for attachment in attachments:
            if isinstance(attachment, str):
                # C'est un chemin de fichier
                email.attach_file(attachment)
            elif isinstance(attachment, tuple) and len(attachment) == 3:
                # C'est un tuple (filename, content, mimetype)
                filename, content, mimetype = attachment
                email.attach(filename, content, mimetype)
    
    return email.send(fail_silently=fail_silently)
