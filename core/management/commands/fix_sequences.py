"""Corriger les séquences PostgreSQL après import de données."""
from django.core.management.base import BaseCommand
from django.db import connection


TABLES = [
    'core_useractivity', 'core_userprofile', 'core_employee',
    'core_direction', 'core_project', 'core_projectdocument',
    'core_document', 'core_partner', 'core_event', 'core_request',
    'core_budget', 'core_leaverequest', 'core_notification',
    'core_leavedocument', 'core_milestone', 'core_submilestone',
    'core_projectneed', 'core_projectcomment', 'core_projectactivity',
    'core_projectfolder', 'core_projectmember', 'core_permission',
    'core_role', 'core_role_permissions', 'core_eventmember',
    'auth_user', 'auth_group',
]


class Command(BaseCommand):
    help = 'Réinitialiser les séquences PostgreSQL (fix IntegrityError sur clés primaires)'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            for table in TABLES:
                try:
                    cursor.execute(
                        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM \"{table}\"), 1))"
                    )
                    val = cursor.fetchone()
                    self.stdout.write(f'  {table}: OK ({val[0] if val else "?"})')
                except Exception as e:
                    self.stdout.write(f'  {table}: skip ({e})')

        self.stdout.write(self.style.SUCCESS('Séquences PostgreSQL réinitialisées.'))
