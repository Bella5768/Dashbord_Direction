from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, time, timedelta
from core.models import Direction, Project, Milestone, Document, Partner, Event, Request, Employee, Budget


class Command(BaseCommand):
    help = 'Populate database with sample data for CSIG Dashboard'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample data...')
        
        # Create Directions
        directions_data = [
            {'name': 'Transition Numérique', 'code': 'TN', 'color': '#3b82f6'},
            {'name': 'Intelligence Artificielle', 'code': 'IA', 'color': '#059669'},
            {'name': 'Education et Vulgarisation', 'code': 'EDU', 'color': '#d97706'},
            {'name': 'Communication', 'code': 'COM', 'color': '#8b5cf6'},
        ]
        
        directions = {}
        for data in directions_data:
            direction, created = Direction.objects.get_or_create(
                code=data['code'],
                defaults={'name': data['name'], 'color': data['color']}
            )
            directions[data['code']] = direction
            if created:
                self.stdout.write(f'  Created direction: {direction.code}')
        
        # Create Budgets
        budgets_data = [
            {'direction': 'TN', 'allocated': 450000000, 'consumed': 217500000},
            {'direction': 'IA', 'allocated': 200000000, 'consumed': 85000000},
            {'direction': 'EDU', 'allocated': 100000000, 'consumed': 65000000},
            {'direction': 'COM', 'allocated': 75000000, 'consumed': 45000000},
        ]
        
        for data in budgets_data:
            budget, created = Budget.objects.get_or_create(
                direction=directions[data['direction']],
                defaults={'allocated': data['allocated'], 'consumed': data['consumed']}
            )
            if created:
                self.stdout.write(f'  Created budget for: {data["direction"]}')
        
        # Create Projects
        projects_data = [
            {
                'name': 'Plateforme E-Learning CSIG',
                'direction': 'EDU',
                'status': 'en_cours',
                'progress': 65,
                'budget': 150000000,
                'budget_consumed': 97500000,
                'start_date': date(2025, 1, 15),
                'end_date': date(2025, 6, 30),
                'priority': 'haute',
                'manager': 'Mamadou Diallo',
                'description': 'Développement d\'une plateforme de formation en ligne pour les jeunes innovateurs',
                'milestones': [
                    {'name': 'Conception', 'completed': True},
                    {'name': 'Développement Frontend', 'completed': True},
                    {'name': 'Développement Backend', 'completed': False},
                    {'name': 'Tests', 'completed': False},
                    {'name': 'Déploiement', 'completed': False},
                ]
            },
            {
                'name': 'Incubateur Startups Tech',
                'direction': 'TN',
                'status': 'en_cours',
                'progress': 40,
                'budget': 300000000,
                'budget_consumed': 120000000,
                'start_date': date(2025, 2, 1),
                'end_date': date(2025, 12, 31),
                'priority': 'haute',
                'manager': 'Fatoumata Camara',
                'description': 'Création d\'un espace d\'incubation pour les startups technologiques guinéennes',
                'milestones': [
                    {'name': 'Étude de faisabilité', 'completed': True},
                    {'name': 'Aménagement des locaux', 'completed': False},
                    {'name': 'Recrutement mentors', 'completed': False},
                    {'name': 'Lancement programme', 'completed': False},
                ]
            },
            {
                'name': 'Système de Gestion Documentaire',
                'direction': 'TN',
                'status': 'en_cours',
                'progress': 80,
                'budget': 50000000,
                'budget_consumed': 40000000,
                'start_date': date(2024, 11, 1),
                'end_date': date(2025, 3, 15),
                'priority': 'moyenne',
                'manager': 'Ibrahima Sow',
                'description': 'Numérisation et gestion électronique des documents administratifs',
                'milestones': [
                    {'name': 'Analyse des besoins', 'completed': True},
                    {'name': 'Développement', 'completed': True},
                    {'name': 'Migration données', 'completed': True},
                    {'name': 'Formation utilisateurs', 'completed': False},
                ]
            },
            {
                'name': 'Réseau IoT Campus',
                'direction': 'IA',
                'status': 'planifie',
                'progress': 10,
                'budget': 200000000,
                'budget_consumed': 20000000,
                'start_date': date(2025, 4, 1),
                'end_date': date(2025, 10, 30),
                'priority': 'moyenne',
                'manager': 'Oumar Barry',
                'description': 'Déploiement d\'un réseau IoT pour la gestion intelligente du campus',
                'milestones': [
                    {'name': 'Étude technique', 'completed': True},
                    {'name': 'Acquisition équipements', 'completed': False},
                    {'name': 'Installation', 'completed': False},
                    {'name': 'Configuration', 'completed': False},
                ]
            },
            {
                'name': 'Campagne Sensibilisation Innovation',
                'direction': 'COM',
                'status': 'termine',
                'progress': 100,
                'budget': 25000000,
                'budget_consumed': 23500000,
                'start_date': date(2024, 9, 1),
                'end_date': date(2024, 12, 31),
                'priority': 'basse',
                'manager': 'Aissatou Bah',
                'description': 'Campagne nationale de sensibilisation à l\'innovation et aux sciences',
                'milestones': [
                    {'name': 'Conception campagne', 'completed': True},
                    {'name': 'Production contenus', 'completed': True},
                    {'name': 'Diffusion', 'completed': True},
                    {'name': 'Évaluation impact', 'completed': True},
                ]
            },
            {
                'name': 'Partenariat Université Conakry',
                'direction': 'EDU',
                'status': 'en_cours',
                'progress': 55,
                'budget': 75000000,
                'budget_consumed': 41250000,
                'start_date': date(2025, 1, 1),
                'end_date': date(2025, 8, 31),
                'priority': 'haute',
                'manager': 'Sekou Touré',
                'description': 'Établissement d\'un partenariat stratégique avec l\'Université de Conakry',
                'milestones': [
                    {'name': 'Négociations', 'completed': True},
                    {'name': 'Signature convention', 'completed': True},
                    {'name': 'Mise en œuvre', 'completed': False},
                    {'name': 'Évaluation', 'completed': False},
                ]
            },
        ]
        
        for data in projects_data:
            milestones = data.pop('milestones')
            project, created = Project.objects.get_or_create(
                name=data['name'],
                defaults={
                    'direction': directions[data['direction']],
                    'status': data['status'],
                    'progress': data['progress'],
                    'budget': data['budget'],
                    'budget_consumed': data['budget_consumed'],
                    'start_date': data['start_date'],
                    'end_date': data['end_date'],
                    'priority': data['priority'],
                    'manager': data['manager'],
                    'description': data['description'],
                }
            )
            if created:
                self.stdout.write(f'  Created project: {project.name}')
                for i, m in enumerate(milestones):
                    Milestone.objects.create(
                        project=project,
                        name=m['name'],
                        completed=m['completed'],
                        order=i
                    )
        
        # Create Documents
        documents_data = [
            {'title': 'Convention de partenariat - Orange Guinée', 'doc_type': 'contrat', 'status': 'a_signer', 'priority': 'haute', 'direction': 'COM', 'due_date': date(2025, 1, 28), 'created_by': 'Sekou Touré'},
            {'title': 'Budget prévisionnel Q2 2025', 'doc_type': 'budget', 'status': 'a_valider', 'priority': 'haute', 'direction': 'TN', 'due_date': date(2025, 1, 30), 'created_by': 'Ibrahima Sow'},
            {'title': 'Rapport d\'activité Janvier 2025', 'doc_type': 'rapport', 'status': 'a_valider', 'priority': 'moyenne', 'direction': 'EDU', 'due_date': date(2025, 2, 5), 'created_by': 'Mamadou Diallo'},
            {'title': 'Note de service - Horaires', 'doc_type': 'note', 'status': 'signe', 'priority': 'basse', 'direction': 'TN', 'due_date': date(2025, 1, 20), 'created_by': 'Ibrahima Sow'},
            {'title': 'Contrat prestataire IT', 'doc_type': 'contrat', 'status': 'a_signer', 'priority': 'moyenne', 'direction': 'IA', 'due_date': date(2025, 2, 1), 'created_by': 'Oumar Barry'},
        ]
        
        for data in documents_data:
            doc, created = Document.objects.get_or_create(
                title=data['title'],
                defaults={
                    'doc_type': data['doc_type'],
                    'status': data['status'],
                    'priority': data['priority'],
                    'direction': directions[data['direction']],
                    'due_date': data['due_date'],
                    'created_by': data['created_by'],
                }
            )
            if created:
                self.stdout.write(f'  Created document: {doc.title}')
        
        # Create Partners
        partners_data = [
            {'name': 'Orange Guinée', 'partner_type': 'entreprise', 'status': 'actif', 'contact_person': 'Amadou Balde', 'email': 'a.balde@orange-guinee.com', 'phone': '+224 622 00 00 00', 'start_date': date(2024, 6, 1)},
            {'name': 'Université Gamal Abdel Nasser', 'partner_type': 'universite', 'status': 'actif', 'contact_person': 'Dr. Mamadou Bah', 'email': 'm.bah@uganc.edu.gn', 'phone': '+224 621 00 00 00', 'start_date': date(2024, 3, 15)},
            {'name': 'Banque Mondiale', 'partner_type': 'institution', 'status': 'en_discussion', 'contact_person': 'Sarah Johnson', 'email': 's.johnson@worldbank.org', 'phone': '+1 202 000 0000', 'start_date': None},
            {'name': 'GIZ Guinée', 'partner_type': 'ong', 'status': 'actif', 'contact_person': 'Hans Mueller', 'email': 'h.mueller@giz.de', 'phone': '+224 623 00 00 00', 'start_date': date(2024, 1, 1)},
        ]
        
        for data in partners_data:
            partner, created = Partner.objects.get_or_create(
                name=data['name'],
                defaults=data
            )
            if created:
                self.stdout.write(f'  Created partner: {partner.name}')
        
        # Create Events
        today = timezone.now().date()
        events_data = [
            {'title': 'Réunion de Direction', 'event_type': 'reunion', 'date': today + timedelta(days=1), 'time': time(9, 0), 'duration': 120, 'location': 'Salle de conférence A', 'description': 'Réunion hebdomadaire de coordination', 'participants': ['TN', 'IA', 'EDU', 'COM']},
            {'title': 'Inauguration Lab Innovation', 'event_type': 'evenement', 'date': today + timedelta(days=20), 'time': time(10, 0), 'duration': 180, 'location': 'Campus CSIG', 'description': 'Cérémonie d\'inauguration du nouveau laboratoire d\'innovation', 'participants': ['IA', 'COM']},
            {'title': 'Deadline - Rapport Q1', 'event_type': 'deadline', 'date': today + timedelta(days=60), 'time': time(18, 0), 'duration': 0, 'location': '', 'description': 'Date limite de soumission du rapport trimestriel', 'participants': ['TN']},
            {'title': 'Hackathon CSIG 2025', 'event_type': 'evenement', 'date': today + timedelta(days=75), 'time': time(8, 0), 'duration': 1440, 'location': 'Campus CSIG', 'description': 'Hackathon annuel pour les jeunes développeurs guinéens', 'participants': ['TN', 'IA', 'COM']},
            {'title': 'Comité de pilotage E-Learning', 'event_type': 'reunion', 'date': today + timedelta(days=3), 'time': time(14, 0), 'duration': 90, 'location': 'Salle B', 'description': 'Point d\'avancement sur le projet E-Learning', 'participants': ['EDU', 'IA']},
        ]
        
        for data in events_data:
            participants = data.pop('participants')
            event, created = Event.objects.get_or_create(
                title=data['title'],
                date=data['date'],
                defaults=data
            )
            if created:
                for code in participants:
                    event.participants.add(directions[code])
                self.stdout.write(f'  Created event: {event.title}')
        
        # Create Requests
        requests_data = [
            {'title': 'Validation budget supplémentaire', 'description': 'Demande de budget additionnel de 25M GNF pour le projet E-Learning', 'direction': 'EDU', 'priority': 'haute', 'status': 'en_attente', 'created_by': 'Mamadou Diallo'},
            {'title': 'Recrutement développeur senior', 'description': 'Besoin urgent d\'un développeur senior pour renforcer l\'équipe technique', 'direction': 'IA', 'priority': 'haute', 'status': 'en_attente', 'created_by': 'Oumar Barry'},
            {'title': 'Approbation campagne réseaux sociaux', 'description': 'Validation de la stratégie de communication digitale Q1 2025', 'direction': 'COM', 'priority': 'moyenne', 'status': 'approuve', 'created_by': 'Aissatou Bah'},
            {'title': 'Signature MoU - UNESCO', 'description': 'Demande de signature du mémorandum d\'entente avec l\'UNESCO', 'direction': 'EDU', 'priority': 'haute', 'status': 'en_attente', 'created_by': 'Sekou Touré'},
        ]
        
        for data in requests_data:
            req, created = Request.objects.get_or_create(
                title=data['title'],
                defaults={
                    'description': data['description'],
                    'direction': directions[data['direction']],
                    'priority': data['priority'],
                    'status': data['status'],
                    'created_by': data['created_by'],
                }
            )
            if created:
                self.stdout.write(f'  Created request: {req.title}')
        
        # Create Employees
        employees_data = [
            {'name': 'Mamadou Diallo', 'direction': 'TN', 'role': 'Directeur', 'workload': 85, 'skills': 'Gestion de projet, Innovation, Leadership'},
            {'name': 'Fatoumata Camara', 'direction': 'TN', 'role': 'Chef de projet', 'workload': 90, 'skills': 'Incubation, Startups, Mentorat'},
            {'name': 'Oumar Barry', 'direction': 'IA', 'role': 'Directeur Technique', 'workload': 75, 'skills': 'Architecture, DevOps, IoT'},
            {'name': 'Ibrahima Sow', 'direction': 'TN', 'role': 'Directeur Financier', 'workload': 70, 'skills': 'Finance, Comptabilité, Budget'},
            {'name': 'Aissatou Bah', 'direction': 'COM', 'role': 'Directrice Communication', 'workload': 65, 'skills': 'Communication, Marketing, Relations publiques'},
            {'name': 'Sekou Touré', 'direction': 'EDU', 'role': 'Directeur Education', 'workload': 80, 'skills': 'Pédagogie, Formation, Vulgarisation'},
            {'name': 'Kadiatou Balde', 'direction': 'IA', 'role': 'Développeur Senior', 'workload': 95, 'skills': 'React, Node.js, Python'},
            {'name': 'Mohamed Sylla', 'direction': 'EDU', 'role': 'Analyste', 'workload': 60, 'skills': 'Analyse, Data, Reporting'},
        ]
        
        for data in employees_data:
            emp, created = Employee.objects.get_or_create(
                name=data['name'],
                defaults={
                    'direction': directions[data['direction']],
                    'role': data['role'],
                    'workload': data['workload'],
                    'skills': data['skills'],
                }
            )
            if created:
                self.stdout.write(f'  Created employee: {emp.name}')
        
        self.stdout.write(self.style.SUCCESS('Sample data created successfully!'))
