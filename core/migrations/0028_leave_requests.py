from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0027_budget_project_optional_direction'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='is_hr_manager',
            field=models.BooleanField(default=False, verbose_name='Gestionnaire RH (vérifie les demandes de congé)'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_approve_leaves',
            field=models.BooleanField(default=False, verbose_name="Peut donner l'avis hiérarchique sur les congés"),
        ),
        migrations.CreateModel(
            name='LeaveRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('leave_type', models.CharField(choices=[
                    ('annuel', 'Congé annuel'),
                    ('maladie', 'Congé maladie'),
                    ('maternite', 'Congé maternité / paternité'),
                    ('exceptionnelle', 'Permission exceptionnelle'),
                    ('sans_solde', 'Congé sans solde'),
                    ('formation', 'Formation / Mission'),
                ], max_length=20, verbose_name='Type de congé')),
                ('start_date', models.DateField(verbose_name='Date de début')),
                ('end_date', models.DateField(verbose_name='Date de fin')),
                ('days_count', models.PositiveIntegerField(default=0, verbose_name='Nombre de jours')),
                ('reason', models.TextField(verbose_name='Motif')),
                ('replacement', models.CharField(blank=True, max_length=200, verbose_name='Suppléant / agent intérimaire')),
                ('handover_note', models.TextField(blank=True, verbose_name='Note de passation')),
                ('justification', models.FileField(blank=True, null=True, upload_to='leaves/', verbose_name='Justificatif')),
                ('status', models.CharField(choices=[
                    ('soumise', 'Soumise - en attente avis hiérarchique'),
                    ('avis_favorable', 'Avis hiérarchique favorable - en attente RH'),
                    ('avis_defavorable', 'Avis hiérarchique défavorable'),
                    ('rh_conforme', 'Vérifiée RH - en attente décision finale'),
                    ('rh_non_conforme', 'Non conforme RH'),
                    ('approuvee', 'Approuvée'),
                    ('rejetee', 'Rejetée'),
                    ('annulee', 'Annulée par le demandeur'),
                ], default='soumise', max_length=20, verbose_name='Statut')),
                ('manager_decision', models.CharField(blank=True, choices=[('', 'En attente'), ('favorable', 'Favorable'), ('defavorable', 'Défavorable')], default='', max_length=15, verbose_name='Avis hiérarchique')),
                ('manager_comment', models.TextField(blank=True, verbose_name='Observations hiérarchie')),
                ('manager_decision_at', models.DateTimeField(blank=True, null=True, verbose_name='Date avis hiérarchique')),
                ('hr_decision', models.CharField(blank=True, choices=[('', 'En attente'), ('conforme', 'Conforme'), ('non_conforme', 'Non conforme')], default='', max_length=15, verbose_name='Vérification RH')),
                ('hr_comment', models.TextField(blank=True, verbose_name='Observations RH')),
                ('hr_decision_at', models.DateTimeField(blank=True, null=True, verbose_name='Date vérification RH')),
                ('final_decision', models.CharField(blank=True, choices=[('', 'En attente'), ('approuve', 'Approuvée'), ('rejete', 'Rejetée')], default='', max_length=15, verbose_name='Décision finale')),
                ('final_comment', models.TextField(blank=True, verbose_name='Observations Direction')),
                ('final_decision_at', models.DateTimeField(blank=True, null=True, verbose_name='Date décision finale')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Soumise le')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('direction', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='leave_requests', to='core.direction', verbose_name='Direction / Service')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='leave_requests', to='core.employee', verbose_name='Employé')),
                ('final_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leaves_final', to=settings.AUTH_USER_MODEL, verbose_name='Décidé par (Direction)')),
                ('hr_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leaves_hr', to=settings.AUTH_USER_MODEL, verbose_name='Vérifié par (RH)')),
                ('manager_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leaves_managed', to=settings.AUTH_USER_MODEL, verbose_name='Validé par (hiérarchie)')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leave_requests', to=settings.AUTH_USER_MODEL, verbose_name='Utilisateur')),
            ],
            options={
                'verbose_name': 'Demande de congé',
                'verbose_name_plural': 'Demandes de congé',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='LeaveDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='leaves/docs/', verbose_name='Fichier')),
                ('label', models.CharField(blank=True, max_length=200, verbose_name='Libellé')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('leave_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='core.leaverequest', verbose_name='Demande')),
            ],
            options={
                'verbose_name': 'Document de congé',
                'verbose_name_plural': 'Documents de congé',
                'ordering': ['-uploaded_at'],
            },
        ),
    ]
