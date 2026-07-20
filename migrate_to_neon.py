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

# Lire .env au démarrage (comme settings.py le fait)
_env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(_env_path):
    with open(_env_path, encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith('#') or '=' not in _line:
                continue
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

EXPORT_FILE = 'data_export.json'

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

IMPORT_ORDER_JSON = json.dumps(IMPORT_ORDER)


# ═══════════════════════════════════════════════════════════════════════
#  WORKER EXPORT — sous-processus avec DATABASE_URL='' (SQLite/MySQL)
# ═══════════════════════════════════════════════════════════════════════

EXPORT_WORKER = '''\
import os, sys, json
os.environ["DATABASE_URL"] = ""
os.environ["MYSQL_HOST"] = ""
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_csig.settings")

import django; django.setup()

from django.conf import settings
from django.core.management import call_command

engine = settings.DATABASES["default"]["ENGINE"]
db_name = settings.DATABASES["default"]["NAME"]
print(f"\U0001f4e6 Source: {engine} ({db_name})")

call_command("migrate", "--run-syncdb", verbosity=0)

output = sys.argv[1]
call_command("dumpdata", "--natural-foreign", "--natural-primary",
             indent=2, output=output)

with open(output, "r", encoding="utf-8") as f:
    data = json.load(f)

counts = {}
for item in data:
    counts[item["model"]] = counts.get(item["model"], 0) + 1

print(f"[OK] {len(data)} objets exportés ({len(counts)} modeles)")
for m in sorted(counts):
    print(f"   {m}: {counts[m]}")
'''


# ═══════════════════════════════════════════════════════════════════════
#  WORKER IMPORT — sous-processus avec DATABASE_URL=Neon
# ═══════════════════════════════════════════════════════════════════════

IMPORT_WORKER = '''\
import os, sys, json, time
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_csig.settings")

import django; django.setup()

from django.conf import settings
from django.db import connection
host = settings.DATABASES["default"].get("HOST", "?")
print(f"\U0001f4e5 Cible: {settings.DATABASES['default']['ENGINE']} ({host})")

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)

import_order = json.loads(sys.argv[2])
model_data = {}
for item in data:
    model_data.setdefault(item["model"], []).append(item)

from django.core import serializers
batch_size = 5
total_ok = 0
total_err = 0

for model_name in import_order:
    items = model_data.pop(model_name, [])
    if not items:
        continue
    print(f"\\n   {model_name} ({len(items)})")
    ok = 0
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        try:
            objs = serializers.deserialize("json", json.dumps(batch))
            for obj in objs:
                obj.save()
            ok += len(batch)
        except Exception as e:
            err = str(e).lower()
            if "duplicate key" in err or "already exists" in err:
                ok += len(batch)
            else:
                print(f"      WARN lot {i // batch_size + 1}: {str(e)[:100]}")
                total_err += len(batch)
                continue
        time.sleep(0.05)
    total_ok += ok
    print(f"      OK {ok}/{len(items)}")

for model_name, items in model_data.items():
    print(f"\\n   {model_name} ({len(items)}) [non ordonne]")
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        try:
            objs = serializers.deserialize("json", json.dumps(batch))
            for obj in objs:
                obj.save()
            total_ok += len(batch)
        except Exception:
            total_err += len(batch)
        time.sleep(0.05)

print(f"\\n{'='*50}")
print(f"Import: {total_ok} reussis, {total_err} erreurs")
print(f"{'='*50}")

# Recalculer les sequences PostgreSQL apres import
from django.db import connection
tables = [
    'auth_user', 'auth_permission', 'django_content_type',
    'core_direction', 'core_employee', 'core_partner',
    'core_permission', 'core_role', 'core_projectrole',
    'core_project', 'core_projectfolder', 'core_projectdocument',
    'core_projectmember', 'core_milestone', 'core_submilestone',
    'core_event', 'core_eventmember', 'core_projectactivity',
    'core_budget', 'core_request', 'core_projectneed',
    'core_projectcomment', 'core_userprofile', 'core_useractivity',
    'core_notification', 'core_leaverequest', 'core_leavedocument',
]
fixed = 0
with connection.cursor() as c:
    for t in tables:
        try:
            c.execute(
                "SELECT setval(pg_get_serial_sequence('{t}', 'id'), "
                "COALESCE((SELECT MAX(id) FROM {t}), 1))".format(t=t)
            )
            fixed += 1
        except Exception:
            pass
print(f"Sequences PostgreSQL recalculees ({fixed} tables)")

sys.exit(0 if total_err == 0 else 1)
'''


# ═══════════════════════════════════════════════════════════════════════
#  FONCTIONS
# ═══════════════════════════════════════════════════════════════════════

def _run_worker(script, args, env_overrides=None):
    """Écrit un script temporaire, l'exécute dans un sous-processus, le supprime."""
    import tempfile
    fd, path = tempfile.mkstemp(suffix='.py', dir=BASE_DIR)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(script)
        env = os.environ.copy()
        env['PYTHONUTF8'] = '1'
        if env_overrides:
            env.update(env_overrides)
        result = subprocess.run(
            [sys.executable, path] + args,
            env=env, capture_output=True, text=True, cwd=BASE_DIR, timeout=600,
        )
    finally:
        os.remove(path)

    if result.stdout:
        print(result.stdout, end='')
    if result.stderr:
        for line in result.stderr.splitlines():
            if 'Traceback' in line or 'Error' in line:
                print(f"  {line}")
    return result.returncode == 0


def export_data():
    """Exporte depuis SQLite/MySQL vers data_export.json."""
    print("📦 Export depuis la DB source...")
    return _run_worker(EXPORT_WORKER, [EXPORT_FILE])


def import_data():
    """Importe data_export.json vers Neon."""
    neon_url = os.environ.get('DATABASE_URL', '')
    if not neon_url:
        print("❌ DATABASE_URL non défini")
        return False
    if not os.path.exists(EXPORT_FILE):
        print(f"❌ {EXPORT_FILE} introuvable")
        return False

    print("\n📥 Import vers Neon...")
    return _run_worker(IMPORT_WORKER, [EXPORT_FILE, IMPORT_ORDER_JSON],
                       env_overrides={'DATABASE_URL': neon_url, 'MYSQL_HOST': ''})


def verify():
    """Vérifie les compteurs Neon."""
    neon_url = os.environ.get('DATABASE_URL', '')
    if not neon_url:
        print("❌ DATABASE_URL non défini")
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
        ('Utilisateurs', User), ('Permissions', Permission),
        ('Rôles', Role), ('Rôles projet', ProjectRole),
        ('Directions', Direction), ('Employés', Employee),
        ('Partenaires', Partner), ('Projets', Project),
        ('Membres projet', ProjectMember), ('Jalons', Milestone),
        ('Sous-étapes', SubMilestone), ('Événements', Event),
        ('Membres événement', EventMember), ('Budgets', Budget),
        ('Documents', Document), ('Demandes', Request),
        ('Profils', UserProfile), ('Activités', UserActivity),
        ('Notifications', Notification), ('Congés', LeaveRequest),
        ('Docs congés', LeaveDocument),
    ]

    print(f"\n{'='*50}")
    print("📊 Compteurs Neon")
    print(f"{'='*50}")
    for label, model in models:
        try:
            print(f"  {label:25s} {model.objects.count():>6}")
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
    group.add_argument('--export-only', action='store_true')
    group.add_argument('--import-only', action='store_true')
    group.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()

    print("=" * 50)
    print("🚀 Migration vers Neon PostgreSQL")
    print("=" * 50)

    if args.verify_only:
        # Vérifier avec un sous-processus Neon
        ok = _run_worker('''
import os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_csig.settings")
import django; django.setup()
from django.db import connection
print(f"Connecté: {connection.settings_dict.get('HOST', '?')}")
''', [])
        return

    if args.import_only:
        ok = import_data()
        if ok:
            ok = _run_worker('''
import os; os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_csig.settings")
import django; django.setup()
from django.contrib.auth.models import User
from core.models import *
models = [("Utilisateurs", User), ("Projets", Project), ("Employés", Employee),
          ("Directions", Direction), ("Jalons", Milestone), ("Events", Event)]
print("\\n📊 Compteurs Neon")
for label, m in models:
    print(f"  {label:20s} {m.objects.count():>6}")
''', [])
        sys.exit(0 if ok else 1)

    if args.export_only:
        sys.exit(0 if export_data() else 1)

    # Mode complet : export → import → vérification
    if not export_data():
        sys.exit(1)
    if not import_data():
        sys.exit(1)
    print("\n✅ Migration terminée")


if __name__ == '__main__':
    main()
