"""
Data migration : réconcilie les permissions des rôles systèmes « Direction ».

Contexte : la seed 0002 prévoit pour chaque rôle système un ensemble de
permissions (voir ROLES dans 0002_seed_directions_rbac). Deux écueils ont été
constatés sur les bases déjà en place :

- `update Milestone same_direction` était référencé dans ROLES['directeur']
  mais absent de la liste PERMISSIONS : le garde `if perm:` le sautait
  silencieusement ;
- les bases héritées de seeds antérieurs peuvent manquer d'autres permissions
  (ex. `manage ProjectMember same_direction`) : le directeur ne peut alors pas
  agir sur les projets / jalons / membres de sa direction ;
- les permissions « besoins » et « commentaires » projet
  (`create Request`, `create Comment`, variantes cancondition) ont été ajoutées
  au plan pour le directeur (same_direction), le directeur général (global) et
  le chef de projet (is_project_manager) : les bases existantes doivent les
  recevoir.

Cette migration garantit que les rôles systèmes concernés reçoivent bien TOUT
l'ensemble prévu (additif uniquement, rien n'est retiré). Idempotente pour les
bases neuves comme existantes.

Les ensembles cibles sont ceux déclarés dans 0002_seed_directions_rbac.ROLES
pour les slugs 'directeur', 'directeur_general' et 'chef_projet'.
"""
from django.db import migrations

# (action, subject, condition) — ensemble prévu pour le rôle « directeur »
SYNC_DIRECTEUR_PERMISSIONS = [
    ('read',    'Project',       'same_direction'),
    ('update',  'Project',       'same_direction'),
    ('create',  'Project',       ''),
    ('manage',  'ProjectMember', 'same_direction'),
    ('create',  'Milestone',     'same_direction'),
    ('update',  'Milestone',     'same_direction'),
    ('read',    'Budget',        'same_direction'),
    ('manage',  'Budget',        'same_direction'),
    ('read',    'User',          ''),
    ('read',    'Employee',      ''),
    ('manage',  'Employee',      ''),
    ('read',    'LeaveRequest',  'is_owner'),
    ('create',  'LeaveRequest',  'is_owner'),
    ('read',    'LeaveRequest',  'same_direction'),
    ('approve', 'LeaveRequest',  'same_direction'),
    ('read',    'Document',      ''),
    ('manage',  'Document',      ''),
    ('approve', 'Document',      ''),
    ('read',    'Partner',       ''),
    ('manage',  'Partner',       ''),
    ('read',    'Request',       ''),
    ('create',  'Request',       'same_direction'),
    ('create',  'Comment',       'same_direction'),
    ('approve', 'Request',       ''),
    ('read',    'Event',         ''),
    ('manage',  'Event',         ''),
    ('read',    'Report',        ''),
    ('export',  'Employee',      ''),
    ('export',  'Project',       ''),
]

# Ensemble prévu pour le rôle « directeur_general »
SYNC_DIRECTEUR_GENERAL_PERMISSIONS = [
    ('read',    'Project',       ''),
    ('create',  'Project',       ''),
    ('update',  'Project',       ''),
    ('delete',  'Project',       ''),
    ('manage',  'ProjectMember', ''),
    ('create',  'Milestone',     ''),
    ('update',  'Milestone',     ''),
    ('delete',  'Milestone',     ''),
    ('read',    'Budget',        ''),
    ('manage',  'Budget',        ''),
    ('read',    'User',          ''),
    ('manage',  'User',          ''),
    ('read',    'Employee',      ''),
    ('manage',  'Employee',      ''),
    ('read',    'LeaveRequest',  'is_owner'),
    ('create',  'LeaveRequest',  'is_owner'),
    ('manage',  'LeaveRequest',  ''),
    ('read',    'Document',      ''),
    ('manage',  'Document',      ''),
    ('approve', 'Document',      ''),
    ('read',    'Partner',       ''),
    ('manage',  'Partner',       ''),
    ('read',    'Request',       ''),
    ('create',  'Request',       ''),
    ('create',  'Comment',       ''),
    ('approve', 'Request',       ''),
    ('read',    'Event',         ''),
    ('manage',  'Event',         ''),
    ('read',    'Report',        ''),
    ('manage',  'Direction',     ''),
    ('manage',  'Role',          ''),
    ('export',  'Employee',      ''),
    ('export',  'Project',       ''),
]

# Ensemble prévu pour le rôle « chef_projet »
SYNC_CHEF_PROJET_PERMISSIONS = [
    ('read',    'Project',       'is_project_member'),
    ('create',  'Project',       ''),
    ('update',  'Project',       'is_project_manager'),
    ('manage',  'ProjectMember', 'is_project_manager'),
    ('create',  'Milestone',     'is_project_manager'),
    ('update',  'Milestone',     'is_project_manager'),
    ('create',  'Milestone',     'is_project_member'),
    ('read',    'Budget',        'same_direction'),
    ('read',    'Employee',      ''),
    ('read',    'LeaveRequest',  'is_owner'),
    ('create',  'LeaveRequest',  'is_owner'),
    ('read',    'Document',      ''),
    ('read',    'Partner',       ''),
    ('read',    'Request',       ''),
    ('create',  'Request',       'is_project_manager'),
    ('create',  'Comment',       'is_project_manager'),
    ('read',    'Event',         ''),
    ('manage',  'Event',         ''),
    ('read',    'Report',        ''),
    ('export',  'Project',       ''),
]

SYNC_ROLES = {
    'directeur': SYNC_DIRECTEUR_PERMISSIONS,
    'directeur_general': SYNC_DIRECTEUR_GENERAL_PERMISSIONS,
    'chef_projet': SYNC_CHEF_PROJET_PERMISSIONS,
}

_DESCRIPTIONS = {
    ('read', 'Project', 'same_direction'): 'Voir les projets de sa direction',
    ('update', 'Project', 'same_direction'): 'Modifier les projets de sa direction',
    ('create', 'Project', ''): 'Créer un projet',
    ('manage', 'ProjectMember', 'same_direction'): 'Gérer les membres (même direction)',
    ('create', 'Milestone', 'same_direction'): 'Ajouter des jalons (même direction)',
    ('update', 'Milestone', 'same_direction'): 'Modifier les jalons (même direction)',
    ('read', 'Budget', 'same_direction'): 'Voir les budgets de sa direction',
    ('manage', 'Budget', 'same_direction'): 'Gérer les budgets de sa direction',
    ('read', 'User', ''): 'Voir la liste des utilisateurs',
    ('read', 'Employee', ''): 'Voir les employés',
    ('manage', 'Employee', ''): 'Gérer les employés',
    ('read', 'LeaveRequest', 'is_owner'): 'Voir ses propres demandes de congé',
    ('create', 'LeaveRequest', 'is_owner'): 'Soumettre une demande de congé',
    ('read', 'LeaveRequest', 'same_direction'): 'Voir les congés de sa direction',
    ('approve', 'LeaveRequest', 'same_direction'): "Donner l'avis hiérarchique (même direction)",
    ('read', 'Document', ''): 'Voir les documents',
    ('manage', 'Document', ''): 'Gérer les documents',
    ('approve', 'Document', ''): 'Approuver / signer les documents',
    ('read', 'Partner', ''): 'Voir les partenaires',
    ('manage', 'Partner', ''): 'Gérer les partenaires',
    ('read', 'Request', ''): 'Voir les demandes',
    ('create', 'Request', 'same_direction'): 'Ajouter des besoins (même direction)',
    ('create', 'Request', 'is_project_manager'): 'Ajouter des besoins (manager du projet)',
    ('create', 'Comment', 'same_direction'): 'Commenter (même direction)',
    ('create', 'Comment', 'is_project_manager'): 'Commenter (manager du projet)',
    ('create', 'Request', ''): 'Ajouter des besoins à tout projet',
    ('create', 'Comment', ''): 'Commenter sur tout projet',
    ('approve', 'Request', ''): 'Approuver les demandes',
    ('read', 'Event', ''): 'Voir le calendrier',
    ('manage', 'Event', ''): 'Créer des événements',
    ('read', 'Report', ''): 'Voir les rapports',
    ('export', 'Employee', ''): 'Exporter les employés (PDF)',
    ('export', 'Project', ''): 'Exporter les activités projet',
    ('read', 'Project', ''): 'Voir tous les projets',
    ('delete', 'Project', ''): 'Supprimer un projet',
    ('update', 'Project', ''): 'Modifier tout projet',
    ('manage', 'ProjectMember', ''): 'Gérer les membres de tout projet',
    ('create', 'Milestone', ''): 'Ajouter des jalons à tout projet',
    ('update', 'Milestone', ''): 'Modifier tout jalon',
    ('delete', 'Milestone', ''): 'Supprimer un jalon',
    ('read', 'Budget', ''): 'Voir tous les budgets',
    ('manage', 'Budget', ''): 'Gérer les budgets',
    ('manage', 'User', ''): 'Gérer les utilisateurs',
    ('manage', 'LeaveRequest', ''): 'Approbation finale des congés',
    ('manage', 'Direction', ''): 'Gérer les directions',
    ('manage', 'Role', ''): 'Gérer les rôles et permissions',
    ('read', 'Project', 'is_project_member'): 'Voir ses projets',
    ('update', 'Project', 'is_project_manager'): 'Modifier ses projets',
    ('manage', 'ProjectMember', 'is_project_manager'): 'Gérer les membres de ses projets',
    ('create', 'Milestone', 'is_project_manager'): 'Ajouter des jalons (manager)',
    ('update', 'Milestone', 'is_project_manager'): 'Modifier les jalons (manager)',
    ('create', 'Milestone', 'is_project_member'): 'Ajouter des jalons (membre)',
}


_ROLE_DEFAULTS = {
    'directeur': {'name': 'Directeur', 'description': "Directeur d'une direction."},
    'directeur_general': {'name': 'Directeur Général', 'description': 'Directeur général de la direction générale.'},
    'chef_projet': {'name': 'Chef de Projet', 'description': 'Responsable de projets.'},
}


def sync_role_permissions(apps, schema_editor):
    Permission = apps.get_model('core', 'Permission')
    Role = apps.get_model('core', 'Role')

    for slug, perms in SYNC_ROLES.items():
        defaults = dict(_ROLE_DEFAULTS[slug], is_system=True)
        role, _ = Role.objects.get_or_create(
            slug=slug,
            defaults=defaults,
        )
        for action, subject, condition in perms:
            perm, _ = Permission.objects.get_or_create(
                action=action,
                subject=subject,
                condition=condition,
                defaults={'description': _DESCRIPTIONS.get((action, subject, condition), '')},
            )
            role.permissions.add(perm)


def drop_sync_role_permissions(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    Permission = apps.get_model('core', 'Permission')

    for slug, perms in SYNC_ROLES.items():
        role = Role.objects.filter(slug=slug).first()
        if role is None:
            continue
        perm_ids = set()
        for action, subject, condition in perms:
            match = Permission.objects.filter(
                action=action,
                subject=subject,
                condition=condition,
            ).first()
            if match is not None:
                perm_ids.add(match.pk)
        role.permissions.remove(*Permission.objects.filter(pk__in=perm_ids))


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_userprofile_language'),
    ]

    operations = [
        migrations.RunPython(
            sync_role_permissions,
            drop_sync_role_permissions,
        ),
    ]