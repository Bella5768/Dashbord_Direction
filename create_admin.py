#!/usr/bin/env python
import os
import sys
import django

# Configuration Django
sys.path.insert(0, '/home/dgdashbord/Dashbord_Direction')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard_csig.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import UserProfile, Direction

def create_super_admin():
    """Crée un super-administrateur avec tous les accès"""
    
    # Données de l'admin
    username = "admin"
    email = "admin@csig.com" 
    password = "Admin123!@#"
    
    try:
        # Créer l'utilisateur Django
        if User.objects.filter(username=username).exists():
            print(f"L'utilisateur '{username}' existe déjà.")
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name="Super",
                last_name="Administrateur"
            )
            print(f"✅ Utilisateur '{username}' créé avec succès")
        
        # Créer ou mettre à jour le profil utilisateur
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.role = 'admin'
        profile.is_active_profile = True
        
        # Donner toutes les permissions
        profile.budget_view = True
        profile.budget_manage = True
        profile.budget_view_all_directions = True
        profile.can_create_project = True
        profile.can_edit_projects = True
        profile.can_add_milestones = True
        profile.can_add_members = True
        profile.can_manage_users = True
        profile.can_approve_requests = True
        profile.can_create_events = True
        profile.save()
        
        print(f"✅ Profil utilisateur mis à jour avec rôle 'admin'")
        print(f"✅ Tous les accès accordés")
        
        print(f"\n🔑 IDENTIFIANTS DE CONNEXION :")
        print(f"📍 URL : https://dgdashbord.pythonanywhere.com/login")
        print(f"👤 Utilisateur : {username}")
        print(f"🔐 Mot de passe : {password}")
        print(f"📧 Email : {email}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return False

if __name__ == "__main__":
    print("🚀 Création du super-administrateur...")
    success = create_super_admin()
    
    if success:
        print("\n✨ Super-administrateur créé avec succès !")
        print("🌐 Vous pouvez maintenant vous connecter et accéder à tout.")
    else:
        print("\n❌ Échec de la création. Vérifiez les erreurs ci-dessus.")
