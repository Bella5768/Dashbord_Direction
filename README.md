# Dashboard Direction Générale - CSIG

Plateforme de pilotage et de suivi stratégique pour la Cité des Sciences et de l'Innovation de Guinée (CSIG).

## Fonctionnalités

- **Tableau de bord** : Vue d'ensemble avec KPIs, graphiques et widgets
- **Suivi des projets** : Visualisation de l'avancement, jalons, sous-étapes, budgets
- **Gestion des ressources** : Suivi des employés, directions et budgets par direction
- **Documents** : Gestion des documents à signer/valider/télécharger
- **Demandes** : Traitement des demandes des directions
- **Congés** : Workflow de validation en cascade (manager → RH → direction)
- **Calendrier** : Agenda partagé avec événements et deadlines
- **Notifications temps réel** : Notifications WebSocket (Django Channels) + emails
- **Rapports** : Analyses et génération de rapports (PDF/Excel)
- **Partenaires** : Gestion des partenariats et événements
- **Administration RBAC** : Rôles et permissions par direction, gestion des utilisateurs

## Technologies

- **Backend** : Django 4.2 / 5.1 (`requirements.txt`)
- **Frontend** : HTML5, CSS3, JavaScript (Vanilla)
- **Base de données** : PostgreSQL Neon (production) — repli SQLite (développement)
- **Temps réel** : Django Channels + Redis (InMemory en développement)
- **Internationalisation** : Django i18n (français par défaut)
- **Graphiques** : Chart.js
- **Stockage média** : Amazon S3 + CloudFront (optionnel)
- **Emails** : Amazon SES (prioritaire), replis SendGrid / Outlook SMTP

## Architecture des données

Depuis la migration UUID, **toutes les clés primaires des modèles métier (`core.*`)
sont des `UUID`** (v4) :

- Le modèle utilisateur est **`core.User`** (`AbstractUser`, PK `UUIDField`),
  défini par `AUTH_USER_MODEL = 'core.User'`.
- Toutes les FK internes (`project`, `milestone`, `employee`, `user`, …) sont des
  UUID ; les FK vers l'utilisateur pointent sur `core.User`.
- Les ressources exposées en URL utilisent des **slugs** lisibles
  (`projets/<slug:project_id>/`) ou des UUID (`utilisateurs/<uuid:user_id>/`).
- Tables internes Django (`auth_group`, `auth_permission`,
  `django_content_type`, `django_admin_log`) conservent par design des PK entières.

## Installation

### Prérequis

- Python 3.10+
- PostgreSQL accessible (optionnel pour le développement local)

### Étapes

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

# Configurer l'environnement
cp .env.example .env
#  → renseigner DJANGO_SECRET_KEY (obligatoire) et DJANGO_ADMIN_PASSWORD

# Appliquer les migrations
python manage.py migrate

# Créer le superutilisateur initial
python manage.py create_admin

# Assigner les rôles aux utilisateurs (RBAC)
python manage.py assign_roles

# Lancer le serveur de développement (Daphne pour le support WebSocket)
daphne -b 0.0.0.0 -p 8000 dashboard_csig.asgi:application

# Alternative (sans WebSocket) :
# python manage.py runserver
```

## Structure du projet

```
dashboard_csig/          # Configuration Django
├── settings.py          # Paramètres (env, DB, AUTH_USER_MODEL, channels)
├── urls.py              # URLs principales
├── asgi.py              # ASGI (Daphne / Channels)
├── wsgi.py              # WSGI (gunicorn)
└── middleware.py        # Middleware personnalisé

core/                    # Application principale
├── models.py            # Modèles (UUID) + core.User (AbstractUser, PK UUID)
├── views.py             # Vues et logique métier
├── views_roles.py       # Vues RBAC (rôles, permissions)
├── urls.py              # URLs de l'application
├── admin.py             # Configuration admin
├── consumers.py         # Consommateur WebSocket (notifications temps réel)
├── notifs.py            # Envoi WS + emails
├── notifications.py     # Génération des notifications métier
├── email_backend.py     # Backends email (SES / SendGrid / Outlook)
├── ability.py           # Gestion des droits (RBAC)
├── fields.py            # Champs personnalisés (téléphone international)
└── management/          # Commandes personnalisées
    └── commands/
        ├── create_admin.py      # Superutilisateur initial
        ├── assign_roles.py      # Attribution des rôles RBAC
        ├── populate_data.py     # Données de démonstration
        ├── fix_sequences.py     # Réinitialisation des séquences PostgreSQL
        └── send_due_date_alerts.py

scripts/                 # Scripts utilitaires (hors serveur)
├── convert_data_to_uuid.py  # Migration de données vers PK UUID/Neon
└── (i18n, audits...)

templates/               # Templates HTML (base.html + core/)
static/                  # Fichiers statiques (css/, js/)
docs/
└── AWS_MIGRATION.md     # Checklist de provisionnement AWS (ECS, RDS, SES, S3…)
NEON_SETUP.md            # Configuration Neon PostgreSQL
```

## Scripts de maintenance

- **`python manage.py create_admin`** — crée le superutilisateur `admin`
  (mot de passe via `DJANGO_ADMIN_PASSWORD`).
- **`python manage.py assign_roles`** — réconcilie les rôles RBAC des utilisateurs.
- **`python manage.py populate_data [--clear]`** — génère des données de
  démonstration.
- **`python manage.py fix_sequences`** — corrige les séquences PostgreSQL si le
  type d'une colonne entière le nécessite.
- **`python manage.py send_due_date_alerts`** — envoie les alertes d'échéances
  (à planifier en cron).
- **`python scripts/convert_data_to_uuid.py <DATABASE_URL_source>`** — bascule
  les données d'une base legacy vers le schéma UUID (idempotent).

## Configuration de la base de données

La base est choisie par priorité dans `settings.py` :

1. **PostgreSQL** si `DATABASE_URL` est défini (recommandé, ex. Neon/RDS)
2. **SQLite** sinon (développement local rapide)

Exemple `.env` :

```
DATABASE_URL=postgresql://user:password@ep-xxx.aws.neon.tech/neondb?sslmode=require
REDIS_URL=redis://localhost:6379/0   # optionnel pour Channels
```

> **Important** : avec le schéma UUID, toute nouvelle base doit être créée via
> `python manage.py migrate` (les migrations référencent `core.User` en premier).
> Pour reprendre des données historiques, utilisez `convert_data_to_uuid.py`.

## Accès

- **Application** : http://localhost:8000
- **Administration** : http://localhost:8000/admin
- **Console** : `python manage.py shell`

## Licence

CSIG - Cité des Sciences et de l'Innovation de Guinée