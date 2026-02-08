from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def notify_assignment(employee, task_type, task_name, project_name, assigned_by):
    """
    Envoie un email de notification lorsqu'une étape ou sous-étape est attribuée à un employé.
    
    Args:
        employee: L'employé (Employee) à qui la tâche est attribuée
        task_type: 'jalon' ou 'sous-étape'
        task_name: Nom de la tâche
        project_name: Nom du projet
        assigned_by: L'utilisateur qui a fait l'attribution
    """
    if not employee or not employee.email:
        logger.warning(f"Notification non envoyée : pas d'email pour {employee}")
        return False
    
    if not settings.EMAIL_HOST_USER:
        logger.warning("Notification non envoyée : EMAIL_HOST_USER non configuré")
        return False
    
    subject = f"[CSIG] Nouvelle attribution : {task_name}"
    
    message = (
        f"Bonjour {employee.name},\n\n"
        f"Une nouvelle {task_type} vous a été attribuée :\n\n"
        f"  Projet : {project_name}\n"
        f"  {task_type.capitalize()} : {task_name}\n"
        f"  Attribué par : {assigned_by}\n\n"
        f"Veuillez vous connecter au tableau de bord CSIG pour consulter les détails.\n\n"
        f"Cordialement,\n"
        f"Dashboard CSIG - Direction Générale"
    )
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[employee.email],
            fail_silently=False,
        )
        logger.info(f"Email de notification envoyé à {employee.email} pour {task_type} '{task_name}'")
        return (True, f"Email envoyé à {employee.email}")
    except Exception as e:
        error_msg = f"Erreur envoi email à {employee.email}: {e}"
        logger.error(error_msg)
        return (False, error_msg)
