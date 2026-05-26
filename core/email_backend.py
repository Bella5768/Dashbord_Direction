"""Backend SMTP qui force un local_hostname valide.

Outlook (Office 365) renvoie "501 5.5.4 Invalid domain name" si le client
envoie un EHLO/HELO avec un nom de machine sans domaine (ex: DESKTOP-XYZ).
Ce backend force un FQDN valide pour la commande EHLO.
"""
import smtplib

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPBackend


def _local_hostname():
    return getattr(settings, 'EMAIL_LOCAL_HOSTNAME', '') or 'csig.edu.gn'


class _OutlookSMTP(smtplib.SMTP):
    def __init__(self, host='', port=0, local_hostname=None, *args, **kwargs):
        super().__init__(host, port, _local_hostname(), *args, **kwargs)


class _OutlookSMTP_SSL(smtplib.SMTP_SSL):
    def __init__(self, host='', port=0, local_hostname=None, *args, **kwargs):
        super().__init__(host, port, _local_hostname(), *args, **kwargs)


class OutlookSMTPBackend(DjangoSMTPBackend):
    @property
    def connection_class(self):
        return _OutlookSMTP_SSL if self.use_ssl else _OutlookSMTP
