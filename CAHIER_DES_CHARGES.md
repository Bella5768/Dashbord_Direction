# Cahier des Charges - Dashboard Direction CSIG

## 1. Présentation du Projet

### 1.1 Contexte
La **Cité des Sciences et de l'Innovation de Guinée (CSIG)** a besoin d'une plateforme de pilotage stratégique pour sa Direction Générale. Cette solution permet de centraliser la gestion des projets, des ressources humaines, des budgets, des partenariats et du calendrier institutionnel.

### 1.2 Objectifs
- Centraliser le suivi des projets de toutes les directions
- Faciliter la gestion des ressources humaines et des équipes projet
- Assurer un suivi budgétaire précis par projet et par direction
- Gérer les partenariats et les demandes internes
- Planifier et suivre les événements institutionnels
- Fournir des rapports et statistiques pour la prise de décision

### 1.3 Technologies Utilisées
- **Backend** : Django 4.x (Python)
- **Frontend** : HTML5, CSS3, JavaScript
- **Base de données** : SQLite (développement) / MySQL (production)
- **Hébergement** : PythonAnywhere
- **Génération PDF** : ReportLab

---

## 2. Modules Fonctionnels

### 2.1 Module Authentification et Gestion des Utilisateurs

#### 2.1.1 Connexion / Déconnexion
- Page de connexion sécurisée avec identifiant et mot de passe
- Page "Mot de passe oublié" avec coordonnées de l'administrateur
- Session sécurisée avec expiration automatique

#### 2.1.2 Gestion des Utilisateurs
- **Création d'utilisateur** : nom, prénom, email, nom d'utilisateur, mot de passe
- **Profil utilisateur** : rôle, direction, téléphone, avatar
- **Rôles disponibles** :
  - **Admin** : Accès total à toutes les fonctionnalités
  - **DG (Directeur Général)** : Vision globale, accès à tous les projets et budgets
  - **Directeur** : Gestion des projets de sa direction
  - **Chef de Projet** : Gestion des projets dont il est responsable
  - **Employé** : Consultation et participation aux projets assignés
  - **Visiteur** : Consultation uniquement

#### 2.1.3 Permissions Granulaires
Chaque utilisateur peut avoir des permissions individuelles :
- Créer des projets
- Modifier les projets
- Ajouter des jalons
- Ajouter des membres aux projets
- Gérer les utilisateurs
- Approuver les demandes
- Créer des événements
- Voir les budgets
- Gérer les budgets
- Voir les budgets de toutes les directions

#### 2.1.4 Journal d'Activités
- Historique des connexions
- Traçabilité des actions (création, modification, suppression)

---

### 2.2 Module Tableau de Bord (Dashboard)

#### 2.2.1 Vue d'Ensemble
- **Statistiques globales** :
  - Nombre total de projets
  - Projets en cours / terminés / en retard
  - Budget total alloué vs consommé
  - Nombre d'employés
  - Nombre de partenaires

#### 2.2.2 Widgets
- Graphique de répartition des projets par statut
- Graphique budgétaire
- Liste des projets récents
- Événements à venir
- Demandes en attente

#### 2.2.3 Filtrage par Direction
- Les utilisateurs voient les données de leur direction
- Le DG et Admin voient toutes les directions

---

### 2.3 Module Gestion des Projets

#### 2.3.1 Informations du Projet
- **Nom** du projet
- **Description** détaillée
- **Direction** responsable
- **Responsable** (chef de projet)
- **Statut** : Planifié, En cours, Terminé, En retard, Suspendu
- **Priorité** : Basse, Moyenne, Haute
- **Dates** : Date de début, Date de fin prévue
- **Budget** : Budget alloué, Budget consommé
- **Progression** : Pourcentage d'avancement (calculé automatiquement)

#### 2.3.2 Jalons (Milestones)
- Création de jalons/étapes pour chaque projet
- Attribution d'un responsable par jalon
- Statut : Complété / Non complété
- Ordre d'affichage personnalisable

#### 2.3.3 Sous-étapes (Sub-Milestones)
- Création de sous-étapes pour chaque jalon
- Attribution d'un responsable par sous-étape
- Case à cocher pour marquer comme complétée
- Calcul automatique de la progression du jalon parent
- Mise à jour automatique du statut du jalon quand toutes les sous-étapes sont complétées

#### 2.3.4 Membres du Projet
- Ajout de membres avec différents rôles :
  - **Responsable** : Chef du projet
  - **Membre** : Participant actif
  - **Observateur** : Consultation uniquement
  - **Personne ressource** : Expert consulté
  - **Ressource externe** : Intervenant externe
- Possibilité de créer un nouvel employé lors de l'ajout

#### 2.3.5 Documents du Projet
- Organisation en dossiers et sous-dossiers
- Upload de fichiers (PDF, Word, Excel, images, etc.)
- Téléchargement des documents
- Métadonnées : nom, description, date d'ajout

#### 2.3.6 Besoins du Projet
- Liste des besoins identifiés
- Priorité : Basse, Moyenne, Haute
- Créateur du besoin

#### 2.3.7 Commentaires
- Fil de discussion sur le projet
- Horodatage des commentaires

---

### 2.4 Module Gestion des Ressources Humaines

#### 2.4.1 Directions
- Création et gestion des directions
- Code et nom de la direction
- Liste des employés par direction

#### 2.4.2 Employés
- **Informations** : Nom, Direction, Rôle/Fonction
- **Contact** : Téléphone, Email
- **Compétences** : Liste des compétences
- **Charge de travail** : Pourcentage d'occupation
- **Affectations** : Liste des projets assignés

---

### 2.5 Module Gestion Budgétaire

#### 2.5.1 Budgets par Direction
- Budget annuel alloué par direction
- Suivi des dépenses
- Pourcentage de consommation

#### 2.5.2 Budgets par Projet
- Budget alloué au projet
- Budget consommé
- Alertes en cas de dépassement

#### 2.5.3 Rapports Budgétaires
- Vue consolidée par direction
- Vue consolidée globale
- Export PDF des rapports

---

### 2.6 Module Gestion des Documents

#### 2.6.1 Types de Documents
- Rapport
- Contrat
- Facture
- Correspondance
- Autre

#### 2.6.2 Attributs
- Titre
- Type de document
- Statut : Brouillon, En révision, Validé, Archivé
- Priorité
- Direction concernée
- Date d'échéance
- Créateur
- Fichier joint

---

### 2.7 Module Gestion des Demandes

#### 2.7.1 Types de Demandes
- Demande de budget
- Demande de personnel
- Demande de matériel
- Demande de formation
- Autre

#### 2.7.2 Workflow
- **Statuts** : En attente, Approuvée, Rejetée, En cours
- Validation par les responsables habilités
- Historique des demandes

---

### 2.8 Module Partenariats

#### 2.8.1 Informations Partenaire
- Nom du partenaire
- Type : Institution, Entreprise, ONG, Université, Autre
- Pays
- Personne de contact
- Email, Téléphone
- Statut : Actif, En négociation, Inactif

#### 2.8.2 Suivi
- Date de début du partenariat
- Projets associés
- Historique des interactions

---

### 2.9 Module Calendrier et Événements

#### 2.9.1 Types d'Événements
- Réunion
- Formation
- Conférence
- Deadline
- Autre

#### 2.9.2 Informations Événement
- Titre
- Description
- Date et heure de début
- Date et heure de fin
- Lieu
- Type d'événement

#### 2.9.3 Affichage
- Vue calendrier mensuelle
- Liste des événements à venir
- Filtrage par type

---

### 2.10 Module Rapports et Statistiques

#### 2.10.1 Rapports Disponibles
- Rapport global des projets
- Rapport par direction
- Rapport budgétaire
- Rapport des ressources humaines

#### 2.10.2 Export
- Export PDF avec mise en page professionnelle
- Graphiques et tableaux

---

## 3. Spécifications Techniques

### 3.1 Architecture
```
Dashboard_CSIG/
├── core/                    # Application principale
│   ├── models.py           # Modèles de données
│   ├── views.py            # Vues et logique métier
│   ├── forms.py            # Formulaires utilisateur
│   ├── forms_project.py    # Formulaires projet
│   ├── urls.py             # Routes URL
│   └── admin.py            # Interface admin Django
├── templates/              # Templates HTML
│   ├── base.html          # Template de base
│   ├── core/              # Templates spécifiques
│   └── registration/      # Templates authentification
├── static/                 # Fichiers statiques
│   ├── css/
│   ├── js/
│   └── images/
├── media/                  # Fichiers uploadés
└── dashboard_csig/         # Configuration Django
    ├── settings.py
    ├── urls.py
    └── wsgi.py
```

### 3.2 Modèles de Données

#### Utilisateurs
- `User` (Django built-in)
- `UserProfile` : Extension du profil utilisateur
- `UserActivity` : Journal des activités

#### Organisation
- `Direction` : Directions de l'organisation
- `Employee` : Employés

#### Projets
- `Project` : Projets
- `ProjectMember` : Membres des projets
- `Milestone` : Jalons
- `SubMilestone` : Sous-étapes
- `ProjectFolder` : Dossiers de documents
- `ProjectDocument` : Documents de projet
- `ProjectNeed` : Besoins de projet
- `ProjectComment` : Commentaires

#### Autres
- `Document` : Documents généraux
- `Request` : Demandes
- `Partner` : Partenaires
- `Event` : Événements
- `Budget` : Budgets par direction

### 3.3 Sécurité
- Authentification par session Django
- Protection CSRF sur tous les formulaires
- Vérification des permissions à chaque action
- Mots de passe hashés (PBKDF2)
- Accès restreint selon le rôle et les permissions

### 3.4 Performance
- Requêtes optimisées avec `select_related` et `prefetch_related`
- Pagination des listes longues
- Cache des données statiques

---

## 4. Interface Utilisateur

### 4.1 Design
- Interface moderne et responsive
- Palette de couleurs professionnelle (bleu marine #2a4a6f)
- Typographie Inter
- Icônes Lucide/Heroicons

### 4.2 Navigation
- Menu latéral avec les modules principaux
- Fil d'Ariane pour la navigation
- Recherche globale

### 4.3 Composants
- Cards pour l'affichage des informations
- Tableaux avec tri et filtrage
- Formulaires avec validation
- Modales pour les actions rapides
- Notifications toast pour les feedbacks

---

## 5. Déploiement

### 5.1 Environnement de Développement
- Windows avec WAMP
- SQLite
- Django Debug Toolbar

### 5.2 Environnement de Production
- PythonAnywhere
- MySQL
- Collectstatic pour les fichiers statiques
- DEBUG = False

### 5.3 Procédure de Mise à Jour
```bash
cd ~/Dashbord_Direction
git pull origin master
python manage.py migrate
python manage.py collectstatic --noinput
# Web → Reload
```

---

## 6. Contacts

### Administrateur Système
- **Email** : bella@csig.edu.gn
- **Téléphone** : +224 621 05 76 98

---

## 7. Annexes

### 7.1 Glossaire
- **CSIG** : Cité des Sciences et de l'Innovation de Guinée
- **DG** : Directeur Général
- **Jalon** : Étape clé d'un projet
- **Sous-étape** : Tâche détaillée d'un jalon

### 7.2 Versions
| Version | Date | Description |
|---------|------|-------------|
| 1.0 | Janvier 2026 | Version initiale |
| 1.1 | Février 2026 | Ajout des sous-étapes, permissions granulaires |

---

*Document généré le 3 février 2026*
*Dashboard Direction CSIG - Tous droits réservés*
