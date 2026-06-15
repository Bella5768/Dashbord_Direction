from django.db import migrations
from django.utils import timezone


def sync_milestone_status(apps, schema_editor):
    """Corrige les jalons existants : completed=True doit avoir status='termine'."""
    Milestone = apps.get_model('core', 'Milestone')
    now = timezone.now()
    # Jalons cochés mais dont le statut est resté au défaut 'a_faire'
    Milestone.objects.filter(completed=True).exclude(status='termine').update(
        status='termine',
    )
    # Jalons cochés sans completed_at
    Milestone.objects.filter(completed=True, completed_at__isnull=True).update(
        completed_at=now,
    )
    # Jalons non cochés avec status='termine' par erreur
    Milestone.objects.filter(completed=False, status='termine').update(
        status='en_cours',
        completed_at=None,
    )


def reverse_sync(apps, schema_editor):
    pass  # pas de rollback pertinent


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_project_module_improvements'),
    ]

    operations = [
        migrations.RunPython(sync_milestone_status, reverse_sync),
    ]
