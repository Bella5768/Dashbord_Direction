"""Backend SMTP qui force un local_hostname valide.

Outlook (Office 365) renvoie "501 5.5.4 Invalid domain name" si le client
envoie un EHLO/HELO avec un nom de machine sans domaine (ex: DESKTOP-XYZ).
Ce backend force un FQDN valide pour la commande EHLO.
"""
import smtplib

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPBackend
from django.core.mail import EmailMessage, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def _local_hostname():
    return getattr(settings, 'EMAIL_LOCAL_HOSTNAME', '') or 'csig.edu.gn'


class _OutlookSMTP(smtplib.SMTP):
    def __init__(self, host='', port=0, local_hostname=None, *args, **kwargs):
        # Forcer le local_hostname pour éviter l'erreur "Invalid domain name"
        hostname = _local_hostname()
        super().__init__(host, port, hostname, *args, **kwargs)


class _OutlookSMTP_SSL(smtplib.SMTP_SSL):
    def __init__(self, host='', port=0, local_hostname=None, *args, **kwargs):
        # Forcer le local_hostname pour éviter l'erreur "Invalid domain name"
        hostname = _local_hostname()
        super().__init__(host, port, hostname, *args, **kwargs)


class OutlookSMTPBackend(DjangoSMTPBackend):
    @property
    def connection_class(self):
        return _OutlookSMTP_SSL if self.use_ssl else _OutlookSMTP


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
