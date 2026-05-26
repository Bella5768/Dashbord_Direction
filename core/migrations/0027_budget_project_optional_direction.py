from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_alter_project_direction'),
    ]

    operations = [
        migrations.AlterField(
            model_name='budget',
            name='direction',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='budgets', to='core.direction', verbose_name='Direction'),
        ),
        migrations.AddField(
            model_name='budget',
            name='project',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='budget_lines', to='core.project', verbose_name='Projet'),
        ),
    ]
