"""
Moteur d'autorisation CASL-inspired.

Usage:
    ability = Ability(request.user)
    ability.can('read',   'Budget')
    ability.can('update', 'Project', project_instance)
    ability.can('manage', 'all')
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import User


class Ability:
    def __init__(self, user: "User"):
        self.user = user
        self._rules: list | None = None

    # ------------------------------------------------------------------
    # Chargement lazy des règles
    # ------------------------------------------------------------------
    @property
    def rules(self):
        if self._rules is None:
            profile = getattr(self.user, 'profile', None)
            if self.user.is_superuser:
                # superuser : règle synthétique manage:all sans condition
                self._rules = [_Rule('manage', 'all', '')]
            elif profile and profile.role_id:
                self._rules = list(
                    profile.role.permissions.values('action', 'subject', 'condition')
                )
            else:
                self._rules = []
        return self._rules

    # ------------------------------------------------------------------
    # Vérification principale
    # ------------------------------------------------------------------
    def can(self, action: str, subject: str, instance=None) -> bool:
        profile = getattr(self.user, 'profile', None)

        for rule in self.rules:
            r_action  = rule['action']  if isinstance(rule, dict) else rule.action
            r_subject = rule['subject'] if isinstance(rule, dict) else rule.subject
            r_cond    = rule['condition'] if isinstance(rule, dict) else rule.condition

            # Correspondance action
            if r_action not in (action, 'manage'):
                continue
            # Correspondance subject
            if r_subject not in (subject, 'all'):
                continue
            # Évaluation de la condition
            if self._check_condition(r_cond, instance, profile):
                return True

        return False

    # ------------------------------------------------------------------
    # Évaluation des conditions
    # ------------------------------------------------------------------
    def _check_condition(self, condition: str, instance, profile) -> bool:
        if not condition:
            return True

        if profile is None:
            return False

        if condition == 'same_direction':
            return self._cond_same_direction(instance, profile)

        if condition == 'is_project_manager':
            return self._cond_is_project_manager(instance, profile)

        if condition == 'is_project_member':
            return self._cond_is_project_member(instance, profile)

        if condition == 'is_owner':
            return self._cond_is_owner(instance)

        if condition == 'hr_pipeline':
            return self._cond_hr_pipeline(instance)

        return False

    # ------------------------------------------------------------------
    # Implémentations des conditions
    # ------------------------------------------------------------------
    def _cond_same_direction(self, instance, profile) -> bool:
        if profile.direction_id is None:
            return False
        direction_id = getattr(instance, 'direction_id', None)
        if direction_id is None:
            return False
        return direction_id == profile.direction_id

    def _cond_is_project_manager(self, instance, profile) -> bool:
        if instance is None:
            return False
        if profile.employee_id and instance.manager_employee_id:
            return instance.manager_employee_id == profile.employee_id
        return False

    def _cond_is_project_member(self, instance, profile) -> bool:
        if instance is None or not profile.employee_id:
            return False
        return instance.members.filter(employee_id=profile.employee_id).exists()

    def _cond_is_owner(self, instance) -> bool:
        if instance is None:
            return False
        # LeaveRequest : champ user
        owner_user_id = getattr(instance, 'user_id', None)
        if owner_user_id is not None:
            return owner_user_id == self.user.id
        # Fallback : champ created_by (CharField)
        created_by = getattr(instance, 'created_by', None)
        if created_by:
            return created_by == (self.user.get_full_name() or self.user.username)
        return False

    def _cond_hr_pipeline(self, instance) -> bool:
        """L'instance (LeaveRequest) doit avoir dépassé l'étape 'soumise'."""
        if instance is None:
            return False
        status = getattr(instance, 'status', None)
        return status in ['avis_favorable', 'rh_conforme', 'rh_non_conforme', 'approuvee', 'rejetee']

    # ------------------------------------------------------------------
    # Helpers pour les projets (is_project_manager OU is_project_member)
    # ------------------------------------------------------------------

    def _project_member_perm(self, project, action: str, subject: str) -> bool:
        """Vérifie si l'utilisateur, en tant que membre du projet, possède la permission."""
        if project is None:
            return False
        profile = getattr(self.user, 'profile', None)
        if profile is None or not profile.employee_id:
            return False
        from .models import ProjectMember
        try:
            member = (ProjectMember.objects
                      .select_related('project_role')
                      .prefetch_related('project_role__permissions')
                      .get(project=project, employee_id=profile.employee_id))
            return member._has_perm(action, subject)
        except ProjectMember.DoesNotExist:
            return False

    def can_view_project(self, project) -> bool:
        return (
            self.can('read', 'Project')
            or self.can('read', 'Project', project)
            or self._cond_is_project_manager(project, getattr(self.user, 'profile', None))
            or self._cond_is_project_member(project, getattr(self.user, 'profile', None))
        )

    def can_edit_project(self, project) -> bool:
        return (
            self.can('update', 'Project')
            or self.can('update', 'Project', project)
            or self._project_member_perm(project, 'update', 'Project')
        )

    def can_add_project_milestones(self, project) -> bool:
        return (
            self.can('create', 'Milestone')
            or self.can('create', 'Milestone', project)
            or self._project_member_perm(project, 'create', 'Milestone')
        )

    def can_edit_project_milestones(self, project) -> bool:
        return (
            self.can('update', 'Milestone')
            or self.can('update', 'Milestone', project)
            or self._project_member_perm(project, 'update', 'Milestone')
        )

    def can_add_project_documents(self, project) -> bool:
        return (
            self.can('create', 'Document')
            or self.can('create', 'Document', project)
            or self._project_member_perm(project, 'create', 'Document')
        )

    def can_edit_project_documents(self, project) -> bool:
        return (
            self.can('update', 'Document')
            or self.can('update', 'Document', project)
            or self._project_member_perm(project, 'update', 'Document')
        )

    def can_add_project_needs(self, project) -> bool:
        return (
            self.can('create', 'Request')
            or self.can('create', 'Request', project)
            or self._project_member_perm(project, 'create', 'Request')
        )

    def can_add_project_comments(self, project) -> bool:
        return (
            self.can('create', 'Comment')
            or self.can('create', 'Comment', project)
            or self._project_member_perm(project, 'create', 'Comment')
        )

    def can_manage_project_members(self, project) -> bool:
        return (
            self.can('manage', 'ProjectMember')
            or self.can('manage', 'ProjectMember', project)
            or self._project_member_perm(project, 'manage', 'ProjectMember')
        )

    def is_project_readonly(self, project) -> bool:
        return not (
            self.can_edit_project(project)
            or self.can_add_project_milestones(project)
            or self.can_edit_project_milestones(project)
            or self.can_add_project_documents(project)
            or self.can_edit_project_documents(project)
            or self.can_add_project_needs(project)
            or self.can_add_project_comments(project)
        )


class _Rule:
    """Règle synthétique pour superuser."""
    def __init__(self, action, subject, condition):
        self.action = action
        self.subject = subject
        self.condition = condition
