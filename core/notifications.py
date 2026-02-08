from django.conf import settings
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

SENDGRID_API_URL = 'https://api.sendgrid.com/v3/mail/send'


def notify_assignment(employee, task_type, task_name, project_name, assigned_by):
    """
    Envoie un email de notification via SendGrid API lorsqu'une étape ou sous-étape
    est attribuée à un employé.
    
    Args:
        employee: L'employé (Employee) à qui la tâche est attribuée
        task_type: 'jalon' ou 'sous-étape'
        task_name: Nom de la tâche
        project_name: Nom du projet
        assigned_by: L'utilisateur qui a fait l'attribution
    """
    if not employee or not employee.email:
        logger.warning(f"Notification non envoyée : pas d'email pour {employee}")
        return (False, "Pas d'email pour cet employé")
    
    api_key = getattr(settings, 'SENDGRID_API_KEY', '')
    if not api_key:
        logger.warning("Notification non envoyée : SENDGRID_API_KEY non configuré")
        return (False, "SENDGRID_API_KEY non configuré")
    
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@csig.edu.gn')
    subject = f"[CSIG] Nouvelle attribution : {task_name}"
    
    text_content = (
        f"Bonjour {employee.name},\n\n"
        f"Une nouvelle {task_type} vous a été attribuée :\n\n"
        f"  Projet : {project_name}\n"
        f"  {task_type.capitalize()} : {task_name}\n"
        f"  Attribué par : {assigned_by}\n\n"
        f"Veuillez vous connecter au tableau de bord CSIG pour consulter les détails.\n\n"
        f"Cordialement,\n"
        f"Dashboard CSIG - Direction Générale"
    )
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #1e3a5f; color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
            <h2 style="margin: 0;">Dashboard CSIG</h2>
            <p style="margin: 5px 0 0; opacity: 0.8;">Direction Générale</p>
        </div>
        <div style="background: #f9fafb; padding: 25px; border: 1px solid #e5e7eb;">
            <p>Bonjour <strong>{employee.name}</strong>,</p>
            <p>Une nouvelle <strong>{task_type}</strong> vous a été attribuée :</p>
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white; font-weight: bold; width: 140px;">Projet</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white;">{project_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white; font-weight: bold;">{task_type.capitalize()}</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white;">{task_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white; font-weight: bold;">Attribué par</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white;">{assigned_by}</td>
                </tr>
            </table>
            <p>Veuillez vous connecter au tableau de bord CSIG pour consulter les détails.</p>
        </div>
        <div style="background: #f3f4f6; padding: 15px; border-radius: 0 0 8px 8px; text-align: center; font-size: 12px; color: #6b7280; border: 1px solid #e5e7eb; border-top: none;">
            <p style="margin: 0;">© 2026 CSIG - Centre de Suivi et d'Information de Gestion</p>
        </div>
    </div>
    """
    
    payload = {
        "personalizations": [
            {
                "to": [{"email": employee.email, "name": employee.name}],
                "subject": subject
            }
        ],
        "from": {"email": from_email, "name": "CSIG Dashboard"},
        "content": [
            {"type": "text/plain", "value": text_content},
            {"type": "text/html", "value": html_content}
        ]
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            SENDGRID_API_URL,
            data=data,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            method='POST'
        )
        response = urllib.request.urlopen(req)
        logger.info(f"Email envoyé à {employee.email} via SendGrid (status {response.status})")
        return (True, f"Email envoyé à {employee.email}")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        error_msg = f"Erreur SendGrid ({e.code}): {body}"
        logger.error(error_msg)
        return (False, error_msg)
    except Exception as e:
        error_msg = f"Erreur envoi email à {employee.email}: {e}"
        logger.error(error_msg)
        return (False, error_msg)
