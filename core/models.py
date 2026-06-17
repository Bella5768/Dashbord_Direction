from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


# =====================================================================
# RBAC : Permission / Role / ProjectRole
# =====================================================================

class Permission(models.Model):
    ACTION_CHOICES = [
        ('read',    'Lire'),
        ('create',  'Créer'),
        ('update',  'Modifier'),
        ('delete',  'Supprimer'),
        ('manage',  'Gérer (tout)'),
        ('approve', 'Approuver'),
        ('export',  'Exporter'),
    ]
    SUBJECT_CHOICES = [
        ('all',           'Tout'),
        ('Project',       'Projets'),
        ('Milestone',     'Jalons / Tâches'),
        ('Comment',       'Commentaires projet'),
        ('ProjectMember', 'Membres de projet'),
        ('Budget',        'Budgets'),
        ('User',          'Utilisateurs'),
        ('Employee',      'Employés'),
        ('LeaveRequest',  'Demandes de congé'),
        ('Partner',       'Partenaires'),
        ('Document',      'Documents'),
        ('Request',       'Demandes / Besoins projet'),
        ('Event',         'Événements'),
        ('Direction',     'Directions'),
        ('Role',          'Rôles'),
        ('Report',        'Rapports'),
    ]
    CONDITION_CHOICES = [
        ('',                   'Aucune (accès global)'),
        ('same_direction',     'Même direction'),
        ('is_project_manager', 'Est manager du projet'),
        ('is_project_member',  'Est membre du projet'),
        ('is_owner',           'Est propriétaire'),
        ('hr_pipeline',        'Pipeline RH (après avis hiérarchique)'),
    ]

    action      = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Action")
    subject     = models.CharField(max_length=30, choices=SUBJECT_CHOICES, verbose_name="Sujet")
    condition   = models.CharField(max_length=30, choices=CONDITION_CHOICES, blank=True, default='', verbose_name="Condition")
    description = models.CharField(max_length=200, blank=True, verbose_name="Description")

    class Meta:
        unique_together = ['action', 'subject', 'condition']
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"
        ordering = ['subject', 'action']

    def __str__(self):
        cond = f" [{self.condition}]" if self.condition else ""
        return f"{self.get_action_display()} : {self.get_subject_display()}{cond}"


class Role(models.Model):
    name        = models.CharField(max_length=100, verbose_name="Nom")
    slug        = models.SlugField(max_length=50, unique=True, verbose_name="Identifiant")
    description = models.TextField(blank=True, verbose_name="Description")
    permissions = models.ManyToManyField(Permission, blank=True, related_name='roles', verbose_name="Permissions")
    is_system   = models.BooleanField(default=False, verbose_name="Rôle système (non supprimable)")
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rôle"
        verbose_name_plural = "Rôles"
        ordering = ['name']

    def __str__(self):
        return self.name


class ProjectRole(models.Model):
    name        = models.CharField(max_length=100, verbose_name="Nom")
    slug        = models.SlugField(max_length=50, unique=True, verbose_name="Identifiant")
    description = models.TextField(blank=True, verbose_name="Description")
    permissions = models.ManyToManyField(Permission, blank=True, related_name='project_roles', verbose_name="Permissions projet")
    is_system   = models.BooleanField(default=False, verbose_name="Rôle système (non supprimable)")
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rôle projet"
        verbose_name_plural = "Rôles projet"
        ordering = ['name']

    def __str__(self):
        return self.name


# =====================================================================
# Profil utilisateur
# =====================================================================

class UserProfile(models.Model):
    user                = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role                = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='users', verbose_name="Rôle")
    direction           = models.ForeignKey('Direction', on_delete=models.SET_NULL, null=True, blank=True, related_name='users', verbose_name="Direction")
    employee            = models.OneToOneField('Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='user_profile', verbose_name="Employé")
    employee_identifier = models.CharField(max_length=50, null=True, blank=True, verbose_name="ID Employé")
    phone               = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    avatar              = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name="Photo")
    is_active_profile   = models.BooleanField(default=True, verbose_name="Profil actif")
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"

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
    # Wrappers fonctionnels — délèguent à Ability
    # Conservés pour compatibilité avec les vues existantes
    # ------------------------------------------------------------------

    # Budget
    def can_view_budgets(self):
        return self.can('read', 'Budget') or self.can('manage', 'Budget')

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
        return self.can('manage', 'Partner') or self.can('read', 'Partner')

    # Documents
    def can_approve_documents(self):
        return self.can('approve', 'Document')

    # Projets — globaux
    def can_create_projects(self):
        return self.can('create', 'Project')

    def can_manage_projects(self):
        return self.can('read', 'Project') or self.can('manage', 'Project')

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
    name = models.CharField(max_length=200, verbose_name="Nom")
    code = models.CharField(max_length=10, unique=True, verbose_name="Code")
    color = models.CharField(max_length=7, default="#3b82f6", verbose_name="Couleur")
    
    class Meta:
        verbose_name = "Direction"
        verbose_name_plural = "Directions"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Project(models.Model):
    STATUS_CHOICES = [
        ('planifie', 'Planifié'),
        ('en_cours', 'En cours'),
        ('suspendu', 'Suspendu'),
        ('termine', 'Terminé'),
        ('en_retard', 'En retard'),
    ]
    PRIORITY_CHOICES = [
        ('basse', 'Basse'),
        ('moyenne', 'Moyenne'),
        ('haute', 'Haute'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Nom du projet")
    description = models.TextField(blank=True, verbose_name="Description")
    direction = models.ForeignKey(Direction, on_delete=models.SET_NULL, null=True, blank=True, related_name='projects', verbose_name="Direction")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planifie', verbose_name="Statut")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='moyenne', verbose_name="Priorité")
    progress = models.IntegerField(default=0, verbose_name="Progression (%)")
    budget = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Budget alloué")
    budget_consumed = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Budget consommé")
    currency = models.CharField(max_length=3, default='GNF', verbose_name="Devise")
    start_date = models.DateField(verbose_name="Date de début")
    end_date = models.DateField(verbose_name="Date de fin")
    original_start_date = models.DateField(null=True, blank=True, editable=False, verbose_name="Date de début originale")
    original_end_date = models.DateField(null=True, blank=True, editable=False, verbose_name="Date de fin originale")
    manager = models.CharField(max_length=100, verbose_name="Responsable")
    manager_employee = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_projects', verbose_name="Responsable (lié)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Projet"
        verbose_name_plural = "Projets"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Sauvegarde les dates originales lors de la première création"""
        if not self.pk:  # Si c'est une nouvelle création
            self.original_start_date = self.start_date
            self.original_end_date = self.end_date
        super().save(*args, **kwargs)

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

    project      = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='members', verbose_name="Projet")
    employee     = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='project_memberships', verbose_name="Employé")
    project_role = models.ForeignKey(ProjectRole, on_delete=models.SET_NULL, null=True, blank=True, related_name='memberships', verbose_name="Rôle projet")
    joined_at    = models.DateTimeField(auto_now_add=True, verbose_name="Date d'ajout")

    class Meta:
        verbose_name = "Membre de projet"
        verbose_name_plural = "Membres de projet"
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
        return self._has_perm('manage', 'ProjectMember')

    def can_edit_project(self):
        return self._has_perm('update', 'Project')

    def can_add_milestones(self):
        return self._has_perm('create', 'Milestone')

    def can_update_milestones(self):
        return self._has_perm('update', 'Milestone')

    def can_add_documents(self):
        return self._has_perm('create', 'Document')

    def can_update_documents(self):
        return self._has_perm('update', 'Document')

    def can_add_needs(self):
        return self._has_perm('create', 'Request')

    def can_add_comments(self):
        return self._has_perm('create', 'Comment')

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
        ('a_faire', 'À faire'),
        ('en_cours', 'En cours'),
        ('bloque', 'Bloqué'),
        ('en_revision', 'En révision'),
        ('termine', 'Terminé'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones', verbose_name="Projet")
    name = models.CharField(max_length=200, verbose_name="Nom du jalon")
    assigned_to = models.ManyToManyField('Employee', blank=True, related_name='assigned_milestones', verbose_name="Responsables")
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_milestones_created', verbose_name="Attribué par")
    due_date = models.DateField(null=True, blank=True, verbose_name="Date de la tâche")
    status = models.CharField(max_length=20, choices=TASK_STATUS_CHOICES, default='a_faire', verbose_name="Statut")
    completed = models.BooleanField(default=False, verbose_name="Complété")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Terminé le")
    need = models.TextField(blank=True, default='', verbose_name="Besoin")
    manual_progress = models.IntegerField(default=0, verbose_name="Progression manuelle (%)")
    order = models.IntegerField(default=0, verbose_name="Ordre")
    
    class Meta:
        verbose_name = "Jalon"
        verbose_name_plural = "Jalons"
        ordering = ['order']
    
    def __str__(self):
        return f"{self.project.name} - {self.name}"
    
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
    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE, related_name='sub_milestones', verbose_name="Jalon parent")
    name = models.CharField(max_length=200, verbose_name="Nom de la sous-étape")
    assigned_to = models.ManyToManyField('Employee', blank=True, related_name='assigned_sub_milestones', verbose_name="Responsables")
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_sub_milestones_created', verbose_name="Attribué par")
    due_date = models.DateField(null=True, blank=True, verbose_name="Date de la sous-tâche")
    completed = models.BooleanField(default=False, verbose_name="Complétée")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Terminée le")
    need = models.TextField(blank=True, default='', verbose_name="Besoin")
    order = models.IntegerField(default=0, verbose_name="Ordre")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Sous-étape"
        verbose_name_plural = "Sous-étapes"
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return f"{self.milestone.name} - {self.name}"
    
    def save(self, *args, **kwargs):
        from django.utils import timezone
        if self.completed and not self.completed_at:
            self.completed_at = timezone.now()
        elif not self.completed:
            self.completed_at = None
        super().save(*args, **kwargs)


class ProjectNeed(models.Model):
    PRIORITY_CHOICES = [
        ('basse', 'Basse'),
        ('moyenne', 'Moyenne'),
        ('haute', 'Haute'),
    ]
    NEED_STATUS_CHOICES = [
        ('ouvert', 'Ouvert'),
        ('en_cours', 'En cours'),
        ('resolu', 'Résolu'),
        ('rejete', 'Rejeté'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='needs', verbose_name="Projet")
    title = models.CharField(max_length=200, verbose_name="Titre")
    description = models.TextField(blank=True, verbose_name="Description")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='moyenne', verbose_name="Priorité")
    status = models.CharField(max_length=20, choices=NEED_STATUS_CHOICES, default='ouvert', verbose_name="Statut")
    created_by = models.CharField(max_length=100, verbose_name="Créé par")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.CharField(max_length=100, blank=True, verbose_name="Traité par")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Traité le")

    class Meta:
        verbose_name = "Besoin de projet"
        verbose_name_plural = "Besoins de projet"
        ordering = ['status', '-created_at']

    def __str__(self):
        return f"{self.project.name} - {self.title}"

    @property
    def is_open(self):
        return self.status in ('ouvert', 'en_cours')


class ProjectComment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='comments', verbose_name="Projet")
    message = models.TextField(verbose_name="Commentaire")
    created_by = models.CharField(max_length=100, verbose_name="Créé par")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Commentaire de projet"
        verbose_name_plural = "Commentaires de projet"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.project.name} - {self.created_by}"


class ProjectActivity(models.Model):
    """Journal d'activité pour suivre toutes les modifications sur un projet"""
    ACTION_CHOICES = [
        ('creation', 'Création'),
        ('modification', 'Modification'),
        ('suppression', 'Suppression'),
        ('ajout_membre', 'Ajout de membre'),
        ('retrait_membre', 'Retrait de membre'),
        ('ajout_jalon', 'Ajout de jalon'),
        ('modif_jalon', 'Modification de jalon'),
        ('suppr_jalon', 'Suppression de jalon'),
        ('ajout_sous_etape', 'Ajout de sous-étape'),
        ('modif_sous_etape', 'Modification de sous-étape'),
        ('suppr_sous_etape', 'Suppression de sous-étape'),
        ('toggle_jalon',      'Changement statut jalon'),
        ('modif_statut_jalon','Modification statut jalon'),
        ('toggle_sous_etape', 'Changement statut sous-étape'),
        ('ajout_document', 'Ajout de document'),
        ('suppr_document', 'Suppression de document'),
        ('ajout_dossier', 'Ajout de dossier'),
        ('suppr_dossier', 'Suppression de dossier'),
        ('ajout_besoin', 'Ajout de besoin'),
        ('ajout_commentaire', 'Ajout de commentaire'),
        ('changement_statut', 'Changement de statut'),
        ('changement_progression', 'Changement de progression'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='activities', verbose_name="Projet")
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, verbose_name="Action")
    description = models.TextField(verbose_name="Description")
    user = models.CharField(max_length=100, verbose_name="Utilisateur")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Activité de projet"
        verbose_name_plural = "Activités de projet"
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
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='folders', verbose_name="Projet")
    name = models.CharField(max_length=200, verbose_name="Nom du dossier")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders', verbose_name="Dossier parent")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Dossier de projet"
        verbose_name_plural = "Dossiers de projet"
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
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='project_documents', verbose_name="Projet")
    folder = models.ForeignKey(ProjectFolder, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents', verbose_name="Dossier")
    title = models.CharField(max_length=200, verbose_name="Titre")
    description = models.TextField(blank=True, verbose_name="Description")
    file = models.FileField(upload_to='project_documents/', verbose_name="Fichier")
    uploaded_by = models.CharField(max_length=100, verbose_name="Uploadé par")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Document de projet"
        verbose_name_plural = "Documents de projet"
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.project.name} - {self.title}"


class Document(models.Model):
    TYPE_CHOICES = [
        ('contrat', 'Contrat'),
        ('budget', 'Budget'),
        ('rapport', 'Rapport'),
        ('note', 'Note'),
    ]
    STATUS_CHOICES = [
        ('a_signer', 'À signer'),
        ('a_valider', 'À valider'),
        ('signe', 'Signé'),
    ]
    PRIORITY_CHOICES = [
        ('basse', 'Basse'),
        ('moyenne', 'Moyenne'),
        ('haute', 'Haute'),
    ]
    
    title = models.CharField(max_length=200, verbose_name="Titre")
    doc_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Type")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='a_valider', verbose_name="Statut")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='moyenne', verbose_name="Priorité")
    direction = models.ForeignKey(Direction, on_delete=models.CASCADE, related_name='documents', verbose_name="Direction")
    created_by = models.CharField(max_length=100, verbose_name="Créé par")
    created_at = models.DateField(auto_now_add=True, verbose_name="Date de création")
    due_date = models.DateField(verbose_name="Date limite")
    signed_at = models.DateField(null=True, blank=True, verbose_name="Date de signature")
    file = models.FileField(upload_to='documents/', null=True, blank=True, verbose_name="Fichier")
    
    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class Partner(models.Model):
    TYPE_CHOICES = [
        ('entreprise', 'Entreprise'),
        ('universite', 'Université'),
        ('institution', 'Institution'),
        ('ong', 'ONG'),
    ]
    STATUS_CHOICES = [
        ('actif', 'Actif'),
        ('en_discussion', 'En discussion'),
        ('inactif', 'Inactif'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Nom")
    partner_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Type")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='en_discussion', verbose_name="Statut")
    contact_person = models.CharField(max_length=100, verbose_name="Personne de contact")
    email = models.EmailField(verbose_name="Email")
    phone = models.CharField(max_length=20, verbose_name="Téléphone")
    start_date = models.DateField(null=True, blank=True, verbose_name="Date de début")
    logo = models.ImageField(upload_to='partners/', null=True, blank=True, verbose_name="Logo")
    
    class Meta:
        verbose_name = "Partenaire"
        verbose_name_plural = "Partenaires"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Event(models.Model):
    TYPE_CHOICES = [
        ('reunion', 'Réunion'),
        ('evenement', 'Événement'),
        ('deadline', 'Deadline'),
    ]
    
    title = models.CharField(max_length=200, verbose_name="Titre")
    event_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Type")
    description = models.TextField(blank=True, verbose_name="Description")
    date = models.DateField(verbose_name="Date")
    time = models.TimeField(verbose_name="Heure")
    duration = models.IntegerField(default=60, verbose_name="Durée (minutes)")
    location = models.CharField(max_length=200, blank=True, verbose_name="Lieu")
    participants = models.ManyToManyField(Direction, related_name='events', verbose_name="Participants", blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_events', verbose_name="Créé par")
    created_at = models.DateTimeField(null=True, blank=True, auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(null=True, blank=True, auto_now=True, verbose_name="Modifié le")

    class Meta:
        verbose_name = "Événement"
        verbose_name_plural = "Événements"
        ordering = ['date', 'time']

    def __str__(self):
        return f"{self.title} - {self.date}"

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


class Request(models.Model):
    STATUS_CHOICES = [
        ('en_attente', 'En attente'),
        ('approuve', 'Approuvé'),
        ('rejete', 'Rejeté'),
    ]
    PRIORITY_CHOICES = [
        ('basse', 'Basse'),
        ('moyenne', 'Moyenne'),
        ('haute', 'Haute'),
    ]
    
    title = models.CharField(max_length=200, verbose_name="Titre")
    description = models.TextField(verbose_name="Description")
    direction = models.ForeignKey(Direction, on_delete=models.CASCADE, related_name='requests', verbose_name="Direction")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='moyenne', verbose_name="Priorité")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='en_attente', verbose_name="Statut")
    created_by = models.CharField(max_length=100, verbose_name="Créé par")
    created_at = models.DateField(auto_now_add=True, verbose_name="Date de création")
    approved_at = models.DateField(null=True, blank=True, verbose_name="Date d'approbation")
    
    class Meta:
        verbose_name = "Demande"
        verbose_name_plural = "Demandes"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class Employee(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nom")
    direction = models.ForeignKey(Direction, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees', verbose_name="Direction")
    role = models.CharField(max_length=100, verbose_name="Rôle / Fonction")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    workload = models.IntegerField(default=0, verbose_name="Charge de travail (%)")
    skills = models.TextField(blank=True, verbose_name="Compétences")
    is_external = models.BooleanField(default=False, verbose_name="Personne externe")
    organization = models.CharField(max_length=150, blank=True, verbose_name="Organisation / Entreprise")
    
    class Meta:
        verbose_name = "Employé"
        verbose_name_plural = "Employés"
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
        ('login', 'Connexion'),
        ('logout', 'Déconnexion'),
        ('create', 'Création'),
        ('update', 'Modification'),
        ('delete', 'Suppression'),
        ('view', 'Consultation'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities', verbose_name="Utilisateur")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Action")
    description = models.TextField(blank=True, verbose_name="Description")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Adresse IP")
    user_agent = models.TextField(blank=True, verbose_name="Navigateur")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date")
    
    class Meta:
        verbose_name = "Activité utilisateur"
        verbose_name_plural = "Activités utilisateurs"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} - {self.created_at}"


class Budget(models.Model):
    direction = models.ForeignKey(Direction, on_delete=models.SET_NULL, null=True, blank=True, related_name='budgets', verbose_name="Direction")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name='budget_lines', verbose_name="Projet")
    allocated = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Budget alloué")
    consumed = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Budget consommé")
    currency = models.CharField(max_length=3, default='GNF', verbose_name="Devise")
    
    class Meta:
        verbose_name = "Budget"
        verbose_name_plural = "Budgets"
    
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
        ('annuel', 'Congé annuel'),
        ('maladie', 'Congé maladie'),
        ('maternite', 'Congé maternité / paternité'),
        ('exceptionnelle', 'Permission exceptionnelle'),
        ('sans_solde', 'Congé sans solde'),
        ('formation', 'Formation / Mission'),
    ]

    STATUS_CHOICES = [
        ('soumise', 'Soumise - en attente avis hiérarchique'),
        ('avis_favorable', 'Avis hiérarchique favorable - en attente RH'),
        ('avis_defavorable', 'Avis hiérarchique défavorable'),
        ('rh_conforme', 'Vérifiée RH - en attente décision finale'),
        ('rh_non_conforme', 'Non conforme RH'),
        ('approuvee', 'Approuvée'),
        ('rejetee', 'Rejetée'),
        ('annulee', 'Annulée par le demandeur'),
    ]

    DECISION_CHOICES = [
        ('', 'En attente'),
        ('favorable', 'Favorable'),
        ('defavorable', 'Défavorable'),
    ]

    HR_DECISION_CHOICES = [
        ('', 'En attente'),
        ('conforme', 'Conforme'),
        ('non_conforme', 'Non conforme'),
    ]

    FINAL_DECISION_CHOICES = [
        ('', 'En attente'),
        ('approuve', 'Approuvée'),
        ('rejete', 'Rejetée'),
    ]

    # Demandeur
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='leave_requests', verbose_name="Employé")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leave_requests', verbose_name="Utilisateur")
    direction = models.ForeignKey(Direction, on_delete=models.PROTECT, related_name='leave_requests', verbose_name="Direction / Service")

    # Demande
    leave_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Type de congé")
    start_date = models.DateField(verbose_name="Date de début")
    end_date = models.DateField(verbose_name="Date de fin")
    days_count = models.PositiveIntegerField(default=0, verbose_name="Nombre de jours")
    reason = models.TextField(verbose_name="Motif")
    replacement = models.CharField(max_length=200, blank=True, verbose_name="Suppléant / agent intérimaire")
    handover_note = models.TextField(blank=True, verbose_name="Note de passation")

    # Justificatif principal
    justification = models.FileField(upload_to='leaves/', null=True, blank=True, verbose_name="Justificatif")

    # Statut global
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='soumise', verbose_name="Statut")

    # Etape 1 : superieur hierarchique (48h)
    manager_decision = models.CharField(max_length=15, choices=DECISION_CHOICES, blank=True, default='', verbose_name="Avis hiérarchique")
    manager_comment = models.TextField(blank=True, verbose_name="Observations hiérarchie")
    manager_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leaves_managed', verbose_name="Validé par (hiérarchie)")
    manager_decision_at = models.DateTimeField(null=True, blank=True, verbose_name="Date avis hiérarchique")

    # Etape 2 : RH (72h)
    hr_decision = models.CharField(max_length=15, choices=HR_DECISION_CHOICES, blank=True, default='', verbose_name="Vérification RH")
    hr_comment = models.TextField(blank=True, verbose_name="Observations RH")
    hr_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leaves_hr', verbose_name="Vérifié par (RH)")
    hr_decision_at = models.DateTimeField(null=True, blank=True, verbose_name="Date vérification RH")

    # Etape 3 : Direction Generale / Coordination (decision finale)
    final_decision = models.CharField(max_length=15, choices=FINAL_DECISION_CHOICES, blank=True, default='', verbose_name="Décision finale")
    final_comment = models.TextField(blank=True, verbose_name="Observations Direction")
    final_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leaves_final', verbose_name="Décidé par (Direction)")
    final_decision_at = models.DateTimeField(null=True, blank=True, verbose_name="Date décision finale")

    # Meta
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Soumise le")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Demande de congé"
        verbose_name_plural = "Demandes de congé"
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
        return {
            'soumise': '1/3 - Avis hiérarchique',
            'avis_favorable': '2/3 - Vérification RH',
            'rh_conforme': '3/3 - Décision Direction',
            'approuvee': 'Terminé - Approuvée',
            'rejetee': 'Terminé - Rejetée',
            'avis_defavorable': 'Terminé - Refus hiérarchique',
            'rh_non_conforme': 'Terminé - Non conforme RH',
            'annulee': 'Annulée',
        }.get(self.status, self.get_status_display())


class LeaveDocument(models.Model):
    """Piece jointe supplementaire pour une demande de conge."""
    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, related_name='documents', verbose_name="Demande")
    file = models.FileField(upload_to='leaves/docs/', verbose_name="Fichier")
    label = models.CharField(max_length=200, blank=True, verbose_name="Libellé")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Document de congé"
        verbose_name_plural = "Documents de congé"
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.label or self.file.name
