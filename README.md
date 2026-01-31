# Dashboard Direction Générale - CSIG

Plateforme de pilotage et de suivi stratégique pour la Cité des Sciences et de l'Innovation de Guinée (CSIG).

## Fonctionnalités

- **Tableau de bord** : Vue d'ensemble avec KPIs, graphiques et widgets
- **Suivi des projets** : Visualisation de l'avancement, jalons, budgets
- **Gestion des ressources** : Suivi budgétaire et RH par direction
- **Documents** : Gestion des documents à signer/valider
- **Demandes** : Traitement des demandes des directions
- **Calendrier** : Agenda partagé avec événements et deadlines
- **Rapports** : Analyses et génération de rapports
- **Partenaires** : Gestion des partenariats et événements

## Technologies

- **Backend** : Django 4.2
- **Frontend** : HTML5, CSS3, JavaScript (Vanilla)
- **Base de données** : SQLite (développement)
- **Graphiques** : Chart.js

## Installation

```bash
# Créer un environnement virtuel
python -m venv venv

# Activer l'environnement virtuel
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Appliquer les migrations
python manage.py migrate

# Créer les données de démonstration
python manage.py populate_data

# Créer un superutilisateur (optionnel)
python manage.py createsuperuser

# Lancer le serveur de développement
python manage.py runserver
```

## Structure du projet

```
dashboard_csig/          # Configuration Django
├── settings.py          # Paramètres du projet
├── urls.py              # URLs principales
└── wsgi.py              # Configuration WSGI

core/                    # Application principale
├── models.py            # Modèles de données
├── views.py             # Vues et logique métier
├── urls.py              # URLs de l'application
├── admin.py             # Configuration admin
└── management/          # Commandes personnalisées
    └── commands/
        └── populate_data.py

templates/               # Templates HTML
├── base.html            # Template de base
└── core/                # Templates des pages
    ├── dashboard.html
    ├── projects.html
    ├── resources.html
    ├── documents.html
    ├── requests.html
    ├── calendar.html
    ├── reports.html
    └── partners.html

static/                  # Fichiers statiques
├── css/
│   └── style.css        # Styles CSS
└── js/
    └── main.js          # JavaScript
```

## Accès

- **Application** : http://localhost:8000
- **Administration** : http://localhost:8000/admin

## Licence

CSIG - Cité des Sciences et de l'Innovation de Guinée
