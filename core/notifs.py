"""
Notifications in-app — création centralisée.

Chaque helper crée une ou plusieurs entrées Notification pour les
destinataires concernés, en silence (aucune exception ne remonte).

Les titres et messages sont traduits selon la langue préférée de
l'utilisateur (profil utilisateur), à l'instar des emails.
"""
from django.urls import reverse
from django.utils.translation import gettext as _, override


def _user_language(user):
    """Retourne la langue préférée d'un utilisateur (profil)."""
    try:
        return getattr(getattr(user, 'profile', None), 'language', None) or 'fr'
    except Exception:
        return 'fr'


def push_project_update(project_id, data):
    """Diffuse une mise à jour de projet à tous les membres connectés (toutes pages)."""
    data = {**data, 'project_id': project_id}
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(
                f'project_{project_id}',
                {'type': 'project.update', 'data': data},
            )
    except Exception:
        pass


def push_section_refresh(project_id, section, actor='', project_progress=None):
    """Demande aux clients d'actualiser un panel de la page projet via fetch+DOMParser."""
    payload = {'event': 'section_refresh', 'section': section, 'actor': actor}
    if project_progress is not None:
        payload['project_progress'] = project_progress
    push_project_update(project_id, payload)


def push_project_meta(project):
    """Diffuse les métadonnées projet mises à jour (statut, nom, progression)."""
    push_project_update(project.id, {
        'event': 'project_meta',
        'name': project.name,
        'status': project.status,
        'computed_status': project.computed_status,
        'status_label': project.get_status_display(),
        'progress': project.progress,
    })


def push_milestone_status(project_id, milestone_id, status, status_label, completed, milestone_progress, project_progress):
    """Mise à jour in-place du statut d'un jalon (badge + progression)."""
    push_project_update(project_id, {
        'event': 'milestone_status',
        'milestone_id': milestone_id,
        'status': status,
        'status_label': status_label,
        'completed': completed,
        'progress': milestone_progress,
        'project_progress': project_progress,
    })


def _push_ws(receiver_id, notif_data):
    """Envoie la notification en temps réel via le channel layer."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(
                f'notif_user_{receiver_id}',
                {'type': 'notif.new', 'data': notif_data},
            )
    except Exception:
        pass


def _create(receiver, notif_type, title, message='', link=''):
    """Créer une notification et la pousser via WebSocket."""
    try:
        from .models import Notification
        lang = _user_language(receiver)
        with override(lang):
            n = Notification.objects.create(
                receiver=receiver,
                notif_type=notif_type,
                title=title,
                message=message,
                link=link,
            )
            _push_ws(receiver.id, {
                'id': n.id,
                'type': notif_type,
                'title': title,
                'message': message,
                'link': link,
                'is_read': False,
                'created_at': n.created_at.strftime('%d/%m à %H:%M'),
            })
    except Exception:
        pass


def _user_from_employee(employee):
    """Retourne le User lié à un Employee (via UserProfile), ou None."""
    try:
        return employee.user_profile.user
    except Exception:
        return None


# ------------------------------------------------------------------
# Jalons
# ------------------------------------------------------------------

def notify_jalon_completed(milestone, actor_user):
    """
    Notifie le chef de projet quand un jalon est complété.
    Ne notifie pas l'acteur lui-même.
    """
    project = milestone.project
    link = reverse('core:project_detail', args=[project.slug]) + '#jalons'

    manager_user = getattr(project, 'manager_user', None)
    if manager_user and manager_user != actor_user:
        lang = _user_language(manager_user)
        with override(lang):
            title = _("Jalon complété — {project}").format(project=project.name)
            msg = _("« {milestone} » a été marqué comme terminé par {actor}.").format(
                milestone=milestone.name,
                actor=actor_user.get_full_name() or actor_user.username,
            )
        _create(manager_user, 'jalon_complete', title, msg, link)

    for emp in milestone.assigned_to.all():
        user = _user_from_employee(emp)
        if user and user != actor_user and user != manager_user:
            lang = _user_language(user)
            with override(lang):
                title = _("Jalon complété — {project}").format(project=project.name)
                msg = _("« {milestone} » est terminé.").format(milestone=milestone.name)
            _create(user, 'jalon_complete', title, msg, link)


def notify_sous_etape_completed(sub_milestone, actor_user):
    """Notifie les assignés du jalon parent quand une sous-étape est complétée."""
    milestone = sub_milestone.milestone
    project = milestone.project
    link = reverse('core:project_detail', args=[project.slug]) + '#jalons'

    for emp in milestone.assigned_to.all():
        user = _user_from_employee(emp)
        if user and user != actor_user:
            lang = _user_language(user)
            with override(lang):
                title = _("Sous-étape complétée — {project}").format(project=project.name)
                msg = _("« {sub} » (jalon : {milestone}) est terminée.").format(
                    sub=sub_milestone.name,
                    milestone=milestone.name,
                )
            _create(user, 'sous_etape_complete', title, msg, link)


# ------------------------------------------------------------------
# Membres de projet
# ------------------------------------------------------------------

def notify_membre_ajoute(member, actor_user):
    """Notifie l'employé ajouté à un projet (si son compte User existe)."""
    user = _user_from_employee(member.employee)
    if not user or user == actor_user:
        return
    project = member.project
    link = reverse('core:project_detail', args=[project.slug])
    role_label = member.project_role.name if member.project_role else _('Membre')
    lang = _user_language(user)
    with override(lang):
        title = _("Vous avez été ajouté au projet « {project} »").format(project=project.name)
        msg = _("Rôle : {role}. Ajouté par {actor}.").format(
            role=role_label,
            actor=actor_user.get_full_name() or actor_user.username,
        )
    _create(user, 'membre_projet', title, msg, link)


# ------------------------------------------------------------------
# Commentaires
# ------------------------------------------------------------------

def notify_commentaire(project, actor_user):
    """Notifie les membres du projet d'un nouveau commentaire (sauf l'auteur)."""
    link = reverse('core:project_detail', args=[project.slug]) + '#commentaires'
    author = actor_user.get_full_name() or actor_user.username

    for pm in project.members.select_related('employee__user_profile__user').all():
        user = _user_from_employee(pm.employee)
        if user and user != actor_user:
            lang = _user_language(user)
            with override(lang):
                title = _("Nouveau commentaire — {project}").format(project=project.name)
                msg = _("{author} a laissé un commentaire sur le projet.").format(author=author)
            _create(user, 'commentaire', title, msg, link)


# ------------------------------------------------------------------
# Congés
# ------------------------------------------------------------------

def _leave_requestor_user(leave):
    """Retourne le User demandeur du congé, ou None."""
    return leave.user


def notify_conge_avis(leave, actor_user):
    """Notifie le demandeur de l'avis hiérarchique."""
    user = _leave_requestor_user(leave)
    if not user or user == actor_user:
        return
    link = reverse('core:leave_detail', args=[leave.id])
    favorable = leave.status == 'avis_favorable'
    lang = _user_language(user)
    with override(lang):
        if favorable:
            title = _("Avis hiérarchique favorable sur votre congé")
            msg = _("Votre demande de congé du {start} au {end} a reçu un avis favorable.").format(
                start=leave.start_date, end=leave.end_date,
            )
        else:
            title = _("Avis hiérarchique défavorable sur votre congé")
            msg = _("Votre demande de congé du {start} au {end} a reçu un avis défavorable.").format(
                start=leave.start_date, end=leave.end_date,
            )
    _create(user, 'conge_avis', title, msg, link)


def notify_conge_rh(leave, actor_user):
    """Notifie le demandeur de la vérification RH."""
    user = _leave_requestor_user(leave)
    if not user or user == actor_user:
        return
    link = reverse('core:leave_detail', args=[leave.id])
    conforme = leave.status == 'rh_conforme'
    lang = _user_language(user)
    with override(lang):
        if conforme:
            title = _("Vérification RH : conforme")
            msg = _("Votre demande de congé du {start} au {end} est déclarée conforme par les RH.").format(
                start=leave.start_date, end=leave.end_date,
            )
        else:
            title = _("Vérification RH : non conforme")
            msg = _("Votre demande de congé du {start} au {end} est déclarée non conforme par les RH.").format(
                start=leave.start_date, end=leave.end_date,
            )
    _create(user, 'conge_rh', title, msg, link)


# ------------------------------------------------------------------
# Événements / Calendrier
# ------------------------------------------------------------------

def push_calendar_update(action, event_id, event_date):
    """Broadcast WS global pour actualiser le calendrier sur tous les clients connectés."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(
                'calendar',
                {'type': 'calendar.update', 'data': {
                    'action': action,
                    'event_id': event_id,
                    'date': str(event_date),
                }},
            )
    except Exception:
        pass


def _users_from_directions(directions):
    """Retourne les Users actifs liés à une liste de directions (via UserProfile)."""
    try:
        from .models import UserProfile
        profiles = (
            UserProfile.objects
            .filter(direction__in=directions, is_active_profile=True)
            .select_related('user')
        )
        return [p.user for p in profiles]
    except Exception:
        return []


def notify_event_members_updated(event, actor_user, exclude_employee_ids=None):
    """Notifie les EventMember existants de la modification d'un événement."""
    link = reverse('core:event_detail', args=[event.slug])
    actor_name = actor_user.get_full_name() or actor_user.username
    date_fmt = event.date.strftime('%d/%m/%Y')
    exclude = exclude_employee_ids or set()

    members = (
        event.event_members
        .exclude(employee_id__in=exclude)
        .select_related('employee')
    )
    for m in members:
        user = _user_from_employee(m.employee)
        if user and user != actor_user:
            lang = _user_language(user)
            with override(lang):
                title = _("Événement modifié — {event}").format(event=event.title)
                msg = _("« {event} » du {date} a été modifié par {actor}.").format(
                    event=event.title, date=date_fmt, actor=actor_name,
                )
            _create(user, 'event_update', title, msg, link)


def notify_event_deleted(event_title, event_date, directions, actor_user):
    """Notifie les users des directions participantes à la suppression d'un événement."""
    actor_name = actor_user.get_full_name() or actor_user.username
    date_fmt = event_date.strftime('%d/%m/%Y')
    for user in _users_from_directions(directions):
        if user != actor_user:
            lang = _user_language(user)
            with override(lang):
                title = _("Événement annulé — {event}").format(event=event_title)
                msg = _("« {event} » prévu le {date} a été annulé par {actor}.").format(
                    event=event_title, date=date_fmt, actor=actor_name,
                )
            _create(user, 'event_cancel', title, msg, '')


def notify_event_member_invited(event_member, actor_user):
    """Notifie un employé qu'il est invité à un événement."""
    user = _user_from_employee(event_member.employee)
    if not user or user == actor_user:
        return
    event = event_member.event
    link = reverse('core:event_detail', args=[event.slug])
    actor_name = actor_user.get_full_name() or actor_user.username
    date_fmt = event.date.strftime('%d/%m/%Y')
    time_fmt = event.time.strftime('%H:%M')
    lang = _user_language(user)
    with override(lang):
        title = _("Invitation — {event}").format(event=event.title)
        msg = _("Vous êtes invité à « {event} » le {date} à {time}. Organisé par {actor}.").format(
            event=event.title, date=date_fmt, time=time_fmt, actor=actor_name,
        )
    _create(user, 'event_invite', title, msg, link)


def notify_event_rsvp(event_member, actor_user):
    """Notifie le créateur de l'événement d'une réponse RSVP."""
    event = event_member.event
    creator = event.created_by
    if not creator or creator == actor_user:
        return
    link = reverse('core:event_detail', args=[event.slug])
    employee_name = event_member.employee.name
    status_label = event_member.get_status_display()
    lang = _user_language(creator)
    with override(lang):
        title = _("Réponse RSVP — {event}").format(event=event.title)
        msg = _("{employee} a répondu « {status} » à l'invitation pour « {event} ».").format(
            employee=employee_name, status=status_label, event=event.title,
        )
    _create(creator, 'event_rsvp', title, msg, link)


def notify_conge_decision(leave, actor_user):
    """Notifie le demandeur de la décision finale."""
    user = _leave_requestor_user(leave)
    if not user or user == actor_user:
        return
    link = reverse('core:leave_detail', args=[leave.id])
    approved = leave.status == 'approuvee'
    lang = _user_language(user)
    with override(lang):
        if approved:
            title = _("Votre congé a été approuvée")
            msg = _("La décision finale sur votre demande du {start} au {end} est : approuvée.").format(
                start=leave.start_date, end=leave.end_date,
            )
        else:
            title = _("Votre congé a été rejetée")
            msg = _("La décision finale sur votre demande du {start} au {end} est : rejetée.").format(
                start=leave.start_date, end=leave.end_date,
            )
    _create(user, 'conge_decision', title, msg, link)
