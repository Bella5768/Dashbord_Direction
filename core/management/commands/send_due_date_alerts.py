"""
Envoie les alertes d'échéance par email aux responsables des jalons et sous-étapes
non terminés dont la date d'échéance approche ou est dépassée.

Déclencheurs par défaut (configurable via --trigger-days) :
  J-7, J-3, J-1, J-0, J+1 (1er jour de retard), J+7 (1 semaine de retard)

Planifier quotidiennement via le Planificateur de tâches Windows :
  python manage.py send_due_date_alerts
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from core.models import Milestone, SubMilestone
from core.notifications import notify_due_date_alert

DEFAULT_TRIGGER_DAYS = (7, 3, 1, 0, -1, -7)


class Command(BaseCommand):
    help = "Envoie les alertes d'échéance aux responsables des tâches non terminées (M2M)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--trigger-days',
            type=int,
            nargs='+',
            default=list(DEFAULT_TRIGGER_DAYS),
            metavar='N',
            help=(
                "Jours de déclenchement (positif = J-N à venir, négatif = retard). "
                f"Défaut : {DEFAULT_TRIGGER_DAYS}"
            ),
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Affiche ce qui serait envoyé sans envoyer réellement.",
        )

    def handle(self, *args, **options):
        today = date.today()
        trigger_set = set(options['trigger_days'])
        dry_run = options['dry_run']

        # Calcule la fenêtre de dates à requêter (évite un full-scan)
        max_ahead = max((d for d in trigger_set if d >= 0), default=7)
        max_behind = abs(min((d for d in trigger_set if d < 0), default=0))
        date_min = today - timedelta(days=max_behind)
        date_max = today + timedelta(days=max_ahead)

        self.stdout.write(
            f"Date courante : {today}  |  Fenetre : {date_min} -> {date_max}"
            + ("  [DRY-RUN]" if dry_run else "")
        )

        sent = skipped = errors = 0

        # ── Jalons ──────────────────────────────────────────────────────
        milestones = (
            Milestone.objects
            .filter(completed=False, due_date__range=(date_min, date_max))
            .exclude(status='termine')
            .prefetch_related('assigned_to')
            .select_related('project', 'project__direction')
        )

        for m in milestones:
            days_diff = (m.due_date - today).days
            if days_diff not in trigger_set:
                continue

            assignees = list(m.assigned_to.all())
            if not assignees:
                self.stdout.write(f"  ! Jalon '{m.name}' sans responsable assigne - ignore")
                skipped += 1
                continue

            for emp in assignees:
                if not emp.email:
                    skipped += 1
                    continue
                self.stdout.write(
                    f"  Jalon '{m.name}' (projet {m.project.name}) "
                    f"-> {emp.name} <{emp.email}>  J{days_diff:+d}"
                )
                if dry_run:
                    continue
                ok, msg = notify_due_date_alert(
                    emp, 'jalon', m.name, m.project.name, m.due_date, days_diff,
                    project=m.project,
                )
                if ok:
                    sent += 1
                else:
                    errors += 1
                    self.stdout.write(self.style.WARNING(f"    ECHEC {msg}"))

        # ── Sous-étapes ──────────────────────────────────────────────────
        sub_milestones = (
            SubMilestone.objects
            .filter(completed=False, due_date__range=(date_min, date_max))
            .prefetch_related('assigned_to')
            .select_related('milestone__project', 'milestone__project__direction')
        )

        for s in sub_milestones:
            days_diff = (s.due_date - today).days
            if days_diff not in trigger_set:
                continue

            assignees = list(s.assigned_to.all())
            if not assignees:
                skipped += 1
                continue

            project = s.milestone.project
            for emp in assignees:
                if not emp.email:
                    skipped += 1
                    continue
                self.stdout.write(
                    f"  Sous-étape '{s.name}' (projet {project.name}) "
                    f"-> {emp.name} <{emp.email}>  J{days_diff:+d}"
                )
                if dry_run:
                    continue
                ok, msg = notify_due_date_alert(
                    emp, 'sous-étape', s.name, project.name, s.due_date, days_diff,
                    project=project,
                )
                if ok:
                    sent += 1
                else:
                    errors += 1
                    self.stdout.write(self.style.WARNING(f"    ECHEC {msg}"))

        suffix = "  (dry-run, aucun email envoye)" if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"\nTermine.  Envoyes : {sent}  |  Erreurs : {errors}  |  Ignores : {skipped}{suffix}"
        ))
