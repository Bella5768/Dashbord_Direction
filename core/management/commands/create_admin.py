from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile, Role


class Command(BaseCommand):
    help = "Crée le super-administrateur initial (à exécuter une seule fois)"

    def handle(self, *args, **options):
        username = "admin"
        email = "admin@csig.com"
        password = "Admin123!@#"

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"L'utilisateur '{username}' existe déjà.")
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name="Super",
                last_name="Administrateur",
            )
            self.stdout.write(self.style.SUCCESS(f"Utilisateur '{username}' créé."))

        admin_role = Role.objects.filter(slug='admin').first()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = admin_role
        profile.is_active_profile = True
        profile.budget_view = True
        profile.budget_manage = True
        profile.budget_view_all_directions = True
        profile.can_create_project = True
        profile.can_edit_projects = True
        profile.can_add_milestones = True
        profile.can_add_members = True
        profile.can_manage_users = True
        profile.can_approve_requests = True
        profile.can_create_events = True
        profile.save()

        self.stdout.write(self.style.SUCCESS("Profil admin configuré avec tous les accès."))
