from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError


# =====================================================================
# RBAC : Permission / Role / ProjectRole
# =====================================================================

class Permission(models.Model):
    ACTION_CHOICES = [
        ('read', _('Lire')),
        ('create', _('Créer')),
        ('update', _('Modifier')),
        ('delete', _('Supprimer')),
        ('manage', _('Gérer (tout)')),
        ('approve', _('Approuver')),
        ('export', _('Exporter')),
    ]
    SUBJECT_CHOICES = [
        ('all', _('Tout')),
        ('Project', _('Projets')),
        ('Milestone', _('Jalons / Tâches')),
        ('Comment', _('Commentaires projet')),
        ('ProjectMember', _('Membres de projet')),
        ('Budget', _('Budgets')),
        ('User', _('Utilisateurs')),
        ('Employee', _('Employés')),
        ('LeaveRequest', _('Demandes de congé')),
        ('Partner', _('Partenaires')),
        ('Document', _('Documents')),
        ('Request', _('Demandes / Besoins projet')),
        ('Event', _('Événements')),
        ('Direction', _('Directions')),
        ('Role', _('Rôles')),
        ('Report', _('Rapports')),
    ]
    CONDITION_CHOICES = [
        ('', _('Aucune (accès global)')),
        ('same_direction', _('Même direction')),
        ('is_project_manager', _('Est manager du projet')),
        ('is_project_member', _('Est membre du projet')),
        ('is_owner', _('Est propriétaire')),
        ('hr_pipeline', _('Pipeline RH (après avis hiérarchique)')),
    ]

    action      = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name=_("Action"))
    subject     = models.CharField(max_length=30, choices=SUBJECT_CHOICES, verbose_name=_("Sujet"))
    condition   = models.CharField(max_length=30, choices=CONDITION_CHOICES, blank=True, default='', verbose_name=_("Condition"))
    description = models.CharField(max_length=200, blank=True, verbose_name=_("Description"))

    class Meta:
        unique_together = ['action', 'subject', 'condition']
        verbose_name = _("Permission")
        verbose_name_plural = _("Permissions")
        ordering = ['subject', 'action']

    def __str__(self):
        cond = f" [{self.condition}]" if self.condition else ""
        return f"{self.get_action_display()} : {self.get_subject_display()}{cond}"


class Role(models.Model):
    name        = models.CharField(max_length=100, verbose_name=_("Nom"))
    slug        = models.SlugField(max_length=50, unique=True, verbose_name=_("Identifiant"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    permissions = models.ManyToManyField(Permission, blank=True, related_name='roles', verbose_name=_("Permissions"))
    is_system   = models.BooleanField(default=False, verbose_name=_("Rôle système (non supprimable)"))
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Rôle")
        verbose_name_plural = _("Rôles")
        ordering = ['name']

    def __str__(self):
        return self.name


class ProjectRole(models.Model):
    name        = models.CharField(max_length=100, verbose_name=_("Nom"))
    slug        = models.SlugField(max_length=50, unique=True, verbose_name=_("Identifiant"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    permissions = models.ManyToManyField(Permission, blank=True, related_name='project_roles', verbose_name=_("Permissions projet"))
    is_system   = models.BooleanField(default=False, verbose_name=_("Rôle système (non supprimable)"))
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Rôle projet")
        verbose_name_plural = _("Rôles projet")
        ordering = ['name']

    def __str__(self):
        return self.name


# =====================================================================
# Profil utilisateur
# =====================================================================

class UserProfile(models.Model):
    user                = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role                = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='users', verbose_name=_("Rôle"))
    direction           = models.ForeignKey('Direction', on_delete=models.SET_NULL, null=True, blank=True, related_name='users', verbose_name=_("Direction"))
    employee            = models.OneToOneField('Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='user_profile', verbose_name=_("Employé"))
    employee_identifier = models.CharField(max_length=50, null=True, blank=True, verbose_name=_("ID Employé"))
    phone               = models.CharField(max_length=20, blank=True, verbose_name=_("Téléphone"))
    avatar              = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name=_("Photo"))
    is_active_profile   = models.BooleanField(default=True, verbose_name=_("Profil actif"))
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Profil utilisateur")
        verbose_name_plural = _("Profils utilisateurs")

    def __str__(self):
        role_name = self.role.name if self.role else "Sans rôle"
        return f"{self.user.get_full_name() or self.user.username} - {role_name}"

    def get_initials(self):
        if self.user.first_name and self.user.last_name:
            return f"{self.user.first_name[0]}{self.user.last_name[0]}".upper()
        return self.user.username[:2].upper()

    @property
    def role_slug(self):
        return self.role.slug if self.role else None

    def get_project_membership(self, project):
        """Trouve le ProjectMember lié à cet utilisateur pour un projet donné."""
        if not self.employee_id:
            return None
        return project.members.filter(employee_id=self.employee_id).first()

    # ------------------------------------------------------------------
    # Point d'entrée CASL
    # ------------------------------------------------------------------
    def can(self, action, subject, instance=None):
        from .ability import Ability
        return Ability(self.user).can(action, subject, instance)

    # ------------------------------------------------------------------
    # Wrappers de rôle — utilisés dans les templates et l'affichage
    # Ne pas utiliser pour des décisions de sécurité : préférer .can()
    # ------------------------------------------------------------------
    def is_admin(self):
        return self.role_slug == 'admin' or self.user.is_superuser

    def is_directeur_general(self):
        return self.role_slug in ['admin', 'directeur_general'] or self.user.is_superuser

    def is_directeur(self):
        return self.role_slug in ['admin', 'directeur_general', 'directeur'] or self.user.is_superuser

    def is_chef_projet(self):
        return self.role_slug in ['admin', 'directeur_general', 'directeur', 'chef_projet']

    # ------------------------------------------------------------------
    # Helpers de permission (avec ou sans condition)
    # ------------------------------------------------------------------
    def _has_permission(self, action, subject):
        """Vérifie si le profil possède au moins une règle (action, subject)
        avec ou sans condition. Utile pour les widgets qui ne ciblent pas
        une instance précise mais veulent savoir si l'utilisateur a un accès
        scopé à un type d'objet."""
        from .ability import Ability
        ab = Ability(self.user)
        for rule in ab.rules:
            r_action  = rule.get('action')       if isinstance(rule, dict) else rule.action
            r_subject = rule.get('subject')      if isinstance(rule, dict) else rule.subject
            if r_action in (action, 'manage') and r_subject in (subject, 'all'):
                return True
        return False

    # ------------------------------------------------------------------
    # Wrappers fonctionnels — délèguent à Ability
    # Conservés pour compatibilité avec les vues existantes
    # ------------------------------------------------------------------

    # Budget
    def can_view_budgets(self):
        return self._has_permission('read', 'Budget') or self._has_permission('manage', 'Budget')

    def can_manage_budgets(self):
        return self.can('manage', 'Budget')

    def can_view_all_budget_directions(self):
        from .ability import Ability
        ab = Ability(self.user)
        for rule in ab.rules:
            action  = rule.get('action')       if isinstance(rule, dict) else rule.action
            subject = rule.get('subject')      if isinstance(rule, dict) else rule.subject
            cond    = rule.get('condition','') if isinstance(rule, dict) else rule.condition
            if action in ('read', 'manage') and subject in ('Budget', 'all') and not cond:
                return True
        return False

    # Utilisateurs
    def has_manage_users_permission(self):
        return self.can('manage', 'User')

    def can_manage_users(self):
        return self.can('manage', 'User')

    # Demandes
    def has_approve_requests_permission(self):
        return self.can('approve', 'Request')

    def can_approve_requests(self):
        return self.can('approve', 'Request')

    # Événements
    def has_create_events_permission(self):
        return self.can('manage', 'Event')

    def can_manage_events(self):
        return self.can('manage', 'Event')

    def can_read_events(self):
        return self.can('read', 'Event') or self.can('manage', 'Event')

    # Rapports
    def can_view_reports(self):
        return self.can('read', 'Report')

    # Partenaires
    def can_manage_partners(self):
        return self.can('manage', 'Partner')

    def can_read_partners(self):
        return self.can('read', 'Partner') or self.can('manage', 'Partner')

    # Documents
    def can_approve_documents(self):
        return self.can('approve', 'Document')

    # Projets — globaux
    def can_create_projects(self):
        return self.can('create', 'Project')

    def can_manage_projects(self):
        return self.can('read', 'Project') or self.can('manage', 'Project')

    def can_view_all_projects(self):
        """Permission globale de voir tous les projets (sans condition de direction/appartenance)."""
        from .ability import Ability
        ab = Ability(self.user)
        for rule in ab.rules:
            action  = rule.get('action')       if isinstance(rule, dict) else rule.action
            subject = rule.get('subject')      if isinstance(rule, dict) else rule.subject
            cond    = rule.get('condition','') if isinstance(rule, dict) else rule.condition
            if action in ('read', 'manage') and subject in ('Project', 'all') and not cond:
                return True
        return False

    # Projets — niveau instance
    def can_view_project(self, project):
        from .ability import Ability
        return Ability(self.user).can_view_project(project)

    def can_edit_project(self, project):
        from .ability import Ability
        return Ability(self.user).can_edit_project(project)

    def can_add_project_milestones(self, project):
        from .ability import Ability
        return Ability(self.user).can_add_project_milestones(project)

    def can_edit_project_milestones(self, project):
        from .ability import Ability
        return Ability(self.user).can_edit_project_milestones(project)

    def can_add_project_documents(self, project):
        from .ability import Ability
        return Ability(self.user).can_add_project_documents(project)

    def can_edit_project_documents(self, project):
        from .ability import Ability
        return Ability(self.user).can_edit_project_documents(project)

    def can_add_project_needs(self, project):
        from .ability import Ability
        return Ability(self.user).can_add_project_needs(project)

    def can_add_project_comments(self, project):
        from .ability import Ability
        return Ability(self.user).can_add_project_comments(project)

    def can_add_project_members(self, project):
        from .ability import Ability
        return Ability(self.user).can_manage_project_members(project)

    def can_manage_project_members(self, project):
        from .ability import Ability
        return Ability(self.user).can_manage_project_members(project)

    def can_perform_actions_as_member(self, project):
        from .ability import Ability
        return not Ability(self.user).is_project_readonly(project)

    def is_project_readonly(self, project):
        from .ability import Ability
        return Ability(self.user).is_project_readonly(project)

    # Congés
    def can_give_final_approval(self):
        return self.can('manage', 'LeaveRequest')

    def is_hr(self):
        from .ability import Ability
        ab = Ability(self.user)
        for rule in ab.rules:
            action  = rule.get('action')       if isinstance(rule, dict) else rule.action
            subject = rule.get('subject')      if isinstance(rule, dict) else rule.subject
            cond    = rule.get('condition','') if isinstance(rule, dict) else rule.condition
            if action in ('approve', 'manage') and subject in ('LeaveRequest', 'all') and cond == 'hr_pipeline':
                return True
        return False

    def can_give_hr_check(self):
        return self.is_hr() or self.can_give_final_approval()

    def can_give_manager_approval(self, leave_request=None):
        if self.can_give_final_approval():
            return True
        if leave_request is not None:
            return self.can('approve', 'LeaveRequest', leave_request)
        from .ability import Ability
        ab = Ability(self.user)
        for rule in ab.rules:
            action  = rule.get('action')       if isinstance(rule, dict) else rule.action
            subject = rule.get('subject')      if isinstance(rule, dict) else rule.subject
            if action in ('approve', 'manage') and subject in ('LeaveRequest', 'all'):
                return True
        return False

    # Calendrier
    def can_view_calendar(self):
        return self.can('read', 'Event')


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


class Direction(models.Model):
    name = models.CharField(max_length=200, verbose_name=_("Nom"))
    code = models.CharField(max_length=10, unique=True, verbose_name=_("Code"))
    color = models.CharField(max_length=7, default="#3b82f6", verbose_name=_("Couleur"))
    
    class Meta:
        verbose_name = _("Direction")
        verbose_name_plural = _("Directions")
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Project(models.Model):
    STATUS_CHOICES = [
        ('planifie', _('Planifié')),
        ('en_cours', _('En cours')),
        ('suspendu', _('Suspendu')),
        ('termine', _('Terminé')),
        ('en_retard', _('En retard')),
    ]
    PRIORITY_CHOICES = [
        ('basse', _('Basse')),
        ('moyenne', _('Moyenne')),
        ('haute', _('Haute')),
    ]
    
    name = models.CharField(max_length=200, verbose_name=_("Nom du projet"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    direction = models.ForeignKey(Direction, on_delete=models.SET_NULL, null=True, blank=True, related_name='projects', verbose_name=_("Direction"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planifie', verbose_name=_("Statut"))
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='moyenne', verbose_name=_("Priorité"))
    progress = models.IntegerField(default=0, verbose_name=_("Progression (%)"))
    budget = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name=_("Budget alloué"))
    budget_consumed = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name=_("Budget consommé"))
    currency = models.CharField(max_length=3, default='GNF', verbose_name=_("Devise"))
    start_date = models.DateField(verbose_name=_("Date de début"))
    end_date = models.DateField(verbose_name=_("Date de fin"))
    original_start_date = models.DateField(null=True, blank=True, editable=False, verbose_name=_("Date de début originale"))
    original_end_date = models.DateField(null=True, blank=True, editable=False, verbose_name=_("Date de fin originale"))
    manager = models.CharField(max_length=100, verbose_name=_("Responsable"))
    manager_employee = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_projects', verbose_name=_("Responsable (lié)"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Projet")
        verbose_name_plural = _("Projets")
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Sauvegarde les dates originales lors de la première création"""
        if not self.pk:  # Si c'est une nouvelle création
            self.original_start_date = self.start_date
            self.original_end_date = self.end_date
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': _("La date de fin doit être postérieure ou égale à la date de début.")
            })

    @property
    def computed_status(self):
        """Retourne 'en_retard' si la date est dépassée et le projet non terminé, sinon le statut stocké."""
        from datetime import date
        if self.status != 'termine' and self.end_date and self.end_date < date.today():
            return 'en_retard'
        return self.status

    def recalculate_progress(self, save=True):
        """Recalcule la progression basée sur toutes les sous-étapes de tous les jalons"""
        milestones = list(self.milestones.prefetch_related('sub_milestones').all())
        total_milestones = len(milestones)
        
        if total_milestones <= 0:
            new_progress = 0
        else:
            total_progress = 0
            for milestone in milestones:
                subs = list(milestone.sub_milestones.all())
                sub_count = len(subs)
                if sub_count > 0:
                    completed_subs = sum(1 for s in subs if s.completed)
                    milestone_progress = (completed_subs / sub_count) * 100
                else:
                    if milestone.completed:
                        milestone_progress = 100
                    else:
                        milestone_progress = milestone.manual_progress
                total_progress += milestone_progress
            new_progress = round(total_progress / total_milestones)

        new_progress = max(0, min(100, int(new_progress)))

        if self.progress == new_progress:
            return self.progress

        self.progress = new_progress
        if save:
            self.save(update_fields=['progress', 'updated_at'])
        return self.progress
    
    @property
    def budget_percentage(self):
        if self.budget > 0:
            return round((float(self.budget_consumed) / float(self.budget)) * 100, 1)
        return 0


class ProjectMember(models.Model):
    """Membres d'un projet — le rôle et ses permissions sont portés par ProjectRole."""

    project      = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='members', verbose_name=_("Projet"))
    employee     = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='project_memberships', verbose_name=_("Employé"))
    project_role = models.ForeignKey(ProjectRole, on_delete=models.SET_NULL, null=True, blank=True, related_name='memberships', verbose_name=_("Rôle projet"))
    joined_at    = models.DateTimeField(auto_now_add=True, verbose_name=_("Date d'ajout"))

    class Meta:
        verbose_name = _("Membre de projet")
        verbose_name_plural = _("Membres de projet")
        unique_together = ['project', 'employee']
        ordering = ['joined_at']

    def __str__(self):
        role_name = self.project_role.name if self.project_role else 'Sans rôle'
        return f"{self.project.name} - {self.employee.name} ({role_name})"

    # ------------------------------------------------------------------
    # Helpers qui délèguent aux permissions du ProjectRole
    # ------------------------------------------------------------------
    def _has_perm(self, action, subject):
        if not self.project_role_id:
            return False
        return self.project_role.permissions.filter(action=action, subject=subject).exists()

    def can_manage_members(self):
        return self._has_perm('manage', _('ProjectMember'))

    def can_edit_project(self):
        return self._has_perm('update', _('Project'))

    def can_add_milestones(self):
        return self._has_perm('create', _('Milestone'))

    def can_update_milestones(self):
        return self._has_perm('update', _('Milestone'))

    def can_add_documents(self):
        return self._has_perm('create', _('Document'))

    def can_update_documents(self):
        return self._has_perm('update', _('Document'))

    def can_add_needs(self):
        return self._has_perm('create', _('Request'))

    def can_add_comments(self):
        return self._has_perm('create', _('Comment'))

    def can_perform_actions(self):
        return any([
            self.can_edit_project(), self.can_add_milestones(), self.can_update_milestones(),
            self.can_add_documents(), self.can_update_documents(),
            self.can_add_needs(), self.can_add_comments(),
        ])

    def is_readonly(self):
        return not self.can_perform_actions()


class Milestone(models.Model):
    TASK_STATUS_CHOICES = [
        ('a_faire', _('À faire')),
        ('en_cours', _('En cours')),
        ('bloque', _('Bloqué')),
        ('en_revision', _('En révision')),
        ('termine', _('Terminé')),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones', verbose_name=_("Projet"))
    name = models.CharField(max_length=200, verbose_name=_("Nom du jalon"))
    assigned_to = models.ManyToManyField('Employee', blank=True, related_name='assigned_milestones', verbose_name=_("Responsables"))
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_milestones_created', verbose_name=_("Attribué par"))
    due_date = models.DateField(null=True, blank=True, verbose_name=_("Date de la tâche"))
    status = models.CharField(max_length=20, choices=TASK_STATUS_CHOICES, default='a_faire', verbose_name=_("Statut"))
    completed = models.BooleanField(default=False, verbose_name=_("Complété"))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Terminé le"))
    need = models.TextField(blank=True, default='', verbose_name=_("Besoin"))
    manual_progress = models.IntegerField(default=0, verbose_name=_("Progression manuelle (%)"))
    order = models.IntegerField(default=0, verbose_name=_("Ordre"))
    
    class Meta:
        verbose_name = _("Jalon")
        verbose_name_plural = _("Jalons")
        ordering = ['order']
    
    def __str__(self):
        return f"{self.project.name} - {self.name}"

    def clean(self):
        super().clean()
        if self.due_date and self.project_id:
            project = self.project
            if project.start_date and project.end_date:
                if self.due_date < project.start_date or self.due_date > project.end_date:
                    raise ValidationError({
                        'due_date': _("La date du jalon doit être comprise entre %(start)s et %(end)s.") % {
                            'start': project.start_date,
                            'end': project.end_date,
                        }
                    })

    @property
    def progress(self):
        """Calcule le pourcentage de progression basé sur les sous-étapes ou la progression manuelle"""
        total = self.sub_milestones.count()
        if total == 0:
            # Pas de sous-étapes : utiliser la progression manuelle
            if self.completed:
                return 100
            return self.manual_progress
        # Avec sous-étapes : calculer automatiquement
        completed = self.sub_milestones.filter(completed=True).count()
        return round((completed / total) * 100)
    
    def save(self, *args, **kwargs):
        """Enforce la cohérence entre completed, status et completed_at avant chaque écriture."""
        from django.utils import timezone
        if self.completed:
            self.status = 'termine'
            if not self.completed_at:
                self.completed_at = timezone.now()
        else:
            if self.status == 'termine':
                self.status = 'en_cours'
            self.completed_at = None
        super().save(*args, **kwargs)

    def update_completion(self):
        """Met à jour completed depuis les sous-étapes ou la progression manuelle."""
        total = self.sub_milestones.count()
        if total > 0:
            done = self.sub_milestones.filter(completed=True).count()
            self.completed = (done == total)
        else:
            self.completed = (self.manual_progress >= 100)
        # save() enforce la cohérence status/completed_at automatiquement
        self.save(update_fields=['completed', 'status', 'completed_at'])


class SubMilestone(models.Model):
    """Sous-étapes d'un jalon"""
    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE, related_name='sub_milestones', verbose_name=_("Jalon parent"))
    name = models.CharField(max_length=200, verbose_name=_("Nom de la sous-étape"))
    assigned_to = models.ManyToManyField('Employee', blank=True, related_name='assigned_sub_milestones', verbose_name=_("Responsables"))
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_sub_milestones_created', verbose_name=_("Attribué par"))
    due_date = models.DateField(null=True, blank=True, verbose_name=_("Date de la sous-tâche"))
    completed = models.BooleanField(default=False, verbose_name=_("Complétée"))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Terminée le"))
    need = models.TextField(blank=True, default='', verbose_name=_("Besoin"))
    order = models.IntegerField(default=0, verbose_name=_("Ordre"))
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Sous-étape")
        verbose_name_plural = _("Sous-étapes")
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return f"{self.milestone.name} - {self.name}"

    def clean(self):
        super().clean()
        if self.due_date and self.milestone_id:
            milestone = self.milestone
            if milestone.due_date and self.due_date > milestone.due_date:
                raise ValidationError({
                    'due_date': _("La date de la sous-étape doit être antérieure ou égale à celle du jalon (%(date)s).") % {
                        'date': milestone.due_date,
                    }
                })
            project = milestone.project
            if project and project.start_date and project.end_date:
                if self.due_date < project.start_date or self.due_date > project.end_date:
                    raise ValidationError({
                        'due_date': _("La date de la sous-étape doit être comprise entre %(start)s et %(end)s.") % {
                            'start': project.start_date,
                            'end': project.end_date,
                        }
                    })

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if self.completed and not self.completed_at:
            self.completed_at = timezone.now()
        elif not self.completed:
            self.completed_at = None
        super().save(*args, **kwargs)


class ProjectNeed(models.Model):
    PRIORITY_CHOICES = [
        ('basse', _('Basse')),
        ('moyenne', _('Moyenne')),
        ('haute', _('Haute')),
    ]
    NEED_STATUS_CHOICES = [
        ('ouvert', _('Ouvert')),
        ('en_cours', _('En cours')),
        ('resolu', _('Résolu')),
        ('rejete', _('Rejeté')),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='needs', verbose_name=_("Projet"))
    title = models.CharField(max_length=200, verbose_name=_("Titre"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='moyenne', verbose_name=_("Priorité"))
    status = models.CharField(max_length=20, choices=NEED_STATUS_CHOICES, default='ouvert', verbose_name=_("Statut"))
    created_by = models.CharField(max_length=100, verbose_name=_("Créé par"))
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.CharField(max_length=100, blank=True, verbose_name=_("Traité par"))
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Traité le"))

    class Meta:
        verbose_name = _("Besoin de projet")
        verbose_name_plural = _("Besoins de projet")
        ordering = ['status', '-created_at']

    def __str__(self):
        return f"{self.project.name} - {self.title}"

    @property
    def is_open(self):
        return self.status in ('ouvert', 'en_cours')


class ProjectComment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='comments', verbose_name=_("Projet"))
    message = models.TextField(verbose_name=_("Commentaire"))
    created_by = models.CharField(max_length=100, verbose_name=_("Créé par"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Commentaire de projet")
        verbose_name_plural = _("Commentaires de projet")
        ordering = ['created_at']

    def __str__(self):
        return f"{self.project.name} - {self.created_by}"


class ProjectActivity(models.Model):
    """Journal d'activité pour suivre toutes les modifications sur un projet"""
    ACTION_CHOICES = [
        ('creation', _('Création')),
        ('modification', _('Modification')),
        ('suppression', _('Suppression')),
        ('ajout_membre', _('Ajout de membre')),
        ('retrait_membre', _('Retrait de membre')),
        ('ajout_jalon', _('Ajout de jalon')),
        ('modif_jalon', _('Modification de jalon')),
        ('suppr_jalon', _('Suppression de jalon')),
        ('ajout_sous_etape', _('Ajout de sous-étape')),
        ('modif_sous_etape', _('Modification de sous-étape')),
        ('suppr_sous_etape', _('Suppression de sous-étape')),
        ('toggle_jalon', _('Changement statut jalon')),
        ('modif_statut_jalon', _('Modification statut jalon')),
        ('toggle_sous_etape', _('Changement statut sous-étape')),
        ('ajout_document', _('Ajout de document')),
        ('suppr_document', _('Suppression de document')),
        ('ajout_dossier', _('Ajout de dossier')),
        ('suppr_dossier', _('Suppression de dossier')),
        ('ajout_besoin', _('Ajout de besoin')),
        ('ajout_commentaire', _('Ajout de commentaire')),
        ('changement_statut', _('Changement de statut')),
        ('changement_progression', _('Changement de progression')),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='activities', verbose_name=_("Projet"))
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, verbose_name=_("Action"))
    description = models.TextField(verbose_name=_("Description"))
    user = models.CharField(max_length=100, verbose_name=_("Utilisateur"))
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Activité de projet")
        verbose_name_plural = _("Activités de projet")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.project.name} - {self.get_action_display()} par {self.user}"


@receiver(post_save, sender=Milestone)
def update_project_progress_on_milestone_save(sender, instance, **kwargs):
    instance.project.recalculate_progress(save=True)


@receiver(post_delete, sender=Milestone)
def update_project_progress_on_milestone_delete(sender, instance, **kwargs):
    instance.project.recalculate_progress(save=True)


@receiver(post_save, sender=SubMilestone)
def update_project_progress_on_sub_milestone_save(sender, instance, **kwargs):
    """Recalcule la progression du projet quand une sous-étape est modifiée"""
    instance.milestone.update_completion()
    instance.milestone.project.recalculate_progress(save=True)


@receiver(post_delete, sender=SubMilestone)
def update_project_progress_on_sub_milestone_delete(sender, instance, **kwargs):
    """Recalcule la progression du projet quand une sous-étape est supprimée"""
    instance.milestone.update_completion()
    instance.milestone.project.recalculate_progress(save=True)


class ProjectFolder(models.Model):
    """Dossier pour organiser les documents d'un projet"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='folders', verbose_name=_("Projet"))
    name = models.CharField(max_length=200, verbose_name=_("Nom du dossier"))
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders', verbose_name=_("Dossier parent"))
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Dossier de projet")
        verbose_name_plural = _("Dossiers de projet")
        ordering = ['name']
    
    def __str__(self):
        return f"{self.project.name} - {self.name}"
    
    @property
    def full_path(self):
        """Retourne le chemin complet du dossier"""
        if self.parent:
            return f"{self.parent.full_path} / {self.name}"
        return self.name


class ProjectDocument(models.Model):
    """Document lié à un projet et stocké dans un dossier"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='project_documents', verbose_name=_("Projet"))
    folder = models.ForeignKey(ProjectFolder, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents', verbose_name=_("Dossier"))
    title = models.CharField(max_length=200, verbose_name=_("Titre"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    file = models.FileField(upload_to='project_documents/', verbose_name=_("Fichier"))
    uploaded_by = models.CharField(max_length=100, verbose_name=_("Uploadé par"))
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Document de projet")
        verbose_name_plural = _("Documents de projet")
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.project.name} - {self.title}"


class Document(models.Model):
    TYPE_CHOICES = [
        ('contrat', _('Contrat')),
        ('budget', _('Budget')),
        ('rapport', _('Rapport')),
        ('note', _('Note')),
    ]
    STATUS_CHOICES = [
        ('a_signer', _('À signer')),
        ('a_valider', _('À valider')),
        ('signe', _('Signé')),
    ]
    PRIORITY_CHOICES = [
        ('basse', _('Basse')),
        ('moyenne', _('Moyenne')),
        ('haute', _('Haute')),
    ]
    
    title = models.CharField(max_length=200, verbose_name=_("Titre"))
    doc_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name=_("Type"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='a_valider', verbose_name=_("Statut"))
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='moyenne', verbose_name=_("Priorité"))
    direction = models.ForeignKey(Direction, on_delete=models.CASCADE, related_name='documents', verbose_name=_("Direction"))
    created_by = models.CharField(max_length=100, verbose_name=_("Créé par"))
    created_at = models.DateField(auto_now_add=True, verbose_name=_("Date de création"))
    due_date = models.DateField(verbose_name=_("Date limite"))
    signed_at = models.DateField(null=True, blank=True, verbose_name=_("Date de signature"))
    file = models.FileField(upload_to='documents/', null=True, blank=True, verbose_name=_("Fichier"))
    
    class Meta:
        verbose_name = _("Document")
        verbose_name_plural = _("Documents")
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.due_date and self.signed_at and self.signed_at > self.due_date:
            raise ValidationError({
                'signed_at': _("La date de signature ne peut pas être postérieure à la date limite.")
            })
        from datetime import date as _date_cls
        creation_ref = self.created_at if self.created_at else _date_cls.today()
        if self.due_date and self.due_date < creation_ref:
            raise ValidationError({
                'due_date': _("La date limite doit être postérieure ou égale à la date de création.")
            })


class Partner(models.Model):
    TYPE_CHOICES = [
        ('entreprise', _('Entreprise')),
        ('universite', _('Université')),
        ('institution', _('Institution')),
        ('ong', _('ONG')),
    ]
    STATUS_CHOICES = [
        ('actif', _('Actif')),
        ('en_discussion', _('En discussion')),
        ('inactif', _('Inactif')),
    ]
    
    name = models.CharField(max_length=200, verbose_name=_("Nom"))
    partner_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name=_("Type"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='en_discussion', verbose_name=_("Statut"))
    contact_person = models.CharField(max_length=100, verbose_name=_("Personne de contact"))
    email = models.EmailField(verbose_name=_("Email"))
    phone = models.CharField(max_length=20, verbose_name=_("Téléphone"))
    start_date = models.DateField(null=True, blank=True, verbose_name=_("Date de début"))
    logo = models.ImageField(upload_to='partners/', null=True, blank=True, verbose_name=_("Logo"))
    
    class Meta:
        verbose_name = _("Partenaire")
        verbose_name_plural = _("Partenaires")
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.start_date:
            from datetime import date
            if self.start_date > date.today():
                raise ValidationError({
                    'start_date': _("La date de début de collaboration ne peut pas être dans le futur.")
                })


class Event(models.Model):
    TYPE_CHOICES = [
        ('reunion', _('Réunion')),
        ('evenement', _('Événement')),
    ]
    
    title = models.CharField(max_length=200, verbose_name=_("Titre"))
    event_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name=_("Type"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    date = models.DateField(verbose_name=_("Date"))
    time = models.TimeField(verbose_name=_("Heure"))
    duration = models.IntegerField(default=60, verbose_name=_("Durée (minutes)"))
    location = models.CharField(max_length=200, blank=True, verbose_name=_("Lieu"))
    participants = models.ManyToManyField(Direction, related_name='events', verbose_name=_("Participants"), blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_events', verbose_name=_("Créé par"))
    created_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name=_("Créé le"))
    updated_at = models.DateTimeField(auto_now=True, null=True, verbose_name=_("Modifié le"))

    class Meta:
        verbose_name = _("Événement")
        verbose_name_plural = _("Événements")
        ordering = ['date', 'time']

    def __str__(self):
        return f"{self.title} - {self.date}"

    def clean(self):
        super().clean()
        if self.duration is not None and self.duration <= 0:
            raise ValidationError({
                'duration': _("La durée doit être positive.")
            })

    def is_past(self):
        from django.utils import timezone
        return self.date < timezone.now().date()

    def is_today(self):
        from django.utils import timezone
        return self.date == timezone.now().date()

    def duration_display(self):
        h, m = divmod(self.duration, 60)
        if h and m:
            return f"{h}h{m:02d}"
        elif h:
            return f"{h}h"
        return f"{m} min"


class EventMember(models.Model):
    STATUS_CHOICES = [
        ('invite',    _('Invité')),
        ('accepte',   _('Accepté')),
        ('refuse',    _('Refusé')),
        ('peut_etre', _('Peut-être')),
    ]

    event        = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='event_members', verbose_name=_("Événement"))
    employee     = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='event_memberships', verbose_name=_("Employé"))
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='invite', verbose_name=_("Statut RSVP"))
    invited_at   = models.DateTimeField(auto_now_add=True, verbose_name=_("Invité le"))
    responded_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Répondu le"))
    note         = models.TextField(blank=True, verbose_name=_("Note"))

    class Meta:
        verbose_name        = _("Membre d'événement")
        verbose_name_plural = _("Membres d'événement")
        unique_together     = ('event', 'employee')
        ordering            = ['employee__name']
        indexes             = [
            models.Index(fields=['event', 'status']),
        ]

    def __str__(self):
        return f"{self.employee.name} — {self.event.title} ({self.get_status_display()})"

    def has_responded(self):
        return self.status != 'invite'


class Request(models.Model):
    STATUS_CHOICES = [
        ('en_attente', _('En attente')),
        ('approuve', _('Approuvé')),
        ('rejete', _('Rejeté')),
    ]
    PRIORITY_CHOICES = [
        ('basse', _('Basse')),
        ('moyenne', _('Moyenne')),
        ('haute', _('Haute')),
    ]
    
    title = models.CharField(max_length=200, verbose_name=_("Titre"))
    description = models.TextField(verbose_name=_("Description"))
    direction = models.ForeignKey(Direction, on_delete=models.CASCADE, related_name='requests', verbose_name=_("Direction"))
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='moyenne', verbose_name=_("Priorité"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='en_attente', verbose_name=_("Statut"))
    created_by = models.CharField(max_length=100, verbose_name=_("Créé par"))
    created_at = models.DateField(auto_now_add=True, verbose_name=_("Date de création"))
    approved_at = models.DateField(null=True, blank=True, verbose_name=_("Date d'approbation"))
    
    class Meta:
        verbose_name = _("Demande")
        verbose_name_plural = _("Demandes")
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.approved_at and self.created_at and self.approved_at < self.created_at:
            raise ValidationError({
                'approved_at': _("La date d'approbation ne peut pas être antérieure à la date de création.")
            })


class Employee(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Nom"))
    direction = models.ForeignKey(Direction, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees', verbose_name=_("Direction"))
    role = models.CharField(max_length=100, verbose_name=_("Rôle / Fonction"))
    phone = models.CharField(max_length=20, blank=True, verbose_name=_("Téléphone"))
    email = models.EmailField(blank=True, verbose_name=_("Email"))
    workload = models.IntegerField(default=0, verbose_name=_("Charge de travail (%)"))
    skills = models.TextField(blank=True, verbose_name=_("Compétences"))
    is_external = models.BooleanField(default=False, verbose_name=_("Personne externe"))
    organization = models.CharField(max_length=150, blank=True, verbose_name=_("Organisation / Entreprise"))
    
    class Meta:
        verbose_name = _("Employé")
        verbose_name_plural = _("Employés")
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_skills_list(self):
        if self.skills:
            return [s.strip() for s in self.skills.split(',')]
        return []


class UserActivity(models.Model):
    """Log des activités utilisateur"""
    ACTION_CHOICES = [
        ('login', _('Connexion')),
        ('logout', _('Déconnexion')),
        ('create', _('Création')),
        ('update', _('Modification')),
        ('delete', _('Suppression')),
        ('view', _('Consultation')),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities', verbose_name=_("Utilisateur"))
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name=_("Action"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name=_("Adresse IP"))
    user_agent = models.TextField(blank=True, verbose_name=_("Navigateur"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Date"))
    
    class Meta:
        verbose_name = _("Activité utilisateur")
        verbose_name_plural = _("Activités utilisateurs")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} - {self.created_at}"


class Budget(models.Model):
    direction = models.ForeignKey(Direction, on_delete=models.SET_NULL, null=True, blank=True, related_name='budgets', verbose_name=_("Direction"))
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name='budget_lines', verbose_name=_("Projet"))
    allocated = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name=_("Budget alloué"))
    consumed = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name=_("Budget consommé"))
    currency = models.CharField(max_length=3, default='GNF', verbose_name=_("Devise"))
    
    class Meta:
        verbose_name = _("Budget")
        verbose_name_plural = _("Budgets")
    
    def __str__(self):
        if self.project:
            return f"Budget {self.project.name}"
        if self.direction:
            return f"Budget {self.direction.code}"
        return "Budget sans affectation"
    
    @property
    def available(self):
        return self.allocated - self.consumed
    
    @property
    def consumption_rate(self):
        if self.allocated > 0:
            return round((float(self.consumed) / float(self.allocated)) * 100, 1)
        return 0


# =====================================================================
# Conges
# =====================================================================

class LeaveRequest(models.Model):
    """Demande de conge - workflow CSIG (Employe -> Hierarchie -> RH -> Direction)."""

    TYPE_CHOICES = [
        ('annuel', _('Congé annuel')),
        ('maladie', _('Congé maladie')),
        ('maternite', _('Congé maternité / paternité')),
        ('exceptionnelle', _('Permission exceptionnelle')),
        ('sans_solde', _('Congé sans solde')),
        ('formation', _('Formation / Mission')),
    ]

    STATUS_CHOICES = [
        ('soumise', _('Soumise - en attente avis hiérarchique')),
        ('avis_favorable', _('Avis hiérarchique favorable - en attente RH')),
        ('avis_defavorable', _('Avis hiérarchique défavorable')),
        ('rh_conforme', _('Vérifiée RH - en attente décision finale')),
        ('rh_non_conforme', _('Non conforme RH')),
        ('approuvee', _('Approuvée')),
        ('rejetee', _('Rejetée')),
        ('annulee', _('Annulée par le demandeur')),
    ]

    DECISION_CHOICES = [
        ('', _('En attente')),
        ('favorable', _('Favorable')),
        ('defavorable', _('Défavorable')),
    ]

    HR_DECISION_CHOICES = [
        ('', _('En attente')),
        ('conforme', _('Conforme')),
        ('non_conforme', _('Non conforme')),
    ]

    FINAL_DECISION_CHOICES = [
        ('', _('En attente')),
        ('approuve', _('Approuvée')),
        ('rejete', _('Rejetée')),
    ]

    # Demandeur
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='leave_requests', verbose_name=_("Employé"))
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leave_requests', verbose_name=_("Utilisateur"))
    direction = models.ForeignKey(Direction, on_delete=models.PROTECT, related_name='leave_requests', verbose_name=_("Direction / Service"))

    # Demande
    leave_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name=_("Type de congé"))
    start_date = models.DateField(verbose_name=_("Date de début"))
    end_date = models.DateField(verbose_name=_("Date de fin"))
    days_count = models.PositiveIntegerField(default=0, verbose_name=_("Nombre de jours"))
    reason = models.TextField(verbose_name=_("Motif"))
    replacement = models.CharField(max_length=200, blank=True, verbose_name=_("Suppléant / agent intérimaire"))
    handover_note = models.TextField(blank=True, verbose_name=_("Note de passation"))

    # Justificatif principal
    justification = models.FileField(upload_to='leaves/', null=True, blank=True, verbose_name=_("Justificatif"))

    # Statut global
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='soumise', verbose_name=_("Statut"))

    # Etape 1 : superieur hierarchique (48h)
    manager_decision = models.CharField(max_length=15, choices=DECISION_CHOICES, blank=True, default='', verbose_name=_("Avis hiérarchique"))
    manager_comment = models.TextField(blank=True, verbose_name=_("Observations hiérarchie"))
    manager_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leaves_managed', verbose_name=_("Validé par (hiérarchie)"))
    manager_decision_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Date avis hiérarchique"))

    # Etape 2 : RH (72h)
    hr_decision = models.CharField(max_length=15, choices=HR_DECISION_CHOICES, blank=True, default='', verbose_name=_("Vérification RH"))
    hr_comment = models.TextField(blank=True, verbose_name=_("Observations RH"))
    hr_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leaves_hr', verbose_name=_("Vérifié par (RH)"))
    hr_decision_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Date vérification RH"))

    # Etape 3 : Direction Generale / Coordination (decision finale)
    final_decision = models.CharField(max_length=15, choices=FINAL_DECISION_CHOICES, blank=True, default='', verbose_name=_("Décision finale"))
    final_comment = models.TextField(blank=True, verbose_name=_("Observations Direction"))
    final_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leaves_final', verbose_name=_("Décidé par (Direction)"))
    final_decision_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Date décision finale"))

    # Meta
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Soumise le"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Demande de congé")
        verbose_name_plural = _("Demandes de congé")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.name} - {self.get_leave_type_display()} ({self.start_date} -> {self.end_date})"

    # ---- helpers ----------------------------------------------------------
    def compute_days(self):
        """Nombre de jours calendaires inclusifs."""
        if not (self.start_date and self.end_date):
            return 0
        delta = (self.end_date - self.start_date).days + 1
        return max(delta, 0)

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date and not self.days_count:
            self.days_count = self.compute_days()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': _("La date de fin doit être postérieure ou égale à la date de début.")
            })
        if self.start_date and self.leave_type == 'annuel':
            from django.utils import timezone
            min_delay = (self.start_date - timezone.now().date()).days
            if min_delay < 15:
                raise ValidationError({
                    'start_date': _("Un congé annuel doit être demandé au moins 15 jours avant le départ.")
                })

    @property
    def is_pending(self):
        return self.status in ['soumise', 'avis_favorable', 'rh_conforme']

    @property
    def is_finalized(self):
        return self.status in ['approuvee', 'rejetee', 'annulee', 'avis_defavorable', 'rh_non_conforme']

    @property
    def status_color(self):
        return {
            'soumise': '#f59e0b',
            'avis_favorable': '#3b82f6',
            'avis_defavorable': '#ef4444',
            'rh_conforme': '#6366f1',
            'rh_non_conforme': '#ef4444',
            'approuvee': '#16a34a',
            'rejetee': '#ef4444',
            'annulee': '#6b7280',
        }.get(self.status, '#6b7280')

    @property
    def current_step_label(self):
        from django.utils.translation import gettext as _gt
        return {
            'soumise':          _gt('1/3 - Avis hiérarchique'),
            'avis_favorable':   _gt('2/3 - Vérification RH'),
            'rh_conforme':      _gt('3/3 - Décision Direction'),
            'approuvee':        _gt('Terminé - Approuvée'),
            'rejetee':          _gt('Terminé - Rejetée'),
            'avis_defavorable': _gt('Terminé - Refus hiérarchique'),
            'rh_non_conforme':  _gt('Terminé - Non conforme RH'),
            'annulee':          _gt('Annulée'),
        }.get(self.status, self.get_status_display())


class Notification(models.Model):
    """Notification in-app pour un utilisateur."""

    TYPE_CHOICES = [
        ('jalon_complete',      _('Jalon complété')),
        ('sous_etape_complete', _('Sous-étape complétée')),
        ('membre_projet',       _('Ajout comme membre de projet')),
        ('commentaire',         _('Nouveau commentaire')),
        ('conge_avis',          _('Avis hiérarchique congé')),
        ('conge_rh',            _('Vérification RH congé')),
        ('conge_decision',      _('Décision finale congé')),
        ('event_invite',        _('Invitation à un événement')),
        ('event_update',        _('Événement modifié')),
        ('event_cancel',        _('Événement annulé')),
        ('event_rsvp',          _('Réponse à une invitation')),
    ]

    receiver    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications_received', verbose_name=_("Destinataire"))
    notif_type  = models.CharField(max_length=30, choices=TYPE_CHOICES, verbose_name=_("Type"))
    title       = models.CharField(max_length=200, verbose_name=_("Titre"))
    message     = models.TextField(blank=True, verbose_name=_("Message"))
    link        = models.CharField(max_length=500, blank=True, verbose_name=_("Lien"))
    is_read     = models.BooleanField(default=False, verbose_name=_("Lu"))
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notif_type}] {self.title} → {self.receiver}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])


class LeaveDocument(models.Model):
    """Piece jointe supplementaire pour une demande de conge."""
    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, related_name='documents', verbose_name=_("Demande"))
    file = models.FileField(upload_to='leaves/docs/', verbose_name=_("Fichier"))
    label = models.CharField(max_length=200, blank=True, verbose_name=_("Libellé"))
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Document de congé")
        verbose_name_plural = _("Documents de congé")
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.label or self.file.name
