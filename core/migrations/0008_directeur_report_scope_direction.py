"""Data migration : scope la permission « Rapports » du directeur à sa direction.

Contexte : la seed 0002 accordait au rôle système « directeur » une permission
``read Report`` SANS condition — donc globale. Le contenu de la page Rapports est
déjà borné à la direction (via la portée ``Project same_direction``), mais la
permission elle-même restait globale : ``read_scope('Report')`` renvoyait 'all'
et toute évolution future du module aurait fuité les données des autres
directions.

Cette migration aligne les bases déjà en place (0002/0007 ayant déjà tourné) sur
le nouveau plan : le directeur reçoit ``read Report same_direction`` et perd la
règle globale ``read Report ''``.

Additive/mutante bornée au seul rôle « directeur » : les rôles directeur_general
et chef_projet (qui partagent la règle globale ``read Report ''``) ne sont pas
touchés, et la ligne Permission ``read Report ''`` n'est pas supprimée — elle
reste rattachée à ces rôles. Idempotente, réversible.
"""
from django.db import migrations

_SCOPED = ('read', 'Report', 'same_direction')
_GLOBAL = ('read', 'Report', '')
_SCOPED_DESCRIPTION = 'Voir les rapports de sa direction'
_GLOBAL_DESCRIPTION = 'Voir les rapports'


def _permission(apps, triple, description):
    Permission = apps.get_model('core', 'Permission')
    action, subject, condition = triple
    perm, _ = Permission.objects.get_or_create(
        action=action,
        subject=subject,
        condition=condition,
        defaults={'description': description},
    )
    return perm


def scope_directeur_reports(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    role = Role.objects.filter(slug='directeur').first()
    if role is None:
        return
    role.permissions.add(_permission(apps, _SCOPED, _SCOPED_DESCRIPTION))
    global_perm = apps.get_model('core', 'Permission').objects.filter(
        action=_GLOBAL[0], subject=_GLOBAL[1], condition=_GLOBAL[2],
    ).first()
    if global_perm is not None:
        role.permissions.remove(global_perm)


def unscope_directeur_reports(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    role = Role.objects.filter(slug='directeur').first()
    if role is None:
        return
    role.permissions.add(_permission(apps, _GLOBAL, _GLOBAL_DESCRIPTION))
    scoped_perm = apps.get_model('core', 'Permission').objects.filter(
        action=_SCOPED[0], subject=_SCOPED[1], condition=_SCOPED[2],
    ).first()
    if scoped_perm is not None:
        role.permissions.remove(scoped_perm)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_sync_directeur_project_actions'),
    ]

    operations = [
        migrations.RunPython(
            scope_directeur_reports,
            unscope_directeur_reports,
        ),
    ]
