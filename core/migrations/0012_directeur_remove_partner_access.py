"""Data migration : retire l'accès Partenaires au rôle « directeur ».

Contexte : ``Partner`` n'a pas de champ ``direction`` — la portée
``same_direction`` y est donc inévaluable. Décision : les partenaires restent
réservés aux rôles à périmètre global (DG/admin). Le rôle « directeur », borné à
sa direction, perd donc ses règles globales ``read``/``manage Partner``.

Le rôle « chef_projet » conserve sa ``read Partner`` (accès global préexistant,
hors périmètre de cette décision). Additive/mutante bornée au seul rôle
« directeur », idempotente et réversible.
"""
from django.db import migrations

_PARTNER_GLOBAL = [
    ('read',   'Partner', ''),
    ('manage', 'Partner', ''),
]


def remove_directeur_partner(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    Permission = apps.get_model('core', 'Permission')
    role = Role.objects.filter(slug='directeur').first()
    if role is None:
        return
    for action, subject, condition in _PARTNER_GLOBAL:
        perm = Permission.objects.filter(
            action=action, subject=subject, condition=condition,
        ).first()
        if perm is not None:
            role.permissions.remove(perm)


def restore_directeur_partner(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    Permission = apps.get_model('core', 'Permission')
    role = Role.objects.filter(slug='directeur').first()
    if role is None:
        return
    descriptions = {
        ('read', 'Partner', ''): 'Voir les partenaires',
        ('manage', 'Partner', ''): 'Gérer les partenaires',
    }
    for action, subject, condition in _PARTNER_GLOBAL:
        perm, _ = Permission.objects.get_or_create(
            action=action, subject=subject, condition=condition,
            defaults={'description': descriptions[(action, subject, condition)]},
        )
        role.permissions.add(perm)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_directeur_documents_scope_direction'),
    ]

    operations = [
        migrations.RunPython(
            remove_directeur_partner,
            restore_directeur_partner,
        ),
    ]
