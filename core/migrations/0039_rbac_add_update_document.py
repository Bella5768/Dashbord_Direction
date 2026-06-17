"""
Data migration : ajoute la permission 'update:Document' aux rôles projet
qui ont déjà 'create:Document' (responsable, membre, ressource_externe_edit).

Sans cette permission, les membres ne peuvent pas modifier/supprimer les
documents qu'ils ont créés — le check can_edit_project_documents() retournait
toujours False car le droit n'existait pas dans la table Permission.
"""
from django.db import migrations


ROLES_WITH_UPDATE_DOC = ['responsable', 'membre', 'ressource_externe_edit']


def add_update_document(apps, schema_editor):
    Permission  = apps.get_model('core', 'Permission')
    ProjectRole = apps.get_model('core', 'ProjectRole')

    perm, _ = Permission.objects.get_or_create(
        action='update',
        subject='Document',
        condition='',
        defaults={'description': 'Modifier les documents du projet'},
    )

    for slug in ROLES_WITH_UPDATE_DOC:
        try:
            role = ProjectRole.objects.get(slug=slug)
            role.permissions.add(perm)
        except ProjectRole.DoesNotExist:
            pass


def remove_update_document(apps, schema_editor):
    Permission  = apps.get_model('core', 'Permission')
    ProjectRole = apps.get_model('core', 'ProjectRole')

    try:
        perm = Permission.objects.get(action='update', subject='Document', condition='')
    except Permission.DoesNotExist:
        return

    for slug in ROLES_WITH_UPDATE_DOC:
        try:
            role = ProjectRole.objects.get(slug=slug)
            role.permissions.remove(perm)
        except ProjectRole.DoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_event_add_meta_fields'),
    ]

    operations = [
        migrations.RunPython(add_update_document, remove_update_document),
    ]
