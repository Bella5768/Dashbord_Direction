"""
Script pour configurer le fichier .env avec les paramètres email.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
env_file = BASE_DIR / '.env'

print("=" * 60)
print("CONFIGURATION DES EMAILS - FICHIER .ENV")
print("=" * 60)

# Vérifier si le fichier .env existe
if env_file.exists():
    print(f"\n✅ Fichier .env trouvé: {env_file}")
    print("\nContenu actuel du fichier .env:")
    print("-" * 60)
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
        # Masquer le mot de passe s'il existe
        lines = content.split('\n')
        for line in lines:
            if 'EMAIL_HOST_PASSWORD' in line and '=' in line:
                key, value = line.split('=', 1)
                if value and value != 'remplacer_par_le_mot_de_passe_application_outlook':
                    masked = value[:2] + '*' * (len(value) - 4) + value[-2:] if len(value) > 4 else '****'
                    print(f"{key}={masked}")
                else:
                    print(line)
            else:
                print(line)
    print("-" * 60)
else:
    print(f"\n❌ Fichier .env non trouvé: {env_file}")
    print("Création du fichier .env...")
    env_file.touch()
    print("✅ Fichier .env créé")

# Configuration recommandée
recommended_config = """
# Configuration Email Office 365
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=support@csig.edu.gn
EMAIL_HOST_PASSWORD=gnnthnprwdlklnfd
DEFAULT_FROM_EMAIL=support@csig.edu.gn
EMAIL_LOCAL_HOSTNAME=csig.edu.gn
"""

print("\n📝 Configuration recommandée:")
print("-" * 60)
print(recommended_config)
print("-" * 60)

print("\n⚠️  IMPORTANT:")
print("1. Pour Office 365, vous DEVEZ utiliser un MOT DE PASSE D'APPLICATION")
print("2. Activez l'authentification à deux facteurs sur votre compte Microsoft")
print("3. Générez un mot de passe d'application sur: https://account.microsoft.com/security")
print("4. Remplacez 'gnnthnprwdlklnfd' par votre mot de passe d'application")

print("\n🔧 Options:")
print("1. Mettre à jour automatiquement le fichier .env")
print("2. Afficher seulement les lignes à ajouter manuellement")

choice = input("\nVotre choix (1 ou 2): ").strip()

if choice == '1':
    # Lire le contenu actuel
    current_content = ""
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            current_content = f.read()
    
    # Supprimer les anciennes lignes EMAIL_ si elles existent
    lines = current_content.split('\n')
    filtered_lines = []
    for line in lines:
        if not line.startswith('EMAIL_') and not line.startswith('DEFAULT_FROM_EMAIL') and not line.startswith('EMAIL_LOCAL_HOSTNAME'):
            filtered_lines.append(line)
    
    # Ajouter la nouvelle configuration
    new_content = '\n'.join(filtered_lines)
    if new_content and not new_content.endswith('\n'):
        new_content += '\n'
    new_content += recommended_config
    
    # Écrire le nouveau contenu
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("\n✅ Fichier .env mis à jour avec succès!")
    print("\n⚠️  N'oubliez pas de remplacer EMAIL_HOST_PASSWORD par votre mot de passe d'application!")
    
elif choice == '2':
    print("\n📋 Copiez ces lignes dans votre fichier .env:")
    print("-" * 60)
    print(recommended_config)
    print("-" * 60)

print("\n" + "=" * 60)
print("Une fois configuré, relancez: python test_email.py")
print("=" * 60)
