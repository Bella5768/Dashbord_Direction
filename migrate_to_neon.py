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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ── Ordre d'import (dépendances FK) ──────────────────────────────────
IMPORT_ORDER = [
    # Niveau 0 : tables indépendantes
    'auth.user',
    'core.direction',
    'core.employee',
    'core.partner',
    'core.permission',
    'core.role',
    'core.projectrole',
    # Niveau 1
    'core.project',
    'core.projectfolder',
    'core.document',
    # Niveau 2
    'core.projectdocument',
    'core.projectmember',
    'core.milestone',
    'core.event',
    'core.eventmember',
    # Niveau 3
    'core.submilestone',
    'core.projectactivity',
    'core.budget',
    'core.request',
    'core.projectneed',
    'core.projectcomment',
    # Niveau 4 (dépendent de auth.user)
    'core.userprofile',
    'core.useractivity',
    'core.notification',
    'core.leaverequest',
    'core.leavedocument',
]

EXPORT_FILE = 'data_export.json'


# ═══════════════════════════════════════════════════════════════════════
#  EXPORT
# ═══════════════════════════════════════════════════════════════════════

def _setup_source_db():
    """Force la connexion à SQLite en neutralisant DATABASE_URL / MYSQL_HOST."""
    os.environ.pop('DATABASE_URL', None)
    os.environ.pop('MYSQL_HOST', None)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard_csig.settings')

    # Recharger les settings pour prendre en compte les env vars nettoyés
    import django.conf
    if django.conf.settings.configured:
        django.conf.settings._wrapped = django.conf.empty
    import django
    django.setup()


def export_data():
    """Exporte les données depuis la DB source vers data_export.json."""
    _setup_source_db()

    from django.conf import settings
    from django.core.management import call_command

    engine = settings.DATABASES['default']['ENGINE']
    db_name = settings.DATABASES['default']['NAME']
    print(f"📦 Export depuis {engine} ({db_name})")

    # S'assurer que les tables existent (SQLite peut être vierge)
    print("   Migration de la DB source...")
    call_command('migrate', '--run-syncdb', verbosity=0)

    if os.path.exists(EXPORT_FILE):
        os.remove(EXPORT_FILE)

    # Sur Windows, stdout=file fonctionne mieux que output=
    if sys.platform == 'win32':
        with open(EXPORT_FILE, 'w', encoding='utf-8') as f:
            call_command('dumpdata', '--natural-foreign', '--natural-primary',
                         indent=2, stdout=f)
    else:
        call_command('dumpdata', '--natural-foreign', '--natural-primary',
                     indent=2, output=EXPORT_FILE)

    with open(EXPORT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    counts = {}
    for item in data:
        counts[item['model']] = counts.get(item['model'], 0) + 1

    print(f"✅ {len(data)} objets exportés ({len(counts)} modèles)")
    for model in sorted(counts):
        print(f"   {model}: {counts[model]}")
    return True


# ═══════════════════════════════════════════════════════════════════════
#  IMPORT
# ═══════════════════════════════════════════════════════════════════════

def _setup_neon():
    """Vérifie DATABASE_URL et configure Django vers Neon."""
    if not os.getenv('DATABASE_URL'):
        print("❌ DATABASE_URL non défini — impossible de se connecter à Neon")
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
        print(f"✅ Connecté à Neon ({connection.settings_dict['HOST']})")
        return True
    except Exception as e:
        print(f"❌ Échec connexion Neon: {e}")
        return False


def _group_by_model(data):
    """Regroupe les objets JSON par nom de modèle."""
    groups = {}
    for item in data:
        groups.setdefault(item['model'], []).append(item)
    return groups


def import_data(batch_size=5):
    """Importe data_export.json vers Neon dans l'ordre des dépendances."""
    if not _setup_neon():
        return False

    if not os.path.exists(EXPORT_FILE):
        print(f"❌ {EXPORT_FILE} introuvable — lancez d'abord l'export")
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
                # Doublon → ignorer ; autre erreur → signaler
                if 'duplicate key' in str(e).lower() or 'already exists' in str(e).lower():
                    ok += len(batch)  # considérer comme OK
                else:
                    print(f"    ⚠  lot {i // batch_size + 1}: {str(e)[:100]}")
                    total_err += len(batch)
                    continue
            time.sleep(0.05)

        total_ok += ok
        print(f"    ✓ {ok}/{len(items)}")

    # Modèles non prévus dans l'ordre
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

    # ── Mode complet : export → import → vérification ──
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
