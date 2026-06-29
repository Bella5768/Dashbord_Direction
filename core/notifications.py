from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.translation import gettext as _, ngettext
from django.db.models import Q
from django.urls import reverse
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


def _task_gender_ctx(task_type):
    """Retourne les variables de genre grammatical pour task_type ('jalon', 'tâche', 'sous-étape')."""
    masculine = task_type in ('jalon',)
    return {
        'task_article_indef': _('un nouveau') if masculine else _('une nouvelle'),
        'task_article_def': _('Le') if masculine else _('La'),
        'task_pp_attribue': _('attribué') if masculine else _('attribuée'),
        'task_pp_termine': _('terminé') if masculine else _('terminée'),
    }


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

    member = project.members.filter(project_role__slug='responsable').select_related('employee').first()
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
        return (False, _("Email non configuré"))
    if not user.email:
        return (False, _("Cet utilisateur n'a pas d'adresse email"))

    subject = _("[CSIG] Créez votre mot de passe – Accès au tableau de bord")
    text, html = _render_email('account_invitation.html', {
        'recipient_name': user.get_full_name() or user.username,
        'username': user.username,
        'activation_link': activation_link,
        'invited_by': invited_by,
        'banner_color': '#1e3a5f',
        'banner_title': _('Bienvenue sur CSIG Dashboard'),
        'banner_subtitle': _('Activez votre compte en créant votre mot de passe'),
    })
    try:
        _send(subject, text, html, user.email)
        logger.info(f"Invitation envoyée à {user.email}")
        return (True, _("Invitation envoyée à {email}").format(email=user.email))
    except Exception as e:
        err = str(e)
        logger.error(f"Echec invitation {user.email}: {err}")
        return (False, err)


# =====================================================================
# Réinitialisation de mot de passe
# =====================================================================

def notify_password_reset(user, reset_link):
    """Envoie l'email de réinitialisation de mot de passe."""
    if not _is_email_configured():
        logger.warning("Reset non envoyé : email non configuré")
        return (False, _("Email non configuré"))
    if not user.email:
        return (False, _("Cet utilisateur n'a pas d'adresse email"))

    subject = _("[CSIG] Réinitialisation de votre mot de passe")
    text, html = _render_email('password_reset_email.html', {
        'recipient_name': user.get_full_name() or user.username,
        'username': user.username,
        'reset_link': reset_link,
        'banner_color': '#1e3a5f',
        'banner_title': _('Réinitialisation du mot de passe'),
        'banner_subtitle': _('Dashboard CSIG – Direction Générale'),
    })
    try:
        _send(subject, text, html, user.email)
        logger.info(f"Email reset envoyé à {user.email}")
        return (True, _("Email envoyé à {email}").format(email=user.email))
    except Exception as e:
        err = str(e)
        logger.error(f"Echec reset {user.email}: {err}")
        return (False, err)


# =====================================================================
# Attribution d'une tâche
# =====================================================================

def notify_assignment(employee, task_type, task_name, project_name, assigned_by, project=None, due_date=None):
    """Notifie l'attribution d'une tâche au responsable (+ chef de projet en CC)."""
    if not _is_email_configured():
        logger.warning("Notification non envoyée : identifiants email non configurés")
        return (False, _("Identifiants email non configurés"))

    if not employee or not employee.email:
        logger.warning(f"Notification non envoyée : pas d'email pour {employee}")
        return (False, _("Pas d'email pour cet employé"))

    employee_name = employee.name
    _gctx = _task_gender_ctx(task_type)
    _art = _gctx['task_article_indef']
    _pp = _gctx['task_pp_attribue']
    recipients = [(employee_name, employee.email, _("{article} {type} vous est {past_participle} :").format(article=_art.capitalize(), type=task_type, past_participle=_pp))]

    if project is not None:
        manager_name, manager_email = _resolve_manager_email(project)
        if manager_email and manager_email.lower() != employee.email.lower():
            recipients.append((manager_name, manager_email, _("En tant que chef de projet, vous êtes informé en copie :")))

    subject = _("[CSIG] Nouvelle attribution : {task}").format(task=task_name)
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
            'banner_title': _('Nouvelle attribution'),
            'banner_subtitle': _('Dashboard CSIG – Direction Générale'),
            **_gctx,
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
        return (True, _("Email envoyé à : {emails}").format(emails=', '.join(sent_emails)))
    if sent_emails and errors:
        return (True, _("Email envoyé à : {emails} (échecs : {count})").format(emails=', '.join(sent_emails), count=len(errors)))
    return (False, "; ".join(errors) or _("Échec d'envoi"))


# =====================================================================
# Ajout membre au projet
# =====================================================================

def notify_project_member_added(member, added_by_user):
    if not _is_email_configured():
        logger.warning("Notification non envoyée : identifiants email non configurés")
        return (False, _("Identifiants email non configurés"))

    employee = member.employee
    if not employee or not employee.email:
        logger.warning(f"Notification non envoyée : pas d'email pour {employee}")
        return (False, _("Pas d'email pour ce membre"))

    added_by = added_by_user.get_full_name() or added_by_user.username
    role_label = member.project_role.name if member.project_role else _('Membre')
    subject = _("[CSIG] Ajout au projet : {project}").format(project=member.project.name)

    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    project_url = f"{site_url}{reverse('core:project_detail', args=[member.project.id])}" if site_url else ''
    text, html = _render_email('project_member_added.html', {
        'employee_name': employee.name,
        'project_name': member.project.name,
        'role_label': role_label,
        'added_by': added_by,
        'project_url': project_url,
        'banner_color': '#1e3a5f',
        'banner_title': _('Ajout au projet'),
        'banner_subtitle': _('Dashboard CSIG – Direction Générale'),
    })
    try:
        _send(subject, text, html, employee.email)
        logger.info(f"Email ajout membre projet envoyé à {employee.email}")
        return (True, _("Email envoyé à : {email}").format(email=employee.email))
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
        return (False, _("Identifiants email non configurés"))

    completed_by_name = completed_by_user.get_full_name() or completed_by_user.username
    project_name = project.name

    recipients = []
    manager_name, manager_email = _resolve_manager_email(project)
    if manager_email:
        recipients.append((manager_name, manager_email, _("En tant que chef de projet, vous êtes informé que :")))

    if assigned_employee and assigned_employee.email:
        recipients.append((assigned_employee.name, assigned_employee.email, _("En tant que responsable de cette tâche, vous êtes informé que :")))

    if assigned_by_user and assigned_by_user.email:
        assigned_by_name = assigned_by_user.get_full_name() or assigned_by_user.username
        recipients.append((assigned_by_name, assigned_by_user.email, _("En tant que personne ayant attribué cette tâche, vous êtes informé que :")))

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
        return (False, _("Aucun destinataire avec email pour cette notification"))

    _gctx_tc = _task_gender_ctx(task_type)
    _pp_t = _gctx_tc['task_pp_termine']
    subject = _("[CSIG] {type} {status} : {task}").format(type=task_type.capitalize(), status=_pp_t, task=task_name)
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
            'banner_title': _('{type} {status}').format(type=task_type.capitalize(), status=_pp_t),
            'banner_subtitle': _('Dashboard CSIG – Direction Générale'),
            **_gctx_tc,
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
        return (True, _("Emails envoyés à : {emails}").format(emails=', '.join(sent_emails)))
    if sent_emails and errors:
        return (True, _("Emails envoyés à : {emails} (échecs : {count})").format(emails=', '.join(sent_emails), count=len(errors)))
    return (False, "; ".join(errors) or _("Échec d'envoi"))


# =====================================================================
# Alertes d'échéance
# =====================================================================

def notify_due_date_alert(employee, task_type, task_name, project_name, due_date, days_diff, project=None):
    """Envoie une alerte d'échéance (J-N, J-0, retard).

    days_diff : 0 = aujourd'hui, < 0 = en retard, > 0 = rappel J-N.
    Destinataires : responsable (employee) + chef de projet en CC.
    """
    if not _is_email_configured():
        return (False, _("Identifiants email non configurés"))

    if not employee or not employee.email:
        return (False, f"Pas d'email pour {employee}")

    if days_diff < 0:
        urgency_label = ngettext('EN RETARD de %(days)s jour', 'EN RETARD de %(days)s jours', abs(days_diff)) % {'days': abs(days_diff)}
        banner_color = '#b91c1c'
        banner_text = _('ALERTE ÉCHÉANCE DÉPASSÉE')
        subject_prefix = _('[URGENT - RETARD]')
    elif days_diff == 0:
        urgency_label = _("À FAIRE AUJOURD'HUI")
        banner_color = '#dc2626'
        banner_text = _("ALERTE : ÉCHÉANCE AUJOURD'HUI")
        subject_prefix = _('[URGENT]')
    else:
        urgency_label = ngettext('À faire dans %(days)s jour', 'À faire dans %(days)s jours', days_diff) % {'days': days_diff}
        banner_color = '#ea580c'
        banner_text = _("RAPPEL D'ÉCHÉANCE")
        subject_prefix = _('[RAPPEL]')

    employee_name = employee.name
    _gctx_dd = _task_gender_ctx(task_type)
    _dem = _('ce') if task_type in ('jalon',) else _('cette')
    recipients = [(employee_name, employee.email, _("En tant que responsable, vous devez traiter {demonstrative} {type} impérativement :").format(demonstrative=_dem, type=task_type))]
    if project is not None:
        manager_name, manager_email = _resolve_manager_email(project)
        if manager_email and manager_email.lower() != employee.email.lower():
            recipients.append((manager_name, manager_email, _("En tant que chef de projet, vous êtes informé en copie :")))

    subject = _("{prefix} {task} - échéance {date}").format(prefix=subject_prefix, task=task_name, date=due_date.strftime('%d/%m/%Y'))
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
            **_gctx_dd,
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
        return (True, _("Alertes envoyées à : {emails}").format(emails=', '.join(sent_emails)))
    if sent_emails and errors:
        return (True, _("Alertes envoyées à : {emails} (échecs : {count})").format(emails=', '.join(sent_emails), count=len(errors)))
    return (False, "; ".join(errors) or _("Échec d'envoi"))


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
        recipients.append((name or _('Utilisateur'), email, role))

    employee_email = leave.employee.email if leave.employee else None
    employee_name = leave.employee.name if leave.employee else 'Demandeur'

    def _hr_users():
        try:
            return User_.objects.filter(
                Q(profile__is_hr_manager=True) | Q(profile__role__slug='admin'),
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
                profile__role__slug='directeur',
                profile__direction_id=leave.direction_id,
                is_active=True,
            ).exclude(email='')
        except Exception:
            return []

    def _add_managers(role_label):
        for u in _direction_managers():
            add(u.get_full_name() or u.username, u.email, role_label)

    if step == 'submitted':
        _add_managers(_("Demande de congé soumise par un membre de votre équipe (avis hiérarchique requis) :"))
        add(employee_name, employee_email, _("Confirmation de soumission de votre demande de congé :"))
        _add_hr(_("Nouvelle demande de congé soumise (information RH) :"))

    elif step == 'manager':
        if leave.manager_decision == 'favorable':
            _add_hr(_("Demande de congé à vérifier (RH) :"))
        else:
            _add_hr(_("Avis hiérarchique défavorable enregistré (information RH) :"))
        add(employee_name, employee_email, _("Avis hiérarchique enregistré sur votre demande :"))
        _add_managers(_("Avis hiérarchique enregistré (copie hiérarchie) :"))

    elif step == 'hr':
        if leave.hr_decision == 'conforme':
            try:
                dg_users = User_.objects.filter(
                    profile__role__slug__in=['directeur_general', 'admin'],
                    is_active=True,
                ).exclude(email='')
                for u in dg_users:
                    add(u.get_full_name() or u.username, u.email, _("Demande de congé à valider (Direction Générale) :"))
            except Exception:
                pass
        add(employee_name, employee_email, _("Vérification RH enregistrée sur votre demande :"))
        _add_hr(_("Vérification RH enregistrée (copie équipe RH) :"))
        _add_managers(_("Vérification RH enregistrée (copie hiérarchie) :"))

    elif step == 'final':
        add(employee_name, employee_email, _("Décision finale sur votre demande de congé :"))
        _add_managers(_("Décision finale enregistrée (copie hiérarchie) :"))
        if leave.manager_user and leave.manager_user.email:
            add(leave.manager_user.get_full_name() or leave.manager_user.username, leave.manager_user.email, _("Décision finale (en copie - hiérarchie) :"))
        _add_hr(_("Décision finale enregistrée (copie équipe RH) :"))
        try:
            dg_users = User_.objects.filter(
                profile__role__slug__in=['directeur_general', 'admin'],
                is_active=True,
            ).exclude(email='')
            for u in dg_users:
                add(u.get_full_name() or u.username, u.email, _("Décision finale enregistrée (copie Direction Générale) :"))
        except Exception:
            pass

    return recipients


def _dispatch_leave_emails(leave, step, banner_color, banner_title, banner_subtitle, pdf_attachment=None):
    recipients = _leave_recipients_step(leave, step)
    sent, errors = [], []
    employee_email = leave.employee.email if leave.employee else None
    type_label = leave.get_leave_type_display()
    period = ngettext('%(start)s au %(end)s (%(days)s jour)', '%(start)s au %(end)s (%(days)s jours)', leave.days_count) % {'start': leave.start_date.strftime('%d/%m/%Y'), 'end': leave.end_date.strftime('%d/%m/%Y'), 'days': leave.days_count}
    status_label = leave.get_status_display()

    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    leave_url = f"{site_url}{reverse('core:leave_detail', args=[leave.id])}" if site_url else ''
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
            'leave_url': leave_url,
            'banner_color': banner_color,
            'banner_title': banner_title,
            'banner_subtitle': banner_subtitle,
        })
        subject = _('[CSIG] {title} – {employee}').format(title=banner_title, employee=leave.employee.name if leave.employee else _('Demandeur'))
        attachment = pdf_attachment if email == employee_email else None
        attachment_filename = f"attestation_conge_{leave.id}.pdf" if attachment else None
        try:
            _send(subject, text, html, email, attachment, attachment_filename)
            sent.append(email)
        except Exception as e:
            errors.append(f"{email}: {e}")
            logger.error(f"Echec envoi conge a {email}: {e}")

    if sent and not errors:
        return True, _("Envoyé à : {emails}").format(emails=', '.join(sent))
    if sent:
        return True, _("Envoyé à : {emails} (échecs : {count})").format(emails=', '.join(sent), count=len(errors))
    return False, '; '.join(errors) or _('Aucun destinataire')


def notify_leave_submitted(leave):
    return _dispatch_leave_emails(
        leave, 'submitted',
        banner_color='#f59e0b',
        banner_title=_('Nouvelle demande de congé'),
        banner_subtitle=_('Étape 1/3 – Avis hiérarchique requis'),
    )


def notify_leave_manager_decided(leave):
    favorable = leave.manager_decision == 'favorable'
    return _dispatch_leave_emails(
        leave, 'manager',
        banner_color='#3b82f6' if favorable else '#ef4444',
        banner_title=_('Avis hiérarchique : {decision}').format(decision=_('favorable') if favorable else _('défavorable')),
        banner_subtitle=_('Étape 2/3 – Vérification RH') if favorable else _('Demande refusée par la hiérarchie'),
    )


def notify_leave_hr_decided(leave):
    conforme = leave.hr_decision == 'conforme'
    return _dispatch_leave_emails(
        leave, 'hr',
        banner_color='#6366f1' if conforme else '#ef4444',
        banner_title=_('Vérification RH : {decision}').format(decision=_('conforme') if conforme else _('non conforme')),
        banner_subtitle=_('Étape 3/3 – Décision Direction') if conforme else _('Demande non conforme'),
    )


def notify_leave_final_decided(leave, pdf_attachment=None):
    approved = leave.final_decision == 'approuve'
    return _dispatch_leave_emails(
        leave, 'final',
        banner_color='#16a34a' if approved else '#ef4444',
        banner_title=_('Décision finale : {decision}').format(decision=_('approuvée') if approved else _('rejetée')),
        banner_subtitle=_('Notification officielle CSIG'),
        pdf_attachment=pdf_attachment,
    )


# =====================================================================
# Événements / Calendrier
# =====================================================================

def _event_email_ctx(event, actor_user, action):
    """Contexte commun pour les emails d'événement."""
    action_labels = {
        'created': _('Nouvel événement'),
        'updated': _('Événement modifié'),
        'cancelled': _('Événement annulé'),
        'invited': _('Invitation à un événement'),
    }
    banner_colors = {
        'created': '#1e3a5f',
        'updated': '#b45309',
        'cancelled': '#dc2626',
        'invited': '#1e3a5f',
    }
    label = action_labels.get(action, _('Événement'))
    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    event_url = f"{site_url}{reverse('core:event_detail', args=[event.id])}" if site_url and event.id else ''
    return {
        'title': f"{label} : {event.title}",
        'action_link': event_url,
        'action_text': _('Voir l\'événement'),
        'actor_name': actor_user.get_full_name() or actor_user.username,
        'event_title': event.title,
        'event_date': event.date.strftime('%d/%m/%Y'),
        'event_time': event.time.strftime('%H:%M'),
        'event_location': event.location or '',
        'event_type': event.get_event_type_display(),
        'banner_color': banner_colors.get(action, '#1e3a5f'),
        'banner_title': label,
        'banner_subtitle': _('Dashboard CSIG – Direction Générale'),
    }


def notify_event_directions_email(event, actor_user, action='created'):
    """Envoie un email aux employés des directions participantes à l'événement."""
    if not _is_email_configured():
        return
    from .models import Employee
    directions = list(event.participants.all())
    if not directions:
        return
    employees = (
        Employee.objects
        .filter(direction__in=directions)
        .exclude(email='')
        .exclude(email__isnull=True)
    )
    ctx = _event_email_ctx(event, actor_user, action)
    subject = f"[CSIG] {ctx['title']}"
    for emp in employees:
        text, html = _render_email('notification.html', {**ctx, 'username': emp.name})
        try:
            _send(subject, text, html, emp.email)
            logger.info(f"Email event ({action}) envoyé à {emp.email}")
        except Exception as e:
            logger.error(f"Erreur envoi email event à {emp.email}: {e}")


def notify_event_member_email(event_member, actor_user):
    """Envoie un email d'invitation à un membre d'événement spécifique."""
    if not _is_email_configured():
        return
    emp = event_member.employee
    if not emp.email:
        return
    event = event_member.event
    ctx = _event_email_ctx(event, actor_user, 'invited')
    subject = f"[CSIG] {ctx['title']}"
    text, html = _render_email('notification.html', {**ctx, 'username': emp.name})
    try:
        _send(subject, text, html, emp.email)
        logger.info(f"Email invitation event envoyé à {emp.email}")
    except Exception as e:
        logger.error(f"Erreur envoi email invitation event à {emp.email}: {e}")


def notify_event_deleted_email(event_title, event_date, member_emails, actor_user):
    """Envoie un email d'annulation aux membres d'un événement supprimé.

    member_emails — liste d'adresses email collectées AVANT la suppression.
    """
    if not _is_email_configured() or not member_emails:
        return
    actor_name = actor_user.get_full_name() or actor_user.username
    date_fmt = event_date.strftime('%d/%m/%Y')
    subject = f"[CSIG] Événement annulé : {event_title}"
    for email in member_emails:
        if not email:
            continue
        text, html = _render_email('notification.html', {
            'username': email,
            'title': f"Événement annulé : {event_title}",
            'message': (
                f"L'événement « {event_title} » prévu le {date_fmt} "
                f"a été annulé par {actor_name}."
            ),
            'action_link': '',
            'banner_color': '#dc2626',
            'banner_title': _('Événement annulé'),
            'banner_subtitle': _('Dashboard CSIG – Direction Générale'),
        })
        try:
            _send(subject, text, html, email)
            logger.info(f"Email annulation event envoyé à {email}")
        except Exception as e:
            logger.error(f"Erreur envoi email annulation event à {email}: {e}")
