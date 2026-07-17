import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from core.models import UserProfile, Role


class Command(BaseCommand):
    help = "Crée le super-administrateur initial (à exécuter une seule fois)"

    def handle(self, *args, **options):
        username = "admin"
        email = os.getenv('DJANGO_ADMIN_EMAIL', 'admin@csig.com')
        password = os.getenv('DJANGO_ADMIN_PASSWORD')
        if not password:
            raise CommandError(
                "La variable d'environnement DJANGO_ADMIN_PASSWORD est requise.\n"
                "Exemple : DJANGO_ADMIN_PASSWORD=VotreMotDePasse python manage.py create_admin"
            )

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(
                f"L'utilisateur '{username}' existe déjà — aucune modification effectuée. "
                "Supprimez le compte manuellement si vous souhaitez le recréer."
            ))
            return

        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name="Super",
            last_name="Administrateur",
        )
        self.stdout.write(self.style.SUCCESS(f"Utilisateur '{username}' créé."))

        admin_role = Role.objects.filter(slug='admin').first()
        if admin_role is None:
            self.stdout.write(self.style.WARNING(
                "Rôle 'admin' introuvable — profil sauvegardé sans rôle. "
                "Lancez 'python manage.py assign_roles' puis relancez cette commande."
            ))

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = admin_role
        profile.is_active_profile = True
        profile.save()

        self.stdout.write(self.style.SUCCESS("Profil admin configuré avec tous les accès."))
