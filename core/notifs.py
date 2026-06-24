"""
Notifications in-app — création centralisée.

Chaque helper crée une ou plusieurs entrées Notification pour les
destinataires concernés, en silence (aucune exception ne remonte).
"""
from django.urls import reverse


def push_project_update(project_id, data):
    """Diffuse une mise à jour de projet à tous les membres connectés (toutes pages)."""
    data = {**data, 'project_id': project_id}  # project_id always included for client-side filtering
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


def push_section_refresh(project_id, section, actor=''):
    """Demande aux clients d'actualiser un panel de la page projet via fetch+DOMParser."""
    push_project_update(project_id, {'event': 'section_refresh', 'section': section, 'actor': actor})


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
    link = reverse('core:project_detail', args=[project.id]) + '#jalons'

    # Notifier le manager du projet (si c'est un User distinct de l'acteur)
    manager_user = getattr(project, 'manager_user', None)
    if manager_user and manager_user != actor_user:
        _create(
            manager_user,
            'jalon_complete',
            f"Jalon complété — {project.name}",
            f"« {milestone.name} » a été marqué comme terminé par {actor_user.get_full_name() or actor_user.username}.",
            link,
        )

    # Notifier les autres membres assignés à ce jalon
    for emp in milestone.assigned_to.all():
        user = _user_from_employee(emp)
        if user and user != actor_user and user != manager_user:
            _create(
                user,
                'jalon_complete',
                f"Jalon complété — {project.name}",
                f"« {milestone.name} » est terminé.",
                link,
            )


def notify_sous_etape_completed(sub_milestone, actor_user):
    """Notifie les assignés du jalon parent quand une sous-étape est complétée."""
    milestone = sub_milestone.milestone
    project = milestone.project
    link = reverse('core:project_detail', args=[project.id]) + '#jalons'

    for emp in milestone.assigned_to.all():
        user = _user_from_employee(emp)
        if user and user != actor_user:
            _create(
                user,
                'sous_etape_complete',
                f"Sous-étape complétée — {project.name}",
                f"« {sub_milestone.name} » (jalon : {milestone.name}) est terminée.",
                link,
            )


# ------------------------------------------------------------------
# Membres de projet
# ------------------------------------------------------------------

def notify_membre_ajoute(member, actor_user):
    """Notifie l'employé ajouté à un projet (si son compte User existe)."""
    user = _user_from_employee(member.employee)
    if not user or user == actor_user:
        return
    project = member.project
    link = reverse('core:project_detail', args=[project.id])
    role_label = member.project_role.name if member.project_role else 'membre'
    _create(
        user,
        'membre_projet',
        f"Vous avez été ajouté au projet « {project.name} »",
        f"Rôle : {role_label}. Ajouté par {actor_user.get_full_name() or actor_user.username}.",
        link,
    )


# ------------------------------------------------------------------
# Commentaires
# ------------------------------------------------------------------

def notify_commentaire(project, actor_user):
    """Notifie les membres du projet d'un nouveau commentaire (sauf l'auteur)."""
    link = reverse('core:project_detail', args=[project.id]) + '#commentaires'
    author = actor_user.get_full_name() or actor_user.username

    for pm in project.members.select_related('employee__user_profile__user').all():
        user = _user_from_employee(pm.employee)
        if user and user != actor_user:
            _create(
                user,
                'commentaire',
                f"Nouveau commentaire — {project.name}",
                f"{author} a laissé un commentaire sur le projet.",
                link,
            )


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
    verdict = "favorable" if favorable else "défavorable"
    _create(
        user,
        'conge_avis',
        f"Avis hiérarchique {verdict} sur votre congé",
        f"Votre demande de congé du {leave.start_date} au {leave.end_date} a reçu un avis {verdict}.",
        link,
    )


def notify_conge_rh(leave, actor_user):
    """Notifie le demandeur de la vérification RH."""
    user = _leave_requestor_user(leave)
    if not user or user == actor_user:
        return
    link = reverse('core:leave_detail', args=[leave.id])
    conforme = leave.status == 'rh_conforme'
    verdict = "conforme" if conforme else "non conforme"
    _create(
        user,
        'conge_rh',
        f"Vérification RH : {verdict}",
        f"Votre demande de congé du {leave.start_date} au {leave.end_date} est déclarée {verdict} par les RH.",
        link,
    )


def notify_conge_decision(leave, actor_user):
    """Notifie le demandeur de la décision finale."""
    user = _leave_requestor_user(leave)
    if not user or user == actor_user:
        return
    link = reverse('core:leave_detail', args=[leave.id])
    approved = leave.status == 'approuvee'
    verdict = "approuvée" if approved else "rejetée"
    _create(
        user,
        'conge_decision',
        f"Votre congé a été {verdict}",
        f"La décision finale sur votre demande du {leave.start_date} au {leave.end_date} est : {verdict}.",
        link,
    )
