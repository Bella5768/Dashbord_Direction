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
    phone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name="Photo")
    is_active_profile = models.BooleanField(default=True, verbose_name="Profil actif")

    budget_view = models.BooleanField(default=False, verbose_name="Peut voir les budgets")
    budget_manage = models.BooleanField(default=False, verbose_name="Peut gérer les budgets")
    budget_view_all_directions = models.BooleanField(default=False, verbose_name="Peut voir les budgets de toutes les directions")

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
    
    # Permission methods
    def is_admin(self):
        return self.role == 'admin'
    
    def is_directeur_general(self):
        return self.role in ['admin', 'directeur_general']
    
    def is_directeur(self):
        return self.role in ['admin', 'directeur_general', 'directeur']
    
    def is_chef_projet(self):
        return self.role in ['admin', 'directeur_general', 'directeur', 'chef_projet']
    
    def can_manage_users(self):
        return self.role in ['admin', 'directeur_general']
    
    def can_manage_budgets(self):
        return self.role in ['admin', 'directeur_general', 'directeur'] or self.budget_manage

    def can_view_budgets(self):
        return self.can_manage_budgets() or self.budget_view

    def can_view_all_budget_directions(self):
        return self.is_directeur() or self.budget_view_all_directions
    
    def can_approve_documents(self):
        return self.role in ['admin', 'directeur_general', 'directeur']
    
    def can_approve_requests(self):
        return self.role in ['admin', 'directeur_general']
    
    def can_manage_projects(self):
        return self.role in ['admin', 'directeur_general', 'directeur', 'chef_projet']
    
    def can_view_reports(self):
        return self.role in ['admin', 'directeur_general', 'directeur', 'chef_projet']
    
    def can_manage_partners(self):
        return self.role in ['admin', 'directeur_general', 'directeur']


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
    start_date = models.DateField(verbose_name="Date de début")
    end_date = models.DateField(verbose_name="Date de fin")
    manager = models.CharField(max_length=100, verbose_name="Responsable")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Projet"
        verbose_name_plural = "Projets"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name

    def recalculate_progress(self, save=True):
        total = self.milestones.count()
        if total <= 0:
            new_progress = 0
        else:
            completed = self.milestones.filter(completed=True).count()
            new_progress = round((completed / total) * 100)

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
        ('personne_ressource', 'Personne ressource'),
        ('ressource_externe', 'Ressource externe'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='members', verbose_name="Projet")
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='project_memberships', verbose_name="Employé")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='membre', verbose_name="Rôle")
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'ajout")
    
    class Meta:
        verbose_name = "Membre de projet"
        verbose_name_plural = "Membres de projet"
        unique_together = ['project', 'employee']
        ordering = ['role', 'joined_at']
    
    def __str__(self):
        return f"{self.project.name} - {self.employee.name} ({self.get_role_display})"


class Milestone(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones', verbose_name="Projet")
    name = models.CharField(max_length=200, verbose_name="Nom du jalon")
    assigned_to = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_milestones', verbose_name="Responsable")
    completed = models.BooleanField(default=False, verbose_name="Complété")
    order = models.IntegerField(default=0, verbose_name="Ordre")
    
    class Meta:
        verbose_name = "Jalon"
        verbose_name_plural = "Jalons"
        ordering = ['order']
    
    def __str__(self):
        return f"{self.project.name} - {self.name}"


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


@receiver(post_save, sender=Milestone)
def update_project_progress_on_milestone_save(sender, instance, **kwargs):
    instance.project.recalculate_progress(save=True)


@receiver(post_delete, sender=Milestone)
def update_project_progress_on_milestone_delete(sender, instance, **kwargs):
    instance.project.recalculate_progress(save=True)


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
