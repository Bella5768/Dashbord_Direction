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

def export_auth_users():
    """Exporte les utilisateurs Django depuis la base de données source"""
    source_db = get_source_database()
    print("=" * 60)
    print(f"📦 Export des utilisateurs Django depuis {source_db}")
    print("=" * 60)
    
    try:
        # Nettoyer les fichiers existants
        for f in ['auth_users.json', 'auth_users_clean.json']:
            if os.path.exists(f):
                os.remove(f)
        
        # Exporter les utilisateurs
        import sys
        if sys.platform == 'win32':
            with open('auth_users.json', 'w', encoding='utf-8') as f:
                call_command('dumpdata', 'auth.User', indent=2, stdout=f)
        else:
            call_command('dumpdata', 'auth.User', indent=2, output='auth_users.json')
        
        # Vérifier le fichier
        with open('auth_users.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✅ {len(data)} utilisateurs exportés")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'export: {e}")
        return False

def export_all_core_data():
    """Exporte toutes les données core depuis la base de données source"""
    source_db = get_source_database()
    print("\n" + "=" * 60)
    print(f"📦 Export des données core depuis {source_db}")
    print("=" * 60)
    
    try:
        # Nettoyer les fichiers existants
        for f in ['core_data.json', 'core_data_clean.json']:
            if os.path.exists(f):
                os.remove(f)
        
        # Exporter toutes les données core
        import sys
        if sys.platform == 'win32':
            with open('core_data.json', 'w', encoding='utf-8') as f:
                call_command('dumpdata', 'core', indent=2, stdout=f)
        else:
            call_command('dumpdata', 'core', indent=2, output='core_data.json')
        
        # Vérifier le fichier
        with open('core_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✅ {len(data)} objets core exportés")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'export: {e}")
        return False

def import_auth_users_to_neon():
    """Importe les utilisateurs vers Neon"""
    print("\n" + "=" * 60)
    print("📥 Import des utilisateurs vers Neon")
    print("=" * 60)
    
    try:
        with open('auth_users.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📊 {len(data)} utilisateurs à importer")
        
        # Importer par lots
        for i in range(0, len(data), 5):
            batch = data[i:i+5]
            try:
                for obj in serializers.deserialize("json", json.dumps(batch)):
                    obj.save()
                print(f"   ✓ Lot {i//5 + 1}/{(len(data)-1)//5 + 1} ({len(batch)} utilisateurs)")
                time.sleep(0.1)
            except Exception as e:
                print(f"   ❌ Erreur lot {i//5 + 1}: {e}")
        
        print("✅ Import utilisateurs terminé")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'import: {e}")
        return False

def import_core_data_to_neon():
    """Importe toutes les données core vers Neon"""
    print("\n" + "=" * 60)
    print("📥 Import des données core vers Neon")
    print("=" * 60)
    
    # Ordre d'import correct
    import_order = [
        'core.direction', 'core.employee', 'core.partner', 
        'core.permission', 'core.role', 'core.projectrole',
        'core.project', 'core.projectfolder', 'core.document',
        'core.projectdocument', 'core.projectmember', 'core.milestone',
        'core.event', 'core.eventmember', 'core.submilestone',
        'core.projectactivity', 'core.budget', 'core.request',
        'core.userprofile', 'core.useractivity', 'core.notification',
        'core.leaverequest', 'core.leavedocument'
    ]
    
    try:
        with open('core_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📊 {len(data)} objets core à importer")
        
        # Organiser par modèle
        model_data = {}
        for item in data:
            model = item['model']
            if model not in model_data:
                model_data[model] = []
            model_data[model].append(item)
        
        # Importer dans l'ordre
        for model_name in import_order:
            if model_name in model_data:
                items = model_data[model_name]
                print(f"\n   📥 {model_name} ({len(items)} objets)")
                
                for i in range(0, len(items), 5):
                    batch = items[i:i+5]
                    try:
                        for obj in serializers.deserialize("json", json.dumps(batch)):
                            obj.save()
                        print(f"      ✓ Lot {i//5 + 1}")
                        time.sleep(0.05)
                    except Exception as e:
                        print(f"      ❌ Erreur lot {i//5 + 1}: {str(e)[:80]}")
        
        print("\n✅ Import core terminé")
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
    
    # Étape 1: Export depuis la base de données source
    if not export_auth_users():
        return False
    
    if not export_all_core_data():
        return False
    
    # Étape 2: Import vers Neon
    if not import_auth_users_to_neon():
        return False
    
    if not import_core_data_to_neon():
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
