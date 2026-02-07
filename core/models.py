from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


class UserProfile(models.Model):
    """Extended user profile with role-based access control."""
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('directeur_general', 'Directeur Général'),
        ('directeur', 'Directeur'),
        ('chef_projet', 'Chef de Projet'),
        ('employe', 'Employé'),
        ('visiteur', 'Visiteur'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='visiteur', verbose_name="Rôle")
    direction = models.ForeignKey('Direction', on_delete=models.SET_NULL, null=True, blank=True, 
                                  related_name='users', verbose_name="Direction")
    employee = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='user_profiles', verbose_name="Employé")
    employee_identifier = models.CharField(max_length=50, null=True, blank=True, verbose_name="ID Employé")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name="Photo")
    is_active_profile = models.BooleanField(default=True, verbose_name="Profil actif")

    # Permissions budgets
    budget_view = models.BooleanField(default=False, verbose_name="Peut voir les budgets")
    budget_manage = models.BooleanField(default=False, verbose_name="Peut gérer les budgets")
    budget_view_all_directions = models.BooleanField(default=False, verbose_name="Peut voir les budgets de toutes les directions")
    
    # Permissions projets
    can_create_project = models.BooleanField(default=False, verbose_name="Peut créer des projets")
    can_edit_projects = models.BooleanField(default=False, verbose_name="Peut modifier les projets")
    can_add_milestones = models.BooleanField(default=False, verbose_name="Peut ajouter des jalons")
    can_add_members = models.BooleanField(default=False, verbose_name="Peut ajouter des membres")
    
    # Permissions utilisateurs et demandes
    can_manage_users = models.BooleanField(default=False, verbose_name="Peut gérer les utilisateurs")
    can_approve_requests = models.BooleanField(default=False, verbose_name="Peut approuver les demandes")
    
    # Permissions événements
    can_create_events = models.BooleanField(default=False, verbose_name="Peut créer des événements")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_role_display()}"
    
    def get_initials(self):
        if self.user.first_name and self.user.last_name:
            return f"{self.user.first_name[0]}{self.user.last_name[0]}".upper()
        return self.user.username[:2].upper()
    
    def get_project_membership(self, project):
        """Trouve le ProjectMember lié à cet utilisateur pour un projet donné"""
        # 1. Chercher par le lien direct employee du profil
        if self.employee_id:
            membership = project.members.filter(employee_id=self.employee_id).first()
            if membership:
                return membership
        # 2. Fallback par nom
        user_name = self.user.get_full_name() or self.user.username
        return project.members.filter(employee__name=user_name).first()

    # Permission methods
    def is_admin(self):
        return self.role == 'admin'
    
    def is_directeur_general(self):
        return self.role in ['admin', 'directeur_general']
    
    def is_directeur(self):
        return self.role in ['admin', 'directeur_general', 'directeur']
    
    def is_chef_projet(self):
        return self.role in ['admin', 'directeur_general', 'directeur', 'chef_projet']
    
    def is_employe(self):
        return self.role == 'employe'
    
    def is_visiteur(self):
        return self.role == 'visiteur'
    
    def has_manage_users_permission(self):
        """Admin et DG peuvent gérer les utilisateurs, ou permission explicite"""
        return self.role in ['admin', 'directeur_general'] or self.can_manage_users
    
    def can_manage_budgets(self):
        """Admin, DG et Directeur peuvent gérer les budgets, ou permission explicite"""
        return self.role in ['admin', 'directeur_general', 'directeur'] or self.budget_manage

    def can_view_budgets(self):
        return self.can_manage_budgets() or self.budget_view

    def can_view_all_budget_directions(self):
        return self.is_directeur() or self.budget_view_all_directions
    
    def can_approve_documents(self):
        return self.role in ['admin', 'directeur_general', 'directeur']
    
    def has_approve_requests_permission(self):
        """Admin et DG peuvent approuver les demandes, ou permission explicite"""
        return self.role in ['admin', 'directeur_general'] or self.can_approve_requests
    
    def can_create_projects(self):
        """Admin, DG et Directeur peuvent créer des projets, ou permission explicite"""
        return self.role in ['admin', 'directeur_general', 'directeur'] or self.can_create_project
    
    def can_manage_projects(self):
        """Admin, DG, Directeur et Chef de projet peuvent gérer les projets"""
        return self.role in ['admin', 'directeur_general', 'directeur', 'chef_projet']
    
    def can_add_project_members(self, project):
        """Vérifie si l'utilisateur peut ajouter des membres à un projet"""
        # Permission explicite
        if self.can_add_members:
            if self.direction and self.direction == project.direction:
                return True
        # Rôles par défaut
        if self.role in ['admin', 'directeur_general']:
            return True
        if self.role == 'directeur' and self.direction == project.direction:
            return True
        if self.role == 'chef_projet' and project.manager:
            user_name = self.user.get_full_name() or self.user.username
            if user_name in project.manager:
                return True
        # Vérifier les permissions de membre
        membership = self.get_project_membership(project)
        if membership and membership.can_manage_members():
            return True
        return False
    
    def can_perform_actions_as_member(self, project):
        """Vérifie si l'utilisateur peut effectuer des actions sur un projet en tant que membre"""
        # Admin, DG, Directeur peuvent toujours agir
        if self.role in ['admin', 'directeur_general']:
            return True
        if self.role == 'directeur' and self.direction == project.direction:
            return True
        if self.role == 'chef_projet':
            user_name = self.user.get_full_name() or self.user.username
            if project.manager and user_name in project.manager:
                return True
        
        # Vérifier les permissions de membre
        membership = self.get_project_membership(project)
        if membership:
            return membership.can_perform_actions()
        
        return False
    
    def can_manage_project_members(self, project):
        """Vérifie si l'utilisateur peut gérer les membres d'un projet (ajouter/supprimer)"""
        # Admin, DG peuvent toujours gérer
        if self.role in ['admin', 'directeur_general']:
            return True
        if self.role == 'directeur' and self.direction == project.direction:
            return True
        # Chef de projet principal peut gérer
        if self.role == 'chef_projet' and project.manager:
            user_name = self.user.get_full_name() or self.user.username
            if user_name in project.manager:
                return True
        # Vérifier les permissions de membre
        membership = self.get_project_membership(project)
        if membership and membership.can_manage_members():
            return True
        return False
    
    def is_project_readonly(self, project):
        """Vérifie si l'utilisateur est en lecture seule sur ce projet"""
        # Admin, DG, Directeur ne sont jamais en readonly
        if self.role in ['admin', 'directeur_general']:
            return False
        if self.role == 'directeur' and self.direction == project.direction:
            return False
        # Vérifier si c'est un chef de projet
        if self.role == 'chef_projet':
            user_name = self.user.get_full_name() or self.user.username
            if project.manager and user_name in project.manager:
                return False
        # Vérifier les droits de membre
        membership = self.get_project_membership(project)
        if membership:
            return membership.is_readonly()
        return True
    
    def can_add_project_milestones(self, project):
        """Vérifie si l'utilisateur peut ajouter des jalons à un projet"""
        # Permission explicite du profil
        if self.can_add_milestones:
            if self.direction and self.direction == project.direction:
                return True
        # Admin, DG, Directeur
        if self.role in ['admin', 'directeur_general']:
            return True
        if self.role == 'directeur' and self.direction == project.direction:
            return True
        # Chef de projet principal
        if self.role == 'chef_projet' and project.manager:
            user_name = self.user.get_full_name() or self.user.username
            if user_name in project.manager:
                return True
        # Vérifier les permissions de membre (y compris custom)
        membership = self.get_project_membership(project)
        if membership and membership.can_add_milestones():
            return True
        return False
    
    def can_add_project_documents(self, project):
        """Vérifie si l'utilisateur peut ajouter des documents à un projet"""
        # Admin, DG, Directeur
        if self.role in ['admin', 'directeur_general']:
            return True
        if self.role == 'directeur' and self.direction == project.direction:
            return True
        # Chef de projet principal
        if self.role == 'chef_projet' and project.manager:
            user_name = self.user.get_full_name() or self.user.username
            if user_name in project.manager:
                return True
        # Vérifier les permissions de membre (y compris custom)
        membership = self.get_project_membership(project)
        if membership and membership.can_add_documents():
            return True
        return False
    
    def can_edit_project(self, project):
        """Vérifie si l'utilisateur peut modifier le projet"""
        # Admin, DG, Directeur peuvent toujours modifier
        if self.role in ['admin', 'directeur_general']:
            return True
        if self.role == 'directeur' and self.direction == project.direction:
            return True
        # Chef de projet principal peut modifier
        if self.role == 'chef_projet' and project.manager:
            user_name = self.user.get_full_name() or self.user.username
            if user_name in project.manager:
                return True
        # Vérifier les permissions de membre
        membership = self.get_project_membership(project)
        if membership and membership.can_edit_project():
            return True
        return False
    
    def can_view_project(self, project):
        """Vérifie si l'utilisateur peut voir un projet"""
        if self.role in ['admin', 'directeur_general']:
            return True
        if self.role == 'directeur' and self.direction == project.direction:
            return True
        if self.role in ['chef_projet', 'employe']:
            user_name = self.user.get_full_name() or self.user.username
            if project.manager and user_name in project.manager:
                return True
        # Vérifier si l'utilisateur est membre du projet
        membership = self.get_project_membership(project)
        if membership:
            return True
        return False
    
    def can_view_reports(self):
        return self.role in ['admin', 'directeur_general', 'directeur', 'chef_projet']
    
    def can_manage_partners(self):
        return self.role in ['admin', 'directeur_general', 'directeur']
    
    def can_view_calendar(self):
        """Tous sauf visiteur peuvent voir le calendrier"""
        return self.role != 'visiteur'
    
    def has_create_events_permission(self):
        """Admin, DG, Directeur peuvent créer des événements, ou permission explicite"""
        return self.role in ['admin', 'directeur_general', 'directeur'] or self.can_create_events


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
    direction = models.ForeignKey(Direction, on_delete=models.CASCADE, related_name='projects', verbose_name="Direction")
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

    def recalculate_progress(self, save=True):
        """Recalcule la progression basée sur toutes les sous-étapes de tous les jalons"""
        milestones = self.milestones.all()
        total_milestones = milestones.count()
        
        if total_milestones <= 0:
            new_progress = 0
        else:
            # Calculer la progression totale en tenant compte de chaque jalon
            total_progress = 0
            for milestone in milestones:
                sub_count = milestone.sub_milestones.count()
                if sub_count > 0:
                    # Si le jalon a des sous-étapes, calculer sa progression partielle
                    completed_subs = milestone.sub_milestones.filter(completed=True).count()
                    milestone_progress = (completed_subs / sub_count) * 100
                else:
                    # Si pas de sous-étapes, utiliser la progression manuelle du jalon
                    if milestone.completed:
                        milestone_progress = 100
                    else:
                        milestone_progress = milestone.manual_progress
                total_progress += milestone_progress
            
            # Moyenne de la progression de tous les jalons
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
    """Membres d'un projet"""
    ROLE_CHOICES = [
        ('responsable', 'Responsable'),
        ('membre', 'Membre'),
        ('observateur', 'Observateur'),
        ('ressource_externe_observateur', 'Ressource externe (observateur)'),
        ('ressource_externe_edit', 'Ressource externe (éditeur)'),
        ('custom', 'Personnalisé'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='members', verbose_name="Projet")
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='project_memberships', verbose_name="Employé")
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='membre', verbose_name="Rôle")
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'ajout")
    
    # Permissions individuelles
    can_manage_members_perm = models.BooleanField(default=False, verbose_name="Gérer les membres")
    can_edit_project_perm = models.BooleanField(default=False, verbose_name="Modifier le projet")
    can_add_milestones_perm = models.BooleanField(default=False, verbose_name="Ajouter des jalons")
    can_add_documents_perm = models.BooleanField(default=False, verbose_name="Ajouter des documents")
    can_add_needs_perm = models.BooleanField(default=False, verbose_name="Ajouter des besoins")
    can_add_comments_perm = models.BooleanField(default=False, verbose_name="Ajouter des commentaires")
    
    class Meta:
        verbose_name = "Membre de projet"
        verbose_name_plural = "Membres de projet"
        unique_together = ['project', 'employee']
        ordering = ['role', 'joined_at']
    
    def __str__(self):
        role_display = self.get_role_display() if self.role else 'Sans rôle'
        return f"{self.project.name} - {self.employee.name} ({role_display})"
    
    def can_perform_actions(self):
        """Vérifie si le membre peut effectuer des actions sur le projet (autre que lecture)"""
        if self.role == 'custom':
            return any([self.can_add_milestones_perm, self.can_add_documents_perm, 
                       self.can_add_needs_perm, self.can_add_comments_perm])
        return self.role in ['responsable', 'membre', 'ressource_externe_edit']

    def can_manage_members(self):
        """Vérifie si le membre peut gérer les autres membres"""
        if self.role == 'custom':
            return self.can_manage_members_perm
        return self.role == 'responsable'

    def can_edit_project(self):
        """Vérifie si le membre peut modifier le projet"""
        if self.role == 'custom':
            return self.can_edit_project_perm
        return self.role in ['responsable', 'ressource_externe_edit']

    def can_add_milestones(self):
        """Vérifie si le membre peut ajouter/modifier des jalons"""
        if self.role == 'custom':
            return self.can_add_milestones_perm
        return self.role in ['responsable', 'membre', 'ressource_externe_edit']

    def can_add_documents(self):
        """Vérifie si le membre peut ajouter des documents"""
        if self.role == 'custom':
            return self.can_add_documents_perm
        return self.role in ['responsable', 'membre', 'ressource_externe_edit']
    
    def can_add_needs(self):
        """Vérifie si le membre peut ajouter des besoins"""
        if self.role == 'custom':
            return self.can_add_needs_perm
        return self.role in ['responsable', 'membre', 'ressource_externe_edit']
    
    def can_add_comments(self):
        """Vérifie si le membre peut ajouter des commentaires"""
        if self.role == 'custom':
            return self.can_add_comments_perm
        return self.role in ['responsable', 'membre', 'ressource_externe_edit']

    def is_readonly(self):
        """Vérifie si le membre est en lecture seule"""
        if self.role == 'custom':
            return not any([self.can_manage_members_perm, self.can_edit_project_perm, 
                           self.can_add_milestones_perm, self.can_add_documents_perm,
                           self.can_add_needs_perm, self.can_add_comments_perm])
        return self.role in ['observateur', 'ressource_externe_observateur']


class Milestone(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones', verbose_name="Projet")
    name = models.CharField(max_length=200, verbose_name="Nom du jalon")
    assigned_to = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_milestones', verbose_name="Responsable")
    completed = models.BooleanField(default=False, verbose_name="Complété")
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
    
    def update_completion(self):
        """Met à jour le statut complété basé sur les sous-étapes ou la progression manuelle"""
        total = self.sub_milestones.count()
        if total > 0:
            completed = self.sub_milestones.filter(completed=True).count()
            self.completed = (completed == total)
        else:
            # Sans sous-étapes : complété si progression manuelle = 100%
            self.completed = (self.manual_progress >= 100)
        self.save(update_fields=['completed'])


class SubMilestone(models.Model):
    """Sous-étapes d'un jalon"""
    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE, related_name='sub_milestones', verbose_name="Jalon parent")
    name = models.CharField(max_length=200, verbose_name="Nom de la sous-étape")
    assigned_to = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_sub_milestones', verbose_name="Responsable")
    completed = models.BooleanField(default=False, verbose_name="Complétée")
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
        super().save(*args, **kwargs)
        self.milestone.update_completion()
        self.milestone.project.recalculate_progress()


class ProjectNeed(models.Model):
    PRIORITY_CHOICES = [
        ('basse', 'Basse'),
        ('moyenne', 'Moyenne'),
        ('haute', 'Haute'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='needs', verbose_name="Projet")
    title = models.CharField(max_length=200, verbose_name="Titre")
    description = models.TextField(blank=True, verbose_name="Description")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='moyenne', verbose_name="Priorité")
    created_by = models.CharField(max_length=100, verbose_name="Créé par")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Besoin de projet"
        verbose_name_plural = "Besoins de projet"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.project.name} - {self.title}"


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
    participants = models.ManyToManyField(Direction, related_name='events', verbose_name="Participants")
    
    class Meta:
        verbose_name = "Événement"
        verbose_name_plural = "Événements"
        ordering = ['date', 'time']
    
    def __str__(self):
        return f"{self.title} - {self.date}"


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
    direction = models.ForeignKey(Direction, on_delete=models.CASCADE, related_name='employees', verbose_name="Direction")
    role = models.CharField(max_length=100, verbose_name="Rôle")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    workload = models.IntegerField(default=0, verbose_name="Charge de travail (%)")
    skills = models.TextField(blank=True, verbose_name="Compétences")
    
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
    direction = models.OneToOneField(Direction, on_delete=models.CASCADE, related_name='budget', verbose_name="Direction")
    allocated = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Budget alloué")
    consumed = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Budget consommé")
    currency = models.CharField(max_length=3, default='GNF', verbose_name="Devise")
    
    class Meta:
        verbose_name = "Budget"
        verbose_name_plural = "Budgets"
    
    def __str__(self):
        return f"Budget {self.direction.code}"
    
    @property
    def available(self):
        return self.allocated - self.consumed
    
    @property
    def consumption_rate(self):
        if self.allocated > 0:
            return round((float(self.consumed) / float(self.allocated)) * 100, 1)
        return 0
