"""Smoke tests : aucune page GET de l'application ne doit renvoyer 500.

Audit du 08/10 (incident prod /mes-taches/, NoReverseMatch 'milestone_toggle'
avec argument ''). Trois classes de bugs, toutes corrigées par l'Étape A —
ces tests sont les garde-fous de régression :

1. my_tasks.html:180 reverse item.slug alors que la vue my_tasks construisait
   ses items SANS la clé 'slug' → '' → NoReverseMatch → 500 dès qu'une tâche
   assignée s'affichait. Fix : 'slug' ajouté au contexte de la vue.
2. Slugs legacy vides/NULL : 0001_initial crée les colonnes slug sans
   backfill ; tout {% url %} sur un .slug de modèle vide levait NoReverseMatch
   (500). Fix : migration 0005 (backfill) + garde-fous `|default:<var>.pk`
   dans tous les {% url %} sur .slug (get_sluggable_or_404 résout l'UUID).
3. request.user.profile.* sans profil utilisateur : ~110 accès non protégés,
   27 des 37 pages principales plantaient. Fix :
   EnsureUserProfileMiddleware (recrée le profil manquant avant la vue).

Chaque test vérifie status_code < 500 (302/403/404 acceptés). Les exceptions
non gérées sont re-lancées par le test client : sans les fixes, la régression
prod échoue ici avec le même traceback qu'en production.
"""

import copy as _copy
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.test.utils import ContextList
from django.urls import reverse
from django.utils import timezone, translation

import django.test.client as _dj_client

from . import notifications
from .exchange import CACHE_KEY, DEFAULT_USD_GNF_RATE
from .models import (
    Direction,
    Employee,
    Event,
    Milestone,
    Permission,
    Project,
    ProjectMember,
    ProjectRole,
    Request,
    Role,
    SubMilestone,
    UserProfile,
)

User = get_user_model()


def _store_rendered_templates_safe(store, signal, sender, template, context, **kwargs):
    """store_rendered_templates() avec repli si copy(context) plante.

    Environnement local : Python 3.14 + Django 4.2 (requirements.txt exige
    Django>=5.1.5) — Context.__copy__ lève
    AttributeError: 'super' object has no attribute 'dicts' sur Python 3.14.
    Le rendu de la page a alors déjà réussi : seul l'instrumentation du test
    client échoue. Le repli conserve la copie brute (nos assertions n'utilisent
    pas resp.context). Sans effet dès que l'environnement respecte
    requirements.txt.
    """
    store.setdefault('templates', []).append(template)
    if 'context' not in store:
        store['context'] = ContextList()
    try:
        store['context'].append(_copy.copy(context))
    except Exception:
        store['context'].append(context)


_dj_client.store_rendered_templates = _store_rendered_templates_safe

# Pages principales (GET, sans argument d'URL, sans mutation — logout et les
# endpoints toggle/delete POST-exclants sont volontairement absents).
MAIN_URLS = [
    'dashboard', 'global_search', 'projects', 'resources', 'requests',
    'calendar', 'documents', 'reports', 'partners', 'users_list',
    'roles_list', 'project_roles_list', 'directions_list', 'leave_list',
    'my_tasks', 'profile', 'password_change', 'password_reset_info',
    'notifications_list', 'notifications_count', 'notifications_recent',
    'project_create', 'project_import', 'event_create', 'document_create',
    'employee_create', 'budget_create', 'request_create', 'partner_create',
    'user_create', 'request_new_activation', 'role_create',
    'project_role_create', 'direction_create', 'leave_create',
    'api_budget', 'api_projects',
]

# Pages qui plantaient pour un utilisateur SANS profil AVANT
# EnsureUserProfileMiddleware (inventaire runtime du 08/10 : 27 des 37).
# test_pages_connues_en_crash_sans_profil doit toutes les passer en < 500 ;
# si une régresse, elle réapparaît ici et disparaît de la liste principale.
SANS_PROFIL_CRASH_URLS = {
    'api_budget',
    'api_projects',
    'budget_create',
    'calendar',
    'dashboard',
    'direction_create',
    'directions_list',
    'document_create',
    'documents',
    'event_create',
    'my_tasks',
    'partner_create',
    'partners',
    'profile',
    'project_create',
    'project_import',
    'project_role_create',
    'project_roles_list',
    'projects',
    'reports',
    'request_create',
    'requests',
    'resources',
    'role_create',
    'roles_list',
    'user_create',
    'users_list',
}


class SmokeBase(TestCase):
    """Fixtures partagées : 3 profils (admin, employé assigné, sans profil)
    + un projet avec un jalon feuille et un jalon parent à sous-étape."""

    @classmethod
    def setUpTestData(cls):
        # Taux figé en cache : aucune appelle réseau pendant les tests.
        cache.set(
            CACHE_KEY,
            {
                'rate': DEFAULT_USD_GNF_RATE,
                'date': timezone.now(),
                'source': 'live',
                'fetched_at': timezone.now(),
            },
            None,
        )

        cls.direction = Direction.objects.create(name='Direction Smoke', code='SMK')

        cls.admin = User.objects.create_user(
            'admin_smoke', password='x', is_superuser=True, is_staff=True
        )

        cls.employe_user = User.objects.create_user('employe_smoke', password='x')
        cls.employee = Employee.objects.create(
            name='Employe Smoke', role='Developpeur', direction=cls.direction
        )
        employe_profile = cls.employe_user.profile
        employe_profile.role = Role.objects.get(slug='employe')
        employe_profile.direction = cls.direction
        employe_profile.employee = cls.employee
        employe_profile.save()

        cls.sans_profil = User.objects.create_user('sans_profil_smoke', password='x')
        cls.sans_profil.profile.delete()

        today = timezone.now().date()
        cls.project = Project.objects.create(
            name='Projet Smoke',
            status='en_cours',
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=30),
            manager='Manager Smoke',
            direction=cls.direction,
        )

        # Jalon feuille (sans sous-étapes → can_toggle → branche toggle).
        cls.leaf = Milestone.objects.create(
            project=cls.project, name='Jalon feuille', due_date=today + timedelta(days=7)
        )
        cls.leaf.assigned_to.set([cls.employee])

        # Jalon parent (avec sous-étape → jalon non toggleable, sous-étape oui).
        cls.parent = Milestone.objects.create(
            project=cls.project, name='Jalon parent', due_date=today + timedelta(days=10)
        )
        cls.parent.assigned_to.set([cls.employee])
        cls.sub = SubMilestone.objects.create(
            milestone=cls.parent, name='Sous-etape smoke', due_date=today + timedelta(days=5)
        )
        cls.sub.assigned_to.set([cls.employee])

    def _login(self, user):
        self.client.force_login(user)

    def _get_ok(self, url):
        resp = self.client.get(url)
        self.assertLess(resp.status_code, 500, f'{url} -> {resp.status_code}')
        return resp

    def _main_urls(self, exclude=()):
        return [n for n in MAIN_URLS if n not in exclude]

    def _object_urls(self):
        p, leaf, parent, sub = self.project, self.leaf, self.parent, self.sub
        return [
            reverse('core:project_detail', args=[p.slug]),
            reverse('core:project_edit', args=[p.slug]),
            reverse('core:project_need_create', args=[p.slug]),
            reverse('core:project_comment_create', args=[p.slug]),
            reverse('core:project_folder_create', args=[p.slug]),
            reverse('core:milestone_create', args=[p.slug]),
            reverse('core:milestone_detail', args=[leaf.slug]),
            reverse('core:milestone_edit', args=[leaf.slug]),
            reverse('core:milestone_detail', args=[parent.slug]),
            reverse('core:sub_milestone_edit', args=[sub.slug]),
        ]


class SmokeAdminTests(SmokeBase):
    """Admin (superuser, profil auto-créé, sans employé lié)."""

    def test_main_urls_ne_renvoient_jamais_500(self):
        self._login(self.admin)
        for name in self._main_urls():
            with self.subTest(url=name):
                self._get_ok(reverse(f'core:{name}'))

    def test_object_urls_ne_renvoient_jamais_500(self):
        self._login(self.admin)
        for url in self._object_urls():
            with self.subTest(url=url):
                self._get_ok(url)


class SmokeEmployeTests(SmokeBase):
    """Employé avec profil, employé lié et tâches assignées."""

    def test_main_urls_ne_renvoient_jamais_500(self):
        self._login(self.employe_user)
        for name in self._main_urls():
            with self.subTest(url=name):
                self._get_ok(reverse(f'core:{name}'))

    def test_object_urls_ne_renvoient_jamais_500(self):
        self._login(self.employe_user)
        for url in self._object_urls():
            with self.subTest(url=url):
                self._get_ok(url)

    def test_my_tasks_affiche_liens_toggle(self):
        """Régression prod : /mes-taches/ doit afficher les liens de toggle
        des tâches assignées (jalon feuille + sous-étape). Sans le 'slug'
        fourni par la vue, reverse(item.slug) échouait avec ('',)."""
        self._login(self.employe_user)
        resp = self._get_ok(reverse('core:my_tasks'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse('core:milestone_toggle', args=[self.leaf.slug]))
        self.assertContains(resp, reverse('core:sub_milestone_toggle', args=[self.sub.slug]))


class SmokeSansProfilTests(SmokeBase):
    """Utilisateur dont le profil a été supprimé : aucune page ne doit 500."""

    def _login(self, user):
        # force_login -> update_last_login -> user.save() -> signal
        # save_user_profile : l'instance fixture garde le profil supprimé dans
        # _state.fields_cache (.profile.delete() l'a mis en cache dans
        # setUpTestData) → hasattr True → profile.save() réinsère la ligne.
        # Suppression APRÈS le login, via queryset (aucune instance en cache).
        super()._login(user)
        UserProfile.objects.filter(user=user).delete()

    def test_pages_sans_profil_ne_renvoient_jamais_500(self):
        self._login(self.sans_profil)
        self.assertFalse(
            UserProfile.objects.filter(user=self.sans_profil).exists(),
            'prerequis : le profil doit etre absent pendant les requetes',
        )
        for name in self._main_urls(exclude=SANS_PROFIL_CRASH_URLS):
            with self.subTest(url=name):
                self._get_ok(reverse(f'core:{name}'))

    def test_pages_connues_en_crash_sans_profil(self):
        """Les 27 pages qui plantaient sans profil (inventaire runtime du
        08/10) : EnsureUserProfileMiddleware doit toutes les rendre < 500."""
        self._login(self.sans_profil)
        for name in sorted(SANS_PROFIL_CRASH_URLS):
            with self.subTest(url=name):
                self._get_ok(reverse(f'core:{name}'))


class RegressionSlugVideTests(SmokeBase):
    """Classe 2 : slug legacy vide/NULL sur un modèle → NoReverseMatch.

    Même si la migration 0005 a backfillé la base, un slug vide réintroduit
    (SQL direct) ne doit plus jamais faire planter le rendu : les {% url %}
    sur .slug passent par |default:<var>.pk (résolu par get_sluggable_or_404)."""

    def test_project_detail_avec_jalon_slug_vide_ne_doit_pas_500(self):
        Milestone.objects.filter(pk=self.leaf.pk).update(slug='')
        self._login(self.admin)
        resp = self._get_ok(reverse('core:project_detail', args=[self.project.slug]))
        self.assertEqual(resp.status_code, 200)


class EmailLanguageTests(TestCase):
    """Les emails sont rendus dans la langue du destinataire, pas de l'acteur."""

    def _make_user(self, username, lang):
        user = User.objects.create_user(username, password='x', email=f'{username}@example.com')
        profile = user.profile
        profile.language = lang
        profile.save(update_fields=['language'])
        return user

    def test_password_reset_utilise_la_langue_du_destinataire(self):
        with mock.patch('core.notifications._is_email_configured', return_value=True):
            for lang in ('fr', 'en'):
                with self.subTest(lang=lang):
                    user = self._make_user(f'reset_{lang}', lang)
                    mail.outbox.clear()
                    ok, _msg = notifications.notify_password_reset(user, 'https://example.test/reset')
                    self.assertTrue(ok)
                    self.assertEqual(len(mail.outbox), 1)
                    with translation.override(lang):
                        expected_subject = translation.gettext(
                            '[CSIG] Réinitialisation de votre mot de passe'
                        )
                    self.assertEqual(mail.outbox[0].subject, expected_subject)

    def test_recipient_language_employe_lie(self):
        user = self._make_user('emp_en', 'en')
        employee = Employee.objects.create(name='Emp EN', role='Dev')
        user.profile.employee = employee
        user.profile.save(update_fields=['employee'])
        self.assertEqual(notifications._recipient_language(employee=employee), 'en')

    def test_recipient_language_email_only(self):
        self._make_user('lookup_en', 'en')
        self.assertEqual(
            notifications._recipient_language(email='lookup_en@example.com'), 'en'
        )

    def test_task_type_est_traduit(self):
        with translation.override('en'):
            self.assertEqual(notifications._task_type_label('jalon'), 'milestone')
        with translation.override('fr'):
            self.assertEqual(notifications._task_type_label('jalon'), 'jalon')

    def test_completed_subject_suit_la_langue(self):
        with translation.override('en'):
            self.assertEqual(
                notifications._completed_subject('jalon', 'T1'),
                '[CSIG] Milestone completed: T1',
            )
        with translation.override('fr'):
            self.assertEqual(
                notifications._completed_subject('jalon', 'T1'),
                '[CSIG] Jalon terminé : T1',
            )


class LanguagePreferenceTests(SmokeBase):
    """Le choix de langue de l'interface est persisté et fait foi par compte."""

    def test_set_language_persiste_sur_le_profil(self):
        self._login(self.employe_user)
        resp = self.client.post(
            reverse('set_language'),
            {'language': 'en', 'next': reverse('core:dashboard')},
        )
        self.assertIn(resp.status_code, (200, 302))
        self.employe_user.profile.refresh_from_db()
        self.assertEqual(self.employe_user.profile.language, 'en')

    def test_middleware_realigne_la_langue_sur_le_profil(self):
        profile = self.employe_user.profile
        profile.language = 'en'
        profile.save(update_fields=['language'])
        self._login(self.employe_user)
        resp = self._get_ok(reverse('core:dashboard'))
        self.assertEqual(resp.cookies.get('django_language').value, 'en')


class MemberGroupsTests(SmokeBase):
    """Onglet Équipe : les membres sont regroupés par rôle projet."""

    def test_equipe_regroupee_par_role(self):
        responsable = ProjectRole.objects.get(slug='responsable')
        ProjectMember.objects.create(
            project=self.project, employee=self.employee, project_role=responsable
        )
        self._login(self.admin)
        resp = self._get_ok(reverse('core:project_detail', args=[self.project.slug]))
        self.assertContains(resp, 'pm-group-grid')
        self.assertContains(resp, 'fa-crown')
        self.assertContains(resp, responsable.name)
        self.assertContains(resp, self.employee.name)


class ProjectMemberFormTests(SmokeBase):
    """Le formulaire membre (ajout et édition) se rend sans erreur."""

    def test_formulaire_ajout_ne_500_pas(self):
        self._login(self.admin)
        self._get_ok(reverse('core:project_member_add', args=[self.project.slug]))

    def test_formulaire_edition_ne_500_pas(self):
        role = ProjectRole.objects.get(slug='membre')
        pm = ProjectMember.objects.create(
            project=self.project, employee=self.employee, project_role=role
        )
        self._login(self.admin)
        resp = self._get_ok(reverse('core:project_member_edit', args=[pm.pk]))
        self.assertContains(resp, self.employee.name)


class FilterDirectionScopeTests(SmokeBase):
    """Les options du filtre « direction » s'adaptent à la portée réelle du
    profil : une direction dont aucune ressource n'est visible n'apparaît plus
    dans le menu, sinon le filtre propose des options qui mènent à du vide."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.autre_direction = Direction.objects.create(
            name='Direction Ailleurs', code='AUT'
        )
        cls.employe_ailleurs = Employee.objects.create(
            name='Employe Ailleurs', role='Analyste', direction=cls.autre_direction
        )

        # Rôle borné à la direction (ressources RH et demandes).
        cls.perms_scope = [
            Permission.objects.get_or_create(
                action='read', subject='Employee', condition='same_direction'
            )[0],
            Permission.objects.get_or_create(
                action='read', subject='Request', condition='same_direction'
            )[0],
        ]
        cls.role_scoped = Role.objects.create(name='Directeur test', slug='directeur_test')
        cls.role_scoped.permissions.set(cls.perms_scope)

        cls.dir_scoped = User.objects.create_user('dir_scope_test', password='x')
        cls.dir_scoped.profile.role = cls.role_scoped
        cls.dir_scoped.profile.direction = cls.direction
        cls.dir_scoped.profile.save()

        # Rôle lecture calendrier globale (permet l'accès, le filtre direction
        # ne liste que les directions qui participent à un événement visible).
        cls.role_cal = Role.objects.create(name='Agenda test', slug='agenda_test')
        cls.role_cal.permissions.add(
            Permission.objects.get_or_create(action='read', subject='Event', condition='')[0]
        )
        cls.cal_user = User.objects.create_user('cal_scope_test', password='x')
        cls.cal_user.profile.role = cls.role_cal
        cls.cal_user.profile.direction = cls.direction
        cls.cal_user.profile.save()

    def test_ressources_filtre_direction_scope_direction(self):
        """RH : un profil borné à sa direction ne voit que sa direction dans
        le filtre (pas la direction dont les employés sont invisibles)."""
        self._login(self.dir_scoped)
        resp = self._get_ok(reverse('core:resources') + '?tab=rh')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.direction.code)
        self.assertNotContains(resp, self.autre_direction.code)

    def test_requetes_filtre_direction_scope_direction(self):
        """Demandes : le filtre ne propose que les directions dont une demande
        est visible."""
        Request.objects.create(
            title='Besoin ailleurs', description='…',
            direction=self.autre_direction, created_by='Autre',
        )
        Request.objects.create(
            title='Besoin maison', description='…',
            direction=self.direction, created_by='Maison',
        )
        self._login(self.dir_scoped)
        resp = self._get_ok(reverse('core:requests'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.direction.code)
        self.assertNotContains(resp, self.autre_direction.code)

    def test_calendrier_filtre_direction_sans_evenement_invisible(self):
        """Calendrier : une direction sans aucun événement visible est absente
        du filtre, même pour un lecteur global."""
        Event.objects.create(
            title='Réunion maison', event_type='reunion',
            date=timezone.now().date() + timedelta(days=7),
            time=timezone.now().time(),
        ).participants.add(self.direction)
        self._login(self.cal_user)
        resp = self._get_ok(reverse('core:calendar'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.direction.code)
        self.assertNotContains(resp, self.autre_direction.code)
