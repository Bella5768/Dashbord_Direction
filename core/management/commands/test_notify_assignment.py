from django.core.management.base import BaseCommand, CommandError
from core.models import Employee
from core.notifications import notify_assignment


class Command(BaseCommand):
    help = "Simule l'envoi d'un email de notification d'affectation a un employe (par email)."

    def add_arguments(self, parser):
        parser.add_argument('employee_email', help="Email de l'employe destinataire")
        parser.add_argument('--task', default='Test affectation', help="Nom de la tache")
        parser.add_argument('--project', default='Projet de test', help="Nom du projet")
        parser.add_argument('--type', default='jalon', help="Type de tache (jalon ou sous-etape)")
        parser.add_argument('--by', default='Administrateur CSIG', help="Nom de la personne qui affecte")

    def handle(self, *args, **options):
        email = options['employee_email']
        self.stdout.write(f"Recherche de l'employe avec email = {email}")
        employee = Employee.objects.filter(email__iexact=email).first()
        if not employee:
            raise CommandError(f"Aucun employe trouve avec email {email}. Verifie la fiche RH.")
        self.stdout.write(f"Employe trouve : {employee.name} (id={employee.id}, email={employee.email})")
        self.stdout.write("Appel notify_assignment ...")
        success, msg = notify_assignment(
            employee,
            options['type'],
            options['task'],
            options['project'],
            options['by'],
        )
        if success:
            self.stdout.write(self.style.SUCCESS(f"OK : {msg}"))
        else:
            self.stdout.write(self.style.ERROR(f"ECHEC : {msg}"))
