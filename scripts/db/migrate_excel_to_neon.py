#!/usr/bin/env python
"""
Script pour migrer les données Excel vers Neon PostgreSQL
Usage: python migrate_excel_to_neon.py

Ce script:
1. Lit les fichiers Excel depuis scripts/db/
2. Mappe les colonnes aux modèles Django
3. Importe les données vers Neon en respectant les dépendances
"""

import os
import sys
import django
import pandas as pd
from datetime import datetime
import numpy as np

# Chemin correct vers le répertoire racine du projet
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard_csig.settings')
django.setup()

from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from core.models import (
    Direction, Employee, Partner, Project, ProjectFolder, Document,
    ProjectDocument, ProjectMember, Milestone, Event, EventMember,
    SubMilestone, ProjectActivity, Budget, Request,
    UserProfile, UserActivity, Notification, LeaveRequest, LeaveDocument
)

EXCEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

# Mapping des fichiers Excel vers les modèles Django
EXCEL_MODEL_MAPPING = {
    'auth_permission.xlsx': Permission,
    'auth_user.xlsx': User,
    'core_direction.xlsx': Direction,
    'core_employee.xlsx': Employee,
    'core_partner.xlsx': Partner,
    'core_project.xlsx': Project,
    'core_projectfolder.xlsx': ProjectFolder,
    'core_document.xlsx': Document,
    'core_projectdocument.xlsx': ProjectDocument,
    'core_projectmember.xlsx': ProjectMember,
    'core_milestone.xlsx': Milestone,
    'core_projectactivity.xlsx': ProjectActivity,
    'core_userprofile.xlsx': UserProfile,
    'core_useractivity.xlsx': UserActivity,
    'core_leaverequest.xlsx': LeaveRequest,
    'core_leavedocument.xlsx': LeaveDocument,
    'django_content_type.xlsx': ContentType,
}

# Ordre d'import pour respecter les dépendances
IMPORT_ORDER = [
    'django_content_type.xlsx',
    'auth_permission.xlsx',
    'auth_user.xlsx',
    'core_direction.xlsx',
    'core_employee.xlsx',
    'core_partner.xlsx',
    'core_project.xlsx',
    'core_projectfolder.xlsx',
    'core_document.xlsx',
    'core_projectdocument.xlsx',
    'core_projectmember.xlsx',
    'core_milestone.xlsx',
    'core_projectactivity.xlsx',
    'core_userprofile.xlsx',
    'core_useractivity.xlsx',
    'core_leaverequest.xlsx',
    'core_leavedocument.xlsx',
]

def clean_nan(value):
    """Remplace NaN par None ou valeur par défaut"""
    if isinstance(value, float) and np.isnan(value):
        return None
    return value

def get_model_fields(model_class):
    """Retourne la liste des champs valides pour un modèle"""
    return [field.name for field in model_class._meta.get_fields()]

def filter_valid_fields(row_data, model_class):
    """Filtre les données pour ne garder que les champs valides du modèle"""
    valid_fields = get_model_fields(model_class)
    return {k: v for k, v in row_data.items() if k in valid_fields}

def handle_null_constraints(row_data, model_class):
    """Gère les contraintes NOT NULL en mettant des valeurs par défaut"""
    from django.db.models import TextField, CharField
    
    for field in model_class._meta.get_fields():
        if not field.null and not field.blank and not field.default:
            field_name = field.name
            if field_name in row_data and row_data[field_name] is None:
                # Valeur par défaut selon le type de champ
                if isinstance(field, (TextField, CharField)):
                    row_data[field_name] = ""
                elif hasattr(field, 'default') and field.default != '':
                    row_data[field_name] = field.default
    return row_data

def import_excel_to_model(filename, model_class):
    """Importe un fichier Excel vers un modèle Django"""
    filepath = os.path.join(EXCEL_DIR, filename)
    
    if not os.path.exists(filepath):
        print(f"   ⏭️  {filename} (fichier introuvable)")
        return 0
    
    try:
        df = pd.read_excel(filepath)
        print(f"   📥 {filename} ({len(df)} lignes)")
        
        # Vérifier si des données existent déjà
        if model_class.objects.exists():
            print(f"   ⏭️  Données déjà présentes ({model_class.objects.count()} objets)")
            return 0
        
        imported = 0
        errors = 0
        
        for index, row in df.iterrows():
            try:
                # Nettoyer les valeurs NaN
                row_data = {k: clean_nan(v) for k, v in row.to_dict().items()}
                
                # Filtrer les champs valides
                row_data = filter_valid_fields(row_data, model_class)
                
                # Gérer les contraintes NOT NULL
                row_data = handle_null_constraints(row_data, model_class)
                
                # Créer l'objet (sans update_or_create pour éviter les duplicate key errors)
                obj = model_class(**row_data)
                obj.save()
                imported += 1
                    
            except Exception as e:
                errors += 1
                if errors <= 3:  # Afficher seulement les 3 premières erreurs
                    print(f"      ❌ Erreur ligne {index + 1}: {str(e)[:60]}")
        
        print(f"   ✅ {imported}/{len(df)} importés, {errors} erreurs")
        return imported
        
    except Exception as e:
        print(f"   ❌ Erreur lecture {filename}: {e}")
        return 0

def main():
    print("=" * 60)
    print("🚀 Migration Excel vers Neon PostgreSQL")
    print("=" * 60)
    
    # Vérifier que nous utilisons Neon
    from django.conf import settings
    db_engine = settings.DATABASES['default']['ENGINE']
    if 'postgresql' not in db_engine:
        print(f"⚠️  Base de données actuelle: {db_engine}")
        print("⚠️  Assurez-vous que DATABASE_URL est configuré pour Neon")
        response = input("Continuer quand même? (y/n): ")
        if response.lower() != 'y':
            return False
    else:
        print("✅ Base de données Neon PostgreSQL détectée")
    
    # Appliquer les migrations si nécessaire
    print("\n📋 Application des migrations...")
    try:
        call_command('migrate', '--noinput')
        print("✅ Migrations appliquées")
    except Exception as e:
        print(f"⚠️  Erreur migrations: {e}")
    
    # Importer dans l'ordre
    total_imported = 0
    for filename in IMPORT_ORDER:
        if filename in EXCEL_MODEL_MAPPING:
            model_class = EXCEL_MODEL_MAPPING[filename]
            imported = import_excel_to_model(filename, model_class)
            total_imported += imported
        else:
            print(f"   ⏭️  {filename} (modèle non implémenté)")
    
    # Traiter les fichiers non listés
    all_files = [f for f in os.listdir(EXCEL_DIR) if f.endswith('.xlsx')]
    unlisted_files = set(all_files) - set(IMPORT_ORDER) - set(['analyze_excel.py', 'migrate_excel_to_neon.py'])
    
    if unlisted_files:
        print(f"\n⚠️  Fichiers non traités (modèle non implémenté):")
        for filename in sorted(unlisted_files):
            print(f"   - {filename}")
    
    print("\n" + "=" * 60)
    print(f"✅ Migration terminée: {total_imported} objets importés")
    print("=" * 60)
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
