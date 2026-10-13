"""Verifs du papier en-tête officiel CSIG sur tous les exports PDF.

Chaque export doit :
- répondre 200 avec un vrai PDF ;
- être au bon format de page (portrait/paysage) selon ``letterhead.EXPORT_ORIENTATIONS`` ;
- porter le fond officiel sur toutes les pages (bandeau en haut, pied en bas).

Le fond n'étant pas du texte, ces verifs sont structurelles (taille de page,
nombre de pages, et présence de l'image de fond sur chaque page) — pas de rendu
visuel.

Pour écrire un exemplaire de chaque export sur disque (contrôle manuel) :
    set LETTERHEAD_SAMPLES_DIR=export_tests
    python manage.py test core.tests_letterhead --settings=dashboard_csig.settings_test
"""
import os
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import (
    Direction, Employee, Project, ProjectActivity, LeaveRequest, Role,
)
from . import letterhead


def _load_fitz():
    try:
        import fitz  # PyMuPDF
    except Exception:
        return None
    return fitz


class LetterheadExportTests(TestCase):
    """Les 4 exports PDF portent le gabarit officiel CSIG."""

    @classmethod
    def setUpTestData(cls):
        cls.direction = Direction.objects.create(name='Direction Test', code='TST')
        cls.admin = cls._make_user('lh_admin', Role.objects.get(slug='admin'), superuser=True)
        cls.directeur = cls._make_user('lh_directeur', Role.objects.get(slug='directeur'))

        cls.employee = Employee.objects.create(
            name='Employe Test', role='Developpeur', direction=cls.direction,
        )

        today = timezone.now().date()
        cls.project = Project.objects.create(
            name='Projet Test', status='en_cours',
            start_date=today - timedelta(days=5), end_date=today + timedelta(days=30),
            manager='Manager Test', direction=cls.direction,
        )
        ProjectActivity.objects.create(
            project=cls.project, action='creation', description='Création du projet',
            user='Admin Test',
        )

        cls.leave = LeaveRequest.objects.create(
            employee=cls.employee, user=cls.admin, direction=cls.direction,
            leave_type='annuel',
            start_date=today + timedelta(days=1), end_date=today + timedelta(days=5),
            reason='Congé annuel de test', status='approuvee',
            final_decision='approuve', final_user=cls.admin,
            final_decision_at=timezone.now(),
        )

    @classmethod
    def _make_user(cls, username, role, superuser=False):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user(username, password='x', is_superuser=superuser)
        profile = user.profile
        profile.role = role
        profile.direction = cls.direction
        profile.save()
        return user

    def _export_cases(self):
        """(label, url, orientation attendue)."""
        return [
            ('employees', reverse('core:export_employees_pdf'), letterhead.orientation_for('employees')),
            ('reports', reverse('core:export_reports_pdf'), letterhead.orientation_for('reports')),
            ('project_activities', reverse('core:export_project_activities', args=[self.project.slug]),
             letterhead.orientation_for('project_activities')),
            ('leave_attestation', reverse('core:leave_pdf_download', args=[self.leave.id]),
             letterhead.orientation_for('leave_attestation')),
        ]

    def test_exports_sont_des_pdf_non_vides(self):
        self.client.force_login(self.admin)
        for label, url, _orientation in self._export_cases():
            with self.subTest(export=label):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200, f'{label} -> {resp.status_code}')
                self.assertEqual(resp['Content-Type'], 'application/pdf')
                self.assertTrue(resp.content.startswith(b'%PDF'), f'{label} : pas un PDF')
                self.assertGreater(len(resp.content), 2000, f'{label} : PDF suspicieusement petit')

    def test_orientation_de_page_par_export(self):
        fitz = _load_fitz()
        if fitz is None:
            self.skipTest('PyMuPDF (fitz) indisponible')

        expected = {
            'employees': 'landscape',
            'reports': 'portrait',
            'project_activities': 'landscape',
            'leave_attestation': 'portrait',
        }
        self.client.force_login(self.admin)
        for label, url, _orientation in self._export_cases():
            with self.subTest(export=label):
                resp = self.client.get(url)
                doc = fitz.open(stream=resp.content, filetype='pdf')
                self.assertGreaterEqual(doc.page_count, 1, f'{label} : aucune page')
                rect = doc[0].rect
                got = 'landscape' if rect.width > rect.height else 'portrait'
                self.assertEqual(got, expected[label], f'{label} : orientation {got} != {expected[label]}')
                doc.close()

    def test_fond_officiel_present_sur_chaque_page(self):
        """Chaque page doit contenir une image (le fond du gabarit)."""
        fitz = _load_fitz()
        if fitz is None:
            self.skipTest('PyMuPDF (fitz) indisponible')

        self.client.force_login(self.admin)
        for label, url, _orientation in self._export_cases():
            with self.subTest(export=label):
                resp = self.client.get(url)
                doc = fitz.open(stream=resp.content, filetype='pdf')
                for page_index in range(doc.page_count):
                    images = doc[page_index].get_images(full=True)
                    self.assertTrue(
                        images, f'{label} page {page_index + 1} : fond officiel absent',
                    )
                doc.close()

    def test_dump_exemplaires_si_demande(self):
        """Écrit un exemplaire de chaque export si LETTERHEAD_SAMPLES_DIR est défini."""
        out_dir = os.environ.get('LETTERHEAD_SAMPLES_DIR')
        if not out_dir:
            self.skipTest('LETTERHEAD_SAMPLES_DIR non défini')
        if not os.path.isabs(out_dir):
            out_dir = os.path.join(settings.BASE_DIR, out_dir)
        os.makedirs(out_dir, exist_ok=True)

        self.client.force_login(self.admin)
        for label, url, _orientation in self._export_cases():
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
            with open(os.path.join(out_dir, f'{label}.pdf'), 'wb') as fh:
                fh.write(resp.content)


class EmailLetterheadTests(TestCase):
    """Les emails portent l'en-tête et le pied officiels CSIG (images inline CID)."""

    @classmethod
    def setUpTestData(cls):
        cls.direction = Direction.objects.create(name='Direction Mail', code='MAI')

    def _user(self, username='mail_user', email='mail_user@example.com'):
        user = get_user_model().objects.create_user(username, password='x', email=email)
        profile = user.profile
        profile.role = Role.objects.get(slug='employe')
        profile.direction = self.direction
        profile.save()
        return user

    def test_base_email_reference_les_images_cid(self):
        html = render_to_string('emails/base_email.html', {
            'banner_title': 'Titre de test',
            'banner_subtitle': 'Sous-titre',
        })
        self.assertIn('cid:csig_header', html)
        self.assertIn('cid:csig_footer', html)
        self.assertNotIn('cid:csig_logo', html)

    def test_fichiers_images_email_presents(self):
        for filename in ('email-header.jpg', 'email-footer.jpg'):
            path = os.path.join(settings.BASE_DIR, 'assets', 'templates', filename)
            self.assertTrue(os.path.isfile(path), f'{filename} manquant')

    def test_envoi_attache_les_deux_images_inline(self):
        user = self._user()
        with mock.patch('core.notifications._is_email_configured', return_value=True):
            ok, _msg = self._notify(user)
        self.assertTrue(ok, _msg)
        self.assertEqual(len(mail.outbox), 1)

        mime = mail.outbox[0].message()
        cids = set()
        subtypes = set()
        for part in mime.walk():
            content_id = part.get('Content-ID')
            if content_id:
                cids.add(content_id.strip('<>'))
            if part.get_content_maintype() == 'multipart':
                subtypes.add(part.get_content_subtype())
        self.assertIn('csig_header', cids)
        self.assertIn('csig_footer', cids)
        self.assertIn('related', subtypes)

    def _notify(self, user):
        from . import notifications
        return notifications.notify_password_reset(user, 'https://example.test/reset')

