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
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Fix Windows console encoding
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

IMPORT_ORDER_JSON = json.dumps(IMPORT_ORDER)


# ═══════════════════════════════════════════════════════════════════════
#  WORKER — un seul sous-processus qui fait export + import
# ═══════════════════════════════════════════════════════════════════════

WORKER_SCRIPT = r'''
import os, sys, json, time

# Phase 1 : EXPORT — forcer SQLite/MySQL (pas Neon)
os.environ["DATABASE_URL"] = ""
os.environ["MYSQL_HOST"] = ""
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_csig.settings")

import django
django.setup()

from django.conf import settings
from django.core.management import call_command

engine = settings.DATABASES["default"]["ENGINE"]
db_name = settings.DATABASES["default"]["NAME"]
print(f"📦 Source: {engine} ({db_name})")

call_command("migrate", "--run-syncdb", verbosity=0)

output_file = sys.argv[1]
call_command("dumpdata", "--natural-foreign", "--natural-primary",
             indent=2, output=output_file)

with open(output_file, "r", encoding="utf-8") as f:
    data = json.load(f)

counts = {}
for item in data:
    counts[item["model"]] = counts.get(item["model"], 0) + 1

print(f"✅ {len(data)} objets exportés ({len(counts)} modèles)")
for m in sorted(counts):
    print(f"   {m}: {counts[m]}")

# Fermer la connexion SQLite
from django.db import connection
connection.close()

# Phase 2 : IMPORT — recharger Django vers Neon
neon_url = sys.argv[2]
os.environ["DATABASE_URL"] = neon_url
os.environ["MYSQL_HOST"] = ""

# Recharger les settings avec DATABASE_URL
import importlib
import dashboard_csig.settings
importlib.reload(dashboard_csig.settings)

from django.conf import settings as s2
print(f"\n📥 Cible: {s2.DATABASES['default']['ENGINE']} ({s2.DATABASES['default']['HOST']})")

from django.core import serializers

import_order = json.loads(sys.argv[3])
model_data = {}
for item in data:
    model_data.setdefault(item["model"], []).append(item)

batch_size = 5
total_ok = 0
total_err = 0

for model_name in import_order:
    items = model_data.pop(model_name, [])
    if not items:
        continue

    print(f"\n   {model_name} ({len(items)})")
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
                print(f"      ⚠  lot {i // batch_size + 1}: {str(e)[:100]}")
                total_err += len(batch)
                continue
        time.sleep(0.05)

    total_ok += ok
    print(f"      ✓ {ok}/{len(items)}")

# Modèles non dans l'ordre
for model_name, items in model_data.items():
    print(f"\n   {model_name} ({len(items)}) [non ordonné]")
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

print(f"\n{'='*50}")
print(f"✅ Import: {total_ok} réussis, {total_err} erreurs")
print(f"{'='*50}")

sys.exit(0 if total_err == 0 else 1)
'''


# ═══════════════════════════════════════════════════════════════════════
#  EXPORT + IMPORT — un seul sous-processus
# ═══════════════════════════════════════════════════════════════════════

def run_migration():
    """Lance export + import dans un seul sous-processus isolé."""
    neon_url = os.environ.get('DATABASE_URL', '')
    if not neon_url:
        print("❌ DATABASE_URL non défini — impossible d'importer vers Neon")
        return False

    # Sauvegarder le worker dans un fichier temporaire
    worker_path = os.path.join(BASE_DIR, '_migrate_worker.py')
    with open(worker_path, 'w', encoding='utf-8') as f:
        f.write(WORKER_SCRIPT)

    try:
        env = os.environ.copy()
        env['PYTHONUTF8'] = '1'

        result = subprocess.run(
            [sys.executable, worker_path, EXPORT_FILE, neon_url, IMPORT_ORDER_JSON],
            env=env,
            capture_output=True,
            text=True,
            cwd=BASE_DIR,
            timeout=600,
        )
    finally:
        if os.path.exists(worker_path):
            os.remove(worker_path)

    # Afficher la sortie
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        for line in result.stderr.splitlines():
            if 'Traceback' in line or 'Error' in line:
                print(f"❌ {line}")

    return result.returncode == 0


# ═══════════════════════════════════════════════════════════════════════
#  EXPORT SEUL
# ═══════════════════════════════════════════════════════════════════════

def export_only():
    """Exporte depuis la DB source vers data_export.json."""
    neon_url = os.environ.get('DATABASE_URL', '')

    worker_path = os.path.join(BASE_DIR, '_migrate_worker.py')
    # Worker qui fait juste l'export (pas d'import)
    export_script = WORKER_SCRIPT.split('# Phase 2')[0].rstrip()

    with open(worker_path, 'w', encoding='utf-8') as f:
        f.write(export_script + '\nprint("OK_EXPORT")\n')

    try:
        env = os.environ.copy()
        env['PYTHONUTF8'] = '1'

        result = subprocess.run(
            [sys.executable, worker_path, EXPORT_FILE],
            env=env,
            capture_output=True,
            text=True,
            cwd=BASE_DIR,
        )
    finally:
        if os.path.exists(worker_path):
            os.remove(worker_path)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        for line in result.stderr.splitlines():
            if 'Traceback' in line or 'Error' in line:
                print(f"❌ {line}")

    return result.returncode == 0


# ═══════════════════════════════════════════════════════════════════════
#  IMPORT SEUL
# ═══════════════════════════════════════════════════════════════════════

def import_only():
    """Importe data_export.json vers Neon."""
    neon_url = os.environ.get('DATABASE_URL', '')
    if not neon_url:
        print("❌ DATABASE_URL non défini")
        return False

    if not os.path.exists(EXPORT_FILE):
        print(f"❌ {EXPORT_FILE} introuvable")
        return False

    # Worker qui fait juste l'import
    import_script = WORKER_SCRIPT.split('# Phase 2')[1]
    import_script = WORKER_SCRIPT.split('# Fermer la connexion SQLite')[0].rstrip() + \
        WORKER_SCRIPT.split('# Phase 2 : IMPORT')[1]

    # Simpler: écrire un worker import-only
    import_worker = r'''
import os, sys, json, time
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_csig.settings")

import django
django.setup()

from django.conf import settings
neon_url = sys.argv[1]
print(f"📥 Cible: {settings.DATABASES['default']['ENGINE']} ({settings.DATABASES['default'].get('HOST', '?')})")

from django.core import serializers

with open(sys.argv[2], "r", encoding="utf-8") as f:
    data = json.load(f)

import_order = json.loads(sys.argv[3])
model_data = {}
for item in data:
    model_data.setdefault(item["model"], []).append(item)

batch_size = 5
total_ok = 0
total_err = 0

for model_name in import_order:
    items = model_data.pop(model_name, [])
    if not items:
        continue
    print(f"\n   {model_name} ({len(items)})")
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
                print(f"      ⚠  lot {i // batch_size + 1}: {str(e)[:100]}")
                total_err += len(batch)
                continue
        time.sleep(0.05)
    total_ok += ok
    print(f"      ✓ {ok}/{len(items)}")

for model_name, items in model_data.items():
    print(f"\n   {model_name} ({len(items)}) [non ordonné]")
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

print(f"\n{'='*50}")
print(f"✅ Import: {total_ok} réussis, {total_err} erreurs")
print(f"{'='*50}")
sys.exit(0 if total_err == 0 else 1)
'''
    worker_path = os.path.join(BASE_DIR, '_import_worker.py')
    with open(worker_path, 'w', encoding='utf-8') as f:
        f.write(import_worker)

    try:
        env = os.environ.copy()
        env['PYTHONUTF8'] = '1'
        result = subprocess.run(
            [sys.executable, worker_path, neon_url, EXPORT_FILE, IMPORT_ORDER_JSON],
            env=env, capture_output=True, text=True, cwd=BASE_DIR,
        )
    finally:
        if os.path.exists(worker_path):
            os.remove(worker_path)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        for line in result.stderr.splitlines():
            if 'Traceback' in line or 'Error' in line:
                print(f"❌ {line}")

    return result.returncode == 0


# ═══════════════════════════════════════════════════════════════════════
#  VÉRIFICATION
# ═══════════════════════════════════════════════════════════════════════

def verify():
    """Affiche les compteurs de chaque modèle dans Neon."""
    if not os.environ.get('DATABASE_URL'):
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
        print(f"✅ Connecté à {connection.settings_dict.get('HOST', '?')}")
    except Exception as e:
        print(f"❌ Connexion échouée: {e}")
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
        verify(); return
    if args.import_only:
        ok = import_only()
        if ok: verify()
        sys.exit(0 if ok else 1)
    if args.export_only:
        sys.exit(0 if export_only() else 1)

    # Mode complet
    ok = run_migration()
    if ok:
        verify()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
