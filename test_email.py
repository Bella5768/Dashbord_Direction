"""
Script de test pour diagnostiquer les problèmes d'envoi d'emails Django.
Exécutez ce script avec: python test_email.py
"""
import os
import sys
import django

# Configuration de l'environnement Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard_csig.settings')
django.setup()

from django.core.mail import send_mail, EmailMessage
from django.conf import settings
import smtplib

print("=" * 60)
print("TEST DE CONFIGURATION SMTP - DJANGO")
print("=" * 60)

# Affichage de la configuration email
print("\n📧 Configuration email actuelle :")
print("-" * 60)
print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
print(f"EMAIL_LOCAL_HOSTNAME: {getattr(settings, 'EMAIL_LOCAL_HOSTNAME', 'Non défini')}")

# Masquer le mot de passe partiellement
password = settings.EMAIL_HOST_PASSWORD
if password:
    masked_password = password[:2] + '*' * (len(password) - 4) + password[-2:] if len(password) > 4 else '****'
    print(f"EMAIL_HOST_PASSWORD: {masked_password}")
else:
    print(f"EMAIL_HOST_PASSWORD: Non configuré!")

print("-" * 60)

# Test 1: Connexion SMTP brute
print("\n🔍 Test 1: Connexion SMTP brute")
print("-" * 60)
try:
    server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
    server.ehlo()
    print("✅ Connexion SMTP réussie")
    print(f"   Réponse EHLO: {server.ehlo_resp}")
    server.starttls()
    print("✅ STARTTLS réussi")
    server.ehlo()
    print(f"   Réponse EHLO après TLS: {server.ehlo_resp}")
    
    # Test d'authentification
    try:
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        print("✅ Authentification SMTP réussie")
        server.quit()
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Erreur d'authentification: {e}")
        print("\n💡 Solutions possibles:")
        print("   - Vérifiez que le mot de passe est correct")
        print("   - Pour Office 365, utilisez un MOT DE PASSE D'APPLICATION (pas le mot de passe du compte)")
        print("   - Activez l'authentification à deux facteurs sur votre compte Microsoft")
        print("   - Générez un mot de passe d'application sur: https://account.microsoft.com/security")
        server.quit()
    except Exception as e:
        print(f"❌ Erreur lors de l'authentification: {e}")
        server.quit()
        
except smtplib.SMTPConnectError as e:
    print(f"❌ Erreur de connexion SMTP: {e}")
    print("\n💡 Solutions possibles:")
    print("   - Vérifiez que le serveur SMTP est accessible")
    print("   - Vérifiez que le port 587 n'est pas bloqué par le firewall")
    print("   - Vérifiez votre connexion internet")
except Exception as e:
    print(f"❌ Erreur inattendue: {e}")

# Test 2: Envoi d'email via Django
print("\n🔍 Test 2: Envoi d'email via Django")
print("-" * 60)

test_email = input("\nEntrez votre adresse email pour le test (ou appuyez sur Entrée pour ignorer): ").strip()

if test_email:
    try:
        print(f"\n📤 Tentative d'envoi à: {test_email}")
        
        result = send_mail(
            subject='Test de configuration SMTP - CSIG',
            message='Ceci est un email de test pour vérifier la configuration SMTP.\n\n'
                    f'Date du test: {__import__("datetime").datetime.now()}\n'
                    f'Serveur: {settings.EMAIL_HOST}\n'
                    f'Port: {settings.EMAIL_PORT}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[test_email],
            fail_silently=False
        )
        
        if result == 1:
            print("✅ Email envoyé avec succès!")
            print(f"   Vérifiez votre boîte de réception (et le dossier spam)")
        else:
            print(f"⚠️  Résultat inattendu: {result}")
            
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Erreur d'authentification: {e}")
        print("\n💡 Vérifiez:")
        print("   - Que vous utilisez un MOT DE PASSE D'APPLICATION Microsoft")
        print("   - Que l'authentification à deux facteurs est activée")
        print("   - Que le mot de passe d'application est correct")
    except smtplib.SMTPException as e:
        print(f"❌ Erreur SMTP: {e}")
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        print(f"   Type: {type(e).__name__}")
else:
    print("⏭️  Test d'envoi ignoré")

# Test 3: Vérification du backend personnalisé
print("\n🔍 Test 3: Vérification du backend personnalisé")
print("-" * 60)
try:
    from core.email_backend import OutlookSMTPBackend
    print("✅ Backend personnalisé OutlookSMTPBackend importé avec succès")
    
    backend = OutlookSMTPBackend()
    print(f"   Connection class: {backend.connection_class}")
    print(f"   Use SSL: {backend.use_ssl}")
    print(f"   Use TLS: {backend.use_tls}")
except Exception as e:
    print(f"❌ Erreur avec le backend personnalisé: {e}")

print("\n" + "=" * 60)
print("FIN DU TEST")
print("=" * 60)
print("\n💡 Si les emails ne partent toujours pas, vérifiez:")
print("   1. Que vous utilisez un MOT DE PASSE D'APPLICATION Microsoft")
print("   2. Que l'authentification à deux facteurs est activée")
print("   3. Que le mot de passe d'application est correct")
print("   4. Que le port 587 n'est pas bloqué")
print("   5. Les logs Django pour plus de détails")
