import smtplib
from email.message import EmailMessage

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Teste l'envoi d'un email via SMTP Outlook en utilisant smtplib directement."

    def add_arguments(self, parser):
        parser.add_argument('recipient', type=str, help='Adresse email de destination pour le test')
        parser.add_argument('--user', type=str, default='', help='Adresse Outlook SMTP si EMAIL_HOST_USER est vide')
        parser.add_argument('--password', type=str, default='', help='Mot de passe Outlook SMTP si EMAIL_HOST_PASSWORD est vide')
        parser.add_argument('--helo', type=str, default='', help='Nom de domaine local envoyé dans EHLO (defaut csig.edu.gn)')
        parser.add_argument('--debug', action='store_true', help='Active le debug SMTP verbeux')

    def handle(self, *args, **options):
        recipient = options['recipient']
        smtp_user = options['user'] or settings.EMAIL_HOST_USER
        smtp_password = options['password'] or settings.EMAIL_HOST_PASSWORD
        helo = options['helo'] or getattr(settings, 'EMAIL_LOCAL_HOSTNAME', '') or 'csig.edu.gn'
        from_email = smtp_user or settings.DEFAULT_FROM_EMAIL

        self.stdout.write('Configuration email :')
        self.stdout.write(f"EMAIL_HOST = {settings.EMAIL_HOST}")
        self.stdout.write(f"EMAIL_PORT = {settings.EMAIL_PORT}")
        self.stdout.write(f"EMAIL_USE_TLS = {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"EMAIL_HOST_USER = {smtp_user or '(vide)'}")
        self.stdout.write(f"EMAIL_HOST_PASSWORD défini = {bool(smtp_password)}")
        self.stdout.write(f"FROM = {from_email}")
        self.stdout.write(f"EHLO local_hostname = {helo}")

        if not smtp_user:
            raise CommandError('EMAIL_HOST_USER est vide. Utilisez --user.')
        if not smtp_password:
            raise CommandError('EMAIL_HOST_PASSWORD est vide. Utilisez --password.')

        msg = EmailMessage()
        msg['Subject'] = 'Test email Outlook - Dashboard CSIG'
        msg['From'] = from_email
        msg['To'] = recipient
        msg.set_content('Ceci est un test SMTP Outlook envoye via smtplib direct.')

        try:
            with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, local_hostname=helo, timeout=30) as server:
                if options['debug']:
                    server.set_debuglevel(1)
                server.ehlo(helo)
                if settings.EMAIL_USE_TLS:
                    server.starttls()
                    server.ehlo(helo)
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        except smtplib.SMTPResponseException as exc:
            raise CommandError(f'SMTP {exc.smtp_code}: {exc.smtp_error!r}') from exc
        except Exception as exc:
            raise CommandError(f'Échec SMTP Outlook : {type(exc).__name__}: {exc}') from exc

        self.stdout.write(self.style.SUCCESS(f'Email de test envoyé à {recipient}'))
