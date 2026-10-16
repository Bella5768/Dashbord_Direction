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
    Budget,
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


def pdf_text(content):
    """Texte décodé d'un PDF ReportLab (flux ASCII85 + Flate).

    Sans ce décodage, les chaînes du PDF sont compressées : un
    ``assertIn(b'Budget', resp.content)`` passerait ou échouerait au hasard.
    """
    import base64
    import re as _re
    import zlib

    chunks = []
    for match in _re.finditer(rb'stream\r?\n(.*?)endstream', content, _re.S):
        raw = match.group(1).strip(b'\r\n')
        if raw.endswith(b'~>'):
            raw = raw[:-2]
        try:
            chunks.append(zlib.decompress(base64.a85decode(raw)))
        except Exception:
            try:
                chunks.append(zlib.decompress(raw))
            except Exception:
                continue
    return b'\n'.join(chunks)


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


class ReportsDirecteurScopeTests(SmokeBase):
    """Le directeur accède aux Rapports, bornés à sa direction (export compris).

    Régression : la permission ``read Report`` du directeur est ``same_direction``
    (jamais globale). ``can_view_reports()`` doit malgré tout accorder le module
    (règle conditionnelle évaluée sans instance → False) et l'export, tandis que
    la page et le PDF ne présentent que la direction du directeur."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.dir_a = Direction.objects.create(name='Direction Rapport A', code='RPA')
        cls.dir_b = Direction.objects.create(name='Direction Rapport B', code='RPB')

        today = timezone.now().date()
        cls.proj_a = Project.objects.create(
            name='Projet Alpha Rapport', status='en_cours',
            start_date=today - timedelta(days=5), end_date=today + timedelta(days=30),
            manager='Manager Alpha', direction=cls.dir_a,
        )
        cls.proj_b = Project.objects.create(
            name='Projet Beta Rapport', status='en_cours',
            start_date=today - timedelta(days=5), end_date=today + timedelta(days=30),
            manager='Manager Beta', direction=cls.dir_b,
        )

        cls.directeur_a = cls._make_directeur('directeur_rapport_a', cls.dir_a)
        cls.directeur_b = cls._make_directeur('directeur_rapport_b', cls.dir_b)

    @classmethod
    def _make_directeur(cls, username, direction):
        user = User.objects.create_user(username, password='x')
        profile = user.profile
        profile.role = Role.objects.get(slug='directeur')
        profile.direction = direction
        profile.save()
        return user

    def test_permission_report_du_directeur_est_bornee_direction(self):
        prof = self.directeur_a.profile
        self.assertEqual(prof.read_scope('Report'), 'direction')
        self.assertFalse(prof.can_view_all_projects())
        self.assertTrue(prof.can_view_reports())

    def test_page_reports_ne_montre_que_sa_direction(self):
        self._login(self.directeur_a)
        resp = self._get_ok(reverse('core:reports'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.dir_a.code)
        self.assertNotContains(resp, self.dir_b.code)
        self.assertContains(resp, self.proj_a.name)
        self.assertNotContains(resp, self.proj_b.name)

    def test_export_reports_accessible_et_borne(self):
        self._login(self.directeur_a)
        resp = self.client.get(reverse('core:export_reports_pdf'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))
        # Le contenu du PDF ne doit pas nommer un projet d'une autre direction.
        text = pdf_text(resp.content)
        self.assertIn(b'Projet Alpha Rapport', text)
        self.assertNotIn(b'Projet Beta Rapport', text)


class BudgetRbacScopeTests(SmokeBase):
    """Le budget agrégé (Rapports, Ressources, Détail projet) respecte le
    périmètre RBAC du profil.

    Régression : la vue ``reports`` agrégait les budget sur les projets
    accessibles ET sur ``direction.budgets.all()`` sans passer par le scope
    Budget. Un membre sans droit Budget (ou un directeur d'une autre direction)
    voyait donc dans Rapports des montants invisibles dans Ressources, dont des
    lignes budgétaires de direction.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.dir_a = Direction.objects.create(name='Direction Budget A', code='BGA')
        cls.dir_b = Direction.objects.create(name='Direction Budget B', code='BGB')

        today = timezone.now().date()
        cls.proj_a = Project.objects.create(
            name='Projet Budget Alpha', status='en_cours',
            start_date=today - timedelta(days=5), end_date=today + timedelta(days=30),
            manager='Manager Alpha', direction=cls.dir_a,
        )
        cls.proj_b = Project.objects.create(
            name='Projet Budget Beta', status='en_cours',
            start_date=today - timedelta(days=5), end_date=today + timedelta(days=30),
            manager='Manager Beta', direction=cls.dir_b,
        )

        # Ligne projet sur A + ligne « direction » sur B (le cas qui fuyait).
        Budget.objects.create(project=cls.proj_a, allocated=10000000, consumed=2500000)
        Budget.objects.create(direction=cls.dir_b, allocated=99000000, consumed=1000000)

        cls.directeur_a = cls._make_user('budget_directeur_a', cls.dir_a, 'directeur')

        # Régression : l'appartenance (membre / manager) rend un projet d'une
        # AUTRE direction *accessible* (ouvrable) sans ouvrir le droit Budget.
        # Le budget inline de ce projet ne doit donc jamais être agrégé.
        cls.proj_b_leak = Project.objects.create(
            name='Projet Budget Beta Membre', status='en_cours',
            start_date=today - timedelta(days=5), end_date=today + timedelta(days=30),
            manager='Manager Beta', direction=cls.dir_b,
            budget=5000000, budget_consumed=1000000,
        )
        # Budget inline d'un projet de la VRAIE direction : doit rester visible
        # (non-régression de la restriction).
        cls.proj_a_inline = Project.objects.create(
            name='Projet Budget Alpha Inline', status='en_cours',
            start_date=today - timedelta(days=5), end_date=today + timedelta(days=30),
            manager='Manager Alpha', direction=cls.dir_a,
            budget=5000000, budget_consumed=2500000,
        )
        _dir_a_emp = Employee.objects.create(
            name='Directeur Budget A', role='Directeur', direction=cls.dir_a
        )
        cls.directeur_a.profile.employee = _dir_a_emp
        cls.directeur_a.profile.save()
        ProjectMember.objects.create(project=cls.proj_b_leak, employee=_dir_a_emp)

        # Lecteur Projets + Rapports, SANS aucun droit Budget.
        role_nobudget = Role.objects.create(name='Lecteur sans budget', slug='lecteur_sans_budget')
        role_nobudget.permissions.set([
            Permission.objects.get_or_create(action='read', subject='Project', condition='')[0],
            Permission.objects.get_or_create(action='read', subject='Report', condition='')[0],
        ])
        cls.viewer = cls._make_user('budget_viewer', cls.dir_a, role_nobudget)

        # Lecteur RH : droit Employee seulement, aucun droit Budget.
        role_rh = Role.objects.create(name='Lecteur RH seul', slug='lecteur_rh_seul')
        role_rh.permissions.set([
            Permission.objects.get_or_create(action='read', subject='Employee', condition='same_direction')[0],
        ])
        cls.rh_only = cls._make_user('budget_rh_only', cls.dir_a, role_rh)

        # Lecteur Budget : droit Budget seulement, aucun droit Employee.
        role_budget = Role.objects.create(name='Lecteur Budget seul', slug='lecteur_budget_seul')
        role_budget.permissions.set([
            Permission.objects.get_or_create(action='read', subject='Budget', condition='same_direction')[0],
        ])
        cls.budget_only = cls._make_user('budget_only', cls.dir_a, role_budget)

    @classmethod
    def _make_user(cls, username, direction, role):
        user = User.objects.create_user(username, password='x')
        profile = user.profile
        profile.role = role if isinstance(role, Role) else Role.objects.get(slug=role)
        profile.direction = direction
        profile.save()
        return user

    def test_lecteur_sans_droit_budget_ne_voit_aucune_ui_budget_dans_reports(self):
        prof = self.viewer.profile
        self.assertFalse(prof.can_view_budgets())
        self.assertTrue(prof.can_view_reports())

        self._login(self.viewer)
        resp = self._get_ok(reverse('core:reports'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'id="tab-budget"')
        self.assertNotContains(resp, 'budgetByDirectionChart')
        self.assertNotContains(resp, 'stat-box amber')

    def test_lecteur_sans_droit_budget_recoit_403_sur_onglet_budget(self):
        self._login(self.viewer)
        resp = self.client.get(reverse('core:resources') + '?tab=budget')
        self.assertEqual(resp.status_code, 403)

    def test_directeur_ne_voit_pas_le_budget_de_l_autre_direction_dans_reports(self):
        self._login(self.directeur_a)
        resp = self._get_ok(reverse('core:reports'))
        self.assertEqual(resp.status_code, 200)
        # L'onglet Budget est bien rendu pour un profil habilité…
        self.assertContains(resp, 'budgetByDirectionChart')
        # …et le taux n'inclut pas le budget de l'autre direction : agrégat de la
        # direction A = (2,5M + 2,5M) / (10M + 5M) = 33 % (30 % si B fuyait).
        self.assertContains(resp, '33%')
        self.assertNotContains(resp, '30%')

    def test_directeur_budget_ressources_borne_a_sa_direction(self):
        self._login(self.directeur_a)
        resp = self._get_ok(reverse('core:resources') + '?tab=budget')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.dir_a.code)
        self.assertNotContains(resp, self.dir_b.code)

    def test_ressources_onglet_budget_absent_sans_droit_budget(self):
        self.assertTrue(self.rh_only.profile.can_view_employees())
        self.assertFalse(self.rh_only.profile.can_view_budgets())

        self._login(self.rh_only)
        resp = self._get_ok(reverse('core:resources'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'data-tab="budget"')
        self.assertContains(resp, 'data-tab="rh"')

    def test_ressources_onglet_budget_demande_est_rabattu_sur_rh(self):
        self._login(self.rh_only)
        resp = self._get_ok(reverse('core:resources') + '?tab=budget')
        self.assertEqual(resp.status_code, 200)
        # Aucune donnée budget n'est transmise au client.
        self.assertNotContains(resp, 'budgetRowsData')
        self.assertNotContains(resp, 'budgetFilterOptions')

    def test_ressources_onglet_rh_absent_sans_droit_employes(self):
        self.assertTrue(self.budget_only.profile.can_view_budgets())
        self.assertFalse(self.budget_only.profile.can_view_employees())
        self._login(self.budget_only)
        resp = self._get_ok(reverse('core:resources'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-tab="budget"')
        self.assertNotContains(resp, 'data-tab="rh"')

    def test_filtre_direction_absent_sans_acces_budget_global(self):
        """Le filtre Direction n'a de sens que pour un accès budget global :
        un directeur, borné à sa direction, ne doit pas le voir."""
        self.assertFalse(
            self.directeur_a.profile.can_view_all_budget_directions()
        )
        self._login(self.directeur_a)
        resp = self._get_ok(reverse('core:resources') + '?tab=budget')
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'id="bfDirection"')

    def test_filtre_direction_present_avec_acces_budget_global(self):
        dg = self._make_user('budget_dg_global', self.dir_a, 'directeur_general')
        self.assertTrue(dg.profile.can_view_all_budget_directions())
        self._login(dg)
        resp = self._get_ok(reverse('core:resources') + '?tab=budget')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="bfDirection"')

    def test_scoped_budget_rows_ne_renvoie_que_le_perimetre_du_profil(self):
        """Primitive partagée par Ressources, Rapports et l'export PDF."""
        from .views import _scoped_budget_rows, get_accessible_projects_qs

        rows, inline = _scoped_budget_rows(
            self.directeur_a.profile, get_accessible_projects_qs(self.directeur_a)
        )
        # Aucune ligne du périmètre B (ni rattachée à la direction B, ni à un
        # projet de B) ne doit sortir.
        self.assertEqual({b.direction_id for b in rows if b.direction_id}, set())
        self.assertEqual({b.project.direction_id for b in rows}, {self.dir_a.id})
        # Les budgets inline suivent le même périmètre : ceux de la direction du
        # profil oui, ceux d'un projet « membre » d'une autre direction non.
        inline_ids = {p.id for p in inline}
        self.assertIn(self.proj_a_inline.id, inline_ids)
        self.assertNotIn(self.proj_b_leak.id, inline_ids)

    def test_budget_ne_fuit_pas_par_appartenance_a_un_projet_hors_direction(self):
        """Régression : membre d'un projet d'une autre direction, le directeur
        ouvre le projet mais ne doit pas voir son budget inline."""
        from .views import _scoped_budget_rows, get_accessible_projects_qs

        accessible = get_accessible_projects_qs(self.directeur_a)
        self.assertIn(
            self.proj_b_leak.id, set(accessible.values_list('id', flat=True))
        )
        rows, inline = _scoped_budget_rows(self.directeur_a.profile, accessible)
        self.assertNotIn(self.proj_b_leak.id, {p.id for p in inline})
        self.assertNotIn(self.dir_b.id, {b.direction_id for b in rows})

    def test_ressources_budget_directeur_ignore_le_projet_membre_hors_direction(self):
        self._login(self.directeur_a)
        resp = self._get_ok(reverse('core:resources') + '?tab=budget')
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Projet Budget Beta Membre')
        self.assertContains(resp, 'Projet Budget Alpha Inline')

    def test_export_pdf_rapports_sans_droit_budget_n_expose_pas_le_budget(self):
        self.assertFalse(self.viewer.profile.can_view_budgets())
        self._login(self.viewer)
        resp = self.client.get(reverse('core:export_reports_pdf'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b'%PDF'))
        text = pdf_text(resp.content)
        self.assertNotIn(b'Budget consomm', text)
        self.assertIn(b'Projets totaux', text)

    def test_export_pdf_rapports_directeur_contient_le_budget_de_sa_direction(self):
        self.assertTrue(self.directeur_a.profile.can_view_budgets())
        self._login(self.directeur_a)
        resp = self.client.get(reverse('core:export_reports_pdf'))
        self.assertEqual(resp.status_code, 200)
        text = pdf_text(resp.content)
        self.assertIn(b'Budget consomm', text)
        # Taux agrégé = (2,5M + 2,5M) / (10M + 5M) = 33 %. Le budget inline du
        # projet « membre » de la direction B (1M consommé) est exclu : sinon 30 %.
        self.assertIn(b'33%', text)

    def test_panneau_budget_projet_masque_sans_droit(self):
        self._login(self.viewer)
        resp = self._get_ok(reverse('core:project_detail', args=[self.proj_a.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'dash-budget-' + str(self.proj_a.pk))


class ProjectFormBudgetNegativeTests(SmokeBase):
    """Le budget d'un projet ne peut pas être négatif (alignement client/serveur).

    project_form.html refuse une valeur négative côté client ; ce test vérifie
    que ProjectForm.clean_budget / clean_budget_consumed appliquent la même règle
    côté serveur (et gardent 0 lorsque le champ est vide)."""

    def _form_data(self, **overrides):
        today = timezone.now().date()
        data = {
            'name': 'Projet Budget Test',
            'direction': self.direction.pk,
            'status': 'en_cours',
            'priority': 'moyenne',
            'currency': 'GNF',
            'start_date': (today - timedelta(days=1)).isoformat(),
            'end_date': (today + timedelta(days=10)).isoformat(),
            'manager_employee': self.employee.pk,
            'budget': '1000',
            'budget_consumed': '500',
        }
        data.update(overrides)
        return data

    def test_budget_negatif_rejete(self):
        from .forms_project import ProjectForm
        form = ProjectForm(data=self._form_data(budget='-1'), user=self.admin)
        self.assertFalse(form.is_valid())
        self.assertIn('budget', form.errors)

    def test_budget_consomme_negatif_rejete(self):
        from .forms_project import ProjectForm
        form = ProjectForm(data=self._form_data(budget_consumed='-1'), user=self.admin)
        self.assertFalse(form.is_valid())
        self.assertIn('budget_consumed', form.errors)

    def test_budget_vide_devient_zero(self):
        from .forms_project import ProjectForm
        form = ProjectForm(data=self._form_data(budget='', budget_consumed=''), user=self.admin)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['budget'], 0)
        self.assertEqual(form.cleaned_data['budget_consumed'], 0)


class ProjectFormDateRequiredTests(SmokeBase):
    """Les dates début/fin d'un projet peuvent être inconnues à la création
    (colonnes NULL autorisées depuis la migration dédiée).

    Le formulaire accepte donc un projet sans dates, en création comme en
    édition ; lorsqu'une date est laissée vide à l'édition, la valeur existante
    est conservée."""

    def _post_data(self, **overrides):
        today = timezone.now().date()
        data = {
            'name': 'Projet sans date de fin',
            'direction': self.direction.pk,
            'status': 'en_cours',
            'priority': 'moyenne',
            'currency': 'GNF',
            'start_date': (today - timedelta(days=1)).isoformat(),
            'end_date': (today + timedelta(days=10)).isoformat(),
            'manager_employee': self.employee.pk,
            'budget': '0',
            'budget_consumed': '0',
        }
        data.update(overrides)
        return data

    def test_dates_optionnelles_a_la_creation(self):
        from .forms_project import ProjectForm
        form = ProjectForm(data=self._post_data(start_date='', end_date=''), user=self.admin)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['start_date'])
        self.assertIsNone(form.cleaned_data['end_date'])

    def test_creation_sans_dates_cree_un_projet(self):
        self._login(self.admin)
        before = Project.objects.count()
        resp = self.client.post(
            reverse('core:project_create'),
            self._post_data(start_date='', end_date=''),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Project.objects.count(), before + 1)
        created = Project.objects.latest('created_at')
        self.assertIsNone(created.end_date)

    def test_creation_avec_date_de_fin_seule(self):
        self._login(self.admin)
        resp = self.client.post(
            reverse('core:project_create'),
            self._post_data(start_date=''),
        )
        self.assertEqual(resp.status_code, 302)
        created = Project.objects.latest('created_at')
        self.assertIsNone(created.start_date)
        self.assertIsNotNone(created.end_date)

    def test_edition_dates_optionnelles_conserve_lexistant(self):
        self._login(self.admin)
        before = (self.project.start_date, self.project.end_date)
        resp = self.client.post(
            reverse('core:project_edit', args=[self.project.slug]),
            self._post_data(name=self.project.name, start_date='', end_date=''),
        )
        self.assertEqual(resp.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual((self.project.start_date, self.project.end_date), before)


class ValidationCrashGuardsTests(SmokeBase):
    """Aucune erreur de validation ne doit produire un 500 (audit validation).

    Même racine que ProjectFormDateRequiredTests : les clés UUID (default=uuid4)
    rendent self.instance.pk toujours vrai. Toute logique création/édition qui
    teste `pk` au lieu de `_state.adding` fait passer une soumission invalide
    puis save() lève IntegrityError (NOT NULL ou unique_together) → 500 au lieu
    d'un re-rendu du formulaire avec les erreurs.
    """

    def test_membre_sans_employe_retourne_formulaire(self):
        self._login(self.admin)
        before = ProjectMember.objects.count()
        resp = self.client.post(
            reverse('core:project_member_add', args=[self.project.slug]),
            {'employee': '', 'project_role': ''},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ProjectMember.objects.count(), before)

    def test_membre_duplique_retourne_formulaire(self):
        role = ProjectRole.objects.get(slug='membre')
        ProjectMember.objects.create(project=self.project, employee=self.employee, project_role=role)
        self._login(self.admin)
        before = ProjectMember.objects.count()
        resp = self.client.post(
            reverse('core:project_member_add', args=[self.project.slug]),
            {'employee': self.employee.pk, 'project_role': role.pk},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ProjectMember.objects.count(), before)

    def test_membre_valide_se_creer(self):
        role = ProjectRole.objects.get(slug='membre')
        self._login(self.admin)
        resp = self.client.post(
            reverse('core:project_member_add', args=[self.project.slug]),
            {'employee': self.employee.pk, 'project_role': role.pk},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(ProjectMember.objects.filter(project=self.project, employee=self.employee).exists())

    def test_milestone_ordre_auto_incremente_a_la_creation(self):
        from .forms_project import MilestoneForm
        form = MilestoneForm(project=self.project)
        self.assertEqual(form.fields['order'].initial, self.leaf.order + 1)

    def test_leave_prefill_employe_direction_a_la_creation(self):
        from .forms_leave import LeaveRequestForm
        form = LeaveRequestForm(user=self.employe_user)
        self.assertEqual(form.initial.get('employee'), self.employee.pk)
        self.assertEqual(form.initial.get('direction'), self.direction.pk)


class ValidationCrashGuardsHttpTests(SmokeBase):
    """Aucune donnée invalide envoyée par un client ne doit produire un 500 :
    formulaire invalide → re-rendu/erreur propre, jamais IntegrityError ou
    ValidationError non maîtrisée (audit validation views)."""

    def _milestone_post(self, **overrides):
        data = {
            'name': 'Jalon invariant',
            'due_date': (timezone.now().date() + timedelta(days=6)).isoformat(),
            'need': '',
            'status': 'en_cours',
            'manual_progress': '',
            'completed': '',
            'order': '1',
        }
        data.update(overrides)
        return data

    def test_membre_edit_sans_employe_conserve_existant(self):
        role = ProjectRole.objects.get(slug='membre')
        member = ProjectMember.objects.create(
            project=self.project, employee=self.employee, project_role=role
        )
        self._login(self.admin)
        before = member.employee_id
        resp = self.client.post(
            reverse('core:project_member_edit', args=[member.pk]),
            {'employee': '', 'project_role': role.pk},
        )
        self.assertEqual(resp.status_code, 302)
        member.refresh_from_db()
        self.assertEqual(member.employee_id, before)

    def test_direction_delete_protegee_retourne_404_ou_message(self):
        from .models import LeaveRequest
        LeaveRequest.objects.create(
            employee=self.employee, direction=self.direction, leave_type='annuel',
            start_date=timezone.now().date() + timedelta(days=20),
            end_date=timezone.now().date() + timedelta(days=24),
            reason='Audit',
        )
        self._login(self.admin)
        resp = self.client.post(reverse('core:direction_delete', args=[self.direction.slug]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Direction.objects.filter(pk=self.direction.pk).exists())

    def test_activation_avec_deux_comptes_same_email_pas_de_500(self):
        User.objects.create_user('inactif_a', email=self.employee.email, is_active=False)
        User.objects.create_user('inactif_b', email=self.employee.email, is_active=False)
        resp = self.client.post(reverse('core:request_new_activation'), {'email': self.employee.email})
        self.assertEqual(resp.status_code, 200)

    def test_milestone_assigned_to_invalide_pas_de_500(self):
        self._login(self.admin)
        before = Milestone.objects.count()
        resp = self.client.post(
            reverse('core:milestone_create', args=[self.project.slug]),
            self._milestone_post(assigned_to=['pas-un-uuid', 'non-plus']),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Milestone.objects.count(), before)

    def test_milestone_edit_assigned_to_invalide_pas_de_500(self):
        self._login(self.admin)
        resp = self.client.post(
            reverse('core:milestone_edit', args=[self.leaf.slug]),
            self._milestone_post(name=self.leaf.name, assigned_to=['invalide']),
        )
        self.assertEqual(resp.status_code, 200)

    def test_import_json_malforme_pas_de_500(self):
        self._login(self.admin)
        resp = self.client.post(
            reverse('core:project_import'),
            {'step': 'import_json', 'json_text': '{"pas": "une liste"}', 'direction_id': ''},
        )
        self.assertEqual(resp.status_code, 200)

    def test_import_json_direction_id_invalide_pas_de_500(self):
        self._login(self.admin)
        resp = self.client.post(
            reverse('core:project_import'),
            {'step': 'import_json', 'json_text': '[]', 'direction_id': 'abc'},
        )
        self.assertLess(resp.status_code, 500)

    def test_slug_non_uuid_retourne_404(self):
        self._login(self.admin)
        resp = self.client.get(reverse('core:project_detail', args=['zzz-pas-un-uuid']))
        self.assertEqual(resp.status_code, 404)
