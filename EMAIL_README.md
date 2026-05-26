# Configuration et Utilisation des Emails

## Configuration

La configuration SMTP est déjà définie dans `dashboard_csig/settings.py`. Vous devez configurer les variables d'environnement dans votre fichier `.env` :

```env
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=support@csig.edu.gn
EMAIL_HOST_PASSWORD=gnnthnprwdlklnfd
DEFAULT_FROM_EMAIL=support@csig.edu.gn
EMAIL_LOCAL_HOSTNAME=csig.edu.gn
```

**Important :** Pour Office 365, vous devez utiliser un "mot de passe d'application" et non votre mot de passe habituel. Pour en générer un :
1. Allez sur https://account.microsoft.com/security
2. Activez l'authentification à deux facteurs
3. Créez un mot de passe d'application pour "Outlook"
4. Utilisez ce mot de passe dans `EMAIL_HOST_PASSWORD`

## Fonctions Disponibles

### 1. `send_email()` - Email simple

Envoie un email simple en texte brut ou HTML.

```python
from core.email_backend import send_email

send_email(
    subject="Sujet de l'email",
    message="Contenu de l'email en texte",
    recipient_list=["destinataire@example.com"],
    html_message="<h1>Version HTML</h1>",  # Optionnel
    fail_silently=False
)
```

### 2. `send_html_email()` - Email avec template Django

Envoie un email HTML en utilisant un template Django.

```python
from core.email_backend import send_html_email

context = {
    'username': 'Jean Dupont',
    'activation_link': 'https://example.com/activate/12345'
}

send_html_email(
    subject="Activation de compte",
    template_name='emails/account_activation.html',
    context=context,
    recipient_list=["destinataire@example.com"]
)
```

### 3. `send_email_with_attachments()` - Email avec pièces jointes

Envoie un email avec des pièces jointes.

```python
from core.email_backend import send_email_with_attachments

# Avec un fichier
send_email_with_attachments(
    subject="Document joint",
    message="Veuillez trouver le document ci-joint",
    recipient_list=["destinataire@example.com"],
    attachments=["/path/to/document.pdf"]
)

# Avec du contenu en mémoire
attachments = [
    ("rapport.pdf", pdf_content, "application/pdf"),
    ("resume.txt", "Résumé", "text/plain")
]

send_email_with_attachments(
    subject="Rapport",
    message="Voir les pièces jointes",
    recipient_list=["destinataire@example.com"],
    attachments=attachments
)
```

## Templates Disponibles

Les templates sont situés dans `templates/emails/` :

- **base_email.html** - Template de base pour tous les emails
- **account_activation.html** - Email d'activation de compte
- **password_reset.html** - Email de réinitialisation de mot de passe
- **notification.html** - Email de notification générique

## Exemple d'utilisation dans une Vue

```python
from django.shortcuts import render, redirect
from django.contrib import messages
from core.email_backend import send_email

def my_view(request):
    try:
        send_email(
            subject="Confirmation",
            message="Votre action a été confirmée",
            recipient_list=[request.user.email],
            fail_silently=False
        )
        messages.success(request, "Email envoyé avec succès")
    except Exception as e:
        messages.error(request, f"Erreur: {e}")
    
    return redirect('core:dashboard')
```

## Tests

Pour tester l'envoi d'emails, vous pouvez utiliser le fichier `core/email_examples.py` qui contient plusieurs exemples.

En développement, vous pouvez configurer Django pour afficher les emails dans la console au lieu de les envoyer réellement :

```python
# Dans settings.py
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

## Dépannage

### Erreur "501 5.5.4 Invalid domain name"
Cette erreur est gérée automatiquement par le backend personnalisé `OutlookSMTPBackend` qui force un nom d'hôte valide.

### Erreur d'authentification
- Vérifiez que vous utilisez un mot de passe d'application et non votre mot de passe habituel
- Vérifiez que l'authentification à deux facteurs est activée sur votre compte Microsoft

### Email non reçu
- Vérifiez le dossier spam
- Vérifiez que l'adresse email est correcte
- Consultez les logs Django pour les erreurs
