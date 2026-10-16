"""Data migration : autorise le directeur à supprimer les projets de sa direction.

Contexte : le rôle système « directeur » disposait de ``update Project
same_direction`` (modifier les projets de sa direction) mais pas de la
permission de suppression — celle-ci n'existait qu'en variante globale
``delete Project ''`` réservée au DG/admin. Un directeur ne pouvait donc pas
supprimer un projet de sa propre direction, alors qu'il gère déjà tous les
autres aspects (jalons, membres, documents, besoins, budget).

Cette migration ajoute ``delete Project same_direction`` au rôle « directeur ».
Elle est additive et idempotente (bases neuves comme existantes) : la règle
globale ``delete Project ''`` n'est pas touchée et reste rattachée au DG/admin.
"""
from django.db import migrations

_SCOPED = ('delete', 'Project', 'same_direction')
_DESCRIPTION = 'Supprimer les projets de sa direction'


def grant_directeur_delete_project(apps, schema_editor):
    Permission = apps.get_model('core', 'Permission')
    Role = apps.get_model('core', 'Role')

    perm, _ = Permission.objects.get_or_create(
        action=_SCOPED[0],
        subject=_SCOPED[1],
        condition=_SCOPED[2],
        defaults={'description': _DESCRIPTION},
    )
    role = Role.objects.filter(slug='directeur').first()
    if role is not None:
        role.permissions.add(perm)


def revoke_directeur_delete_project(apps, schema_editor):
    Permission = apps.get_model('core', 'Permission')
    Role = apps.get_model('core', 'Role')

    role = Role.objects.filter(slug='directeur').first()
    if role is None:
        return
    perm = Permission.objects.filter(
        action=_SCOPED[0],
        subject=_SCOPED[1],
        condition=_SCOPED[2],
    ).first()
    if perm is not None:
        role.permissions.remove(perm)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_alter_project_end_date_alter_project_start_date'),
    ]

    operations = [
        migrations.RunPython(
            grant_directeur_delete_project,
            revoke_directeur_delete_project,
        ),
    ]
