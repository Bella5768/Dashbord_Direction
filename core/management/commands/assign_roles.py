"""
Commande de réassignation des rôles utilisateurs après la migration RBAC.

Usage:
  python manage.py assign_roles                    # rapport sans rien changer
  python manage.py assign_roles --auto             # auto : superuser→admin, autres→employé
  python manage.py assign_roles --user oumar --role directeur
  python manage.py assign_roles --list-roles
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Réassigne les rôles utilisateurs après la migration RBAC"

    def add_arguments(self, parser):
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Assignation automatique : superuser→admin, actifs sans rôle approprié→employé',
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Nom d\'utilisateur à modifier',
        )
        parser.add_argument(
            '--role',
            type=str,
            help='Slug du rôle à assigner (ex: admin, directeur, chef_projet, employe, visiteur)',
        )
        parser.add_argument(
            '--list-roles',
            action='store_true',
            help='Afficher tous les rôles disponibles',
        )

    def handle(self, *args, **options):
        from core.models import UserProfile, Role

        if options['list_roles']:
            self._list_roles()
            return

        if options['user'] and options['role']:
            self._assign_single(options['user'], options['role'])
            return

        if options['auto']:
            self._auto_assign()
            return

        # Par défaut : rapport
        self._report()

    def _list_roles(self):
        from core.models import Role
        self.stdout.write("\nRôles disponibles :")
        self.stdout.write("-" * 50)
        for r in Role.objects.all().order_by('name'):
            n = r.users.count()
            sys = " [systeme]" if r.is_system else ""
            self.stdout.write(f"  {r.slug:<25} {r.name:<20} ({n} utilisateur(s)){sys}")
        self.stdout.write("")

    def _report(self):
        from core.models import UserProfile
        self.stdout.write("\nÉtat des utilisateurs :")
        self.stdout.write("-" * 60)
        for u in User.objects.prefetch_related('profile__role').order_by('username'):
            try:
                profile = u.profile
                role_name = profile.role.name if profile.role else "SANS RÔLE [!]"
                role_slug = profile.role.slug if profile.role else "-"
                su = " [superuser]" if u.is_superuser else ""
                active = "" if u.is_active else " [inactif]"
                self.stdout.write(f"  {u.username:<20} {role_slug:<20} {role_name}{su}{active}")
            except UserProfile.DoesNotExist:
                self.stdout.write(f"  {u.username:<20} (pas de profil)")
        self.stdout.write("")
        self.stdout.write("Pour réassigner :")
        self.stdout.write("  python manage.py assign_roles --auto")
        self.stdout.write("  python manage.py assign_roles --user <username> --role <slug>")
        self.stdout.write("  python manage.py assign_roles --list-roles")
        self.stdout.write("")

    def _assign_single(self, username, role_slug):
        from core.models import UserProfile, Role
        try:
            u = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"Utilisateur '{username}' introuvable.")
        try:
            role = Role.objects.get(slug=role_slug)
        except Role.DoesNotExist:
            raise CommandError(
                f"Rôle '{role_slug}' introuvable. "
                f"Utilisez --list-roles pour voir les rôles disponibles."
            )
        profile, _ = UserProfile.objects.get_or_create(user=u)
        old = profile.role.slug if profile.role else "aucun"
        profile.role = role
        profile.save(update_fields=['role'])
        self.stdout.write(
            self.style.SUCCESS(f"OK {username} : {old} -> {role_slug} ({role.name})")
        )

    def _auto_assign(self):
        from core.models import UserProfile, Role

        try:
            admin_role    = Role.objects.get(slug='admin')
            employe_role  = Role.objects.get(slug='employe')
            visiteur_role = Role.objects.get(slug='visiteur')
        except Role.DoesNotExist as e:
            raise CommandError(f"Rôle système manquant : {e}. Lancez d'abord migrate.")

        changed = 0
        for u in User.objects.prefetch_related('profile__role').order_by('username'):
            try:
                profile = u.profile
            except UserProfile.DoesNotExist:
                continue

            current_slug = profile.role.slug if profile.role else None

            if u.is_superuser and current_slug != 'admin':
                profile.role = admin_role
                profile.save(update_fields=['role'])
                self.stdout.write(
                    self.style.SUCCESS(f"  OK {u.username}: {current_slug or 'aucun'} -> admin (superuser)")
                )
                changed += 1

            elif not u.is_superuser and current_slug == 'visiteur' and u.is_active:
                # Visiteur par défaut → employé pour les comptes actifs non-super
                profile.role = employe_role
                profile.save(update_fields=['role'])
                self.stdout.write(
                    self.style.WARNING(f"  ~ {u.username}: visiteur -> employe (actif, non-superuser)")
                )
                changed += 1

        if changed == 0:
            self.stdout.write(self.style.SUCCESS("Aucun changement nécessaire."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n{changed} utilisateur(s) mis a jour."))
            self.stdout.write("Verifiez et ajustez manuellement si necessaire :")
            self.stdout.write("  python manage.py assign_roles --user <username> --role <slug>")
