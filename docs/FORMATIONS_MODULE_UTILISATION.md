# Module de formation — Dashboard Direction CSIG

Formation à l'utilisation de la plateforme de pilotage et de suivi stratégique
de la Cité des Sciences et de l'Innovation de Guinée (CSIG).

| | |
|---|---|
| **Durée recommandée** | 3 h (théorie + pratique) |
| **Public** | Administration, directions, chefs de projet, employés, partenaires |
| **Prérequis** | Navigateur moderne, connexion réseau, identifiants fournis |
| **Formateur** | Support technique CSIG |

---

## Sommaire

1. [Présentation de la plateforme](#1-présentation-de-la-plateforme)
2. [Se connecter et gérer son compte](#2-se-connecter-et-gérer-son-compte)
3. [Découverte de l'interface](#3-découverte-de-linterface)
4. [Tableau de bord](#4-tableau-de-bord)
5. [Gestion des projets](#5-gestion-des-projets)
6. [Mes tâches](#6-mes-tâches)
7. [Calendrier et événements](#7-calendrier-et-événements)
8. [Congés](#8-congés)
9. [Documents](#9-documents)
10. [Demandes](#10-demandes)
11. [Ressources et budgets](#11-ressources-et-budgets)
12. [Partenaires](#12-partenaires)
13. [Rapports](#13-rapports)
14. [Notifications temps réel](#14-notifications-temps-réel)
15. [Administration : utilisateurs, directions, rôles](#15-administration--utilisateurs-directions-rôles)
16. [Matrice des rôles et permissions](#16-matrice-des-rôles-et-permissions)
17. [Exercices pratiques](#17-exercices-pratiques)
18. [Foire aux questions](#18-foire-aux-questions)

---

## 1. Présentation de la plateforme

Le **Dashboard Direction Générale** est l'outil central de pilotage de la CSIG.
Il permet de :

- **Suivre les projets** en temps réel (jalons, sous-étapes, budgets, membres).
- **Visualiser l'avancement** grâce à des indicateurs (KPIs), graphiques et
  tableaux de bord.
- **Gérer les documents** : dépôt, signature, validation, téléchargement.
- **Traiter les demandes** des directions et **valider les congés** selon un
  workflow en cascade (hiérarchie → RH → direction).
- **Partager un calendrier** : réunions, événements, échéances.
- **Suivre les partenariats** et générer des **rapports** (PDF).
- **Recevoir des alertes en temps réel** (notifications + emails).

L'application est accessible depuis un navigateur web. Les droits de chaque
utilisateur sont définis par son **rôle** (voir §16).

---

## 2. Se connecter et gérer son compte

### 2.1 Connexion

1. Ouvrir le navigateur et saisir l'adresse de la plateforme fournie (ex.
   `https://dashbord.csig.edu.gn`).
2. Saisir son **identifiant** (nom d'utilisateur) et son **mot de passe**.
3. Cliquer sur **Se connecter**.

> Le mot de passe initial est fourni par l'administrateur. Il est conseillé de
> le modifier à la première connexion.

### 2.2 Mot de passe oublié

Utiliser le lien **« Mot de passe oublié »** sur la page de connexion :

1. Saisir l'email (ou l'identifiant) du compte.
2. Un email de réinitialisation est envoyé.
3. Ouvrir le lien reçu et définir un nouveau mot de passe.

### 2.3 Modifier ses informations et son mot de passe

- En haut à droite : cliquer sur son **avatar / nom** → **Mon compte**.
- Onglet **profil** : téléphone, photo, etc.
- Bouton **Changer le mot de passe** : saisir l'ancien, puis le nouveau.

### 2.4 Se déconnecter

Utiliser le menu du compte (avatar) → **Se déconnecter**. Toujours se
déconnecter sur un poste partagé.

---

## 3. Découverte de l'interface

L'interface se compose de :

- **Barre latérale gauche (menu)** : les sections accessibles selon le rôle.
- **Barre supérieure** : recherche globale, notifications, menu du compte.
- **Zone centrale** : le contenu de la page active.

### Menu principal (visible pour tous)

| Icône | Section | Rôle principal |
|---|---|---|
| ⌂ | **Tableau de bord** | Vue d'ensemble et KPIs |
| 📁 | **Projets** | Liste et suivi des projets |
| ✅ | **Mes tâches** | Jalons et sous-étapes assignés à moi |
| 📅 | **Calendrier** | Agenda partagé |
| ✈️ | **Congés** | Demandes et suivi des congés |

### Menu « Gestion » (selon permissions)

| Section | Description |
|---|---|
| **Ressources** | Budgets, dépenses par direction, employés |
| **Demandes** | Demandes des directions à valider |
| **Documents** | Documents à signer / valider / télécharger |
| **Partenaires** | Base des partenariats |
| **Rapports** | Analyses et export PDF |

### Menu « Administration » (réservé aux administrateurs / DG)

| Section | Description |
|---|---|
| **Utilisateurs** | Création, activation, rôles des comptes |
| **Directions** | Structuration de l'organisation |
| **Rôles** | Gestion des rôles et permissions (RBAC) |

---

## 4. Tableau de bord

Le tableau de bord affiche une vue d'ensemble personnalisée :

- **Mes projets** : projets auxquels je participe.
- **Mes tâches** : jalons / sous-étapes dont je suis responsable.
- **Mes congés** : demandes récentes et leur état.
- **Budget consommé** : pourcentage utilisé (en GNF).
- **Partenaires actifs** : collaborations en cours.
- **Projets en cours** : nombre de projets actifs dans ma direction.
- **Graphiques** : répartition des projets, avancement, budgets par direction.

**Lecture d'un indicateur** : les cartes (KPIs) sont cliquables et mènent à la
liste détaillée correspondante.

---

## 5. Gestion des projets

### 5.1 Accéder aux projets

Menu **Projets** → liste des projets. Recherche et filtres disponibles
(statut, priorité, direction).

### 5.2 Créer un projet

1. **Projets** → **Nouveau projet**.
2. Renseigner : nom, description, **priorité** (basse/moyenne/haute),
   **statut** (planifié, en cours, suspendu, terminé, en retard).
3. Enregistrer.

> Seuls les profils autorisés (directeur, chef de projet, DG) peuvent créer
> des projets.

### 5.3 Fiche projet

Une fiche projet contient :

- **Jalons** : étapes clés avec date, statut, responsable(s), progression.
- **Sous-étapes** : découpage d'un jalon en tâches plus fines.
- **Budget** : montant alloué / consommé.
- **Membres** : personnes assignées au projet avec leur rôle projet.
- **Documents** : dossier documentaire du projet.
- **Besoins** : besoin exprimés pour le projet.
- **Commentaires** : fil de discussion du projet.

### 5.4 Créer et suivre un jalon

1. Ouvrir le projet → section **Jalons** → **Ajouter un jalon**.
2. Nom, date d'échéance, **responsables** (employés), statut initial.
3. Suivre l'évolution : **à faire → en cours → en révision → terminé**
   (ou **bloqué** avec justification).
4. Renseigner la **progression manuelle** (%) si pertinent.

### 5.5 Sous-étapes

Une sous-étape précise un point d'avancement ; même logique que les jalons
(statut, responsable, progression). Les jalons et sous-étapes peuvent être
réordonnés (glisser-déposer / boutons d'ordre).

### 5.6 Membres et rôles projet

1. Section **Membres** → **Ajouter un membre** (choisir un employé).
2. Assigner un **rôle projet** :
   - **Responsable** : gestion complète du projet.
   - **Membre** : contribution active (jalons, documents, commentaires).
   - **Observateur** : lecture seule.
   - **Ressource externe** (éditeur / observateur) : partenaire avec ou sans
     droits d'édition.

### 5.7 Documents de projet

Depuis un projet : **Documents** → **Nouveau document** (téléversement). Les
documents projet sont gérés comme les documents de la section globale (§9).

---

## 6. Mes tâches

La section **Mes tâches** centralise :

- Les **jalons** dont je suis responsable.
- Les **sous-étapes** assignées.

Pour chaque tâche, on peut :
- Modifier le **statut** (à faire, en cours, bloqué, en révision, terminé).
- Mettre à jour la **progression**.
- Accéder au **projet parent** et aux détails.

> Les changements de statut sont **notifiés en temps réel** aux participants
> (voir §14).

---

## 7. Calendrier et événements

Le calendrier est un **agenda partagé** : réunions, événements et échéances
des projets.

### Créer un événement

1. **Calendrier** → **Nouveau** (ou cliquer sur une date).
2. Type : **réunion** ou **événement**.
3. Titre, description, **date**, **heure**, **durée**, **lieu**.
4. Sélectionner les **directions participantes**.
5. Enregistrer.

### Gérer sa participation

- **RSVP** : répondre présent / absent depuis la fiche événement.
- Modifier ou **supprimer** un événement (selon droits).

> Les utilisateurs avec le rôle **Visiteur** n'ont accès qu'au calendrier en
> lecture seule.

---

## 8. Congés

Le module **Congés** gère les demandes selon un **workflow en cascade** :

```
Soumise → Avis hiérarchique (manager) → Vérification RH → Décision finale
                                                                ↓
                                                  Approuvée / Rejetée
```

### 8.1 Faire une demande

1. **Congés** → **Nouvelle demande**.
2. Renseigner : dates de début et fin, **type de congé**, motif.
3. Joindre un **document justificatif** si nécessaire (attestation, etc.).
4. **Soumettre** : la demande passe à l'étape « soumise ».

### 8.2 Suivre sa demande

La liste **Congés** affiche l'état de mes demandes :
- **En attente** (soumise, avis favorable, conforme RH).
- **Approuvée** / **Rejetée** (+ nombre total de jours approuvés).

### 8.3 Valider les demandes (selon rôle)

- **Manager / hiérarchie** : donner un **avis favorable** ou **défavorable**
  (étape « soumise »).
- **RH** : vérifier la **conformité** (étape « avis favorable »).
- **Décideur final** (direction générale) : **approuver / rejeter** (étape
  « conforme RH »).

Chaque décision envoie une **notification** et un **email** au demandeur.

### 8.4 Annuler / modifier

- Une demande **soumise** peut être **modifiée** ou **annulée** par son auteur.
- Une fois validée, elle ne peut plus être modifiée.

### 8.5 Attestation

Une fois la demande **approuvée**, il est possible de **télécharger**
l'attestation de congé au format PDF.

---

## 9. Documents

La section **Documents** centralise les fichiers de l'organisation.

### Actions disponibles (selon permissions)

| Action | Description |
|---|---|
| **Nouveau document** | Téléverser un fichier (PDF, image, Office, etc.) |
| **Prévisualiser** | Aperçu dans le navigateur |
| **Télécharger** | Récupérer le fichier (nom et en-têtes corrects) |
| **Signer** | Marquer un document comme signé |
| **Valider** | Approuver un document (selon workflow) |
| **Modifier / Supprimer** | Selon droits |

> Les documents peuvent être **projets** (dossiers d'un projet) ou **globaux**
> (section Documents).

### Upload

1. **Documents** → **Nouveau document**.
2. Choisir le fichier, renseigner le titre/description si demandé.
3. Enregistrer : le fichier est stocké (S3/CloudFront en production) et son
   URL est immédiatement utilisable.

---

## 10. Demandes

La section **Demandes** gère les **demandes** (besoins) émises par les
directions et soumises à validation.

### Soumettre une demande

1. **Demandes** → **Nouvelle demande**.
2. Décrire le besoin (titre, détail, projet lié si pertinent).
3. Soumettre pour **approbation**.

### Approuver / rejeter (selon rôle)

- Les profils avec permission `approve` (directeurs, DG, chef de projet sur
  scope projet) traitent les demandes.
- Une décision déclenche **notification** + **email** au demandeur.

---

## 11. Ressources et budgets

La section **Ressources** donne une vue des **moyens** de l'organisation :
- **Budgets** par projet et par direction (alloué, consommé, reste).
- **Dépenses** consolidées.
- **Employés** : charge de travail, compétences, direction.

### Gérer un budget

1. **Ressources** → **Budgets** → **Nouveau budget**.
2. Renseigner le montant alloué, lié à un projet / une direction.
3. Les dépenses enregistrées mettent à jour automatiquement le **budget
   consommé** (affiché dans le tableau de bord).

### Employés

La base **Employés** stocke : nom, fonction, direction, téléphone, email,
charge de travail (%), compétences, statut **interne / externe** (partenaire).
Un employé peut être relié à un **compte utilisateur** (→ ses tâches et
projets).

---

## 12. Partenaires

La section **Partenaires** regroupe les collaborations :
- **Type** : entreprise, université, institution, ONG.
- **Statut** : actif, en discussion, inactif.
- Fiche partenaire : contact, logo, dates, projets associés.

### Ajouter un partenaire

1. **Partenaires** → **Nouveau partenaire**.
2. Nom, type, contact, statut, logo.
3. Enregistrer.

> Les partenaires peuvent aussi être ajoutés comme **ressources externes** sur
> un projet (rôle projet §5.6), avec ou sans droits d'édition.

---

## 13. Rapports

La section **Rapports** produit des analyses exportables :
- **Rapport général** (activités, projets, budgets).
- **Rapport employés** (effectifs, charge de travail).
- **Export des activités d'un projet**.

Formats : **PDF** (reportlab).

### Générer un rapport

1. **Rapports** → choisir le rapport.
2. Cliquer **Exporter PDF**.
3. Le fichier PDF est téléchargé (logos inclus, prêt à partager).

---

## 14. Notifications temps réel

La plateforme notifie en **temps réel** (socket) et par **email** :

| Événement | Destinataires |
|---|---|
| Affectation d'un jalon / sous-étape | Responsables assignés |
| Changement de statut d'une tâche | Participants au projet |
| Commentaire projet | Membres du projet |
| Décision sur un congé | Demandeur |
| Décision sur une demande | Demandeur |
| Nouvel événement / invitation | Directions invitées |
| Compte créé / invité | Nouvel utilisateur |

**Fonctionnement** :
- La **cloche** (barre supérieure) affiche le nombre de non-lues et le menu
  déroulant des notifications récentes.
- « **Voir toutes les notifications** » mène à l'historique complet.
- Un clic sur une notification ouvre la ressource concernée.
- Bouton **Tout marquer comme lu** disponible.

---

## 15. Administration : utilisateurs, directions, rôles

Réservé aux **administrateurs** et à la **direction générale**.

### 15.1 Utilisateurs

- **Créer un utilisateur** : nom, identifiant, email, **rôle global**, direction.
- **Activation** : un lien ou un email d'activation est envoyé ; l'utilisateur
  choisit son mot de passe.
- **Renouveler une invitation** : renvoie un nouveau lien (si expiré).
- **Modifier** : rôle, direction, statut (actif/inactif).
- **Réinitialiser le mot de passe** d'un compte.
- **Activités** : journal des dernières actions d'un utilisateur.

> Ne jamais **supprimer** un compte actif : utiliser la **désactivation**.

### 15.2 Directions

- **Créer / modifier / supprimer** des directions (nom, code, couleur).
- Les directions structurent : les employés, les utilisateurs (rattachement),
  le budget, et le scope d'accès (`same_direction`).

### 15.3 Rôles et permissions (RBAC)

- **Rôles globaux** (`Rôles`) : définissent les droits sur l'ensemble du
  système (voir §16).
- **Rôles projet** (`Rôles projet`) : définissent les droits à l'intérieur
  d'un projet.
- Créer ses propres rôles : combiner **action** (lire, créer, modifier,
  supprimer, gérer, approuver, exporter) × **sujet** (projets, jalons, budgets,
  utilisateurs, congés, documents, rapports, …) × **condition** (même
  direction, est manager du projet, est membre du projet, propriétaire, …).
- Certains rôles sont **système** (non supprimables).

---

## 16. Matrice des rôles et permissions

### 16.1 Rôles globaux (système)

| Rôle | Périmètre principal |
|---|---|
| **Administrateur** | Accès total au système (`manage all`) |
| **Directeur Général** | Direction générale : projets, budgets globaux, utilisateurs, congés (tous), documents, partenaires, rapports, directions, rôles |
| **Directeur** | Direction : projets/budgets de sa direction, avis hiérarchique sur les congés, approbations, employés de sa direction |
| **Chef de Projet** | Responsable projets : créer/modifier ses projets, jalons, membres, événements ; lire budgets (direction), employer, rapports |
| **Employé** | Projets (en lecture), créer/modifier ses jalons, congés (les siens), événements |
| **Visiteur** | Calendrier en lecture seule |

### 16.2 Rôles projet (système)

| Rôle projet | Droits |
|---|---|
| **Responsable** | Modifier le projet, gérer les membres, créer/modifier jalons, créer documents, besoins et commentaires |
| **Membre** | Créer/modifier jalons, créer documents, besoins, commentaires |
| **Observateur** | Lecture seule du projet |
| **Ressource externe (éditeur)** | Édition (projet, jalons, documents, besoins, commentaires) |
| **Ressource externe (observateur)** | Lecture seule |

> Le contenu visible et les boutons affichés dépendent des **permissions** du
> rôle connecté. Si une action n'apparaît pas, c'est qu'elle n'est pas
> autorisée pour votre profil.

---

## 17. Exercices pratiques

### Exercice 1 — Première connexion (15 min)
1. Se connecter avec les identifiants fournis.
2. Modifier son mot de passe.
3. Compléter son profil (téléphone, photo).
4. Identifier les sections disponibles dans son menu.

### Exercice 2 — Tableau de bord (15 min)
1. Relever les KPIs affichés (mes projets, mes tâches, budget consommé).
2. Cliquer sur 2 cartes et expliquer où elles mènent.

### Exercice 3 — Projet (30 min)
*Rôle : chef de projet / directeur.*
1. Créer un projet « Test — Formation JJ/MM ».
2. Ajouter un membre avec le rôle projet « Membre ».
3. Créer un jalon daté avec 2 responsables.
4. Créer une sous-étape et lui affecter un responsable.
5. Déposer un document dans le dossier du projet.

### Exercice 4 — Tâches (15 min)
1. Ouvrir « Mes tâches », noter les jalons affichés.
2. Changer le statut d'une tâche et vérifier la notification reçue par le
   deuxième participant (2 écrans).

### Exercice 5 — Congés (20 min)
*En binôme : employé + manager.*
1. L'employé soumet une demande de congé (3 jours).
2. Le manager donne son avis favorable.
3. Vérifier la notification reçue par l'employé.

### Exercice 6 — Calendrier (15 min)
1. Créer une réunion (date, heure, durée, lieu, directions).
2. Simuler une réponse RSVP depuis un autre compte.

### Exercice 7 — Rapport (10 min)
1. Générer le rapport employés en PDF.
2. Vérifier le nom du fichier téléchargé et l'ouverture du PDF.

### Exercice 8 — (Option admin) RBAC (25 min)
1. Créer un utilisateur test avec le rôle « Visiteur ».
2. Se connecter avec ce compte : vérifier que seul le calendrier est visible.
3. Basculer le compte sur « Employé » et comparer le menu.

---

## 18. Foire aux questions

**Q : Je ne vois pas une section dans mon menu. Pourquoi ?**
R : Le menu est adapté à votre rôle (RBAC). Contactez l'administrateur si vous
estimez avoir besoin d'un accès supplémentaire.

**Q : Mon email du lien d'activation n'arrive pas.**
R : Vérifiez les courriers indésirables puis demandez le renouvellement de
l'invitation via **Administration → Utilisateurs → Renvoyer l'invitation**.

**Q : Puis-je modifier une demande de congé déjà acceptée ?**
R : Non. Une demande acceptée est verrouillée. Faites-en une nouvelle demande.

**Q : Le fichier téléchargé a le mauvais nom ?**
R : Le nom du fichier est celui stocké à l'upload. Nommez vos fichiers
clairement (ex. `PV_CA_2026-09.pdf`) avant l'envoi.

**Q : Les notifications en temps réel ne s'affichent pas.**
R : Vérifiez votre connexion (les sockets nécessitent un réseau stable) et
rechargez la page. Si le problème persiste, contactez le support.

**Q : Comment obtenir un accès en tant que partenaire ?**
R : L'administrateur crée un compte avec un profil relié à l'employé « externe »
et un rôle projet « Ressource externe » sur le(s) projet(s) concerné(s).

---

*Document de formation v1.0. Pour toute correction, contacter le support CSIG.*