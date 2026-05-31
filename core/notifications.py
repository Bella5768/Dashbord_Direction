from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from email.mime.image import MIMEImage
from email.utils import formataddr
import logging
import os

logger = logging.getLogger(__name__)

LOGO_CID = 'csig_logo'
LOGO_PATH = os.path.join(settings.BASE_DIR, 'static', 'logocsig.jpg')


def _build_from():
    sender_email = getattr(settings, 'EMAIL_HOST_USER', '') or getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@csig.edu.gn')
    sender_name = getattr(settings, 'EMAIL_FROM_NAME', 'CSIG Dashboard')
    return formataddr((sender_name, sender_email)), sender_email


def _attach_logo(email):
    """Attache le logo CSIG en image inline (CID) si disponible."""
    if not os.path.isfile(LOGO_PATH):
        return False
    try:
        with open(LOGO_PATH, 'rb') as f:
            img = MIMEImage(f.read(), _subtype='jpeg')
        img.add_header('Content-ID', f'<{LOGO_CID}>')
        img.add_header('Content-Disposition', 'inline', filename='logocsig.jpg')
        email.attach(img)
        email.mixed_subtype = 'related'
        return True
    except Exception as e:
        logger.warning(f"Impossible d'attacher le logo CSIG : {e}")
        return False


def _send(subject, text_content, html_content, recipient):
    from_header, sender_email = _build_from()
    headers = {
        'Reply-To': sender_email,
        'X-Auto-Response-Suppress': 'OOF, AutoReply',
        'Auto-Submitted': 'auto-generated',
    }
    email = EmailMultiAlternatives(subject, text_content, from_header, [recipient], headers=headers)
    email.attach_alternative(html_content, 'text/html')
    email.send()


def _logo_header(banner_color, title, subtitle=''):
    """Genere l'en-tete HTML : bandeau colore avec titre et sous-titre."""
    subtitle_html = f'<p style="margin: 5px 0 0; opacity: 0.95;">{subtitle}</p>' if subtitle else ''
    return f"""
    <div style="background: {banner_color}; color: white; padding: 22px 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h2 style="margin: 0; letter-spacing: 0.3px;">{title}</h2>
        {subtitle_html}
    </div>
    """


def _build_assignment_email(recipient_name, role_label, employee_name, task_type, task_name, project_name, assigned_by, due_date=None):
    subject = f"[CSIG] Nouvelle attribution : {task_name}"
    due_line = f"  Échéance : {due_date.strftime('%d/%m/%Y')}\n" if due_date else ''
    text_content = (
        f"Bonjour {recipient_name},\n\n"
        f"{role_label}\n"
        f"Une nouvelle {task_type} a été attribuée à {employee_name} :\n\n"
        f"  Projet : {project_name}\n"
        f"  {task_type.capitalize()} : {task_name}\n"
        f"  Responsable : {employee_name}\n"
        f"{due_line}"
        f"  Attribué par : {assigned_by}\n\n"
        f"Veuillez vous connecter au tableau de bord CSIG pour consulter les détails.\n\n"
        f"Cordialement,\nDashboard CSIG - Direction Générale"
    )
    due_row = (
        f'<tr><td style="padding: 10px; border: 1px solid #e5e7eb; background: white; font-weight: bold;">Échéance</td>'
        f'<td style="padding: 10px; border: 1px solid #e5e7eb; background: white;">{due_date.strftime("%d/%m/%Y")}</td></tr>'
    ) if due_date else ''
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        {_logo_header('#1e3a5f', 'Nouvelle attribution', 'Dashboard CSIG - Direction Générale')}
        <div style="background: #f9fafb; padding: 25px; border: 1px solid #e5e7eb;">
            <p>Bonjour <strong>{recipient_name}</strong>,</p>
            <p style="color: #1e3a5f;">{role_label}</p>
            <p>Une nouvelle <strong>{task_type}</strong> a été attribuée à <strong>{employee_name}</strong> :</p>
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white; font-weight: bold; width: 140px;">Projet</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white;">{project_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: #eff6ff; font-weight: bold;">{task_type.capitalize()}</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: #eff6ff; color: #1e3a5f; font-weight: bold;">{task_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white; font-weight: bold;">Responsable</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white;">{employee_name}</td>
                </tr>
                {due_row}
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
    return subject, text_content, html_content


def notify_assignment(employee, task_type, task_name, project_name, assigned_by, project=None, due_date=None):
    """Notifie l'attribution d'une tache.

    Destinataires :
      - Le responsable (employee) qui recoit la tache
      - Le chef de projet (resolu via project.manager) en CC

    Pour retro-compatibilite, project_name peut etre une chaine et project None.
    Dans ce cas, seul l'employe est notifie.
    """
    if not getattr(settings, 'EMAIL_HOST_USER', '') or not getattr(settings, 'EMAIL_HOST_PASSWORD', ''):
        logger.warning("Notification non envoyée : identifiants Outlook non configurés")
        return (False, "Identifiants Outlook non configurés")

    if not employee or not employee.email:
        logger.warning(f"Notification non envoyée : pas d'email pour {employee}")
        return (False, "Pas d'email pour cet employé")

    employee_name = employee.name

    # Construire la liste des destinataires
    recipients = []  # tuples (name, email, role_label)

    # 1. Responsable de la tache
    recipients.append((
        employee_name, employee.email,
        "Une nouvelle tâche vous est attribuée :"
    ))

    # 2. Chef de projet en CC (si projet fourni)
    if project is not None:
        manager_name, manager_email = _resolve_manager_email(project)
        if manager_email and manager_email.lower() != employee.email.lower():
            recipients.append((
                manager_name, manager_email,
                "En tant que chef de projet, vous êtes informé en copie :"
            ))

    sent_emails = []
    errors = []
    for rec_name, rec_email, role_label in recipients:
        subject, text_content, html_content = _build_assignment_email(
            rec_name, role_label, employee_name, task_type, task_name,
            project_name, assigned_by, due_date,
        )
        try:
            _send(subject, text_content, html_content, rec_email)
            logger.info(f"Email attribution envoyé à {rec_email}")
            sent_emails.append(rec_email)
        except Exception as e:
            err = f"Erreur envoi à {rec_email}: {e}"
            logger.error(err)
            errors.append(err)

    if sent_emails and not errors:
        return (True, f"Email envoyé à : {', '.join(sent_emails)}")
    if sent_emails and errors:
        return (True, f"Email envoyé à : {', '.join(sent_emails)} (échecs : {len(errors)})")
    return (False, "; ".join(errors) or "Échec d'envoi")


def _build_completion_email(recipient_name, role_label, task_type, task_name, project_name, completed_by_name):
    subject = f"[CSIG] {task_type.capitalize()} terminée : {task_name}"
    text_content = (
        f"Bonjour {recipient_name},\n\n"
        f"{role_label}\n"
        f"La {task_type} '{task_name}' est maintenant terminée :\n\n"
        f"  Projet : {project_name}\n"
        f"  {task_type.capitalize()} : {task_name}\n"
        f"  Terminée par : {completed_by_name}\n\n"
        f"Veuillez vous connecter au tableau de bord CSIG pour consulter les détails.\n\n"
        f"Cordialement,\nDashboard CSIG - Direction Générale"
    )
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        {_logo_header('#047857', f'{task_type.capitalize()} terminée', 'Dashboard CSIG - Direction Générale')}
        <div style="background: #f9fafb; padding: 25px; border: 1px solid #e5e7eb;">
            <p>Bonjour <strong>{recipient_name}</strong>,</p>
            <p style="color: #065f46;">{role_label}</p>
            <p>La {task_type} <strong>« {task_name} »</strong> est maintenant terminée.</p>
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white; font-weight: bold; width: 140px;">Projet</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white;">{project_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: #ecfdf5; font-weight: bold;">{task_type.capitalize()}</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: #ecfdf5; color: #065f46; font-weight: bold;">{task_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white; font-weight: bold;">Terminée par</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: white;">{completed_by_name}</td>
                </tr>
            </table>
            <p>Veuillez vous connecter au tableau de bord CSIG pour consulter les détails.</p>
        </div>
        <div style="background: #f3f4f6; padding: 15px; border-radius: 0 0 8px 8px; text-align: center; font-size: 12px; color: #6b7280; border: 1px solid #e5e7eb; border-top: none;">
            <p style="margin: 0;">© 2026 CSIG - Centre de Suivi et d'Information de Gestion</p>
        </div>
    </div>
    """
    return subject, text_content, html_content


def _resolve_manager_email(project):
    """Tente de trouver l'email du chef de projet a partir de Project.manager (nom)."""
    from .models import Employee
    manager_name = (project.manager or '').strip()
    if not manager_name:
        return None, None
    emp = Employee.objects.filter(name__iexact=manager_name, email__isnull=False).exclude(email='').first()
    if emp:
        return emp.name, emp.email
    # Fallback : chercher dans les ProjectMember avec role responsable
    member = project.members.filter(role='responsable').select_related('employee').first()
    if member and member.employee and member.employee.email:
        return member.employee.name, member.employee.email
    return manager_name, None


def notify_task_completed(task_type, task_name, project, assigned_employee, assigned_by_user, completed_by_user):
    """Envoie un email a tous les destinataires concernes par la fin d'une tache.

    Destinataires :
      - Chef de projet (project.manager, resolu en email via Employee)
      - Responsable de la tache (assigned_employee, l'employe qui avait la tache)
      - Personne qui avait affecte la tache (assigned_by_user)

    Chaque destinataire recoit un email personnalise. Pas de doublons d'envoi
    sur la meme adresse.
    """
    if not getattr(settings, 'EMAIL_HOST_USER', '') or not getattr(settings, 'EMAIL_HOST_PASSWORD', ''):
        logger.warning("Notification non envoyée : identifiants Outlook non configurés")
        return (False, "Identifiants Outlook non configurés")

    completed_by_name = completed_by_user.get_full_name() or completed_by_user.username
    project_name = project.name

    # Construire la liste des destinataires uniques (par email)
    recipients = []  # tuples (name, email, role_label)

    # 1. Chef de projet
    manager_name, manager_email = _resolve_manager_email(project)
    if manager_email:
        recipients.append((manager_name, manager_email, "En tant que chef de projet, vous êtes informé que :"))

    # 2. Responsable de la tache (Employee)
    if assigned_employee and assigned_employee.email:
        recipients.append((assigned_employee.name, assigned_employee.email, "En tant que responsable de cette tâche, vous êtes informé que :"))

    # 3. Personne qui a affecte la tache (User)
    if assigned_by_user and assigned_by_user.email:
        assigned_by_name = assigned_by_user.get_full_name() or assigned_by_user.username
        recipients.append((assigned_by_name, assigned_by_user.email, "En tant que personne ayant attribué cette tâche, vous êtes informé que :"))

    # Email de la personne qui a marque comme termine (a exclure)
    completed_by_email = (completed_by_user.email or '').lower().strip() if completed_by_user else ''

    # Deduplication par email + exclusion de celui qui a complete
    seen = set()
    unique_recipients = []
    for name, email, role_label in recipients:
        e = email.lower().strip()
        if e in seen or e == completed_by_email:
            continue
        seen.add(e)
        unique_recipients.append((name, email, role_label))

    if not unique_recipients:
        logger.warning(f"Aucun destinataire pour notification de fin de {task_type} {task_name}")
        return (False, "Aucun destinataire avec email pour cette notification")

    sent_emails = []
    errors = []
    for name, email, role_label in unique_recipients:
        subject, text_content, html_content = _build_completion_email(
            name, role_label, task_type, task_name, project_name, completed_by_name,
        )
        try:
            _send(subject, text_content, html_content, email)
            logger.info(f"Email fin de {task_type} envoyé à {email}")
            sent_emails.append(email)
        except Exception as e:
            err = f"Erreur envoi à {email}: {e}"
            logger.error(err)
            errors.append(err)

    if sent_emails and not errors:
        return (True, f"Emails envoyés à : {', '.join(sent_emails)}")
    if sent_emails and errors:
        return (True, f"Emails envoyés à : {', '.join(sent_emails)} (échecs : {len(errors)})")
    return (False, "; ".join(errors) or "Échec d'envoi")


def _build_due_date_email(recipient_name, role_label, employee_name, task_type, task_name, project_name, due_date, urgency_label, banner_color, banner_text, subject_prefix):
    subject = f"{subject_prefix} {task_name} - échéance {due_date.strftime('%d/%m/%Y')}"
    text_content = (
        f"Bonjour {recipient_name},\n\n"
        f"{role_label}\n"
        f"{banner_text}\n\n"
        f"La {task_type} suivante affectée à {employee_name} n'est pas encore terminée :\n\n"
        f"  Projet : {project_name}\n"
        f"  {task_type.capitalize()} : {task_name}\n"
        f"  Responsable : {employee_name}\n"
        f"  Échéance : {due_date.strftime('%d/%m/%Y')}\n"
        f"  Statut : {urgency_label}\n\n"
        f"Cordialement,\nDashboard CSIG - Direction Générale"
    )
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        {_logo_header(banner_color, banner_text, urgency_label)}
        <div style="background: #fff; padding: 25px; border: 2px solid {banner_color};">
            <p>Bonjour <strong>{recipient_name}</strong>,</p>
            <p style="color: {banner_color}; font-weight: bold; font-size: 14px;">{role_label}</p>
            <p style="color: {banner_color}; font-weight: bold; font-size: 15px;">
                La {task_type} ci-dessous (responsable : <strong>{employee_name}</strong>) n'est pas encore terminée.
            </p>
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: #fef2f2; font-weight: bold; width: 140px;">Projet</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb;">{project_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: #fef2f2; font-weight: bold;">{task_type.capitalize()}</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb;">{task_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: #fef2f2; font-weight: bold;">Responsable</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb;">{employee_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: #fef2f2; font-weight: bold;">Échéance</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; color: {banner_color}; font-weight: bold;">{due_date.strftime('%d/%m/%Y')}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; background: #fef2f2; font-weight: bold;">Statut</td>
                    <td style="padding: 10px; border: 1px solid #e5e7eb; color: {banner_color}; font-weight: bold;">{urgency_label}</td>
                </tr>
            </table>
            <p style="background: #fef2f2; padding: 12px; border-left: 4px solid {banner_color}; color: #7f1d1d;">
                <strong>Action requise :</strong> connectez-vous au tableau de bord CSIG pour suivre l'avancement.
            </p>
        </div>
        <div style="background: #f3f4f6; padding: 15px; border-radius: 0 0 8px 8px; text-align: center; font-size: 12px; color: #6b7280; border: 1px solid #e5e7eb; border-top: none;">
            <p style="margin: 0;">© 2026 CSIG - Centre de Suivi et d'Information de Gestion</p>
        </div>
    </div>
    """
    return subject, text_content, html_content


def notify_due_date_alert(employee, task_type, task_name, project_name, due_date, days_diff, project=None):
    """Envoie une alerte d'echeance.

    Destinataires :
      - Le responsable de la tache (employee)
      - Le chef de projet en CC (si project fourni)

    days_diff : 0 = aujourd'hui, < 0 = en retard de |N| jours, > 0 = rappel J-N.
    """
    if not getattr(settings, 'EMAIL_HOST_USER', '') or not getattr(settings, 'EMAIL_HOST_PASSWORD', ''):
        return (False, "Identifiants Outlook non configurés")

    if not employee or not employee.email:
        return (False, f"Pas d'email pour {employee}")

    if days_diff < 0:
        urgency_label = f"EN RETARD de {abs(days_diff)} jour{'s' if abs(days_diff) > 1 else ''}"
        banner_color = '#b91c1c'
        banner_text = "ALERTE ECHEANCE DEPASSEE"
        subject_prefix = "[URGENT - RETARD]"
    elif days_diff == 0:
        urgency_label = "À FAIRE AUJOURD'HUI"
        banner_color = '#dc2626'
        banner_text = "ALERTE : ECHEANCE AUJOURD'HUI"
        subject_prefix = "[URGENT]"
    else:
        urgency_label = f"À faire dans {days_diff} jour{'s' if days_diff > 1 else ''}"
        banner_color = '#ea580c'
        banner_text = "RAPPEL D'ECHEANCE"
        subject_prefix = "[RAPPEL]"

    employee_name = employee.name

    # Destinataires
    recipients = []
    recipients.append((
        employee_name, employee.email,
        "En tant que responsable, vous devez traiter cette tâche impérativement :"
    ))
    if project is not None:
        manager_name, manager_email = _resolve_manager_email(project)
        if manager_email and manager_email.lower() != employee.email.lower():
            recipients.append((
                manager_name, manager_email,
                "En tant que chef de projet, vous êtes informé en copie :"
            ))

    sent_emails = []
    errors = []
    for rec_name, rec_email, role_label in recipients:
        subject, text_content, html_content = _build_due_date_email(
            rec_name, role_label, employee_name, task_type, task_name,
            project_name, due_date, urgency_label, banner_color, banner_text, subject_prefix,
        )
        try:
            _send(subject, text_content, html_content, rec_email)
            logger.info(f"Alerte échéance envoyée à {rec_email} pour {task_name}")
            sent_emails.append(rec_email)
        except Exception as e:
            err = f"Erreur alerte à {rec_email}: {e}"
            logger.error(err)
            errors.append(err)

    if sent_emails and not errors:
        return (True, f"Alertes envoyées à : {', '.join(sent_emails)}")
    if sent_emails and errors:
        return (True, f"Alertes envoyées à : {', '.join(sent_emails)} (échecs : {len(errors)})")
    return (False, "; ".join(errors) or "Échec d'envoi")


# =====================================================================
# Notifications liees aux conges
# =====================================================================

def _leave_recipients_step(leave, step):
    """Construit la liste des destinataires (name, email, role_label) pour une etape donnee.

    step:
      - 'submitted'    : nouveaux destinataires : hierarchie + demandeur en copie
      - 'manager'      : RH (si favorable) ou demandeur (si defavorable)
      - 'hr'           : DG/Coordination (si conforme) ou demandeur (si non conforme)
      - 'final'        : demandeur + RH + hierarchie en copie
    """
    from django.contrib.auth.models import User
    User_ = User
    recipients = []
    seen = set()

    def add(name, email, role):
        if not email:
            return
        key = email.lower()
        if key in seen:
            return
        seen.add(key)
        recipients.append((name or 'Utilisateur', email, role))

    employee_email = leave.employee.email if leave.employee else None
    employee_name = leave.employee.name if leave.employee else 'Demandeur'

    def _hr_users():
        try:
            return User_.objects.filter(
                Q(profile__is_hr_manager=True) | Q(profile__role='admin'),
                is_active=True,
            ).exclude(email='')
        except Exception:
            return []

    def _add_hr(role_label):
        for u in _hr_users():
            add(u.get_full_name() or u.username, u.email, role_label)

    def _direction_managers():
        """Directeurs (responsables hierarchiques) de la direction du demandeur."""
        try:
            return User_.objects.filter(
                profile__role='directeur',
                profile__direction_id=leave.direction_id,
                is_active=True,
            ).exclude(email='')
        except Exception:
            return []

    def _add_managers(role_label):
        for u in _direction_managers():
            add(u.get_full_name() or u.username, u.email, role_label)

    if step == 'submitted':
        # Hierarchie : action requise (avis hierarchique)
        _add_managers("Demande de congé soumise par un membre de votre équipe (avis hiérarchique requis) :")
        # Demandeur (confirmation) + RH (information / suivi)
        add(employee_name, employee_email, "Confirmation de soumission de votre demande de congé :")
        _add_hr("Nouvelle demande de congé soumise (information RH) :")

    elif step == 'manager':
        if leave.manager_decision == 'favorable':
            # RH : action requise (verification)
            _add_hr("Demande de congé à vérifier (RH) :")
        else:
            # RH informee meme en cas d'avis defavorable
            _add_hr("Avis hiérarchique défavorable enregistré (information RH) :")
        add(employee_name, employee_email, "Avis hiérarchique enregistré sur votre demande :")
        # Hierarchie : copie pour suivi (autres directeurs de la direction)
        _add_managers("Avis hiérarchique enregistré (copie hiérarchie) :")

    elif step == 'hr':
        if leave.hr_decision == 'conforme':
            try:
                dg_users = User_.objects.filter(
                    profile__role__in=['directeur_general', 'admin'],
                    is_active=True,
                ).exclude(email='')
                for u in dg_users:
                    add(u.get_full_name() or u.username, u.email, "Demande de congé à valider (Direction Générale) :")
            except Exception:
                pass
        add(employee_name, employee_email, "Vérification RH enregistrée sur votre demande :")
        # RH informee (copie de la decision RH a toute l'equipe RH)
        _add_hr("Vérification RH enregistrée (copie équipe RH) :")
        # Hierarchie : copie pour suivi
        _add_managers("Vérification RH enregistrée (copie hiérarchie) :")

    elif step == 'final':
        add(employee_name, employee_email, "Décision finale sur votre demande de congé :")
        # Hierarchie : tous les directeurs de la direction (validateur + collegues)
        _add_managers("Décision finale enregistrée (copie hiérarchie) :")
        if leave.manager_user and leave.manager_user.email:
            add(leave.manager_user.get_full_name() or leave.manager_user.username, leave.manager_user.email, "Décision finale (en copie - hiérarchie) :")
        # RH : tous les RH en copie pour archivage
        _add_hr("Décision finale enregistrée (copie équipe RH) :")

    return recipients


def _build_leave_email(recipient_name, role_label, leave, banner_color, banner_title, banner_subtitle):
    """Construit le sujet et les contenus text/html pour un email lie a un conge."""
    subject = f"[CSIG] {banner_title} - {leave.employee.name}"
    type_label = leave.get_leave_type_display()
    period = f"{leave.start_date.strftime('%d/%m/%Y')} au {leave.end_date.strftime('%d/%m/%Y')} ({leave.days_count} jour(s))"
    status_label = leave.get_status_display()

    def fmt_line(label, value):
        return f"  {label} : {value}\n" if value else ''

    text_content = (
        f"Bonjour {recipient_name},\n\n"
        f"{role_label}\n\n"
        f"  Demandeur : {leave.employee.name}\n"
        f"  Direction / Service : {leave.direction.name if leave.direction else '-'}\n"
        f"  Type de congé : {type_label}\n"
        f"  Période : {period}\n"
        f"  Motif : {leave.reason}\n"
        f"{fmt_line('Suppléant', leave.replacement)}"
        f"  Statut actuel : {status_label}\n"
        f"  Étape : {leave.current_step_label}\n\n"
        f"-- CSIG Dashboard"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html><body style="font-family: Arial, sans-serif; background:#f3f4f6; padding:20px; margin:0;">
      <div style="max-width:620px; margin:auto; background:white; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        {_logo_header(banner_color, banner_title, banner_subtitle)}
        <div style="padding:24px 24px 12px;">
          <p style="margin:0 0 10px;">Bonjour <strong>{recipient_name}</strong>,</p>
          <p style="margin:0 0 16px; color:#374151;">{role_label}</p>
          <table cellpadding="6" cellspacing="0" style="width:100%; border-collapse:collapse; font-size:14px;">
            <tr><td style="color:#6b7280;">Demandeur</td><td><strong>{leave.employee.name}</strong></td></tr>
            <tr><td style="color:#6b7280;">Direction / Service</td><td>{leave.direction.name if leave.direction else '-'}</td></tr>
            <tr><td style="color:#6b7280;">Type de congé</td><td>{type_label}</td></tr>
            <tr><td style="color:#6b7280;">Période</td><td>{period}</td></tr>
            <tr><td style="color:#6b7280;">Motif</td><td>{leave.reason}</td></tr>
            {('<tr><td style="color:#6b7280;">Suppléant</td><td>' + leave.replacement + '</td></tr>') if leave.replacement else ''}
            <tr><td style="color:#6b7280;">Statut</td><td><span style="background:{leave.status_color}; color:white; padding:3px 10px; border-radius:4px; font-size:12px;">{status_label}</span></td></tr>
            <tr><td style="color:#6b7280;">Étape</td><td>{leave.current_step_label}</td></tr>
          </table>
        </div>
        <div style="padding:0 24px 24px; color:#6b7280; font-size:12px;">
          <p style="margin:18px 0 0;">CSIG - Cité des Sciences et de l'Innovation de Guinée</p>
        </div>
      </div>
    </body></html>
    """
    return subject, text_content, html_content


def _dispatch_leave_emails(leave, step, banner_color, banner_title, banner_subtitle):
    recipients = _leave_recipients_step(leave, step)
    sent, errors = [], []
    for name, email, role in recipients:
        subject, text_content, html_content = _build_leave_email(name, role, leave, banner_color, banner_title, banner_subtitle)
        try:
            _send(subject, text_content, html_content, email)
            sent.append(email)
        except Exception as e:
            errors.append(f"{email}: {e}")
            logger.error(f"Echec envoi conge a {email}: {e}")
    if sent and not errors:
        return True, f"Envoye a : {', '.join(sent)}"
    if sent:
        return True, f"Envoye a : {', '.join(sent)} (echecs: {len(errors)})"
    return False, '; '.join(errors) or 'Aucun destinataire'


def notify_leave_submitted(leave):
    return _dispatch_leave_emails(
        leave, 'submitted',
        banner_color='#f59e0b',
        banner_title='Nouvelle demande de congé',
        banner_subtitle='Étape 1/3 - Avis hiérarchique requis',
    )


def notify_leave_manager_decided(leave):
    favorable = leave.manager_decision == 'favorable'
    return _dispatch_leave_emails(
        leave, 'manager',
        banner_color='#3b82f6' if favorable else '#ef4444',
        banner_title='Avis hiérarchique : ' + ('favorable' if favorable else 'défavorable'),
        banner_subtitle='Étape 2/3 - Vérification RH' if favorable else 'Demande refusée par la hiérarchie',
    )


def notify_leave_hr_decided(leave):
    conforme = leave.hr_decision == 'conforme'
    return _dispatch_leave_emails(
        leave, 'hr',
        banner_color='#6366f1' if conforme else '#ef4444',
        banner_title='Vérification RH : ' + ('conforme' if conforme else 'non conforme'),
        banner_subtitle='Étape 3/3 - Décision Direction' if conforme else 'Demande non conforme',
    )


def notify_leave_final_decided(leave):
    approved = leave.final_decision == 'approuve'
    return _dispatch_leave_emails(
        leave, 'final',
        banner_color='#16a34a' if approved else '#ef4444',
        banner_title='Décision finale : ' + ('approuvée' if approved else 'rejetée'),
        banner_subtitle='Notification officielle CSIG',
    )
