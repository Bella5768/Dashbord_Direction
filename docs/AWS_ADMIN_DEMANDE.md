# Demande de déploiement — CSIG Dashboard (version Admin, révision 3)

Ce document est une demande d'accès AWS adressée à l'administrateur du compte
`499243079539`, pour le déploiement du CSIG Dashboard (Django 5 + Channels sur
ECS Fargate).

> **Révision 3** — intègre la revue de sécurité : les 3 secrets de
> l'application (clé Django, base, Redis) sont stockés dans **SSM Parameter
> Store** et injectés par `secrets[].valueFrom`, jamais en clair dans la task
> definition ; le rôle d'exécution reçoit `ssm:GetParameters` sur ces 3 paramètres
> nommés. Précisions apportées sur le SES (l'ARN d'identité n'est pas supporté
> par IAM pour les actions d'envoi) et sur la **passerelle NAT, supprimée car
> inutile et facturée en continu**. La liste exacte des actions de déploiement
> est fournie en §7, conformément à la demande de validation préalable.

> Compte concerné : `499243079539` — utilisateur IAM existant : `Guisse`
> (`arn:aws:iam::499243079539:user/Guisse`)
> Région de déploiement : **`eu-north-1`** (Stockholm)

---

## 1. Ce qui est demandé (en une phrase)

> **Créer les 2 rôles IAM ECS du projet — rôle d'exécution (politique managée
> AWS + lecture des 3 secrets par `ssm:GetParameters` borné à ces paramètres) et
> rôle de tâche (borné au bucket S3 du projet et à l'action SES réellement
> utilisée) — et accorder à `Guisse` un `iam:PassRole` restreint à ces deux rôles
> et conditionné au service ECS. Aucun utilisateur IAM supplémentaire, aucune
> clé Access Key, aucune politique `PowerUserAccess`.**

| # | Objet | Créé par | Nécessaire pour |
|---|-------|----------|-----------------|
| A | Rôle `csig-ecs-execution-role` | **Admin** | ECS tire l'image ECR, écrit les logs CloudWatch, **et injecte les 3 secrets** |
| B | Rôle `csig-task-role` | **Admin** | Le conteneur Django accède à S3 (médias) et SES (emails) |
| C | `iam:PassRole` restreint aux rôles A et B, conditionné à `ecs-tasks.amazonaws.com` | **Admin** | Permet à `Guisse` de lancer ECS avec ces rôles |
| D | Droits de déploiement **ponctuels** (§7) | **Admin** | Créer l'infrastructure une fois, puis la politique est retirée |

---

## 2. Pourquoi il n'y a plus de clé AWS dans le conteneur

Sur ECS Fargate, l'agent de la tâche injecte les credentials du **rôle de tâche**
dans le conteneur via `AWS_CONTAINER_CREDENTIALS_RELATIVE_URI`, et les SDK AWS
les récupèrent automatiquement (réf. [ECS — Using IAM roles with Amazon ECS tasks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security-iam-roles.html)).

Le code a été adapté en conséquence : les sessions boto3 ne forcent plus de clés
et basculent sur la chaîne de credentials par défaut quand elles sont absentes
(`core/media_utils.py::aws_session`), et le backend SES est sélectionné sur la
seule présence de `AWS_SES_REGION` (`dashboard_csig/settings.py`). Aucune variable
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` n'est donc présente dans la task
definition ni dans l'environnement du conteneur.

Conséquence directe : **l'utilisateur `csig-deploy` et sa clé Access Key ne sont
plus nécessaires.** Le push de l'image vers ECR (étape 8 du guide) utilise les
credentials que `Guisse` possède déjà.

---

## 3. Bloc A — Rôle d'exécution ECS (`csig-ecs-execution-role`)

Rôle utilisé par ECS/Fargate *pour le compte de l'organisation*, pas par le code
de l'application : il tire l'image depuis ECR, écrit les logs CloudWatch
(réf. [ECS — task execution IAM role](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html))
**et injecte les secrets de l'application dans le conteneur** (réf. [ECS —
Required IAM permissions for secrets](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#secrets_envvar)).

```bash
aws iam create-role \
  --role-name csig-ecs-execution-role \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[
      {"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}
    ]
  }'

aws iam attach-role-policy \
  --role-name csig-ecs-execution-role \
  --policy-name AmazonECSTaskExecutionRolePolicy \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Lecture des 3 secrets de l'application (bornée aux 3 paramètres nommés)
aws iam put-role-policy \
  --role-name csig-ecs-execution-role \
  --policy-name app-secrets \
  --policy-document '{
    "Version":"2012-10-17",
    "Statement":[
      {"Sid":"AppSecrets","Effect":"Allow",
       "Action":["ssm:GetParameters"],
       "Resource":[
         "arn:aws:ssm:eu-north-1:499243079539:parameter/csig/prod/django_secret_key",
         "arn:aws:ssm:eu-north-1:499243079539:parameter/csig/prod/database_url",
         "arn:aws:ssm:eu-north-1:499243079539:parameter/csig/prod/redis_url"
       ]}
    ]
  }'
```

Politique gérée AWS ([référence](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonECSTaskExecutionRolePolicy.html)) :
`ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`,
`ecr:BatchGetImage`, `logs:CreateLogStream`, `logs:PutLogEvents`.

### 3.1 Pourquoi `ssm:GetParameters` et pas `ssm:GetParameter`

C'est l'agent ECS, via le rôle d'exécution, qui résout et injecte les valeurs
déclarées dans `secrets[].valueFrom` : il utilise l'API `GetParameters`
(pluriel) et non `GetParameter` (singulier). Les 3 paramètres sont nommés
explicitement, donc **aucune** permission de lecture large sur l'ensemble du
Parameter Store du compte n'est demandée.

### 3.2 Pourquoi aucun `kms:Decrypt`

Les 3 paramètres sont des `SecureString` **standard**, protégés par la clé AWS
gérée `alias/aws/ssm` (le défaut quand aucune clé client n'est fournie).
Conformément à la documentation AWS : *« The permission to decrypt an AWS KMS
key is only required for `SecureString` parameter types that uses a customer
managed key instead of a default key »*
([référence](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/AWSHowTo.secrets.IAM-permissions.html)).
Aucun `kms:Decrypt` n'est donc requis. Si l'organisation impose un jour une clé
KMS gérée par le client, il faudra ajouter `kms:Decrypt` sur l'ARN de cette clé
au rôle d'exécution — c'est le seul changement à faire dans ce cas.

### 3.3 SSM Parameter Store plutôt que Secrets Manager

Les 3 secrets sont des valeurs courtes (< 4 Ko), stables et lues à chaque
démarrage de tâche. Les paramètres standard Parameter Store sont **gratuits**
(aucun frais de stockage ni d'API), alors que Secrets Manager est facturé par
secret et par tranche de 10 000 appels. Le passage à Secrets Manager reste
possible à tout moment : il suffit de remplacer les `valueFrom` par les ARN de
secrets et l'action `ssm:GetParameters` par `secretsmanager:GetSecretValue`
(variante documentée dans
`docs/AWS_DEPLOIEMENT_BOUT_EN_BOUT.md`, étape 9).

---

## 4. Bloc B — Rôle de tâche (`csig-task-role`)

Identité que le **conteneur Django** utilise au runtime pour accéder à S3 et SES
(réf. [ECS — task IAM role](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html)).
La politique ci-dessous ne contient **aucune** permission générique
(`s3:*`, `ses:*`) : elle est alignée sur les appels AWS réellement effectués par
le code.

| Action | Appelée par (réf. code) |
|--------|--------------------------|
| `s3:PutObject` | upload direct navigateur (presigned POST) — `core/views.py::api_upload_presign` |
| `s3:GetObject` | téléchargement forcé (URL presignée) — `core/media_utils.py::force_download_url` |
| `s3:DeleteObject` | suppression d'un média |
| `s3:ListBucket` | **indispensable** : boto3 résout la région du bucket via `HeadBucket` avant de générer l'URL d'upload (cf. `botocore/utils.py`) ; sans elle l'upload partirait sur l'endpoint `us-east-1` et échouerait |
| `s3:GetBucketLocation` | résolution de région complémentaire |
| `ses:SendRawEmail` | envoi des emails — `core/email_backend.py::SESBackend` (appel `send_raw_email`) |

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
      {"Sid":"BucketLevel","Effect":"Allow",
       "Action":["s3:GetBucketLocation","s3:ListBucket"],
       "Resource":"arn:aws:s3:::csig-media"},
      {"Sid":"BucketObjects","Effect":"Allow",
       "Action":["s3:GetObject","s3:PutObject","s3:DeleteObject"],
       "Resource":"arn:aws:s3:::csig-media/*"},
      {"Sid":"SendMail","Effect":"Allow",
       "Action":["ses:SendRawEmail"],"Resource":"*",
       "Condition":{"StringEquals":{"ses:FromAddress":"noreply@csig.edu.gn"}}}
    ]
  }'
```

Justification des bornes :

- **Séparations bucket / objets** : `ListBucket` et `GetBucketLocation` ne
  s'appliquent qu'à l'ARN du bucket, les autres actions qu'à son contenu
  (principe de moindre privilège).
- **`ses:SendRawEmail` seul** : c'est la seule action SES utilisée par le code
  (`send_raw_email`). L'action `ses:SendEmail` correspond à l'API SES *v2*, non
  utilisée ici.
- **Condition `ses:FromAddress`** : le code envoie toujours depuis
  `DEFAULT_FROM_EMAIL` (`core/email_backend.py` : `from_email` est laissé à
  `None` par défaut), donc la condition reflète exactement l'usage. Si
  `DEFAULT_FROM_EMAIL` change, la condition doit être mise à jour.

### 4.1 Sur le `"Resource": "*"` de l'action SES — pourquoi il reste

Question légitime : peut-on remplacer `"Resource": "*"` par l'ARN de l'identité
SES `arn:aws:ses:eu-north-1:499243079539:identity/csig.edu.gn` ?

**Non, pas dans une politique IAM de rôle ECS.** Les actions d'envoi de SES
(`ses:SendEmail`, `ses:SendRawEmail`) ne sont pas des actions à portée de
ressource dans IAM : la documentation officielle montre systématiquement
`"Resource": "*"`, **y compris avec une condition `ses:FromAddress`**
(réf. [SES — Control access with IAM](https://docs.aws.amazon.com/ses/latest/dg/control-user-access.html)).

La restriction par identité se fait donc **au niveau de l'identité SES**, pas du
rôle IAM. Deux niveaux complémentaires, si un contrôle plus fin est souhaité :

1. **Le rôle IAM** (ci-dessus) : `"Resource": "*"` **avec** la condition
   `ses:FromAddress = noreply@csig.edu.gn`. Toute tentative d'envoi au nom
   d'un autre expéditeur est refusée par IAM.
2. **La politique d'autorisation d'envoi de l'identité SES** (ressource
   `identity/csig.edu.gn`), qui restreint *quels principals* peuvent employer
   cette identité — c'est le mécanisme prévu par AWS pour ce cas
   (réf. [SES — Sending authorization policies](https://docs.aws.amazon.com/ses/latest/dg/sending-authorization-policies.html)) :

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Sid": "AllowCsigTaskRoleOnly",
       "Effect": "Allow",
       "Principal": { "AWS": "arn:aws:iam::499243079539:role/csig-task-role" },
       "Action": "ses:SendRawEmail",
       "Resource": "arn:aws:ses:eu-north-1:499243079539:identity/csig.edu.gn",
       "Condition": { "StringEquals": { "ses:FromAddress": "noreply@csig.edu.gn" } }
     }]
   }
   ```

Cette politique est **optionnelle** : elle est utile si l'organisation veut
interdire explicitement à tout autre rôle du compte d'écrire en
`@csig.edu.gn`. Elle s'applique à l'identité SES et ne remplace pas la
condition IAM.

---

## 5. Bloc C — `iam:PassRole` restreint et conditionné

ECS ne peut pas exécuter les tâches avec les rôles ECS tant que le principal
appelant (`Guisse`) n'a pas le droit de *passer* ces rôles
(réf. [IAM — Passing roles](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html)).
La condition `iam:PassedToService` restreint l'usage de ces rôles au seul
service ECS
(réf. [IAM — Pass a role to a specific AWS service](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_examples_iam-passrole-service.html)).

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
      ],
      "Condition": {
        "StringEquals": { "iam:PassedToService": "ecs-tasks.amazonaws.com" }
      }
    }
  ]
}
```

Double bornage : `Resource` limité aux 2 rôles du projet (jamais `"*"`) +
`iam:PassedToService` limité à ECS.

---

## 6. Ce qui a été retiré par rapport à la révision 1

| Retiré | Motif |
|--------|-------|
| Utilisateur IAM `csig-deploy` + Access Key | Le conteneur utilise le rôle de tâche ; le push ECR utilise les credentials existants de `Guisse`. Une clé supplémentaire n'apporte rien et augmente la surface de risque. |
| `PowerUserAccess` sur `Guisse` | Aucune étape du guide n'exige des droits « tous services sauf IAM » : les droits nécessaires sont ceux des API d'administration des ressources du projet (§7), et le runtime est couvert par les seuls rôles A et B. |
| `s3:*` / `ses:*` sur le rôle de tâche | Remplacés par les 5 actions S3 réellement utilisées, bornées au bucket, et `ses:SendRawEmail`. |
| `ses:SendEmail` | Action de l'API SES v2, non utilisée par le code. |
| Clés statiques dans la task definition | Remplacées par le rôle de tâche (cf. §2). |

---

## 7. Bloc D — Droits de déploiement temporaires

Le runtime est couvert par les rôles A et B. Reste la **création de
l'infrastructure**, effectuée une seule fois par la personne qui exécute le guide
`docs/AWS_DEPLOIEMENT_BOUT_EN_BOUT.md` : VPC, sous-réseaux, groupes de sécurité,
RDS, ElastiCache, ECR, ECS, ALB, ACM, CloudFront, bucket S3, identité SES,
paramètres SSM, enregistrement DNS.

- Si `Guisse` possède déjà ces droits : **aucune demande supplémentaire**, il
  exécute le guide lui-même.
- Sinon : la politique ci-dessous, accordée **pour la durée du déploiement
  uniquement**, puis retirée par l'admin une fois la stack en place.

**Les 2 rôles ECS restent créés par l'admin** (blocs A et B) : la politique ne
demande donc *ni* `iam:CreateRole`, *ni* `iam:PutRolePolicy`. Seul `iam:PassRole`
(bloc C) est demandé pour `Guisse`.

### 7.1 Liste exacte des actions demandées

Toutes sur les ressources du projet, **aucune** permission `iam:*` globale,
aucun `Resource: "*"` hors `iam:CreateServiceLinkedRole`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Vpc",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateVpc", "ec2:CreateTags", "ec2:ModifyVpcAttribute",
        "ec2:DescribeVpcs", "ec2:DescribeAvailabilityZones",
        "ec2:AttachInternetGateway", "ec2:DescribeInternetGateways",
        "ec2:CreateSubnet", "ec2:ModifySubnetAttribute", "ec2:DescribeSubnets",
        "ec2:CreateRouteTable", "ec2:CreateRoute",
        "ec2:AssociateRouteTable", "ec2:DescribeRouteTables",
        "ec2:CreateSecurityGroup", "ec2:DescribeSecurityGroups",
        "ec2:AuthorizeSecurityGroupIngress", "ec2:AuthorizeSecurityGroupEgress",
        "ec2:DeleteSecurityGroup"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestedRegion": "eu-north-1" }
      }
    },
    {
      "Sid": "Rds",
      "Effect": "Allow",
      "Action": [
        "rds:CreateDBInstance", "rds:CreateDBSubnetGroup",
        "rds:ModifyDBSubnetGroup", "rds:DescribeDBInstances",
        "rds:DescribeDBSubnetGroups", "rds:AddTagsToResource",
        "rds:ListTagsForResource"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestedRegion": "eu-north-1" }
      }
    },
    {
      "Sid": "ElastiCache",
      "Effect": "Allow",
      "Action": [
        "elasticache:CreateReplicationGroup", "elasticache:CreateCacheSubnetGroup",
        "elasticache:ModifyCacheSubnetGroup", "elasticache:DescribeReplicationGroups",
        "elasticache:DescribeCacheSubnetGroups", "elasticache:AddTagsToResource",
        "elasticache:ListTagsForResource"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestedRegion": "eu-north-1" }
      }
    },
    {
      "Sid": "Ecr",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken", "ecr:CreateRepository",
        "ecr:DescribeRepositories", "ecr:DeleteRepository",
        "ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestedRegion": "eu-north-1" }
      }
    },
    {
      "Sid": "EcsAlb",
      "Effect": "Allow",
      "Action": [
        "ecs:CreateCluster", "ecs:DescribeClusters", "ecs:DeleteCluster",
        "ecs:RegisterTaskDefinition", "ecs:DescribeTaskDefinition",
        "ecs:CreateService", "ecs:UpdateService", "ecs:DeleteService",
        "ecs:DescribeServices", "ecs:ListTasks", "ecs:DescribeTasks",
        "ecs:RunTask",
        "elasticloadbalancing:CreateLoadBalancer", "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DeleteLoadBalancer", "elasticloadbalancing:CreateTargetGroup",
        "elasticloadbalancing:DescribeTargetGroups", "elasticloadbalancing:DeleteTargetGroup",
        "elasticloadbalancing:ModifyTargetGroupAttributes", "elasticloadbalancing:CreateListener",
        "elasticloadbalancing:DescribeListeners", "elasticloadbalancing:DeleteListener",
        "elasticloadbalancing:DescribeTargetHealth", "elasticloadbalancing:AddTags",
        "elasticloadbalancing:DescribeAccountLimits"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestedRegion": "eu-north-1" }
      }
    },
    {
      "Sid": "AcmCloudFrontSesRoute53",
      "Effect": "Allow",
      "Action": [
        "acm:RequestCertificate", "acm:DescribeCertificate", "acm:ListCertificates",
        "acm:AddTagsToCertificate",
        "cloudfront:CreateDistribution", "cloudfront:GetDistribution",
        "cloudfront:ListDistributions", "cloudfront:TagResource",
        "cloudfront:CreateOriginAccessControl", "cloudfront:GetOriginAccessControl",
        "cloudfront:GetOriginAccessControlConfig",
        "sesv2:CreateEmailIdentity", "sesv2:GetEmailIdentity",
        "sesv2:ListEmailIdentities", "sesv2:DeleteEmailIdentity",
        "route53:ListHostedZones", "route53:GetHostedZone",
        "route53:ListResourceRecordSets", "route53:ChangeResourceRecordSets"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3Bucket",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket", "s3:PutBucketPublicAccessBlock",
        "s3:PutBucketPolicy", "s3:GetBucketPolicy", "s3:GetBucketLocation",
        "s3:DeleteBucket", "s3:ListAllMyBuckets"
      ],
      "Resource": [
        "arn:aws:s3:::csig-media",
        "arn:aws:s3:::csig-media/*"
      ]
    },
    {
      "Sid": "AppSecrets",
      "Effect": "Allow",
      "Action": ["ssm:PutParameter", "ssm:GetParameter", "ssm:DeleteParameter"],
      "Resource": "arn:aws:ssm:eu-north-1:499243079539:parameter/csig/prod/*"
    },
    {
      "Sid": "ServiceLinkedRole",
      "Effect": "Allow",
      "Action": "iam:CreateServiceLinkedRole",
      "Resource": "*"
    },
    {
      "Sid": "PassEcsRoles",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": [
        "arn:aws:iam::499243079539:role/csig-ecs-execution-role",
        "arn:aws:iam::499243079539:role/csig-task-role"
      ],
      "Condition": {
        "StringEquals": { "iam:PassedToService": "ecs-tasks.amazonaws.com" }
      }
    }
  ]
}
```

### 7.2 Deux points à valider par l'admin

1. **`iam:CreateServiceLinkedRole` est dans un statement séparé, sans
   condition.** Voluntary : c'est la seule action IAM sur `Resource: "*"`, et
   elle ne peut pas être restreinte à un ARN. Elle est nécessaire au
   déploiement, car certains services (RDS, ElastiCache, ECS) créent
   automatiquement des *service-linked roles* au premier usage. Si l'admin
   préfère les pré-créer, ce statement peut être retiré de la demande.
2. **`Resource: "*"` est conservé sur EC2/RDS/ElastiCache/ECS/ELB/ECR.** Ces
   APIShield les actions `Create*` (la ressource n'existe pas encore au moment de
   l'appel) ; un ARN ne peut donc pas être utilisé. Le bornage réel est obtenu
   par : la région via `aws:RequestedRegion`, les noms de ressources dans les
   commandes du guide, et le retrait de la politique après déploiement.

`PowerUserAccess` ne correspond à aucun des deux périmètres (runtime,
déploiement) et n'est donc pas demandé.

Le reste de la stack, avec le guide d'exécution :

| Étape | Ressource | Nom AWS |
|---|---|---|
| 2 | VPC + Internet Gateway + sous-réseaux publics + privés (RDS, ElastiCache) — **sans NAT** | `csig-vpc` |
| 3 | Security Groups | `csig-sg-ecs`, `csig-sg-alb`, `csig-sg-rds`, `csig-sg-cache` |
| 4 | RDS PostgreSQL 16 | `csig-db` |
| 5 | ElastiCache Redis (channel layer WebSocket) | `csig-cache` |
| 6 | S3 médias + CloudFront (origin access control) | `csig-media` |
| 7 | SES — identité email du domaine | `csig.edu.gn` |
| 8 | ECR — registre d'images | `csig-dashboard` |
| 9 | SSM — 3 paramètres `SecureString` du projet | `/csig/prod/*` |
| 10 | ECS cluster + ALB + target group + service Fargate | `csig-prod`, `csig-alb` |

Points d'attention validés sur la doc officielle :

1. **Hosted zone ID de l'ALB en `eu-north-1` = `Z23TAZ6LKFMNIO`**
   (réf. [Elastic Load Balancing endpoints](https://docs.aws.amazon.com/general/latest/gr/elb.html)) —
   uniquement pour un alias A Route 53.
2. **Certificat ACM** dans la **région de l'ALB** (`eu-north-1`), pas
   `us-east-1` : `us-east-1` n'est requis que pour un CloudFront servant le
   domaine principal, ce qui n'est pas le cas ici (CloudFront ne sert que les
   médias). Réf. [ACM — regional vs global](https://docs.aws.amazon.com/acm/latest/userguide/acm-regions.html).
3. **Subnets privés obligatoires** pour `csig-db-subs` (RDS) et
   `csig-cache-subs` (ElastiCache). Réf. [RDS — subnet group](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.WorkingWithRDSInstanceScenarios.html),
   [ElastiCache — subnet group](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/ElastiCache-VPCs-creating.html).
4. **Sticky sessions ALB** : les connexions WebSocket sont nativement « sticky »
   (le handshake HTTP 101 fixe la cible) ; la sticky *cookie* n'est pas requise
   pour le WebSocket, mais recommandée pour la cohérence des sessions HTTP.
   Réf. [ALB — sticky sessions](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-target-groups.html#sticky-sessions).
5. **Bucket S3** : laisser l'ownership par défaut (`BucketOwnerEnforced`, ACLs
   désactivées — recommandé par AWS) ; aucune permission `s3:PutObjectAcl` n'est
   nécessaire.

---

## 8. Vérifications (à la fin)

```bash
aws sts get-caller-identity            # → ...:user/Guisse

# Les 2 rôles existent et le rôle de tâche est borné au bucket :
aws iam get-role --role-name csig-ecs-execution-role --query 'Role.Arn' --output text
aws iam get-role --role-name csig-task-role \
  --query 'Role.{Arn:Arn,Inline:RoleName}' --output json
aws iam get-role-policy --role-name csig-task-role --policy-name media-and-mail
```

Côté application (une fois le service ECS démarré) :

1. `curl https://dashbord.csig.edu.gn/healthz/` → `200` avec un statut DB OK ;
2. création d'un projet → email envoyé via SES (log CloudWatch) ;
3. dépôt d'un document → l'upload part vers S3 (URL presignée correcte) ;
4. deux onglets → mise à jour temps réel d'une tâche (Redis + WebSocket).

---

## 9. Suivi

| Rôle | Action | Statut |
|---|---|---|
| Admin | Bloc A : rôle `csig-ecs-execution-role` + `app-secrets` (`ssm:GetParameters`) | ☐ |
| Admin | Bloc B : rôle `csig-task-role` (politique bornée au bucket) | ☐ |
| Admin | Bloc C : `iam:PassRole` conditionné sur les 2 rôles | ☐ |
| Admin | Bloc D : droits de déploiement temporaires (§7), **à retirer après déploiement** | ☐ |
| Admin | Créer les 3 paramètres `SecureString` `/csig/prod/*` (étape 9 du guide) | ☐ |
| Guisse | Exécute `docs/AWS_DEPLOIEMENT_BOUT_EN_BOUT.md` | ☐ |
| Guisse | Valide `get-caller-identity` + `/healthz/` | ☐ |
| Admin | Retire la politique de déploiement une fois la stack opérationnelle | ☐ |

*Révision 3 — septembre 2026, à jour des docs officielles AWS (CLI 2.37).*
*Révisions précédentes : rév. 2 (retrait de `csig-deploy` et de
`PowerUserAccess`), rév. 1 (demande initiale).*