"""
Data migration : seeds de base.

- Directions (code/name)
- Permissions globales + permissions projet
- Rôles globaux (Role) et rôles projet (ProjectRole)

Fusion des anciennes migrations 0010, 0036, 0037 et 0039, adaptées à une
base neuve (schéma UUID) : pas de migration d'utilisateurs (base vide).
"""
from django.db import migrations
from django.utils.text import slugify


class UniqueSlugMixin:
    """Reproduit la génération de slug du modèle SluggableModel."""

    @staticmethod
    def make_slug(model, value):
        base = (slugify(value) or 'item')[:170]
        candidate = base
        n = 1
        while model.objects.filter(slug=candidate).exists():
            n += 1
            candidate = f"{base}-{n}"
        return candidate


# ---------------------------------------------------------------------------
# Directions
# ---------------------------------------------------------------------------
DIRECTIONS = [
    {'code': 'APPTECH', 'name': "Direction d'appui technique"},
    {'code': 'DG', 'name': 'Direction Générale'},
    {'code': 'SEC', 'name': 'Secrétariat'},
    {'code': 'SANTE', 'name': 'Direction Santé'},
    {'code': 'INNOV', 'name': 'Comité Innovation'},
    {'code': 'STRAT', 'name': 'Comité Stratégique'},
    {'code': 'LABO', 'name': 'Comité laboratoire'},
    {'code': 'FIN', 'name': 'Comité Finances'},
    {'code': 'NUMCLD', 'name': "Centre d'expertise_Numerique/cloud"},
    {'code': 'COPIL', 'name': 'Comité COPIL'},
    {'code': 'INFRA', 'name': 'Comité Infrastructures'},
    {'code': 'STAFF', 'name': 'Comité Staff'},
]

# ---------------------------------------------------------------------------
# Permissions globales
# ---------------------------------------------------------------------------
PERMISSIONS = [
    # (action, subject, condition, description)
    # --- Tout (admin) ---
    ('manage', 'all',          '', 'Accès total'),
    # --- Projets ---
    ('read',   'Project',      '', 'Voir tous les projets'),
    ('read',   'Project',      'same_direction',     'Voir les projets de sa direction'),
    ('read',   'Project',      'is_project_member',  'Voir les projets dont on est membre'),
    ('create', 'Project',      '', 'Créer un projet'),
    ('update', 'Project',      '', 'Modifier tout projet'),
    ('update', 'Project',      'same_direction',     'Modifier les projets de sa direction'),
    ('update', 'Project',      'is_project_manager', 'Modifier ses projets (manager)'),
    ('delete', 'Project',      '', 'Supprimer un projet'),
    # --- Jalons ---
    ('create', 'Milestone',    '', 'Ajouter des jalons à tout projet'),
    ('create', 'Milestone',    'same_direction',     'Ajouter des jalons (même direction)'),
    ('create', 'Milestone',    'is_project_manager', 'Ajouter des jalons (manager du projet)'),
    ('create', 'Milestone',    'is_project_member',  'Ajouter des jalons (membre du projet)'),
    ('update', 'Milestone',    '', 'Modifier tout jalon'),
    ('update', 'Milestone',    'is_project_manager', 'Modifier les jalons (manager)'),
    ('update', 'Milestone',    'is_project_member',  'Modifier les jalons (membre)'),
    ('delete', 'Milestone',    '', 'Supprimer un jalon'),
    # --- Membres projet (global) ---
    ('manage', 'ProjectMember','', 'Gérer les membres de tout projet'),
    ('manage', 'ProjectMember','same_direction',     'Gérer les membres (même direction)'),
    ('manage', 'ProjectMember','is_project_manager', 'Gérer les membres (manager)'),
    # --- Budget ---
    ('read',   'Budget',       '', 'Voir tous les budgets'),
    ('read',   'Budget',       'same_direction',     'Voir les budgets de sa direction'),
    ('manage', 'Budget',       '', 'Gérer tous les budgets'),
    ('manage', 'Budget',       'same_direction',     'Gérer les budgets de sa direction'),
    # --- Utilisateurs ---
    ('read',   'User',         '', 'Voir la liste des utilisateurs'),
    ('manage', 'User',         '', 'Gérer les utilisateurs'),
    # --- Employés ---
    ('read',   'Employee',     '', 'Voir les employés'),
    ('manage', 'Employee',     '', 'Gérer les employés'),
    # --- Congés ---
    ('read',   'LeaveRequest', 'is_owner',      'Voir ses propres demandes de congé'),
    ('create', 'LeaveRequest', 'is_owner',      'Soumettre une demande de congé'),
    ('read',   'LeaveRequest', 'same_direction','Voir les congés de sa direction'),
    ('approve','LeaveRequest', 'same_direction','Donner l\'avis hiérarchique (même direction)'),
    ('approve','LeaveRequest', 'hr_pipeline',   'Vérification RH des congés'),
    ('manage', 'LeaveRequest', '',              'Approbation finale des congés'),
    # --- Documents ---
    ('read',   'Document',     '', 'Voir les documents'),
    ('manage', 'Document',     '', 'Gérer les documents'),
    ('approve','Document',     '', 'Approuver / signer les documents'),
    # --- Partenaires ---
    ('read',   'Partner',      '', 'Voir les partenaires'),
    ('manage', 'Partner',      '', 'Gérer les partenaires'),
    # --- Demandes ---
    ('read',   'Request',      '', 'Voir les demandes'),
    ('approve','Request',      '', 'Approuver les demandes'),
    # --- Événements ---
    ('read',   'Event',        '', 'Voir le calendrier'),
    ('manage', 'Event',        '', 'Créer des événements'),
    # --- Rapports ---
    ('read',   'Report',       '', 'Voir les rapports'),
    # --- Directions ---
    ('manage', 'Direction',    '', 'Gérer les directions'),
    # --- Rôles ---
    ('manage', 'Role',         '', 'Gérer les rôles et permissions'),
    # --- Export ---
    ('export', 'Employee',     '', 'Exporter les employés (PDF)'),
    ('export', 'Project',      '', 'Exporter les activités projet'),
]

# ---------------------------------------------------------------------------
# Permissions projet (scope ProjectRole)
# ---------------------------------------------------------------------------
PROJECT_PERMISSIONS = [
    ('update', 'Project',      '', 'Modifier le projet'),
    ('manage', 'ProjectMember','', 'Gérer les membres du projet'),
    ('create', 'Milestone',    '', 'Ajouter des jalons'),
    ('update', 'Milestone',    '', 'Modifier des jalons'),
    ('create', 'Document',     '', 'Ajouter des documents'),
    ('create', 'Request',      '', 'Ajouter des besoins'),
    ('create', 'Comment',      '', 'Commenter'),
    ('read',   'Project',      '', 'Voir le projet (lecture seule)'),
]

# ---------------------------------------------------------------------------
# Rôles globaux et leurs permissions
# ---------------------------------------------------------------------------
ROLES = [
    {
        'name': 'Administrateur',
        'slug': 'admin',
        'description': 'Accès total au système.',
        'is_system': True,
        'permissions': [('manage', 'all', '')],
    },
    {
        'name': 'Directeur Général',
        'slug': 'directeur_general',
        'description': 'Direction générale de l\'organisation.',
        'is_system': True,
        'permissions': [
            ('read',   'Project',       ''),
            ('create', 'Project',       ''),
            ('update', 'Project',       ''),
            ('delete', 'Project',       ''),
            ('manage', 'ProjectMember', ''),
            ('create', 'Milestone',     ''),
            ('update', 'Milestone',     ''),
            ('delete', 'Milestone',     ''),
            ('read',   'Budget',        ''),
            ('manage', 'Budget',        ''),
            ('read',   'User',          ''),
            ('manage', 'User',          ''),
            ('read',   'Employee',      ''),
            ('manage', 'Employee',      ''),
            ('read',   'LeaveRequest',  'is_owner'),
            ('create', 'LeaveRequest',  'is_owner'),
            ('manage', 'LeaveRequest',  ''),
            ('read',   'Document',      ''),
            ('manage', 'Document',      ''),
            ('approve','Document',      ''),
            ('read',   'Partner',       ''),
            ('manage', 'Partner',       ''),
            ('read',   'Request',       ''),
            ('approve','Request',       ''),
            ('read',   'Event',         ''),
            ('manage', 'Event',         ''),
            ('read',   'Report',        ''),
            ('manage', 'Direction',     ''),
            ('manage', 'Role',          ''),
            ('export', 'Employee',      ''),
            ('export', 'Project',       ''),
        ],
    },
    {
        'name': 'Directeur',
        'slug': 'directeur',
        'description': 'Directeur d\'une direction.',
        'is_system': True,
        'permissions': [
            ('read',   'Project',       'same_direction'),
            ('update', 'Project',       'same_direction'),
            ('create', 'Project',       ''),
            ('manage', 'ProjectMember', 'same_direction'),
            ('create', 'Milestone',     'same_direction'),
            ('update', 'Milestone',     'same_direction'),
            ('read',   'Budget',        'same_direction'),
            ('manage', 'Budget',        'same_direction'),
            ('read',   'User',          ''),
            ('read',   'Employee',      ''),
            ('manage', 'Employee',      ''),
            ('read',   'LeaveRequest',  'is_owner'),
            ('create', 'LeaveRequest',  'is_owner'),
            ('read',   'LeaveRequest',  'same_direction'),
            ('approve','LeaveRequest',  'same_direction'),
            ('read',   'Document',      ''),
            ('manage', 'Document',      ''),
            ('approve','Document',      ''),
            ('read',   'Partner',       ''),
            ('manage', 'Partner',       ''),
            ('read',   'Request',       ''),
            ('approve','Request',       ''),
            ('read',   'Event',         ''),
            ('manage', 'Event',         ''),
            ('read',   'Report',        ''),
            ('export', 'Employee',      ''),
            ('export', 'Project',       ''),
        ],
    },
    {
        'name': 'Chef de Projet',
        'slug': 'chef_projet',
        'description': 'Responsable de projets.',
        'is_system': True,
        'permissions': [
            ('read',   'Project',       'is_project_member'),
            ('create', 'Project',       ''),
            ('update', 'Project',       'is_project_manager'),
            ('manage', 'ProjectMember', 'is_project_manager'),
            ('create', 'Milestone',     'is_project_manager'),
            ('update', 'Milestone',     'is_project_manager'),
            ('create', 'Milestone',     'is_project_member'),
            ('read',   'Budget',        'same_direction'),
            ('read',   'Employee',      ''),
            ('read',   'LeaveRequest',  'is_owner'),
            ('create', 'LeaveRequest',  'is_owner'),
            ('read',   'Document',      ''),
            ('read',   'Partner',       ''),
            ('read',   'Request',       ''),
            ('read',   'Event',         ''),
            ('manage', 'Event',         ''),
            ('read',   'Report',        ''),
            ('export', 'Project',       ''),
        ],
    },
    {
        'name': 'Employé',
        'slug': 'employe',
        'description': 'Employé standard.',
        'is_system': True,
        'permissions': [
            ('read',   'Project',       'is_project_member'),
            ('create', 'Milestone',     'is_project_member'),
            ('update', 'Milestone',     'is_project_member'),
            ('read',   'Employee',      ''),
            ('read',   'LeaveRequest',  'is_owner'),
            ('create', 'LeaveRequest',  'is_owner'),
            ('read',   'Event',         ''),
        ],
    },
    {
        'name': 'Visiteur',
        'slug': 'visiteur',
        'description': 'Accès en lecture seule au calendrier.',
        'is_system': True,
        'permissions': [
            ('read',   'Event',         ''),
        ],
    },
]

# ---------------------------------------------------------------------------
# Rôles projet et leurs permissions
# ---------------------------------------------------------------------------
PROJECT_ROLES = [
    {
        'name': 'Responsable',
        'slug': 'responsable',
        'description': 'Responsable du projet — accès complet.',
        'is_system': True,
        'permissions': [
            ('update', 'Project',       ''),
            ('manage', 'ProjectMember', ''),
            ('create', 'Milestone',     ''),
            ('update', 'Milestone',     ''),
            ('create', 'Document',      ''),
            ('create', 'Request',       ''),
            ('create', 'Comment',       ''),
        ],
    },
    {
        'name': 'Membre',
        'slug': 'membre',
        'description': 'Membre actif du projet.',
        'is_system': True,
        'permissions': [
            ('create', 'Milestone',     ''),
            ('update', 'Milestone',     ''),
            ('create', 'Document',      ''),
            ('create', 'Request',       ''),
            ('create', 'Comment',       ''),
        ],
    },
    {
        'name': 'Observateur',
        'slug': 'observateur',
        'description': 'Lecture seule sur le projet.',
        'is_system': True,
        'permissions': [
            ('read',   'Project',       ''),
        ],
    },
    {
        'name': 'Ressource externe (éditeur)',
        'slug': 'ressource_externe_edit',
        'description': 'Externe avec droits d\'édition.',
        'is_system': True,
        'permissions': [
            ('update', 'Project',       ''),
            ('create', 'Milestone',     ''),
            ('update', 'Milestone',     ''),
            ('create', 'Document',      ''),
            ('create', 'Request',       ''),
            ('create', 'Comment',       ''),
        ],
    },
    {
        'name': 'Ressource externe (observateur)',
        'slug': 'ressource_externe_observateur',
        'description': 'Externe en lecture seule.',
        'is_system': True,
        'permissions': [
            ('read',   'Project',       ''),
        ],
    },
]

# Rôles projet devant recevoir aussi update:Document (ex-0039)
ROLES_WITH_UPDATE_DOC = ['responsable', 'membre', 'ressource_externe_edit']


def seed_forward(apps, schema_editor):
    Permission  = apps.get_model('core', 'Permission')
    Role        = apps.get_model('core', 'Role')
    ProjectRole = apps.get_model('core', 'ProjectRole')
    Direction   = apps.get_model('core', 'Direction')

    # Directions
    for item in DIRECTIONS:
        obj, created = Direction.objects.get_or_create(
            code=item['code'],
            defaults={'name': item['name']},
        )
        if created and not obj.slug:
            obj.slug = UniqueSlugMixin.make_slug(Direction, obj.code or obj.name)
            obj.save(update_fields=['slug'])

    # Permissions globales
    perm_cache = {}
    for action, subject, condition, description in PERMISSIONS:
        p, _ = Permission.objects.get_or_create(
            action=action, subject=subject, condition=condition,
            defaults={'description': description},
        )
        perm_cache[(action, subject, condition)] = p

    # Permissions projet (chevauchées)
    for action, subject, condition, description in PROJECT_PERMISSIONS:
        key = (action, subject, condition)
        if key not in perm_cache:
            p, _ = Permission.objects.get_or_create(
                action=action, subject=subject, condition=condition,
                defaults={'description': description},
            )
            perm_cache[key] = p

    # Rôles globaux
    for role_data in ROLES:
        role, _ = Role.objects.get_or_create(
            slug=role_data['slug'],
            defaults={
                'name':        role_data['name'],
                'description': role_data['description'],
                'is_system':   role_data['is_system'],
            },
        )
        for action, subject, condition in role_data['permissions']:
            perm = perm_cache.get((action, subject, condition))
            if perm:
                role.permissions.add(perm)

    # Rôles projet
    for pr_data in PROJECT_ROLES:
        pr, _ = ProjectRole.objects.get_or_create(
            slug=pr_data['slug'],
            defaults={
                'name':        pr_data['name'],
                'description': pr_data['description'],
                'is_system':   pr_data['is_system'],
            },
        )
        for action, subject, condition in pr_data['permissions']:
            perm = perm_cache.get((action, subject, condition))
            if perm:
                pr.permissions.add(perm)

    # update:Document sur les rôles « éditeurs » (ex-0039)
    try:
        update_doc = Permission.objects.get(action='update', subject='Document', condition='')
    except Permission.DoesNotExist:
        update_doc, _ = Permission.objects.get_or_create(
            action='update', subject='Document', condition='',
            defaults={'description': 'Modifier les documents du projet'},
        )
    for slug in ROLES_WITH_UPDATE_DOC:
        try:
            role = ProjectRole.objects.get(slug=slug)
            role.permissions.add(update_doc)
        except ProjectRole.DoesNotExist:
            pass


def seed_backward(apps, schema_editor):
    Role        = apps.get_model('core', 'Role')
    ProjectRole = apps.get_model('core', 'ProjectRole')
    Permission  = apps.get_model('core', 'Permission')
    Direction   = apps.get_model('core', 'Direction')
    Role.objects.all().delete()
    ProjectRole.objects.all().delete()
    Permission.objects.all().delete()
    Direction.objects.filter(code__in=[d['code'] for d in DIRECTIONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_backward),
    ]