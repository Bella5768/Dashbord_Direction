"""
Exemples d'utilisation des fonctions d'envoi d'emails.

Ce fichier montre comment utiliser les fonctions d'envoi d'emails
définies dans core/email_backend.py
"""

from django.utils.translation import gettext as _
from core.email_backend import send_email, send_html_email, send_email_with_attachments


# Exemple 1: Envoi d'un email simple (texte)
def example_simple_email():
    """Envoie un email simple en texte brut."""
    try:
        result = send_email(
            subject="Test d'envoi d'email",
            message="Ceci est un test d'envoi d'email depuis l'application.",
            recipient_list=["destinataire@example.com"],
            fail_silently=False
        )
        print(f"Email envoyé avec succès. Résultat: {result}")
    except Exception as e:
        print(f"Erreur lors de l'envoi: {e}")


# Exemple 2: Envoi d'un email HTML
def example_html_email():
    """Envoie un email avec du contenu HTML."""
    html_message = """
    <html>
        <body>
            <h1>Bonjour!</h1>
            <p>Ceci est un <strong>email HTML</strong> de test.</p>
            <p>Cordialement,<br>L'équipe CSIG</p>
        </body>
    </html>
    """
    
    try:
        result = send_email(
            subject="Test email HTML",
            message="Version texte de l'email",
            recipient_list=["destinataire@example.com"],
            html_message=html_message,
            fail_silently=False
        )
        print(f"Email HTML envoyé avec succès. Résultat: {result}")
    except Exception as e:
        print(f"Erreur lors de l'envoi: {e}")


# Exemple 3: Envoi d'un email avec template Django
def example_template_email():
    """Envoie un email en utilisant un template Django."""
    context = {
        'username': 'Jean Dupont',
        'activation_link': 'https://example.com/activate/12345'
    }
    
    try:
        result = send_html_email(
            subject="Activation de votre compte",
            template_name='emails/account_activation.html',
            context=context,
            recipient_list=["destinataire@example.com"],
            fail_silently=False
        )
        print(f"Email avec template envoyé avec succès. Résultat: {result}")
    except Exception as e:
        print(f"Erreur lors de l'envoi: {e}")


# Exemple 4: Envoi d'un email avec pièce jointe (chemin de fichier)
def example_email_with_file_attachment():
    """Envoie un email avec une pièce jointe (fichier)."""
    try:
        result = send_email_with_attachments(
            subject="Email avec pièce jointe",
            message="Veuillez trouver ci-joint le document demandé.",
            recipient_list=["destinataire@example.com"],
            attachments=["/path/to/document.pdf"],
            fail_silently=False
        )
        print(f"Email avec pièce jointe envoyé avec succès. Résultat: {result}")
    except Exception as e:
        print(f"Erreur lors de l'envoi: {e}")


# Exemple 5: Envoi d'un email avec pièce jointe (contenu en mémoire)
def example_email_with_content_attachment():
    """Envoie un email avec une pièce jointe (contenu en mémoire)."""
    # Création d'un fichier PDF en mémoire (exemple)
    pdf_content = b"Contenu binaire du fichier PDF..."
    
    attachments = [
        ("rapport.pdf", pdf_content, "application/pdf"),
        ("resume.txt", "Résumé du rapport", "text/plain")
    ]
    
    try:
        result = send_email_with_attachments(
            subject="Rapport avec pièces jointes",
            message="Veuillez trouver ci-joint les documents.",
            recipient_list=["destinataire@example.com"],
            attachments=attachments,
            fail_silently=False
        )
        print(f"Email avec pièces jointes envoyé avec succès. Résultat: {result}")
    except Exception as e:
        print(f"Erreur lors de l'envoi: {e}")


# Exemple 6: Envoi à plusieurs destinataires
def example_multiple_recipients():
    """Envoie un email à plusieurs destinataires."""
    recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]
    
    try:
        result = send_email(
            subject="Information importante",
            message="Ceci est une information pour tous les destinataires.",
            recipient_list=recipients,
            fail_silently=False
        )
        print(f"Email envoyé à {result} destinataires avec succès.")
    except Exception as e:
        print(f"Erreur lors de l'envoi: {e}")


# Exemple d'utilisation dans une vue Django
def example_in_view(request):
    """Exemple d'utilisation dans une vue Django."""
    from django.contrib import messages
    
    try:
        send_email(
            subject="Confirmation d'inscription",
            message="Votre inscription a été confirmée avec succès.",
            recipient_list=[request.user.email],
            fail_silently=False
        )
        messages.success(request, _("Email de confirmation envoyé."))
    except Exception as e:
        messages.error(request, _("Erreur lors de l'envoi de l'email: {err}").format(err=e))


if __name__ == "__main__":
    # Pour tester les exemples, décommentez la fonction souhaitée
    # example_simple_email()
    # example_html_email()
    # example_template_email()
    # example_email_with_file_attachment()
    # example_email_with_content_attachment()
    # example_multiple_recipients()
    pass
