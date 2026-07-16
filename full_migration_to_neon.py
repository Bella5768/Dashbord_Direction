#!/usr/bin/env python
"""
Script de migration complète vers Neon incluant l'extraction et l'import
Usage: python full_migration_to_neon.py

Ce script:
1. Extrait les données depuis la base de données source (SQLite/MySQL)
2. Importe les données vers Neon PostgreSQL
3. Gère les dépendances et les erreurs
"""

import os
import sys
import django
import json
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard_csig.settings')
django.setup()

from django.core.management import call_command
from django.core import serializers
from django.conf import settings

def get_source_database():
    """Détecte la base de données source (SQLite ou MySQL)"""
    db_engine = settings.DATABASES['default']['ENGINE']
    
    if 'sqlite' in db_engine:
        return 'SQLite'
    elif 'mysql' in db_engine:
        return 'MySQL'
    elif 'postgresql' in db_engine:
        return 'PostgreSQL'
    else:
        return 'Inconnu'

def export_all_data():
    """Exporte TOUTES les données depuis la base de données source"""
    source_db = get_source_database()
    print("=" * 60)
    print(f"📦 Export de TOUTES les données depuis {source_db}")
    print("=" * 60)
    
    try:
        # Nettoyer les fichiers existants
        for f in ['all_data.json', 'all_data_clean.json']:
            if os.path.exists(f):
                os.remove(f)
        
        # Exporter toutes les données (toutes les applications)
        import sys
        if sys.platform == 'win32':
            with open('all_data.json', 'w', encoding='utf-8') as f:
                call_command('dumpdata', indent=2, stdout=f)
        else:
            call_command('dumpdata', indent=2, output='all_data.json')
        
        # Vérifier le fichier
        with open('all_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Compter par modèle
        model_counts = {}
        for item in data:
            model = item['model']
            model_counts[model] = model_counts.get(model, 0) + 1
        
        print(f"✅ {len(data)} objets exportés au total")
        print(f"📊 {len(model_counts)} modèles différents")
        
        # Afficher les détails
        for model, count in sorted(model_counts.items()):
            print(f"   - {model}: {count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'export: {e}")
        import traceback
        traceback.print_exc()
        return False

def import_all_data_to_neon():
    """Importe toutes les données vers Neon"""
    print("\n" + "=" * 60)
    print("📥 Import de toutes les données vers Neon")
    print("=" * 60)
    
    try:
        with open('all_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📊 {len(data)} objets à importer")
        
        # Organiser par modèle
        model_data = {}
        for item in data:
            model = item['model']
            if model not in model_data:
                model_data[model] = []
            model_data[model].append(item)
        
        # Ordre d'import pour respecter les dépendances
        # Système Django d'abord
        import_order = [
            # Django auth
            'auth.user',
            'auth.permission',
            'auth.group',
            'contenttypes.contenttype',
            'sessions.session',
            # Core - niveau 0 (indépendant)
            'core.direction', 'core.employee', 'core.partner',
            'core.permission', 'core.role', 'core.projectrole',
            # Core - niveau 1 (dépend du niveau 0)
            'core.project', 'core.projectfolder', 'core.document',
            # Core - niveau 2 (dépend du niveau 1)
            'core.projectdocument', 'core.projectmember', 'core.milestone',
            'core.event', 'core.eventmember',
            # Core - niveau 3 (dépend du niveau 2)
            'core.submilestone', 'core.projectactivity', 'core.budget', 'core.request',
            # Core - niveau 4 (dépend de auth.user)
            'core.userprofile', 'core.useractivity', 'core.notification',
            'core.leaverequest', 'core.leavedocument'
        ]
        
        # Importer dans l'ordre
        total_imported = 0
        for model_name in import_order:
            if model_name in model_data:
                items = model_data[model_name]
                print(f"\n   � {model_name} ({len(items)} objets)")
                
                imported = 0
                for i in range(0, len(items), 5):
                    batch = items[i:i+5]
                    try:
                        for obj in serializers.deserialize("json", json.dumps(batch)):
                            obj.save()
                        imported += len(batch)
                        print(f"      ✓ Lot {i//5 + 1}")
                        time.sleep(0.05)
                    except Exception as e:
                        # Ignorer les doublons
                        if "duplicate key" in str(e).lower():
                            continue
                        print(f"      ❌ Erreur lot {i//5 + 1}: {str(e)[:80]}")
                
                total_imported += imported
                print(f"   ✅ {imported}/{len(items)} importés")
        
        # Importer les modèles non listés
        unlisted_models = set(model_data.keys()) - set(import_order)
        if unlisted_models:
            print(f"\n⚠️  Modèles non listés dans l'ordre d'import:")
            for model_name in unlisted_models:
                items = model_data[model_name]
                print(f"   📥 {model_name} ({len(items)} objets)")
                
                imported = 0
                for i in range(0, len(items), 5):
                    batch = items[i:i+5]
                    try:
                        for obj in serializers.deserialize("json", json.dumps(batch)):
                            obj.save()
                        imported += len(batch)
                        time.sleep(0.05)
                    except Exception as e:
                        if "duplicate key" in str(e).lower():
                            continue
                        print(f"      ❌ Erreur: {str(e)[:80]}")
                
                total_imported += imported
        
        print(f"\n📊 Total: {total_imported}/{len(data)} objets importés")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'import: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_migration():
    """Vérifie la migration complète"""
    print("\n" + "=" * 60)
    print("🔍 Vérification de la migration")
    print("=" * 60)
    
    try:
        from django.contrib.auth.models import User
        from core.models import (Project, Employee, Direction, Document, 
                                Milestone, Event, Budget, Request, 
                                UserProfile, UserActivity, Notification)
        
        print(f"👥 Utilisateurs: {User.objects.count()}")
        print(f"📊 Projets: {Project.objects.count()}")
        print(f"👤 Employés: {Employee.objects.count()}")
        print(f"🏢 Directions: {Direction.objects.count()}")
        print(f"📄 Documents: {Document.objects.count()}")
        print(f"🎯 Milestones: {Milestone.objects.count()}")
        print(f"📅 Events: {Event.objects.count()}")
        print(f"💰 Budgets: {Budget.objects.count()}")
        print(f"📋 Requests: {Request.objects.count()}")
        print(f"👤 UserProfiles: {UserProfile.objects.count()}")
        print(f"📝 UserActivities: {UserActivity.objects.count()}")
        print(f"🔔 Notifications: {Notification.objects.count()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")
        return False

def main():
    print("=" * 60)
    print("🚀 Migration complète vers Neon PostgreSQL")
    print("=" * 60)
    
    # Afficher la base de données source
    source_db = get_source_database()
    print(f"📊 Base de données source: {source_db}")
    
    # Étape 1: Export de TOUTES les données depuis la base de données source
    if not export_all_data():
        return False
    
    # Étape 2: Import de toutes les données vers Neon
    if not import_all_data_to_neon():
        return False
    
    # Étape 3: Vérification
    if not verify_migration():
        return False
    
    print("\n" + "=" * 60)
    print("✅ Migration complète terminée avec succès!")
    print("=" * 60)
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
