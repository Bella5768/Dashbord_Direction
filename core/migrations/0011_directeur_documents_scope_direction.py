"""Data migration : borne les documents du directeur à sa direction.

Contexte : le rôle système « directeur » disposait de ``read``/``manage``/
``approve Document`` SANS condition, donc globale — il pouvait agir sur les
documents de toutes les directions. Le modèle ``Document`` porte bien une
``direction`` : la portée ``same_direction`` est applicable.

Cette migration remplace, pour le seul rôle « directeur », les trois règles
globales ``... Document ''`` par leurs variantes ``same_direction``. Les règles
globales ne sont pas supprimées (le DG et le chef de projet les conservent).

La liste des documents (``_apply_read_scope``) et l'ouverture d'un fichier
(``_can_open_document``) gèrent déjà la portée 'direction' ; les vues
d'écriture ont été alignées pour évaluer l'instance. Additive/mutante bornée au
seul rôle « directeur », idempotente et réversible.
"""
from django.db import migrations

_SCOPED = [
    ('read',    'Document', 'same_direction', 'Voir les documents de sa direction'),
    ('manage',  'Document', 'same_direction', 'Gérer les documents de sa direction'),
    ('approve', 'Document', 'same_direction', 'Approuver / signer les documents de sa direction'),
]
_GLOBAL = [
    ('read',    'Document', ''),
    ('manage',  'Document', ''),
    ('approve', 'Document', ''),
]


def _get_permission(apps, action, subject, condition, description=''):
    Permission = apps.get_model('core', 'Permission')
    perm, _ = Permission.objects.get_or_create(
        action=action, subject=subject, condition=condition,
        defaults={'description': description},
    )
    return perm


def scope_directeur_documents(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    role = Role.objects.filter(slug='directeur').first()
    if role is None:
        return
    for action, subject, condition, description in _SCOPED:
        role.permissions.add(_get_permission(apps, action, subject, condition, description))
    Permission = apps.get_model('core', 'Permission')
    for action, subject, condition in _GLOBAL:
        perm = Permission.objects.filter(
            action=action, subject=subject, condition=condition,
        ).first()
        if perm is not None:
            role.permissions.remove(perm)


def unscope_directeur_documents(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    role = Role.objects.filter(slug='directeur').first()
    if role is None:
        return
    Permission = apps.get_model('core', 'Permission')
    for action, subject, condition in _GLOBAL:
        perm = Permission.objects.filter(
            action=action, subject=subject, condition=condition,
        ).first()
        if perm is not None:
            role.permissions.add(perm)
    for action, subject, condition, _desc in _SCOPED:
        perm = Permission.objects.filter(
            action=action, subject=subject, condition=condition,
        ).first()
        if perm is not None:
            role.permissions.remove(perm)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_directeur_delete_project_direction'),
    ]

    operations = [
        migrations.RunPython(
            scope_directeur_documents,
            unscope_directeur_documents,
        ),
    ]
