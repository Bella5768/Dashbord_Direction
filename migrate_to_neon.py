#!/usr/bin/env python
"""
Migration SQLite/MySQL → Neon PostgreSQL

Usage:
    python migrate_to_neon.py                # export + import complet
    python migrate_to_neon.py --export-only  # export depuis la DB source
    python migrate_to_neon.py --import-only  # import vers Neon (nécessite data_export.json)
    python migrate_to_neon.py --verify-only  # vérifier les compteurs Neon
"""

import os
import sys
import json
import time
import argparse
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Fix Windows console encoding (cp1252 can't handle emoji)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

EXPORT_FILE = 'data_export.json'

# ── Ordre d'import (dépendances FK) ──────────────────────────────────
IMPORT_ORDER = [
    'auth.user',
    'core.direction',
    'core.employee',
    'core.partner',
    'core.permission',
    'core.role',
    'core.projectrole',
    'core.project',
    'core.projectfolder',
    'core.document',
    'core.projectdocument',
    'core.projectmember',
    'core.milestone',
    'core.event',
    'core.eventmember',
    'core.submilestone',
    'core.projectactivity',
    'core.budget',
    'core.request',
    'core.projectneed',
    'core.projectcomment',
    'core.userprofile',
    'core.useractivity',
    'core.notification',
    'core.leaverequest',
    'core.leavedocument',
]


# ═══════════════════════════════════════════════════════════════════════
#  EXPORT — sous-processus isolé pour forcer SQLite/MySQL
# ═══════════════════════════════════════════════════════════════════════

def export_data():
    """Exporte les données depuis SQLite/MySQL via un sous-processus Django.

    Le sous-processus a DATABASE_URL et MYSQL_HOST supprimés de son
    environnement, ce qui force settings.py à utiliser SQLite.
    """
    # Vérifier que db.sqlite3 existe
    sqlite_path = os.path.join(BASE_DIR, 'db.sqlite3')
    has_sqlite = os.path.exists(sqlite_path)

    if has_sqlite:
        print(f"📦 Export depuis SQLite ({sqlite_path})")
    else:
        print("⚠  Aucun db.sqlite3 trouvé — tentative depuis MySQL si configuré")

    # Construire un environnement propre pour forcer SQLite
    # IMPORTANT: on met à '' plutôt que de supprimer, car settings.py
    # lit .env et utilise os.environ.setdefault() qui ne touche pas
    # une clé déjà présente. Si on pop(), setdefault la rétablit.
    clean_env = os.environ.copy()
    clean_env['DATABASE_URL'] = ''
    clean_env['MYSQL_HOST'] = ''
    clean_env['PYTHONUTF8'] = '1'

    # Écrire le script d'export dans un fichier temporaire
    export_script_path = os.path.join(BASE_DIR, '_export_worker.py')
    with open(export_script_path, 'w', encoding='utf-8') as f:
        f.write('''\
import os, sys, json
os.environ["DATABASE_URL"] = ""
os.environ["MYSQL_HOST"] = ""
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_csig.settings")

import django
django.setup()

from django.conf import settings
from django.core.management import call_command

engine = settings.DATABASES["default"]["ENGINE"]
db = settings.DATABASES["default"]["NAME"]
print(f"DB detectee: {engine} ({db})")

call_command("migrate", "--run-syncdb", verbosity=0)

output = sys.argv[1]
call_command("dumpdata", "--natural-foreign", "--natural-primary",
             indent=2, output=output)

with open(output, "r", encoding="utf-8") as f:
    data = json.load(f)

counts = {}
for item in data:
    counts[item["model"]] = counts.get(item["model"], 0) + 1

print(f"{len(data)} objets exportes ({len(counts)} modeles)")
for m in sorted(counts):
    print(f"  {m}: {counts[m]}")
''')

    try:
        result = subprocess.run(
            [sys.executable, export_script_path, EXPORT_FILE],
            env=clean_env,
            capture_output=True,
            text=True,
            cwd=BASE_DIR,
        )
    finally:
        if os.path.exists(export_script_path):
            os.remove(export_script_path)

    print(result.stdout)
    if result.stderr:
        # Afficher les erreurs (ignorer les warnings Django)
        for line in result.stderr.splitlines():
            if 'Traceback' in line or 'Error' in line:
                print(f"❌ {line}")

    if result.returncode != 0:
        print("❌ Échec de l'export")
        return False

    if not os.path.exists(EXPORT_FILE):
        print("❌ Fichier data_export.json non généré")
        return False

    with open(EXPORT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not data:
        print("❌ Aucune donnée exportée — la DB source est vide")
        return False

    print(f"✅ {len(data)} objets prêts pour l'import")
    return True


# ═══════════════════════════════════════════════════════════════════════
#  IMPORT — charge Neon via DATABASE_URL
# ═══════════════════════════════════════════════════════════════════════

def _setup_neon():
    """Configure Django vers Neon et teste la connexion."""
    database_url = os.environ.get('DATABASE_URL', '')
    if not database_url:
        print("❌ DATABASE_URL non défini")
        return False

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard_csig.settings')

    import django.conf
    if django.conf.settings.configured:
        django.conf.settings._wrapped = django.conf.empty
    import django
    django.setup()

    from django.db import connection
    try:
        with connection.cursor() as c:
            c.execute('SELECT 1')
        host = connection.settings_dict.get('HOST', '?')
        print(f"✅ Connecté à Neon ({host})")
        return True
    except Exception as e:
        print(f"❌ Échec connexion Neon: {e}")
        return False


def _group_by_model(data):
    groups = {}
    for item in data:
        groups.setdefault(item['model'], []).append(item)
    return groups


def import_data(batch_size=5):
    """Importe data_export.json vers Neon dans l'ordre des dépendances."""
    if not _setup_neon():
        return False

    if not os.path.exists(EXPORT_FILE):
        print(f"❌ {EXPORT_FILE} introuvable")
        return False

    with open(EXPORT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    model_data = _group_by_model(data)
    print(f"📥 {len(data)} objets à importer ({len(model_data)} modèles)")

    from django.core import serializers

    total_ok = 0
    total_err = 0

    for model_name in IMPORT_ORDER:
        items = model_data.pop(model_name, [])
        if not items:
            continue

        print(f"\n  {model_name} ({len(items)})")
        ok = 0

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            try:
                objs = serializers.deserialize('json', json.dumps(batch))
                for obj in objs:
                    obj.save()
                ok += len(batch)
            except Exception as e:
                if 'duplicate key' in str(e).lower() or 'already exists' in str(e).lower():
                    ok += len(batch)
                else:
                    print(f"    ⚠  lot {i // batch_size + 1}: {str(e)[:100]}")
                    total_err += len(batch)
                    continue
            time.sleep(0.05)

        total_ok += ok
        print(f"    ✓ {ok}/{len(items)}")

    for model_name, items in model_data.items():
        print(f"\n  {model_name} ({len(items)}) [non ordonné]")
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            try:
                objs = serializers.deserialize('json', json.dumps(batch))
                for obj in objs:
                    obj.save()
                total_ok += len(batch)
            except Exception:
                total_err += len(batch)
            time.sleep(0.05)

    print(f"\n{'='*50}")
    print(f"✅ Import: {total_ok} réussis, {total_err} erreurs")
    return total_err == 0


# ═══════════════════════════════════════════════════════════════════════
#  VÉRIFICATION
# ═══════════════════════════════════════════════════════════════════════

def verify():
    """Affiche les compteurs de chaque modèle dans Neon."""
    if not _setup_neon():
        return False

    from django.contrib.auth.models import User
    from core.models import (
        Direction, Employee, Partner, Project, ProjectMember,
        Milestone, SubMilestone, Event, EventMember,
        Budget, Document, Request, UserProfile, UserActivity,
        Notification, LeaveRequest, LeaveDocument,
        Permission, Role, ProjectRole,
    )

    models = [
        ('Utilisateurs', User),
        ('Permissions', Permission),
        ('Rôles', Role),
        ('Rôles projet', ProjectRole),
        ('Directions', Direction),
        ('Employés', Employee),
        ('Partenaires', Partner),
        ('Projets', Project),
        ('Membres projet', ProjectMember),
        ('Jalons', Milestone),
        ('Sous-étapes', SubMilestone),
        ('Événements', Event),
        ('Membres événement', EventMember),
        ('Budgets', Budget),
        ('Documents', Document),
        ('Demandes', Request),
        ('Profils', UserProfile),
        ('Activités', UserActivity),
        ('Notifications', Notification),
        ('Congés', LeaveRequest),
        ('Docs congés', LeaveDocument),
    ]

    print(f"\n{'='*50}")
    print("📊 Compteurs Neon")
    print(f"{'='*50}")
    for label, model in models:
        try:
            count = model.objects.count()
            print(f"  {label:25s} {count:>6}")
        except Exception as e:
            print(f"  {label:25s} ERREUR: {e}")
    print(f"{'='*50}")
    return True


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Migration vers Neon PostgreSQL')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--export-only', action='store_true',
                       help='Exporter depuis la DB source uniquement')
    group.add_argument('--import-only', action='store_true',
                       help='Importer vers Neon uniquement')
    group.add_argument('--verify-only', action='store_true',
                       help='Vérifier les compteurs Neon uniquement')
    args = parser.parse_args()

    print("=" * 50)
    print("🚀 Migration vers Neon PostgreSQL")
    print("=" * 50)

    if args.verify_only:
        verify()
        return

    if args.import_only:
        ok = import_data()
        if ok:
            verify()
        sys.exit(0 if ok else 1)

    if args.export_only:
        ok = export_data()
        sys.exit(0 if ok else 1)

    print("\nÉtape 1/3 — Export")
    if not export_data():
        sys.exit(1)

    print("\n\nÉtape 2/3 — Import")
    if not import_data():
        sys.exit(1)

    print("\n\nÉtape 3/3 — Vérification")
    verify()

    print("\n✅ Migration terminée")


if __name__ == '__main__':
    main()
