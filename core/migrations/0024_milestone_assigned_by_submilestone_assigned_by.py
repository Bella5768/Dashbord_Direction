# Generated manually for task assignment notifications

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0023_add_need_to_milestones'),
    ]

    operations = [
        migrations.AddField(
            model_name='milestone',
            name='assigned_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_milestones_created', to=settings.AUTH_USER_MODEL, verbose_name='Attribué par'),
        ),
        migrations.AddField(
            model_name='submilestone',
            name='assigned_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_sub_milestones_created', to=settings.AUTH_USER_MODEL, verbose_name='Attribué par'),
        ),
    ]
