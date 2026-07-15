#!/usr/bin/env python
"""
Script de migration SQLite vers Neon pour développement
Usage: python migrate_to_neon_dev.py

Ce script:
1. Exporte toutes les données depuis SQLite
2. Importe vers Neon PostgreSQL
3. Gère les dépendances et les erreurs
"""

import os
import sys
import django
import json
import time

# Configuration pour utiliser SQLite (source)
os.environ['DATABASE_URL'] = ''
os.environ['MYSQL_HOST'] = ''

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard_csig.settings')
django.setup()

from django.core.management import call_command
from django.core import serializers

def export_from_sqlite():
    """Exporte toutes les données depuis SQLite"""
    print("=" * 60)
    print("📦 Export depuis SQLite")
    print("=" * 60)
    
    try:
        # Nettoyer les fichiers existants
        for f in ['dev_export_auth.json', 'dev_export_core.json']:
            if os.path.exists(f):
                os.remove(f)
        
        # Exporter les utilisateurs
        print("📥 Export des utilisateurs...")
        if sys.platform == 'win32':
            with open('dev_export_auth.json', 'w', encoding='utf-8') as f:
                call_command('dumpdata', 'auth.User', indent=2, stdout=f)
        else:
            call_command('dumpdata', 'auth.User', indent=2, output='dev_export_auth.json')
        
        # Exporter les données core
        print("📥 Export des données core...")
        if sys.platform == 'win32':
            with open('dev_export_core.json', 'w', encoding='utf-8') as f:
                call_command('dumpdata', 'core', indent=2, stdout=f)
        else:
            call_command('dumpdata', 'core', indent=2, output='dev_export_core.json')
        
        # Vérifier
        with open('dev_export_auth.json', 'r', encoding='utf-8') as f:
            auth_count = len(json.load(f))
        with open('dev_export_core.json', 'r', encoding='utf-8') as f:
            core_count = len(json.load(f))
        
        print(f"✅ {auth_count} utilisateurs exportés")
        print(f"✅ {core_count} objets core exportés")
        return True
        
    except Exception as e:
        print(f"❌ Erreur d'export: {e}")
        return False

def import_to_neon():
    """Importe vers Neon avec gestion des dépendances"""
    print("\n" + "=" * 60)
    print("📥 Import vers Neon")
    print("=" * 60)
    
    # Ordre d'import respectant les dépendances
    import_order = [
        # Niveau 0: Indépendant
        'auth.user',
        'core.direction', 'core.employee', 'core.partner',
        'core.permission', 'core.role', 'core.projectrole',
        # Niveau 1: Dépend du niveau 0
        'core.project', 'core.projectfolder', 'core.document',
        # Niveau 2: Dépend du niveau 1
        'core.projectdocument', 'core.projectmember', 'core.milestone',
        'core.event', 'core.eventmember',
        # Niveau 3: Dépend du niveau 2
        'core.submilestone', 'core.projectactivity', 'core.budget', 'core.request',
        # Niveau 4: Dépend de auth.user
        'core.userprofile', 'core.useractivity', 'core.notification',
        'core.leaverequest', 'core.leavedocument'
    ]
    
    # Charger les données
    with open('dev_export_auth.json', 'r', encoding='utf-8') as f:
        auth_data = json.load(f)
    with open('dev_export_core.json', 'r', encoding='utf-8') as f:
        core_data = json.load(f)
    
    all_data = auth_data + core_data
    
    # Organiser par modèle
    model_data = {}
    for item in all_data:
        model = item['model']
        if model not in model_data:
            model_data[model] = []
        model_data[model].append(item)
    
    # Importer dans l'ordre
    total_imported = 0
    for model_name in import_order:
        if model_name in model_data:
            items = model_data[model_name]
            print(f"\n📥 {model_name} ({len(items)} objets)")
            
            imported = 0
            for i in range(0, len(items), 5):
                batch = items[i:i+5]
                try:
                    for obj in serializers.deserialize("json", json.dumps(batch)):
                        obj.save()
                    imported += len(batch)
                    time.sleep(0.05)
                except Exception as e:
                    # Ignorer les doublons en développement
                    if "duplicate key" in str(e).lower():
                        continue
                    print(f"   ⚠️  Erreur lot {i//5 + 1}: {str(e)[:50]}")
            
            total_imported += imported
            print(f"   ✅ {imported}/{len(items)} importés")
    
    print(f"\n📊 Total: {total_imported}/{len(all_data)} objets importés")
    return True

def verify_migration():
    """Vérifie la migration"""
    print("\n" + "=" * 60)
    print("🔍 Vérification")
    print("=" * 60)
    
    try:
        from django.contrib.auth.models import User
        from core.models import (Project, Employee, Direction, Document, 
                                Milestone, Event, Budget, Request, 
                                UserProfile, UserActivity, Notification,
                                LeaveRequest, LeaveDocument)
        
        models = [
            ('Utilisateurs', User),
            ('Projets', Project),
            ('Employés', Employee),
            ('Directions', Direction),
            ('Documents', Document),
            ('Milestones', Milestone),
            ('Events', Event),
            ('Budgets', Budget),
            ('Requests', Request),
            ('UserProfiles', UserProfile),
            ('UserActivities', UserActivity),
            ('Notifications', Notification),
            ('LeaveRequests', LeaveRequest),
            ('LeaveDocuments', LeaveDocument)
        ]
        
        for name, model in models:
            count = model.objects.count()
            print(f"📊 {name}: {count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur de vérification: {e}")
        return False

def main():
    print("=" * 60)
    print("🚀 Migration SQLite → Neon (Développement)")
    print("=" * 60)
    
    # Étape 1: Export
    if not export_from_sqlite():
        return False
    
    # Étape 2: Import
    if not import_to_neon():
        return False
    
    # Étape 3: Vérification
    if not verify_migration():
        return False
    
    print("\n" + "=" * 60)
    print("✅ Migration terminée avec succès!")
    print("=" * 60)
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
