"""Corriger les séquences PostgreSQL après import de données.

Depuis la migration UUID (PK devenues des UUID générés par uuid5), seul
auth_user / auth_group conservent une séquence integer. Les tables core_*
n'ont plus de séquence 'id', elles sont ignorées proprement (skip).
"""
from django.core.management.base import BaseCommand
from django.db import connection


TABLES = [
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
