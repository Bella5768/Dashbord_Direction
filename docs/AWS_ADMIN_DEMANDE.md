# Demande de déploiement — CSIG Dashboard (version Admin)

Ce document est une **demande unique et complète** adressée à l'administrateur
AWS de l'organisation (`499243079539`). L'objectif : **tout ce dont nous avons
besoin pour déployer et exploiter le CSIG Dashboard**, en une seule passe,
sans allers-retours.

Chaque élément est justifié par la **documentation officielle AWS** et par le
**code de l'application** (liens vers les fichiers concernés). Le propriétaire
technique du projet (Guisse) possède déjà des Access Keys valides ; **il reste
à l'administrateur à donner les permissions et à valider ce qui suit.**

> Compte concerné : `499243079539` — utilisateur IAM : `Guisse`
> (ARN `arn:aws:iam::499243079539:user/Guisse`)
> Région de déploiement : **`eu-north-1`** (Stockholm)

---

## 1. Ce qui est demandé en une phrase

> **Accorder à `Guisse` les droits `PowerUserAccess` (+ `iam:PassRole` restreint
> aux rôles du projet), et créer les 3 objets IAM suivants (2 rôles ECS + 1
> utilisateur de déploiement ECR), sachant que le reste de la stack est créé
> ensuite à l'aide du guide d'exécution.**

Concrètement, la demande tient en **tableau de bord suivant**, avec pour chaque
objet : ce qu'il est, pourquoi (réf. code), et qui le crée.

| # | Objet | Type | Créé par | Nécessaire pour |
|---|-------|------|----------|-----------------|
| A | Permissions `PowerUserAccess` sur `Guisse` | Politique gérée AWS | **Admin** | Permet à Guisse de créer/déployer la stack (VPC, RDS, ECS…) |
| B | `iam:PassRole` restreint | Permission IAM | **Admin** | ECS s'exécute avec les rôles ECS (pas en tant que Guisse) |
| C | Rôle `csig-ecs-execution-role` | Rôle IAM + politique gérée | **Admin** | ECS tire l'image d'ECR + écrit les logs CloudWatch |
| D | Rôle `csig-task-role` | Rôle IAM + politique inline | **Admin** | Le conteneur (Django) accède à S3 + SES |
| E | Utilisateur `csig-deploy` + Access Keys | Utilisateur IAM programme | **Admin** (ou Guisse si droit) | Push image ECR + pipe-to-secret dans le conteneur |

---

## 2. Bloc A — Permissions de `Guisse`

### 2.1 Politique `PowerUserAccess`

C'est la **politique gérée AWS prévue pour les développeurs/power users**
(réf. [IAM managed policies — PowerUserAccess](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_job-functions.html#jf_developer-power-user)).
Elle permet **tout service** sauf `iam:*`, `organizations:*`, `account:*` :

- `ec2` (VPC, subnets, SG) — étape 2 du guide ;
- `rds` — étape 4 ;
- `elasticache` — étape 5 ;
- `s3` — étape 6 ;
- `cloudfront` (OAC, distribution) — étape 6 ;
- `ses` — étape 7 ;
- `ecr` — étape 8 ;
- `ecs` + `logs` — étape 10 ;
- `elbv2` (ALB) — étape 10 ;
- `acm`, `route53` — étapes 10-11 ;
- `secretsmanager` — étape 9.

**Attention limitation** (vérifiée dans la doc) : `PowerUserAccess` **ne permet
pas** `iam:PassRole`. Or ECS exige ce droit pour assumer les rôles
`csig-ecs-execution-role`/`csig-task-role`
(réf. [ECS — task execution role](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html),
[rôles de tâche ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html)).
Cf. Bloc B.

**Console IAM** → Users → `Guisse` → **Add permissions** → **Attach policies
directly** → cocher `PowerUserAccess` → Add permissions.

### 2.2 (Option) Garder la main sur les Access Keys

Comme l'admin a déjà créé les clés de `Guisse`, on peut soit :
- **garder ce qui marche** — l'admin gère les clés, Guisse utilise un fichier
  `~/.aws/credentials` fourni ; ou
- autoriser Guisse à gérer ses propres clés (politique self-service ciblée) —
  non nécessaire si la rotation reste chez l'admin.

C'est la décision de l'admin (choix par défaut proposé : garder la gestion chez
l'admin).

---

## 3. Bloc B — `iam:PassRole` restreint

ECS **ne peut pas** exécuter les tâches avec les rôles ECS tant que le principal
appelant (`Guisse`) n'a pas le droit de *passer* ces rôles.
Réf. [IAM — Passing roles](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html).

Politique ciblée exacte (attachée à `Guisse`, en plus de `PowerUserAccess`) :

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": [
        "arn:aws:iam::499243079539:role/csig-ecs-execution-role",
        "arn:aws:iam::499243079539:role/csig-task-role"
      ]
    }
  ]
}
```

> Principe de moindre privilège : PassRole **limité aux seuls** rôles du projet
> (pas `Resource":"*"`).

---

## 4. Bloc C — Rôle d'exécution ECS (`csig-ecs-execution-role`)

**Rôle** : celui par lequel ECS/Fargate agit *pour votre compte* (pas le code
de l'application).
**Utilisé pour** : tirer l'image depuis ECR et écrire les logs dans CloudWatch
(réf. [ECS — task execution role](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html)).

Trust policy + politique gérée `AmazonECSTaskExecutionRolePolicy` :

```bash
aws iam create-role \
  --role-name csig-ecs-execution-role \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[
      {"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}
    ]
  }'

# Politique gérée fournie par AWS (ECR pull + logs CloudWatch) :
aws iam attach-role-policy \
  --role-name csig-ecs-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

Réf. [AmazonECSTaskExecutionRolePolicy](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonECSTaskExecutionRolePolicy.html)
— contient `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`,
`ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`, `logs:CreateLogStream`,
`logs:PutLogEvents`.

---

## 5. Bloc D — Rôle de tâche (`csig-task-role`)

**Rôle** : identité que le **conteneur Django** utilise au runtime pour accéder
aux services AWS **depuis le code** (pas depuis ECS).
**Utilisé pour** :
- `django-storages[s3]` → upload/lire les médias dans `csig-media`
  (réf. code : `settings.py`, variable `AWS_STORAGE_BUCKET_NAME`) ;
- `core.email_backend.SESBackend` → envoi d'emails via SES
  (`send_raw_email`, réf. code : `core/email_backend.py`).

Réf. AWS : [ECS — task IAM role](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html)
(« le rôle de tâche est requis quand l'application accède à S3 »).

```bash
aws iam create-role \
  --role-name csig-task-role \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[
      {"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}
    ]
  }'

aws iam put-role-policy \
  --role-name csig-task-role \
  --policy-name media-and-mail \
  --policy-document '{
    "Version":"2012-10-17",
    "Statement":[
      {"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListBucket"],
       "Resource":["arn:aws:s3:::csig-media","arn:aws:s3:::csig-media/*"]},
      {"Effect":"Allow","Action":["ses:SendEmail","ses:SendRawEmail"],"Resource":"*"}
    ]
  }'
```

---

## 6. Bloc E — Utilisateur de déploiement ECR (`csig-deploy`)

**Rôle** : compte **programme** (sans console) pour pousser l'image Docker dans
ECR et être **la source des clés passées au conteneur** pour S3/SES au runtime
(variables `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` dans la task definition).
Ne **remplace pas** `csig-task-role` — il fournit seulement des credentials
statiques quand les variables d'environnement sont utilisées.

Politique minimale (ECR push + S3/SES en lecture runtime + describe) :

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": ["ecr:GetAuthorizationToken"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["ecr:BatchCheckLayerAvailability","ecr:InitiateLayerUpload","ecr:PutImage","ecr:UploadLayerPart"],
      "Resource": "arn:aws:ecr:eu-north-1:499243079539:repository/csig-dashboard" },
    { "Effect": "Allow", "Action": ["s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListBucket"],
      "Resource": ["arn:aws:s3:::csig-media","arn:aws:s3:::csig-media/*"] },
    { "Effect": "Allow", "Action": ["ses:SendEmail","ses:SendRawEmail"], "Resource": "*" }
  ]
}
```

```bash
aws iam create-user --user-name csig-deploy
aws iam put-user-policy --user-name csig-deploy \
  --policy-name csig-deploy-policy \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["ecr:GetAuthorizationToken"],"Resource":"*"},{"Effect":"Allow","Action":["ecr:BatchCheckLayerAvailability","ecr:InitiateLayerUpload","ecr:PutImage","ecr:UploadLayerPart"],"Resource":"arn:aws:ecr:eu-north-1:499243079539:repository/csig-dashboard"},{"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListBucket"],"Resource":["arn:aws:s3:::csig-media","arn:aws:s3:::csig-media/*"]},{"Effect":"Allow","Action":["ses:SendEmail","ses:SendRawEmail"],"Resource":"*"}]}'

# Créer ses Access Keys (à transmettre de manière sécurisée) :
aws iam create-access-key --user-name csig-deploy
```

---

## 7. Le reste de la stack — créé ensuite avec le guide d'exécution

Une fois Blocs A-E en place, **tout le reste est créé à l'aide du guide
`docs/AWS_DEPLOIEMENT_BOUT_EN_BOUT.md`** (déjà écrit et validé sur les docs
officielles). Il crée dans `eu-north-1` :

| Étape | Ressource | Nom AWS |
|---|---|---|
| 2 | VPC + Internet Gateway + subnets publics (et privés pour RDS/ElastiCache) | `csig-vpc` |
| 3 | Security Groups | `csig-sg-ecs`, `csig-sg-alb`, `csig-sg-rds`, `csig-sg-cache` |
| 4 | RDS PostgreSQL 16 | `csig-db` |
| 5 | ElastiCache Redis (channel layer WebSocket) | `csig-cache` |
| 6 | S3 médias + CloudFront (origin access control) | `csig-media` |
| 7 | SES identity domaine | `csig.edu.gn` |
| 8 | ECR register | `csig-dashboard` |
| 10 | ECS cluster + ALB + Target group + Service Fargate | `csig-prod`, `csig-alb` |

**Corrections apportées dans la version admin** (vs guide v1) :

1. **Hosted zone ID de l'ALB en `eu-north-1` = `Z23TAZ6LKFMNIO`**
   (réf. [Elastic Load Balancing endpoints](https://docs.aws.amazon.com/general/latest/gr/elb.html)).
   Le guide v1 contenait `Z3HSL7lWd73wFK` (fournisseur erroné) — à corriger.
2. **Certificat ACM** : créer dans la **région de l'ALB** (`eu-north-1`), pas
   `us-east-1`. `us-east-1` n'est requis que pour un CloudFront servant *le
   domaine principal*, ce qui n'est pas notre cas (CloudFront ne sert que les
   médias S3). Réf. [ACM — regional vs global](https://docs.aws.amazon.com/acm/latest/userguide/acm-regions.html).
3. **Subnets privés obligatoires** pour `csig-db-subs` (RDS) et `csig-cache-subs`
   (ElastiCache) : il faut créer **2 subnets privés** en plus des publics
   (réf. [RDS — subnet group](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.WorkingWithRDSInstanceScenarios.html),
   [ElastiCache — subnet group](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/ElastiCache-VPCs-creating.html)).
4. **Sticky sessions ALB** : les connexions **WebSocket sont nativement
   « sticky »** (le handshake HTTP 101 fixe la cible) — la sticky *cookie*
   n'est donc pas requise pour le WS lui-même, mais recommandée pour cohérence
   des sessions HTTP Django (réf. [ALB — sticky sessions](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-target-groups.html#sticky-sessions)).
   Le guide v1 indiquait « obligatoires pour WebSocket » → à nuancer.

---

## 8. Vérifications (à la fin)

```bash
# à la racine d'un terminal authentifié en tant que Guisse
aws sts get-caller-identity          # → ...:user/Guisse
aws iam get-user --user-name Guisse  # OK si PowerUserAccess + PassRole applicables
# ECS exécutera les rôles C et D (pass-role OK)
```

---

## 9. Suivi

| Rôle | Action | Statut |
|---|---|---|
| Admin | Bloc A : `PowerUserAccess` sur `Guisse` | ☐ |
| Admin | Bloc B : `PassRole` restreint | ☐ |
| Admin | Bloc C : `csig-ecs-execution-role` | ☐ |
| Admin | Bloc D : `csig-task-role` | ☐ |
| Admin | Bloc E : `csig-deploy` + Access Keys transmises | ☐ |
| Guisse | Exécute `docs/AWS_DEPLOIEMENT_BOUT_EN_BOUT.md` (avec les 4 corrections) | ☐ |
| Guisse | Valide `get-caller-identity` + healthcheck `/healthz/` | ☐ |

*Document généré le 01/10/2026 — à jour des références AWS CLI 2.37 / docs
officielles 2026.*