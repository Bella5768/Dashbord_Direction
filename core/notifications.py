from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db.models import Q
from email.mime.image import MIMEImage
from email.utils import formataddr
import logging
import os
import re

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


def _send(subject, text_content, html_content, recipient, attachment=None, attachment_filename=None):
    from_header, sender_email = _build_from()
    headers = {
        'Reply-To': sender_email,
        'X-Auto-Response-Suppress': 'OOF, AutoReply',
        'Auto-Submitted': 'auto-generated',
    }
    email = EmailMultiAlternatives(subject, text_content, from_header, [recipient], headers=headers)
    email.attach_alternative(html_content, 'text/html')
    _attach_logo(email)
    if attachment and attachment_filename:
        email.attach(attachment_filename, attachment, 'application/pdf')
    email.send()


def _render_email(template_name, context):
    """Rend un template emails/<template_name> et retourne (text, html)."""
    html = render_to_string(f'emails/{template_name}', context)
    text = re.sub(r'[ \t]+', ' ', strip_tags(html))
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text).strip()
    return text, html


def _is_email_configured():
    """Vérifie qu'un backend d'envoi est configuré (Outlook ou SendGrid)."""
    host_user = getattr(settings, 'EMAIL_HOST_USER', '')
    host_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
    return bool(host_user and host_password)


def _resolve_manager_email(project):
    """Résout l'email du chef de projet : manager_employee FK en priorité, puis recherche par nom."""
    from .models import Employee
    if project.manager_employee_id:
        emp = project.manager_employee
        if emp and emp.email:
            return emp.name, emp.email

    manager_name = (project.manager or '').strip()
    if manager_name:
        emp = Employee.objects.filter(name__iexact=manager_name, email__isnull=False).exclude(email='').first()
        if emp:
            return emp.name, emp.email

    member = project.members.filter(role='responsable').select_related('employee').first()
    if member and member.employee and member.employee.email:
        return member.employee.name, member.employee.email

    return manager_name or None, None


# =====================================================================
# Invitation à créer un compte
# =====================================================================

def notify_account_invitation(user, activation_link, invited_by=None):
    """Envoie l'email d'invitation pour que l'utilisateur définisse son mot de passe."""
    if not _is_email_configured():
        logger.warning("Invitation non envoyée : email non configuré")
        return (False, "Email non configuré")
    if not user.email:
        return (False, "Cet utilisateur n'a pas d'adresse email")

    subject = "[CSIG] Créez votre mot de passe – Accès au tableau de bord"
    text, html = _render_email('account_invitation.html', {
        'recipient_name': user.get_full_name() or user.username,
        'username': user.username,
        'activation_link': activation_link,
        'invited_by': invited_by,
        'banner_color': '#1e3a5f',
        'banner_title': 'Bienvenue sur CSIG Dashboard',
        'banner_subtitle': 'Activez votre compte en créant votre mot de passe',
    })
    try:
        _send(subject, text, html, user.email)
        logger.info(f"Invitation envoyée à {user.email}")
        return (True, f"Invitation envoyée à {user.email}")
    except Exception as e:
        err = str(e)
        logger.error(f"Echec invitation {user.email}: {err}")
        return (False, err)


# =====================================================================
# Attribution d'une tâche
# =====================================================================

def notify_assignment(employee, task_type, task_name, project_name, assigned_by, project=None, due_date=None):
    """Notifie l'attribution d'une tâche au responsable (+ chef de projet en CC)."""
    if not _is_email_configured():
        logger.warning("Notification non envoyée : identifiants email non configurés")
        return (False, "Identifiants email non configurés")

    if not employee or not employee.email:
        logger.warning(f"Notification non envoyée : pas d'email pour {employee}")
        return (False, "Pas d'email pour cet employé")

    employee_name = employee.name
    recipients = [(employee_name, employee.email, "Une nouvelle tâche vous est attribuée :")]

    if project is not None:
        manager_name, manager_email = _resolve_manager_email(project)
        if manager_email and manager_email.lower() != employee.email.lower():
            recipients.append((manager_name, manager_email, "En tant que chef de projet, vous êtes informé en copie :"))

    subject = f"[CSIG] Nouvelle attribution : {task_name}"
    sent_emails, errors = [], []
    for rec_name, rec_email, role_label in recipients:
        text, html = _render_email('assignment.html', {
            'recipient_name': rec_name,
            'role_label': role_label,
            'employee_name': employee_name,
            'task_type': task_type,
            'task_name': task_name,
            'project_name': project_name,
            'assigned_by': assigned_by,
            'due_date': due_date,
            'banner_color': '#1e3a5f',
            'banner_title': 'Nouvelle attribution',
            'banner_subtitle': 'Dashboard CSIG – Direction Générale',
        })
        try:
            _send(subject, text, html, rec_email)
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


# =====================================================================
# Ajout membre au projet
# =====================================================================

def notify_project_member_added(member, added_by_user):
    if not _is_email_configured():
        logger.warning("Notification non envoyée : identifiants email non configurés")
        return (False, "Identifiants email non configurés")

    employee = member.employee
    if not employee or not employee.email:
        logger.warning(f"Notification non envoyée : pas d'email pour {employee}")
        return (False, "Pas d'email pour ce membre")

    added_by = added_by_user.get_full_name() or added_by_user.username
    role_label = member.get_role_display() if member.role else 'Membre'
    subject = f"[CSIG] Ajout au projet : {member.project.name}"

    text, html = _render_email('project_member_added.html', {
        'employee_name': employee.name,
        'project_name': member.project.name,
        'role_label': role_label,
        'added_by': added_by,
        'banner_color': '#1e3a5f',
        'banner_title': 'Ajout au projet',
        'banner_subtitle': 'Dashboard CSIG – Direction Générale',
    })
    try:
        _send(subject, text, html, employee.email)
        logger.info(f"Email ajout membre projet envoyé à {employee.email}")
        return (True, f"Email envoyé à : {employee.email}")
    except Exception as e:
        err = f"Erreur envoi à {employee.email}: {e}"
        logger.error(err)
        return (False, err)


# =====================================================================
# Tâche terminée
# =====================================================================

def notify_task_completed(task_type, task_name, project, assigned_employee, assigned_by_user, completed_by_user):
    """Notifie la fin d'une tâche : chef de projet, responsable, et personne ayant affecté."""
    if not _is_email_configured():
        logger.warning("Notification non envoyée : identifiants email non configurés")
        return (False, "Identifiants email non configurés")

    completed_by_name = completed_by_user.get_full_name() or completed_by_user.username
    project_name = project.name

    recipients = []
    manager_name, manager_email = _resolve_manager_email(project)
    if manager_email:
        recipients.append((manager_name, manager_email, "En tant que chef de projet, vous êtes informé que :"))

    if assigned_employee and assigned_employee.email:
        recipients.append((assigned_employee.name, assigned_employee.email, "En tant que responsable de cette tâche, vous êtes informé que :"))

    if assigned_by_user and assigned_by_user.email:
        assigned_by_name = assigned_by_user.get_full_name() or assigned_by_user.username
        recipients.append((assigned_by_name, assigned_by_user.email, "En tant que personne ayant attribué cette tâche, vous êtes informé que :"))

    completed_by_email = (completed_by_user.email or '').lower().strip() if completed_by_user else ''
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

    subject = f"[CSIG] {task_type.capitalize()} terminée : {task_name}"
    sent_emails, errors = [], []
    for name, email, role_label in unique_recipients:
        text, html = _render_email('task_completed.html', {
            'recipient_name': name,
            'role_label': role_label,
            'task_type': task_type,
            'task_name': task_name,
            'project_name': project_name,
            'completed_by_name': completed_by_name,
            'banner_color': '#047857',
            'banner_title': f'{task_type.capitalize()} terminée',
            'banner_subtitle': 'Dashboard CSIG – Direction Générale',
        })
        try:
            _send(subject, text, html, email)
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


# =====================================================================
# Alertes d'échéance
# =====================================================================

def notify_due_date_alert(employee, task_type, task_name, project_name, due_date, days_diff, project=None):
    """Envoie une alerte d'échéance (J-N, J-0, retard).

    days_diff : 0 = aujourd'hui, < 0 = en retard, > 0 = rappel J-N.
    Destinataires : responsable (employee) + chef de projet en CC.
    """
    if not _is_email_configured():
        return (False, "Identifiants email non configurés")

    if not employee or not employee.email:
        return (False, f"Pas d'email pour {employee}")

    if days_diff < 0:
        urgency_label = f"EN RETARD de {abs(days_diff)} jour{'s' if abs(days_diff) > 1 else ''}"
        banner_color = '#b91c1c'
        banner_text = 'ALERTE ÉCHÉANCE DÉPASSÉE'
        subject_prefix = '[URGENT - RETARD]'
    elif days_diff == 0:
        urgency_label = "À FAIRE AUJOURD'HUI"
        banner_color = '#dc2626'
        banner_text = "ALERTE : ÉCHÉANCE AUJOURD'HUI"
        subject_prefix = '[URGENT]'
    else:
        urgency_label = f"À faire dans {days_diff} jour{'s' if days_diff > 1 else ''}"
        banner_color = '#ea580c'
        banner_text = "RAPPEL D'ÉCHÉANCE"
        subject_prefix = '[RAPPEL]'

    employee_name = employee.name
    recipients = [(employee_name, employee.email, "En tant que responsable, vous devez traiter cette tâche impérativement :")]
    if project is not None:
        manager_name, manager_email = _resolve_manager_email(project)
        if manager_email and manager_email.lower() != employee.email.lower():
            recipients.append((manager_name, manager_email, "En tant que chef de projet, vous êtes informé en copie :"))

    subject = f"{subject_prefix} {task_name} - échéance {due_date.strftime('%d/%m/%Y')}"
    sent_emails, errors = [], []
    for rec_name, rec_email, role_label in recipients:
        text, html = _render_email('due_date_alert.html', {
            'recipient_name': rec_name,
            'role_label': role_label,
            'employee_name': employee_name,
            'task_type': task_type,
            'task_name': task_name,
            'project_name': project_name,
            'due_date': due_date,
            'urgency_label': urgency_label,
            'banner_color': banner_color,
            'banner_title': banner_text,
            'banner_subtitle': urgency_label,
        })
        try:
            _send(subject, text, html, rec_email)
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
# Notifications liées aux congés
# =====================================================================

def _leave_recipients_step(leave, step):
    """Construit la liste des destinataires (name, email, role_label) pour une étape donnée."""
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
        _add_managers("Demande de congé soumise par un membre de votre équipe (avis hiérarchique requis) :")
        add(employee_name, employee_email, "Confirmation de soumission de votre demande de congé :")
        _add_hr("Nouvelle demande de congé soumise (information RH) :")

    elif step == 'manager':
        if leave.manager_decision == 'favorable':
            _add_hr("Demande de congé à vérifier (RH) :")
        else:
            _add_hr("Avis hiérarchique défavorable enregistré (information RH) :")
        add(employee_name, employee_email, "Avis hiérarchique enregistré sur votre demande :")
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
        _add_hr("Vérification RH enregistrée (copie équipe RH) :")
        _add_managers("Vérification RH enregistrée (copie hiérarchie) :")

    elif step == 'final':
        add(employee_name, employee_email, "Décision finale sur votre demande de congé :")
        _add_managers("Décision finale enregistrée (copie hiérarchie) :")
        if leave.manager_user and leave.manager_user.email:
            add(leave.manager_user.get_full_name() or leave.manager_user.username, leave.manager_user.email, "Décision finale (en copie - hiérarchie) :")
        _add_hr("Décision finale enregistrée (copie équipe RH) :")
        try:
            dg_users = User_.objects.filter(
                profile__role__in=['directeur_general', 'admin'],
                is_active=True,
            ).exclude(email='')
            for u in dg_users:
                add(u.get_full_name() or u.username, u.email, "Décision finale enregistrée (copie Direction Générale) :")
        except Exception:
            pass

    return recipients


def _dispatch_leave_emails(leave, step, banner_color, banner_title, banner_subtitle, pdf_attachment=None):
    recipients = _leave_recipients_step(leave, step)
    sent, errors = [], []
    employee_email = leave.employee.email if leave.employee else None
    type_label = leave.get_leave_type_display()
    period = f"{leave.start_date.strftime('%d/%m/%Y')} au {leave.end_date.strftime('%d/%m/%Y')} ({leave.days_count} jour(s))"
    status_label = leave.get_status_display()

    for name, email, role in recipients:
        text, html = _render_email('leave.html', {
            'recipient_name': name,
            'role_label': role,
            'employee_name': leave.employee.name if leave.employee else '–',
            'direction_name': leave.direction.name if leave.direction else '–',
            'type_label': type_label,
            'period': period,
            'reason': leave.reason,
            'replacement': leave.replacement,
            'status_label': status_label,
            'status_color': leave.status_color,
            'step_label': leave.current_step_label,
            'banner_color': banner_color,
            'banner_title': banner_title,
            'banner_subtitle': banner_subtitle,
        })
        subject = f"[CSIG] {banner_title} – {leave.employee.name if leave.employee else 'Demandeur'}"
        attachment = pdf_attachment if email == employee_email else None
        attachment_filename = f"attestation_conge_{leave.id}.pdf" if attachment else None
        try:
            _send(subject, text, html, email, attachment, attachment_filename)
            sent.append(email)
        except Exception as e:
            errors.append(f"{email}: {e}")
            logger.error(f"Echec envoi conge a {email}: {e}")

    if sent and not errors:
        return True, f"Envoyé à : {', '.join(sent)}"
    if sent:
        return True, f"Envoyé à : {', '.join(sent)} (échecs : {len(errors)})"
    return False, '; '.join(errors) or 'Aucun destinataire'


def notify_leave_submitted(leave):
    return _dispatch_leave_emails(
        leave, 'submitted',
        banner_color='#f59e0b',
        banner_title='Nouvelle demande de congé',
        banner_subtitle='Étape 1/3 – Avis hiérarchique requis',
    )


def notify_leave_manager_decided(leave):
    favorable = leave.manager_decision == 'favorable'
    return _dispatch_leave_emails(
        leave, 'manager',
        banner_color='#3b82f6' if favorable else '#ef4444',
        banner_title='Avis hiérarchique : ' + ('favorable' if favorable else 'défavorable'),
        banner_subtitle='Étape 2/3 – Vérification RH' if favorable else 'Demande refusée par la hiérarchie',
    )


def notify_leave_hr_decided(leave):
    conforme = leave.hr_decision == 'conforme'
    return _dispatch_leave_emails(
        leave, 'hr',
        banner_color='#6366f1' if conforme else '#ef4444',
        banner_title='Vérification RH : ' + ('conforme' if conforme else 'non conforme'),
        banner_subtitle='Étape 3/3 – Décision Direction' if conforme else 'Demande non conforme',
    )


def notify_leave_final_decided(leave, pdf_attachment=None):
    approved = leave.final_decision == 'approuve'
    return _dispatch_leave_emails(
        leave, 'final',
        banner_color='#16a34a' if approved else '#ef4444',
        banner_title='Décision finale : ' + ('approuvée' if approved else 'rejetée'),
        banner_subtitle='Notification officielle CSIG',
        pdf_attachment=pdf_attachment,
    )
