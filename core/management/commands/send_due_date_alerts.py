"""
Envoie les alertes d'echeance par email aux responsables des jalons et sous-etapes
non termines dont la date d'echeance approche ou est depassee.

A planifier quotidiennement via le Planificateur de taches Windows.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from core.models import Milestone, SubMilestone
from core.notifications import notify_due_date_alert


class Command(BaseCommand):
    help = "Envoie les alertes d'echeance aux responsables des taches non terminees."

    def add_arguments(self, parser):
        parser.add_argument(
            '--reminder-days',
            type=int,
            default=1,
            help="Nombre de jours avant echeance pour envoyer un rappel (defaut: 1 = J-1).",
        )
        parser.add_argument(
            '--include-overdue',
            action='store_true',
            default=True,
            help="Inclure aussi les taches en retard (defaut: True).",
        )
        parser.add_argument(
            '--max-overdue-days',
            type=int,
            default=30,
            help="Limite l'envoi aux taches en retard de moins de N jours (defaut: 30).",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Affiche ce qui serait envoye sans envoyer reellement.",
        )

    def handle(self, *args, **options):
        today = date.today()
        reminder_days = options['reminder_days']
        max_overdue = options['max_overdue_days']
        dry_run = options['dry_run']

        target_dates = [today, today + timedelta(days=reminder_days)]
        if options['include_overdue']:
            for d in range(1, max_overdue + 1):
                target_dates.append(today - timedelta(days=d))

        self.stdout.write(f"Date courante : {today}")
        self.stdout.write(f"Recherche des taches non terminees avec echeance dans la fenetre.")

        sent = 0
        skipped = 0
        errors = 0

        # Jalons
        milestones = Milestone.objects.select_related('project', 'assigned_to').filter(
            completed=False,
            due_date__in=target_dates,
            assigned_to__isnull=False,
        )
        for m in milestones:
            if not m.assigned_to or not m.assigned_to.email:
                skipped += 1
                continue
            days_diff = (m.due_date - today).days
            self.stdout.write(
                f"  Jalon #{m.id} '{m.name}' (projet {m.project.name}) "
                f"-> {m.assigned_to.name} <{m.assigned_to.email}> "
                f"echeance {m.due_date} (J{days_diff:+d})"
            )
            if dry_run:
                continue
            ok, msg = notify_due_date_alert(
                m.assigned_to, 'jalon', m.name, m.project.name, m.due_date, days_diff,
                project=m.project,
            )
            if ok:
                sent += 1
            else:
                errors += 1
                self.stdout.write(self.style.WARNING(f"    ECHEC : {msg}"))

        # Sous-etapes
        sub_milestones = SubMilestone.objects.select_related(
            'milestone__project', 'assigned_to'
        ).filter(
            completed=False,
            due_date__in=target_dates,
            assigned_to__isnull=False,
        )
        for s in sub_milestones:
            if not s.assigned_to or not s.assigned_to.email:
                skipped += 1
                continue
            days_diff = (s.due_date - today).days
            project = s.milestone.project
            self.stdout.write(
                f"  Sous-etape #{s.id} '{s.name}' (projet {project.name}) "
                f"-> {s.assigned_to.name} <{s.assigned_to.email}> "
                f"echeance {s.due_date} (J{days_diff:+d})"
            )
            if dry_run:
                continue
            ok, msg = notify_due_date_alert(
                s.assigned_to, 'sous-etape', s.name, project.name, s.due_date, days_diff,
                project=project,
            )
            if ok:
                sent += 1
            else:
                errors += 1
                self.stdout.write(self.style.WARNING(f"    ECHEC : {msg}"))

        self.stdout.write(self.style.SUCCESS(
            f"Termine. Envoyes : {sent} | Erreurs : {errors} | Ignores : {skipped}"
            + (" (dry-run)" if dry_run else "")
        ))
