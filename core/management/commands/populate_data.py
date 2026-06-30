from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, time, timedelta
from core.models import Direction, Project, Milestone, Document, Partner, Event, Request, Employee, Budget


today = date.today()


class Command(BaseCommand):
    help = 'Populate database with rich sample data for CSIG Dashboard'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Clear existing data before populating')

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            for Model in [Milestone, Project, Document, Partner, Event, Request, Employee, Budget]:
                Model.objects.all().delete()
            Direction.objects.all().delete()
            self.stdout.write('  Done.')

        self.stdout.write('Creating sample data...')
        directions = self._create_directions()
        self._create_budgets(directions)
        employees  = self._create_employees(directions)
        self._create_projects(directions, employees)
        self._create_documents(directions)
        self._create_partners()
        self._create_events(directions)
        self._create_requests(directions)
        self.stdout.write(self.style.SUCCESS('Sample data created successfully!'))

    # ------------------------------------------------------------------ #
    def _mk(self, Model, lookup, **defaults):
        obj, created = Model.objects.get_or_create(**lookup, defaults=defaults)
        if created:
            self.stdout.write(f'  + {Model.__name__}: {obj}')
        return obj

    # ------------------------------------------------------------------ #
    def _create_directions(self):
        data = [
            ('Transition Numérique',        'TN',  '#3b82f6'),
            ('Intelligence Artificielle',   'IA',  '#059669'),
            ('Education et Vulgarisation',  'EDU', '#d97706'),
            ('Communication',               'COM', '#8b5cf6'),
            ('Systèmes d\'Information',     'DSI', '#ef4444'),
        ]
        dirs = {}
        for name, code, color in data:
            dirs[code] = self._mk(Direction, {'code': code}, name=name, color=color)
        return dirs

    # ------------------------------------------------------------------ #
    def _create_budgets(self, d):
        data = [
            ('TN',  500_000_000, 237_500_000),
            ('IA',  280_000_000, 112_000_000),
            ('EDU', 150_000_000,  82_500_000),
            ('COM',  90_000_000,  54_000_000),
            ('DSI', 320_000_000, 176_000_000),
        ]
        for code, allocated, consumed in data:
            self._mk(Budget, {'direction': d[code]}, allocated=allocated, consumed=consumed)

    # ------------------------------------------------------------------ #
    def _create_employees(self, d):
        data = [
            # TN
            ('Mamadou Diallo',     'TN',  'Directeur',                    85, '+224 622 11 22 33', 'mamadou.diallo@csig.edu.gn',    'Gestion de projet, Innovation, Leadership, Stratégie'),
            ('Fatoumata Camara',   'TN',  'Chef de projet senior',        90, '+224 622 44 55 66', 'fatoumata.camara@csig.edu.gn',  'Incubation, Startups, Mentorat, Agile'),
            ('Ibrahima Sow',       'TN',  'Directeur Financier',          70, '+224 624 77 88 99', 'ibrahima.sow@csig.edu.gn',      'Finance, Comptabilité, Budget, Audit'),
            ('Mariama Baldé',      'TN',  'Responsable Partenariats',     65, '+224 628 12 34 56', 'mariama.balde@csig.edu.gn',     'Négociation, Relations institutionnelles, Français, Anglais'),
            ('Thierno Bah',        'TN',  'Analyste Système',             75, '+224 621 98 76 54', 'thierno.bah@csig.edu.gn',       'Python, SQL, Systèmes d\'information, Data'),
            # IA
            ('Oumar Barry',        'IA',  'Directeur Technique',          75, '+224 625 11 22 33', 'oumar.barry@csig.edu.gn',       'Architecture logicielle, DevOps, IoT, Cloud'),
            ('Kadiatou Baldé',     'IA',  'Développeuse Senior',          95, '+224 629 44 55 66', 'kadiatou.balde@csig.edu.gn',    'React, Node.js, Python, Machine Learning'),
            ('Alpha Condé',        'IA',  'Data Scientist',               80, '+224 623 77 88 99', 'alpha.conde@csig.edu.gn',       'Python, TensorFlow, Pandas, Data Analysis'),
            ('Hawa Diallo',        'IA',  'Développeuse IA',              70, '+224 626 12 34 56', 'hawa.diallo@csig.edu.gn',       'Deep Learning, NLP, Computer Vision, Keras'),
            ('Boubacar Keïta',     'IA',  'Ingénieur DevOps',             85, '+224 620 98 76 54', 'boubacar.keita@csig.edu.gn',    'Docker, Kubernetes, CI/CD, Linux, Terraform'),
            # EDU
            ('Sekou Touré',        'EDU', 'Directeur Education',          80, '+224 627 11 22 33', 'sekou.toure@csig.edu.gn',       'Pédagogie, Formation, Vulgarisation, E-Learning'),
            ('Mohamed Sylla',      'EDU', 'Analyste Pédagogique',         60, '+224 631 44 55 66', 'mohamed.sylla@csig.edu.gn',     'Analyse, Data, Reporting, Curriculum'),
            ('Aminata Soumah',     'EDU', 'Coordinatrice Programmes',     72, '+224 632 77 88 99', 'aminata.soumah@csig.edu.gn',    'Gestion de programme, Logistique, Coordination'),
            ('Lansana Kourouma',   'EDU', 'Formateur Principal',          68, '+224 633 12 34 56', 'lansana.kourouma@csig.edu.gn',  'Formation, Informatique, Bureautique, Présentation'),
            ('Djénabou Traoré',    'EDU', 'Chargée de Recherche',         65, '+224 634 98 76 54', 'djenabou.traore@csig.edu.gn',   'Recherche, Rédaction, Publication, Analyse'),
            # COM
            ('Aissatou Bah',       'COM', 'Directrice Communication',     65, '+224 635 11 22 33', 'aissatou.bah@csig.edu.gn',      'Communication, Marketing, Relations publiques, Médias'),
            ('Ibrahima Barry',     'COM', 'Chargé de Communication',      70, '+224 636 44 55 66', 'ibrahima.barry@csig.edu.gn',    'Réseaux sociaux, Rédaction, Photographie, Vidéo'),
            ('Nene Camara',        'COM', 'Designer Graphique',           75, '+224 637 77 88 99', 'nene.camara@csig.edu.gn',       'Illustrator, Photoshop, Figma, UI/UX, Canva'),
            ('Youssouf Diallo',    'COM', 'Chargé des Relations Presse',  60, '+224 638 12 34 56', 'youssouf.diallo@csig.edu.gn',   'Journalisme, Relations presse, Veille média, Rédaction'),
            # DSI
            ('Aboubacar Sidibé',   'DSI', 'Directeur des Systèmes',       80, '+224 639 11 22 33', 'aboubacar.sidibe@csig.edu.gn',  'Infrastructure, Sécurité, Réseaux, Management'),
            ('Mariama Kouyaté',    'DSI', 'Administratrice Système',      75, '+224 640 44 55 66', 'mariama.kouyate@csig.edu.gn',   'Linux, Windows Server, Active Directory, VMware'),
            ('Elhadj Diallo',      'DSI', 'Ingénieur Réseau',             70, '+224 641 77 88 99', 'elhadj.diallo@csig.edu.gn',     'Cisco, VLAN, Firewall, VPN, Mikrotik'),
            ('Fatoumata Soumah',   'DSI', 'Développeuse Web',             80, '+224 642 12 34 56', 'fatoumata.soumah@csig.edu.gn',  'Django, HTML/CSS, JavaScript, PostgreSQL, API REST'),
            ('Saliou Bah',         'DSI', 'Support Technique',            55, '+224 643 98 76 54', 'saliou.bah@csig.edu.gn',        'Helpdesk, Windows, Hardware, Réseau, MS Office'),
        ]
        emps = {}
        for name, code, role, workload, phone, email, skills in data:
            emp = self._mk(
                Employee, {'name': name},
                direction=d[code], role=role, workload=workload,
                phone=phone, email=email, skills=skills,
            )
            emps[name] = emp
        return emps

    # ------------------------------------------------------------------ #
    def _create_projects(self, d, emps):
        projects_data = [
            {
                'name': 'Plateforme E-Learning CSIG',
                'direction': 'EDU', 'status': 'en_cours', 'progress': 65,
                'budget': 150_000_000, 'budget_consumed': 97_500_000,
                'start_date': today - timedelta(days=160),
                'end_date':   today + timedelta(days=60),
                'priority': 'haute', 'manager': 'Sekou Touré',
                'description': 'Développement d\'une plateforme de formation en ligne pour les jeunes innovateurs guinéens.',
                'milestones': [
                    ('Conception UX/UI',          'termine',  True,  today - timedelta(days=120)),
                    ('Développement Frontend',    'termine',  True,  today - timedelta(days=90)),
                    ('Développement Backend',     'en_cours', False, today + timedelta(days=15)),
                    ('Intégration & Tests',       'a_faire',  False, today + timedelta(days=40)),
                    ('Déploiement & Formation',   'a_faire',  False, today + timedelta(days=58)),
                ],
            },
            {
                'name': 'Incubateur Startups Tech',
                'direction': 'TN', 'status': 'en_cours', 'progress': 40,
                'budget': 300_000_000, 'budget_consumed': 120_000_000,
                'start_date': today - timedelta(days=130),
                'end_date':   today + timedelta(days=230),
                'priority': 'haute', 'manager': 'Fatoumata Camara',
                'description': 'Création d\'un espace d\'incubation pour les startups technologiques guinéennes.',
                'milestones': [
                    ('Étude de faisabilité',    'termine',  True,  today - timedelta(days=100)),
                    ('Aménagement des locaux',  'en_cours', False, today + timedelta(days=30)),
                    ('Recrutement mentors',     'a_faire',  False, today + timedelta(days=90)),
                    ('Lancement programme',     'a_faire',  False, today + timedelta(days=200)),
                ],
            },
            {
                'name': 'Système de Gestion Documentaire',
                'direction': 'DSI', 'status': 'termine', 'progress': 100,
                'budget': 50_000_000, 'budget_consumed': 47_000_000,
                'start_date': today - timedelta(days=300),
                'end_date':   today - timedelta(days=30),
                'priority': 'moyenne', 'manager': 'Aboubacar Sidibé',
                'description': 'Numérisation et gestion électronique des documents administratifs du CSIG.',
                'milestones': [
                    ('Analyse des besoins',     'termine', True,  today - timedelta(days=250)),
                    ('Développement',           'termine', True,  today - timedelta(days=150)),
                    ('Migration données',       'termine', True,  today - timedelta(days=80)),
                    ('Formation utilisateurs',  'termine', True,  today - timedelta(days=35)),
                ],
            },
            {
                'name': 'Réseau IoT Campus',
                'direction': 'IA', 'status': 'planifie', 'progress': 10,
                'budget': 200_000_000, 'budget_consumed': 20_000_000,
                'start_date': today + timedelta(days=15),
                'end_date':   today + timedelta(days=200),
                'priority': 'moyenne', 'manager': 'Oumar Barry',
                'description': 'Déploiement d\'un réseau IoT pour la gestion intelligente du campus CSIG.',
                'milestones': [
                    ('Étude technique',          'termine',  True,  today - timedelta(days=10)),
                    ('Acquisition équipements',  'a_faire',  False, today + timedelta(days=45)),
                    ('Installation capteurs',    'a_faire',  False, today + timedelta(days=110)),
                    ('Configuration & Tests',    'a_faire',  False, today + timedelta(days=180)),
                ],
            },
            {
                'name': 'Campagne Sensibilisation Innovation',
                'direction': 'COM', 'status': 'termine', 'progress': 100,
                'budget': 25_000_000, 'budget_consumed': 23_500_000,
                'start_date': today - timedelta(days=400),
                'end_date':   today - timedelta(days=180),
                'priority': 'basse', 'manager': 'Aissatou Bah',
                'description': 'Campagne nationale de sensibilisation à l\'innovation et aux sciences.',
                'milestones': [
                    ('Conception campagne',   'termine', True, today - timedelta(days=380)),
                    ('Production contenus',   'termine', True, today - timedelta(days=300)),
                    ('Diffusion médias',      'termine', True, today - timedelta(days=230)),
                    ('Évaluation impact',     'termine', True, today - timedelta(days=185)),
                ],
            },
            {
                'name': 'Partenariat Université de Conakry',
                'direction': 'EDU', 'status': 'en_cours', 'progress': 55,
                'budget': 75_000_000, 'budget_consumed': 41_250_000,
                'start_date': today - timedelta(days=180),
                'end_date':   today + timedelta(days=60),
                'priority': 'haute', 'manager': 'Sekou Touré',
                'description': 'Établissement d\'un partenariat stratégique avec l\'Université de Conakry.',
                'milestones': [
                    ('Négociations initiales', 'termine',  True,  today - timedelta(days=150)),
                    ('Signature convention',   'termine',  True,  today - timedelta(days=100)),
                    ('Mise en œuvre phase 1',  'en_cours', False, today + timedelta(days=20)),
                    ('Évaluation mi-parcours', 'a_faire',  False, today + timedelta(days=55)),
                ],
            },
            {
                'name': 'Cybersécurité Infrastructure CSIG',
                'direction': 'DSI', 'status': 'en_cours', 'progress': 30,
                'budget': 180_000_000, 'budget_consumed': 54_000_000,
                'start_date': today - timedelta(days=60),
                'end_date':   today + timedelta(days=150),
                'priority': 'haute', 'manager': 'Aboubacar Sidibé',
                'description': 'Audit et renforcement de la sécurité de l\'infrastructure informatique du CSIG.',
                'milestones': [
                    ('Audit de sécurité',          'termine',  True,  today - timedelta(days=30)),
                    ('Correctifs critiques',        'en_cours', False, today + timedelta(days=20)),
                    ('Mise en place SOC',           'a_faire',  False, today + timedelta(days=80)),
                    ('Formation équipes',           'a_faire',  False, today + timedelta(days=130)),
                    ('Certification ISO 27001',     'a_faire',  False, today + timedelta(days=148)),
                ],
            },
            {
                'name': 'Application Mobile Citoyenne',
                'direction': 'TN', 'status': 'planifie', 'progress': 5,
                'budget': 120_000_000, 'budget_consumed': 6_000_000,
                'start_date': today + timedelta(days=30),
                'end_date':   today + timedelta(days=270),
                'priority': 'haute', 'manager': 'Mamadou Diallo',
                'description': 'Développement d\'une application mobile d\'accès aux services numériques pour les citoyens.',
                'milestones': [
                    ('Cahier des charges',    'en_cours', False, today + timedelta(days=35)),
                    ('Design UX/UI',          'a_faire',  False, today + timedelta(days=80)),
                    ('Développement MVP',     'a_faire',  False, today + timedelta(days=160)),
                    ('Tests bêta',            'a_faire',  False, today + timedelta(days=220)),
                    ('Lancement officiel',    'a_faire',  False, today + timedelta(days=265)),
                ],
            },
            {
                'name': 'Centre de Données National',
                'direction': 'DSI', 'status': 'suspendu', 'progress': 20,
                'budget': 450_000_000, 'budget_consumed': 90_000_000,
                'start_date': today - timedelta(days=240),
                'end_date':   today + timedelta(days=120),
                'priority': 'haute', 'manager': 'Aboubacar Sidibé',
                'description': 'Construction et équipement d\'un centre de données souverain pour les institutions guinéennes.',
                'milestones': [
                    ('Étude de site',           'termine',  True,  today - timedelta(days=200)),
                    ('Appel d\'offres BTP',     'termine',  True,  today - timedelta(days=160)),
                    ('Travaux infrastructure',  'bloque',   False, today + timedelta(days=60)),
                    ('Équipements serveurs',    'a_faire',  False, today + timedelta(days=100)),
                ],
            },
            {
                'name': 'Plateforme IA Agricole',
                'direction': 'IA', 'status': 'en_cours', 'progress': 45,
                'budget': 160_000_000, 'budget_consumed': 72_000_000,
                'start_date': today - timedelta(days=120),
                'end_date':   today + timedelta(days=90),
                'priority': 'haute', 'manager': 'Oumar Barry',
                'description': 'Développement d\'une IA d\'aide à la décision pour les agriculteurs guinéens (météo, sols, marchés).',
                'milestones': [
                    ('Collecte de données',         'termine',  True,  today - timedelta(days=90)),
                    ('Modèle prédictif v1',          'termine',  True,  today - timedelta(days=50)),
                    ('Interface paysans (mobile)',   'en_cours', False, today + timedelta(days=30)),
                    ('Pilote 3 régions',             'a_faire',  False, today + timedelta(days=75)),
                ],
            },
            {
                'name': 'Portail RH Interne',
                'direction': 'DSI', 'status': 'termine', 'progress': 100,
                'budget': 40_000_000, 'budget_consumed': 38_500_000,
                'start_date': today - timedelta(days=500),
                'end_date':   today - timedelta(days=90),
                'priority': 'moyenne', 'manager': 'Fatoumata Soumah',
                'description': 'Portail de gestion des ressources humaines : congés, évaluations, planning.',
                'milestones': [
                    ('Spécifications',     'termine', True, today - timedelta(days=460)),
                    ('Développement',      'termine', True, today - timedelta(days=300)),
                    ('Recette interne',    'termine', True, today - timedelta(days=140)),
                    ('Mise en production', 'termine', True, today - timedelta(days=92)),
                ],
            },
            {
                'name': 'Programme Coding4Girls',
                'direction': 'EDU', 'status': 'en_cours', 'progress': 70,
                'budget': 85_000_000, 'budget_consumed': 59_500_000,
                'start_date': today - timedelta(days=200),
                'end_date':   today + timedelta(days=40),
                'priority': 'haute', 'manager': 'Aminata Soumah',
                'description': 'Programme national d\'initiation au code pour les jeunes filles de 14-20 ans.',
                'milestones': [
                    ('Recrutement participantes',  'termine',  True,  today - timedelta(days=180)),
                    ('Module 1 – Bases du code',   'termine',  True,  today - timedelta(days=120)),
                    ('Module 2 – Web & Mobile',    'termine',  True,  today - timedelta(days=60)),
                    ('Projets finaux',             'en_cours', False, today + timedelta(days=20)),
                    ('Cérémonie de clôture',       'a_faire',  False, today + timedelta(days=38)),
                ],
            },
        ]

        for data in projects_data:
            milestones = data.pop('milestones')
            project, created = Project.objects.get_or_create(
                name=data['name'],
                defaults={
                    'direction':        d[data.pop('direction')],
                    'status':           data['status'],
                    'progress':         data['progress'],
                    'budget':           data['budget'],
                    'budget_consumed':  data['budget_consumed'],
                    'start_date':       data['start_date'],
                    'end_date':         data['end_date'],
                    'priority':         data['priority'],
                    'manager':          data['manager'],
                    'description':      data['description'],
                }
            )
            if created:
                self.stdout.write(f'  + Project: {project.name}')
                for i, (name, status, completed, due_date) in enumerate(milestones):
                    Milestone.objects.create(
                        project=project, name=name, status=status,
                        completed=completed, due_date=due_date, order=i,
                    )

    # ------------------------------------------------------------------ #
    def _create_documents(self, d):
        data = [
            ('Convention de partenariat – Orange Guinée',    'contrat', 'a_signer',  'haute',   'COM', today + timedelta(days=3),   'Aissatou Bah'),
            ('Budget prévisionnel S2 2026',                  'budget',  'a_valider', 'haute',   'TN',  today + timedelta(days=5),   'Ibrahima Sow'),
            ('Rapport d\'activité Mai 2026',                 'rapport', 'a_valider', 'moyenne', 'EDU', today + timedelta(days=8),   'Sekou Touré'),
            ('Note de service – Télétravail',                'note',    'signe',     'basse',   'DSI', today - timedelta(days=10),  'Aboubacar Sidibé'),
            ('Contrat prestataire sécurité réseau',          'contrat', 'a_signer',  'haute',   'DSI', today + timedelta(days=12),  'Aboubacar Sidibé'),
            ('Rapport technique IoT – Phase 1',              'rapport', 'signe',     'moyenne', 'IA',  today - timedelta(days=20),  'Oumar Barry'),
            ('Budget acquisition équipements DSI',           'budget',  'a_valider', 'haute',   'DSI', today + timedelta(days=6),   'Aboubacar Sidibé'),
            ('MoU UNESCO – Education numérique',             'contrat', 'a_signer',  'haute',   'EDU', today + timedelta(days=15),  'Sekou Touré'),
            ('Note interne – Politique de sécurité SI',      'note',    'a_valider', 'moyenne', 'DSI', today + timedelta(days=10),  'Elhadj Diallo'),
            ('Rapport Coding4Girls – Module 2',              'rapport', 'signe',     'moyenne', 'EDU', today - timedelta(days=5),   'Aminata Soumah'),
            ('Convention GIZ – Développement durable',       'contrat', 'signe',     'haute',   'COM', today - timedelta(days=30),  'Aissatou Bah'),
            ('Budget campagne digitale Q3 2026',             'budget',  'a_valider', 'moyenne', 'COM', today + timedelta(days=20),  'Ibrahima Barry'),
            ('Rapport audit cybersécurité 2026',             'rapport', 'a_valider', 'haute',   'DSI', today + timedelta(days=4),   'Aboubacar Sidibé'),
            ('Note de service – Congés estivaux',            'note',    'signe',     'basse',   'COM', today - timedelta(days=15),  'Aissatou Bah'),
        ]
        for title, doc_type, status, priority, code, due_date, created_by in data:
            self._mk(
                Document, {'title': title},
                doc_type=doc_type, status=status, priority=priority,
                direction=d[code], due_date=due_date, created_by=created_by,
            )

    # ------------------------------------------------------------------ #
    def _create_partners(self):
        data = [
            ('Orange Guinée',                   'entreprise',  'actif',         'Amadou Baldé',      'a.balde@orange-guinee.com',       '+224 622 00 00 00', date(2024,  6,  1)),
            ('Université Gamal Abdel Nasser',   'universite',  'actif',         'Dr. Mamadou Bah',   'm.bah@uganc.edu.gn',              '+224 621 00 00 00', date(2024,  3, 15)),
            ('Banque Mondiale',                 'institution', 'en_discussion', 'Sarah Johnson',     's.johnson@worldbank.org',         '+1 202 000 0000',   None),
            ('GIZ Guinée',                      'ong',         'actif',         'Hans Mueller',      'h.mueller@giz.de',                '+224 623 00 00 00', date(2024,  1,  1)),
            ('MTN Guinée',                      'entreprise',  'en_discussion', 'Kadiatou Diallo',   'k.diallo@mtn.com',                '+224 655 00 00 00', None),
            ('UNESCO Dakar',                    'institution', 'en_discussion', 'Jean-Pierre Mbow',  'jp.mbow@unesco.org',              '+221 33 000 0000',  None),
            ('Institut Pasteur',                'institution', 'actif',         'Dr. Claire Martin', 'c.martin@pasteur.sn',             '+221 33 111 1111',  date(2023, 11, 10)),
            ('Ancien partenaire logistique',    'entreprise',  'inactif',       'Mohamed Konaté',    'm.konate@logistique-gn.com',       '+224 624 11 22 33', date(2022,  5, 20)),
        ]
        for name, ptype, status, contact, email, phone, start_date in data:
            defaults = dict(partner_type=ptype, status=status, contact_person=contact,
                            email=email, phone=phone)
            if start_date:
                defaults['start_date'] = start_date
            self._mk(Partner, {'name': name}, **defaults)

    # ------------------------------------------------------------------ #
    def _create_events(self, d):
        data = [
            ('Réunion hebdo Comité de Direction',    'reunion',   today + timedelta(days=1),  time( 9,  0), 90,   'Salle de conférence A', 'Coordination hebdomadaire des directions.',                ['TN','IA','EDU','COM','DSI']),
            ('Inauguration Lab Innovation IA',       'evenement', today + timedelta(days=20), time(10,  0), 180,  'Campus CSIG – Bâtiment B', 'Cérémonie d\'inauguration du laboratoire d\'IA.',       ['IA', 'COM']),
            ('Hackathon CSIG 2026',                  'evenement', today + timedelta(days=75), time( 8,  0), 1440, 'Campus CSIG',          'Hackathon annuel pour les jeunes développeurs guinéens.',   ['TN','IA','COM']),
            ('Comité de pilotage E-Learning',        'reunion',   today + timedelta(days=3),  time(14,  0), 90,   'Salle B',              'Point d\'avancement projet E-Learning.',                    ['EDU','IA']),
            ('Réunion Budgétaire S2 2026',           'reunion',   today + timedelta(days=7),  time(10, 30), 120,  'Salle de réunion DG',  'Revue et validation des budgets du second semestre.',       ['TN','DSI']),
            ('Forum National Innovation',            'evenement', today + timedelta(days=45), time( 9,  0), 480,  'Palais du Peuple',     'Forum annuel rassemblant startups, institutionnels et partenaires.', ['TN','COM','EDU']),
            ('Atelier Cybersécurité',                'reunion',   today + timedelta(days=10), time(15,  0), 120,  'Salle Informatique C', 'Sensibilisation des équipes aux bonnes pratiques de sécurité SI.',   ['DSI','TN']),
            ('Réunion partenariat GIZ',              'reunion',   today + timedelta(days=14), time(11,  0), 90,   'Salle de conférence A', 'Point d\'avancement convention GIZ – Développement durable.',['COM','EDU']),
            ('Cérémonie clôture Coding4Girls',       'evenement', today + timedelta(days=38), time(10,  0), 240,  'Amphi CSIG',           'Remise de certificats aux 120 participantes du programme.',  ['EDU','COM']),
            ('Réunion technique IoT Campus',         'reunion',   today + timedelta(days=6),  time(14,  0), 60,   'Labo IA',              'Revue des spécifications techniques réseau IoT Campus.',     ['IA','DSI']),
        ]
        for title, etype, edate, etime, duration, location, description, codes in data:
            event, created = Event.objects.get_or_create(
                title=title, date=edate,
                defaults=dict(event_type=etype, time=etime, duration=duration,
                              location=location, description=description),
            )
            if created:
                for code in codes:
                    event.participants.add(d[code])
                self.stdout.write(f'  + Event: {event.title}')

    # ------------------------------------------------------------------ #
    def _create_requests(self, d):
        data = [
            ('Validation budget supplémentaire E-Learning',  'Demande de budget additionnel de 25M GNF pour couvrir les coûts de serveurs cloud.',               'EDU', 'haute',   'en_attente', 'Sekou Touré'),
            ('Recrutement développeur senior IA',            'Besoin urgent d\'un développeur senior Python/ML pour renforcer l\'équipe IA.',                      'IA',  'haute',   'en_attente', 'Oumar Barry'),
            ('Approbation campagne réseaux sociaux Q3',      'Validation de la stratégie de communication digitale pour le troisième trimestre 2026.',             'COM', 'moyenne', 'approuve',   'Ibrahima Barry'),
            ('Signature MoU UNESCO',                         'Demande de signature du mémorandum d\'entente avec l\'UNESCO pour l\'éducation numérique.',           'EDU', 'haute',   'en_attente', 'Aminata Soumah'),
            ('Acquisition 10 laptops – EDU',                 'Remplacement du parc informatique vieillissant pour les formateurs du programme Coding4Girls.',       'EDU', 'haute',   'approuve',   'Lansana Kourouma'),
            ('Renouvellement licence antivirus DSI',         'Renouvellement annuel des licences Kaspersky Endpoint Security pour 80 postes.',                      'DSI', 'moyenne', 'approuve',   'Mariama Kouyaté'),
            ('Accès VPN externe – équipe IA',                'Création de comptes VPN pour 4 développeurs IA travaillant en télétravail partiel.',                  'IA',  'moyenne', 'rejete',     'Kadiatou Baldé'),
            ('Organisation Forum Innovation 2026',           'Demande de budget logistique (50M GNF) pour l\'organisation du Forum National Innovation.',           'COM', 'haute',   'en_attente', 'Aissatou Bah'),
            ('Formation Power BI – équipe TN',               'Inscription de 5 analystes TN à la formation Power BI niveau avancé (3 jours, prestataire externe).', 'TN',  'basse',   'rejete',     'Thierno Bah'),
            ('Mise à niveau switches réseau',                'Remplacement de 12 switches Cisco obsolètes dans les salles serveurs – bâtiment principal.',          'DSI', 'haute',   'en_attente', 'Elhadj Diallo'),
        ]
        for title, description, code, priority, status, created_by in data:
            self._mk(
                Request, {'title': title},
                description=description, direction=d[code],
                priority=priority, status=status, created_by=created_by,
            )
