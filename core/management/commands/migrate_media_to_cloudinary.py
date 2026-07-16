"""
Migrer les fichiers media/ existants vers Cloudinary.

IMPORTANT: Ce script doit etre execute AVANT d'appliquer la migration
qui convertit les FileField en URLField. Lancez-le quand les champs
sont encore des FileField/ImageField.

Usage:
    python manage.py migrate_media_to_cloudinary --dry-run
    python manage.py migrate_media_to_cloudinary
    python manage.py migrate_media_to_cloudinary --clean-local
"""
import os
import cloudinary.uploader
from django.core.management.base import BaseCommand
from django.conf import settings


MODELS_WITH_FILES = [
    ('core.UserProfile', 'avatar'),
    ('core.Partner', 'logo'),
    ('core.Document', 'file'),
    ('core.ProjectDocument', 'file'),
    ('core.LeaveRequest', 'justification'),
    ('core.LeaveDocument', 'file'),
]


class Command(BaseCommand):
    help = 'Migrer tous les fichiers media/ existants vers Cloudinary (a executer AVANT la migration de champs)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Afficher les fichiers sans les uploader',
        )
        parser.add_argument(
            '--clean-local', action='store_true',
            help='Supprimer les fichiers locaux apres migration reussie',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        clean_local = options['clean_local']

        if not os.getenv('CLOUDINARY_CLOUD_NAME'):
            self.stderr.write(self.style.ERROR(
                'CLOUDINARY_CLOUD_NAME non configure. '
                'Ajoutez vos credentials Cloudinary dans le fichier .env'
            ))
            return

        media_root = settings.MEDIA_ROOT
        if not os.path.exists(media_root):
            self.stdout.write(self.style.WARNING('Dossier media/ introuvable, rien a migrer.'))
            return

        total = 0
        errors = 0
        updated = 0

        for model_path, field_name in MODELS_WITH_FILES:
            app_label, model_name = model_path.split('.')
            from django.apps import apps
            try:
                model = apps.get_model(app_label, model_name)
            except LookupError:
                self.stderr.write(self.style.WARNING(f'Modele {model_path} introuvable, ignore.'))
                continue

            self.stdout.write(f'\n--- {model_name}.{field_name} ---')

            for instance in model.objects.all():
                try:
                    field = getattr(instance, field_name)
                except Exception:
                    continue

                if not field:
                    continue

                # FileField has .path attribute; URLField does not
                try:
                    old_path = field.path
                except (AttributeError, ValueError, NotImplementedError):
                    continue

                if not old_path or not os.path.exists(old_path):
                    continue

                total += 1
                rel_path = os.path.relpath(old_path, media_root).replace('\\', '/')
                self.stdout.write(f'  -> {rel_path}', ending='')

                if dry_run:
                    self.stdout.write(' (dry-run)')
                    continue

                try:
                    with open(old_path, 'rb') as f:
                        result = cloudinary.uploader.upload(
                            f,
                            folder='media',
                            resource_type='auto',
                            public_id=os.path.splitext(rel_path)[0],
                        )
                    new_url = result['secure_url']

                    # Stocker l'URL dans le champ (marche pour FileField et URLField)
                    setattr(instance, field_name, new_url)
                    instance.save(update_fields=[field_name])
                    updated += 1
                    self.stdout.write(f' -> {new_url}')

                    if clean_local:
                        os.remove(old_path)
                except Exception as e:
                    errors += 1
                    self.stderr.write(self.style.ERROR(f' ERREUR: {e}'))

        self.stdout.write(f'\n{"="*50}')
        self.stdout.write(self.style.SUCCESS(
            f'Terminé: {total} fichiers traites, {updated} mis a jour, {errors} erreurs'
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING('Mode dry-run: aucun changement effectue.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                'Appliquez maintenant la migration: python manage.py migrate'
            ))
