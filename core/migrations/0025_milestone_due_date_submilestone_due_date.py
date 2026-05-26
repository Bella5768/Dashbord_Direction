# Generated manually for task and sub-task dates

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_milestone_assigned_by_submilestone_assigned_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='milestone',
            name='due_date',
            field=models.DateField(blank=True, null=True, verbose_name='Date de la tâche'),
        ),
        migrations.AddField(
            model_name='submilestone',
            name='due_date',
            field=models.DateField(blank=True, null=True, verbose_name='Date de la sous-tâche'),
        ),
    ]
