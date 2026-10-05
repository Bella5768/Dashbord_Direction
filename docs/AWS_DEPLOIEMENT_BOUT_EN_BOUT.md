# Déploiement AWS bout-en-bout — CSIG Dashboard

Guide de création **de zéro** de toute la stack AWS pour le CSIG Dashboard
(Django 5 + Channels + PostgreSQL). Chaque étape est une commande CLI prête à
l'emploi, validée sur les docs officielles AWS (CLI 2.37, 2026).

> **Prérequis** : accès AWS (CLI authentifié, `aws sts get-caller-identity` ✓),
> Docker, `postgresql-client` (pg_dump) pour la migration de données.

---

## Architecture cible

```
                     Internet (HTTPS)
                          │
                ┌─────────▼─────────┐
                │ Route 53 / DNS    │  → dashbord.csig.edu.gn
                └─────────┬─────────┘
                          │
                ┌─────────▼─────────┐
                │  CloudFront       │  (serve les médias S3)
                └─────────┬─────────┘
                          │
                ┌─────────▼─────────┐      ┌──────────────────┐
                │ ALB (App LB)      │─────▶│  ECS Fargate      │
                │ HTTPS + WS        │      │  csig-prod:web    │
                └─────────┬─────────┘      │  daphne :8080     │
                          │                └────┬──────┬───────┘
                          │        port 5432    │      │ port 6379
                 ┌────────▼────────┐   ┌────────▼──┐  ┌▼──────────────┐
                 │ RDS PostgreSQL  │   │ ElastiCache │  │ Amazon S3     │
                 │ csig-db         │   │ redis       │  │ csig-media    │
                 └─────────────────┘   └────────────┘  └──────────────┘
                          │                 │                 │
                          │                 │        ┌────────▼────────┐
                          ▼                 ▼        │ CloudFront      │
                  __init__/migrations   Channel layer │ (lecture médias) │
                                                      └─────────────────┘
                 Amazon SES : envoi des emails (boto3 send_raw_email)
```

### Calendrier des ressources à créer

| # | Service AWS           | Nom                  | Rôle |
|---|-----------------------|----------------------|------|
| 0 | IAM                   | rôles ECS (`csig-ecs-execution-role`, `csig-task-role`) | runtime sans clé |
| 1 | VPC + Subnets (Réseau)| -                    | réseau privé |
| 2 | Security Groups       | `csig-*`             | isolation pare-feu |
| 3 | RDS PostgreSQL        | `csig-db`            | base de données |
| 4 | ElastiCache Redis     | `csig-cache`         | channel layer WS |
| 5 | S3 + CloudFront       | `csig-media` + dist  | médias téléversés |
| 6 | SES                   | `csig.edu.gn`        | envoi d'emails |
| 7 | ECR                   | `csig-dashboard`     | registre d'image |
| 8 | ECS Fargate + ALB     | `csig-prod` + `csig-alb` | conteneur web |

Tous les services régionaux (RDS, ElastiCache, ECS, ECR, SG, ALB) sont créés
dans **une même région** (ex. `eu-north-1`, celle du profil CLI). CloudFront,
SES et Route 53 sont globaux ou gérés à part.

---

## Étape 0 — Préparer l'environnement

```bash
# Vérifier l'identité AWS (doit répondre sans NoCredentials)
aws sts get-caller-identity

# Poser des variables à réutiliser partout
AWS_REGION=eu-north-1                # région principale
ACCOUNT_ID=499243079539             # ton compte (voir get-caller-identity)
export AWS_REGION ACCOUNT_ID
```

> Si tu veux utils que les commandes s'exécutent sans erreur, définis aussi
> `AWS_PROFILE=default` (ou le profil que tu règles).

---

## Étape 1 — Identité et accès (IAM)

### 1.1 Qui a besoin de quoi (aucun Access Key dans le conteneur)

Le conteneur **n'embarque aucune clé AWS** : sur ECS Fargate il reçoit ses
credentials du *rôle de tâche* (section 1.3), injectés par l'agent. Conséquences :

- **Aucun utilisateur IAM `csig-deploy` n'est nécessaire**, ni clé Access Key
  supplémentaire : le push de l'image vers ECR (étape 8) utilise les
  credentials AWS que l'opérateur possède déjà.
- Les variables `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` ne sont **pas**
  dans la task definition (annexe A) : le code bascule automatiquement sur la
  chaîne de credentials boto3 quand elles sont absentes
  (`core/media_utils.py::aws_session`).
- La seule permission IAM demandée au compte qui **déploie** est
  `iam:PassRole` (ci-dessous), nécessaire pour rattacher les 2 rôles ECS.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": [
        "arn:aws:iam::ACCOUNT_ID:role/csig-ecs-execution-role",
        "arn:aws:iam::ACCOUNT_ID:role/csig-task-role"
      ],
      "Condition": {
        "StringEquals": { "iam:PassedToService": "ecs-tasks.amazonaws.com" }
      }
    }
  ]
}
```

> La condition `iam:PassedToService` restreint ces rôles au service ECS.
> Elle est optionnelle mais recommandée.

> **Attention — droits de bootstrapping.** Exécuter ce guide (créer VPC,
> RDS, ElastiCache, ECR, ECS, ALB, ACM, CloudFront, SES, Route 53, paramètres
> SSM) exige des droits de *déploiement* bien plus larges que ceux du runtime :
> ce sont les API d'administration, utilisées une seule fois. La liste exacte de
> ces actions est dans `docs/AWS_ADMIN_DEMANDE.md` §7 ; ces droits sont
> ponctuels et la politique doit être retirée après le déploiement.

### 1.2 Rôle d'exécution ECS

Le rôle d'exécution (`executionRoleArn`) permet à ECS de tirer l'image depuis
ECR et d'écrire les logs dans CloudWatch Logs. AWS fournit une politique gérée
toute faite :

```bash
aws iam create-role \
  --role-name csig-ecs-execution-role \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }'

aws iam attach-role-policy \
  --role-name csig-ecs-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Enregistrer son ARN
ECS_EXECUTION_ROLE_ARN=$(aws iam get-role --role-name csig-ecs-execution-role \
  --query 'Role.Arn' --output text)
echo "$ECS_EXECUTION_ROLE_ARN"
```

### 1.3 Rôle de tâche (permissions du conteneur)

Le conteneur a besoin de S3 (médias) et de SES (emails) **au runtime**, et
rien d'autre. Ces permissions correspondent exactement aux appels AWS du code :

| Action | Appelée par |
|--------|--------------|
| `s3:PutObject` | upload navigateur direct (presigned POST), `core/views.py::api_upload_presign` |
| `s3:GetObject` | téléchargement enforcer (URL presignée), `core/media_utils.py::force_download_url` |
| `s3:DeleteObject` | suppression d'un média |
| `s3:ListBucket` | **obligatoire** : boto3 résout la région du bucket via `HeadBucket` pour générer l'URL d'upload (`botocore/utils.py`) |
| `s3:GetBucketLocation` | résolution de région complémentaire |
| `ses:SendRawEmail` | envoi des emails, `core/email_backend.py::SESBackend` (`send_raw_email`) |

```bash
aws iam create-role \
  --role-name csig-task-role \
  --assume-role-policy-document '{
  "Version":"2012-10-17",
  "Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]
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

> Le rôle est **borné au bucket du projet** et à la seule action SES utilisée par
> le code (`send_raw_email`), avec la condition `ses:FromAddress` qui reflète
> `DEFAULT_FROM_EMAIL` (le code n'envoie jamais depuis une autre adresse).
> Si `DEFAULT_FROM_EMAIL` change, la condition doit être mise à jour.

---

## Étape 2 — Réseau (VPC et subnets)

Si le compte a un **VPC par défaut** (avec internet gateway), on peut l'utiliser
directement — mais pour un déploiement propre, créer un petit VPC dédié :

```bash
# Créer le VPC (10.0.0.0/16) + 2 subnets publics (ALB) + 2 privés (tâches)
VPC_ID=$(aws ec2 create-vpc --cidr-block 10.0.0.0/16 --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=csig-vpc}]' --query 'Vpc.VpcId' --output text)
aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-support
aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-hostnames
echo "VPC_ID=$VPC_ID"

# Internet Gateway (pour le trafic sortant public)
IGW_ID=$(aws ec2 create-internet-gateway --query 'InternetGateway.InternetGatewayId' --output text)
aws ec2 attach-internet-gateway --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID"
echo "IGW_ID=$IGW_ID"
```

### Subnets publics (ALB) — 2 AZ

```bash
SUBNET_PUB1=$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block 10.0.1.0/24 --availability-zone "${AWS_REGION}a" --query 'Subnet.SubnetId' --output text)
SUBNET_PUB2=$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block 10.0.2.0/24 --availability-zone "${AWS_REGION}b" --query 'Subnet.SubnetId' --output text)
aws ec2 modify-subnet-attribute --subnet-id "$SUBNET_PUB1" --map-public-ip-on-launch
aws ec2 modify-subnet-attribute --subnet-id "$SUBNET_PUB2" --map-public-ip-on-launch

# Route table publique → IGW
RT_ID=$(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" --query 'RouteTables[].RouteTableId' --output text)
aws ec2 create-route --route-table-id "$RT_ID" --destination-cidr-block 0.0.0.0/0 --gateway-id "$IGW_ID"
aws ec2 associate-route-table --subnet-id "$SUBNET_PUB1" --route-table-id "$RT_ID"
aws ec2 associate-route-table --subnet-id "$SUBNET_PUB2" --route-table-id "$RT_ID"
```

### Subnets privés (RDS, ElastiCache) — 2 AZ

RDS et ElastiCache **exigent** des sous-réseaux privés (le groupe de sous-réseaux
DB n'accepte que les sous-réseaux privés). Ils sont créés ici **pour la base et
le cache uniquement**, sans passerelle NAT :

```bash
SUBNET_PRI1=$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block 10.0.10.0/24 --availability-zone "${AWS_REGION}a" --query 'Subnet.SubnetId' --output text)
SUBNET_PRI2=$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block 10.0.11.0/24 --availability-zone "${AWS_REGION}b" --query 'Subnet.SubnetId' --output text)

echo "SUBNET_PRI1=$SUBNET_PRI1"; echo "SUBNET_PRI2=$SUBNET_PRI2"
```

> **Pas de passerelle NAT**, et c'est délibéré : elle est facturée en continu
> (≈ 0,045 €/h, soit ~33 €/mois, **plus** le trafic facturé au Go) alors qu'elle
> n'est pas nécessaire à cette architecture.
>
> Pourquoi elle est inutile ici :
> - les tâches Fargate sont placées dans les **sous-réseaux publics** avec une IP
>   publique (`assignPublicIp=ENABLED`) : leur sortie Internet (ECR, CloudWatch,
>   S3, SES) passe par la passerelle Internet du VPC ;
> - RDS et ElastiCache, en sous-réseaux privés, **n'ont besoin d'aucune sortie**
>   Internet ;
> - l'entrée directe vers les tâches reste fermée : leur groupe de sécurité
>   n'accepte le port 8080 que depuis le groupe de sécurité de l'ALB.
>
> Si l'organisation exige un jour des tâches **sans IP publique**, la NAT devra
> être créée à ce moment-là (les VPC endpoints S3/ECR/CloudWatch ne couvrent pas
> le trafic SES).

```bash
# Récupérer les IDs si besoin
aws ec2 describe-subnets --filters "Name=tag:Name,Values=*csig*" --query 'Subnets[*].{AZ:AvailabilityZone,Id:SubnetId}' --output table
```

---

## Étape 3 — Security Groups

Création des grades de sécurité réseau. Chacun n'accepte que le trafic
nécessaire depuis le groupe qui en a besoin (pas de 0.0.0.0/0 inutile).

```bash
# 1. SG du service ECS (reçoit le trafic de l'ALB sur 8080)
SG_ECS=$(aws ec2 create-security-group --group-name csig-sg-ecs --description "ECS tasks" --vpc-id "$VPC_ID" --query 'GroupId' --output text)

# 2. SG de l'ALB (reçoit HTTP/HTTPS public)
SG_ALB=$(aws ec2 create-security-group --group-name csig-sg-alb --description "ALB" --vpc-id "$VPC_ID" --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id "$SG_ALB" --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id "$SG_ALB" --protocol tcp --port 443 --cidr 0.0.0.0/0

# 3. SG RDS (5432 uniquement depuis le SG ECS)
SG_RDS=$(aws ec2 create-security-group --group-name csig-sg-rds --description "RDS" --vpc-id "$VPC_ID" --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id "$SG_RDS" --protocol tcp --port 5432 --source-group "$SG_ECS"

# 4. SG ElastiCache (6379 uniquement depuis le SG ECS)
SG_CACHE=$(aws ec2 create-security-group --group-name csig-sg-cache --description "ElastiCache" --vpc-id "$VPC_ID" --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id "$SG_CACHE" --protocol tcp --port 6379 --source-group "$SG_ECS"

# 5. Autoriser ECS → tout sortant (pull ECR, OS, etc.)
aws ec2 authorize-security-group-egress --group-id "$SG_ECS" --protocol -1 --cidr 0.0.0.0/0

# 6. Autoriser ALB → ECS sur 8080
aws ec2 authorize-security-group-ingress --group-id "$SG_ECS" --protocol tcp --port 8080 --source-group "$SG_ALB"

# Afficher les valeurs
echo "SG_ECS=$SG_ECS"; echo "SG_ALB=$SG_ALB"; echo "SG_RDS=$SG_RDS"; echo "SG_CACHE=$SG_CACHE"
```

---

## Étape 4 — Base de données (RDS PostgreSQL)

```bash
# Vérifier la version PostgreSQL dispo dans la région
aws rds describe-db-engine-versions --engine postgres \
  --query "DBEngineVersions[?EngineVersion >= '16'].{Version:EngineVersion,Default:DefaultForEngine}" \
  --output table

# Groupe de subnets privées du VPC (OBLIGATOIRE avant de créer l'instance RDS)
aws rds create-db-subnet-group \
  --db-subnet-group-name csig-db-subs \
  --db-subnet-group-description "Subnets prives pour RDS" \
  --subnet-ids "$SUBNET_PRI1" "$SUBNET_PRI2"

# Créer la base (attendre ~10 min)
aws rds create-db-instance \
  --db-instance-identifier csig-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 16.3 \
  --master-username csig_admin \
  --master-user-password 'FortMotDePasse!2026' \
  --allocated-storage 20 \
  --db-name csigdb \
  --multi-az false \
  --publicly-accessible false \
  --backup-retention-period 7 \
  --vpc-security-group-ids "$SG_RDS" \
  --db-subnet-group-name csig-db-subs

# Attendre que le statut passe à "available"
aws rds wait db-instance-available --db-instance-identifier csig-db
```

Récupérer l'endpoint :

```bash
RDS_ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier csig-db \
  --query 'DBInstances[0].Endpoint.Address' --output text)
echo "RDS_ENDPOINT=$RDS_ENDPOINT"   # ex. csig-db.xxxxx.eu-north-1.rds.amazonaws.com
```

### Migration des données depuis Neon (une seule fois)

```bash
pg_dump "postgresql://neondb_owner:...@ep-....neon.tech/neondb?sslmode=require" \
  --no-owner --no-privileges \
  | psql "postgresql://csig_admin:FortMotDePasse!2026@$RDS_ENDPOINT:5432/csigdb?sslmode=require"
```

Puis appliquer les migrations encore non appliquées + recréer l'admin (le dump
contient déjà les tables/relations, `migrate` ne crée que les delta) :

```bash
# Depuis le dossier du projet, avec le bon .env pointant sur RDS
python manage.py migrate
python manage.py create_admin          # si un compte admin n'existe pas dans le dump
python manage.py fix_sequences         # remet les séquences à jour après le dump
```

**Fichier `.env` de prod (section base)** :

```bash
DATABASE_URL=postgresql://csig_admin:FortMotDePasse!2026@$RDS_ENDPOINT:5432/csigdb?sslmode=require
```

---

## Étape 5 — Redis / Channel layer (ElastiCache)

Le projet utilise `channels_redis` (Redis channel layer) dès que `REDIS_URL`
est définie (sinon InMemory, non-SGI multi-noeud).

```bash
# Groupe de subnets ElastiCache (subnets privés du VPC)
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name csig-cache-subs \
  --cache-subnet-group-description "Subnets pour ElastiCache" \
  --subnet-ids "$SUBNET_PRI1" "$SUBNET_PRI2"

# Cluster Redis (cluster mode disabled, 1 nœud)
aws elasticache create-replication-group \
  --replication-group-id csig-cache \
  --replication-group-description "Channel layer du dashboard" \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --engine-version 7.1 \
  --num-cache-clusters 1 \
  --cache-subnet-group-name csig-cache-subs \
  --security-group-ids "$SG_CACHE" \
  --transit-encryption-enabled \
  --at-rest-encryption-enabled \
  --automatic-failover-enabled false

# Attendre
aws elasticache wait replication-group-available --replication-group-id csig-cache
```

Récupérer l'endpoint (TLS, d'où `rediss://`) :

```bash
CACHE_ENDPOINT=$(aws elasticache describe-replication-groups \
  --replication-group-id csig-cache \
  --query 'ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint.Address' --output text)
echo "CACHE_ENDPOINT=$CACHE_ENDPOINT"
```

```bash
# .env de prod
REDIS_URL=rediss://$CACHE_ENDPOINT:6379/0
```

> ElastiCache n'accepte que les connexions **dans le VPC** — d'où le
> `--security-group-ids "$SG_CACHE"` limité au SG ECS. Le port 6379 n'est pas
> accessible depuis l'extérieur.

---

## Étape 6 — Stockage médias (S3 + CloudFront OAC)

Le projet utilise `django-storages[s3]` dès que `AWS_STORAGE_BUCKET_NAME` est
définie (sinon `FileSystemStorage` local).

### 6.1 Créer le bucket S3 privé

```bash
aws s3api create-bucket --bucket csig-media --region "$AWS_REGION" \
  --create-bucket-configuration LocationConstraint="$AWS_REGION"
# (option) Bloquer l'accès public (garde-fou sécurité)
aws s3api put-public-access-block --bucket csig-media \
  --public-access-block-configuration 'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'
```

### 6.2 Créer le CloudFront OAC (Origin Access Control)

```bash
OAC_ID=$(aws cloudfront create-origin-access-control \
  --origin-access-control-config '{
    "Name":"csig-oac",
    "Description":"OAC pour le bucket csig-media",
    "SigningProtocol":"sigv4",
    "SigningBehavior":"always",
    "OriginAccessControlOriginType":"s3"
  }' --query 'OriginAccessControl.Id' --output text)
echo "OAC_ID=$OAC_ID"
```

### 6.3 Créer la distribution CloudFront

Récupérer l'ID du compte (ARN de la distribution) :

```bash
# Créer la distribution (S3 origin + OAC attaché)
DIST_INFO=$(aws cloudfront create-distribution \
  --distribution-config "{
    \"CallerReference\":\"csig-dist-$(date +%s)\",
    \"Comment\":\"CSIG media\",
    \"Enabled\":true,
    \"Origins\":{
      \"Quantity\":1,
      \"Items\":[{
        \"Id\":\"s3-csig-media\",
        \"DomainName\":\"csig-media.s3.$AWS_REGION.amazonaws.com\",
        \"OriginAccessControlId\":\"$OAC_ID\",
        \"S3OriginConfig\":{\"OriginAccessIdentity\":\"\"}
      }]
    },
    \"DefaultCacheBehavior\":{
      \"TargetOriginId\":\"s3-csig-media\",
      \"ViewerProtocolPolicy\":\"redirect-to-https\",
      \"AllowedMethods\":{\"Quantity\":2,\"Items\":[\"GET\",\"HEAD\"],\"CachedMethods\":{\"Quantity\":2,\"Items\":[\"GET\",\"HEAD\"]}},
      \"Compress\":true,
      \"CachePolicyId\":\"658327ea-f89d-4fab-a63d-7e88639e58f6\"
    }
  }")
DIST_ID=$(echo "$DIST_INFO" | python -c "import sys,json;print(json.load(sys.stdin)['Distribution']['Id'])")
DIST_DOMAIN=$(echo "$DIST_INFO" | python -c "import sys,json;print(json.load(sys.stdin)['Distribution']['DomainName'])")
echo "DIST_ID=$DIST_ID"
echo "DIST_DOMAIN=$DIST_DOMAIN"   # ex. dXYZ.cloudfront.net
```

> `658327ea-f89d-4fab-a63d-7e88639e58f6` est l'ID de la cache policy gérée
> `Managed-CachingOptimized` (ne pas changer).

### 6.4 Autoriser CloudFront à lire le bucket (bucket policy)

```bash
aws s3api put-bucket-policy --bucket csig-media --policy "{
  \"Version\":\"2012-10-17\",
  \"Statement\":[{
    \"Sid\":\"AllowCloudFrontServicePrincipalReadOnly\",
    \"Effect\":\"Allow\",
    \"Principal\":{\"Service\":\"cloudfront.amazonaws.com\"},
    \"Action\":\"s3:GetObject\",
    \"Resource\":\"arn:aws:s3:::csig-media/*\",
    \"Condition\":{\"StringEquals\":{\"AWS:SourceArn\":\"arn:aws:cloudfront::$ACCOUNT_ID:distribution/$DIST_ID\"}}
  }]
}"
```

### 6.5 Variables `.env` média

```bash
AWS_STORAGE_BUCKET_NAME=csig-media
AWS_S3_REGION=$AWS_REGION
AWS_CLOUDFRONT_DOMAIN=$DIST_DOMAIN
```

---

## Étape 7 — Emails (Amazon SES)

Le projet choisit le backend SES dès que `AWS_SES_REGION` est défini
(`core.email_backend.SESBackend`, qui utilise `send_raw_email`). Les credentials
proviennent du rôle de tâche `csig-task-role` ; aucune clé n'est requise dans
l'environnement du conteneur.

### 7.1 Vérifier le domaine (production)

```bash
aws sesv2 create-email-identity --identity-name csig.edu.gn --region "$AWS_REGION"
# Récupérer les 3 enregistrements DNS DKIM à ajouter chez ton hébergeur
aws sesv2 get-email-identity --email-identity csig.edu.gn --region "$AWS_REGION" \
  --query 'DkimAttributes' --output json
```

Sur l'hébergeur DNS du domaine `csig.edu.gn`, ajouter :

- 1 enregistrement **MX** vers le serveur mail du domaine,
- 3 enregistrements **CNAME** `*.dkim.amazonses.com` (donnés par SES),
- éventuellement un **SPF** : `v=spf1 include:amazonses.com ~all`.

La vérification dans SES devient « Success » (quelques minutes à quelques
heures). Tant que le domaine n'est pas vérifié, on peut envoyer vers une
adresse de test vérifiée :

```bash
aws sesv2 create-email-identity --identity-name admin@csig.edu.gn --region "$AWS_REGION"
```

### 7.2 Variables `.env` email

```bash
AWS_SES_REGION=$AWS_REGION
DEFAULT_FROM_EMAIL=noreply@csig.edu.gn
```

---

## Étape 8 — Registre d'images (ECR) + build Docker

```bash
# Créer le registre
aws ecr create-repository --repository-name csig-dashboard --region "$AWS_REGION"

# Login Docker (Token court durée)
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Build de l'image
docker build -t csig-dashboard .

# Tag + push
docker tag csig-dashboard "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/csig-dashboard:latest"
docker push "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/csig-dashboard:latest"
```

> Windows PowerShell : le pipe `get-login-password | docker login
> --password-stdin` fonctionne (PowerShell 5.1+).

---

## Étape 9 — Secrets de l'application (SSM Parameter Store)

Les 3 secrets de l'application (clé Django, base de données, Redis) sont stockés
dans **SSM Parameter Store** en `SecureString`, et injectés dans le conteneur via
`secrets[].valueFrom` de la task definition — **jamais en clair** dans la task
definition ni dans l'image Docker.

> Pourquoi Parameter Store plutôt que Secrets Manager : les paramètres standard
> sont **sans frais** (jusqu'à 4 Ko par valeur) et sans coût d'API par
> consultation, alors que Secrets Manager est facturé par secret et par tranche
> de 10 000 appels. Pour 3 petites valeurs, Parameter Store est le choix
> raisonnable. (Réf. [AWS prescriptive guidance — secrets management](https://docs.aws.amazon.com/prescriptive-guidance/latest/aws-startup-security-baseline/wkld-03.html))

```bash
# Clé secrète Django (générer une valeur aléatoire longue)
DJANGO_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(64))")

aws ssm put-parameter --name /csig/prod/django_secret_key --type SecureString --overwrite \
  --value "$DJANGO_SECRET"

aws ssm put-parameter --name /csig/prod/database_url --type SecureString --overwrite \
  --value "postgresql://csig_admin:FortMotDePasse!2026@$RDS_ENDPOINT:5432/csigdb?sslmode=require"

aws ssm put-parameter --name /csig/prod/redis_url --type SecureString --overwrite \
  --value "rediss://$CACHE_ENDPOINT:6379/0"

aws ssm get-parameters-by-path --path /csig/prod --with-decryption
```

> Les paramètres `SecureString` sont chiffrés avec la clé AWS gérée
> `alias/aws/ssm` par défaut : **aucune** permission `kms:Decrypt` n'est donc
> nécessaire dans le rôle d'exécution.

### 9.1 Permissions du rôle d'exécution pour lire les secrets

C'est l'agent ECS, via le **rôle d'exécution**, qui récupère les secrets et les
injecte dans le conteneur (réf. [ECS — task execution IAM role](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html)).
Il faut donc ajouter au rôle `csig-ecs-execution-role` :

```bash
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

> L'action est `ssm:GetParameters` (pluriel), telle que requise par ECS. Les
> 3 paramètres sont nommés explicitement : aucune permission en lecture large
> sur l'ensemble du Parameter Store.
>
> Variante Secrets Manager, si l'organisation l'impose :
> `secretsmanager:GetSecretValue` sur
> `arn:aws:secretsmanager:eu-north-1:499243079539:secret:csig/prod-*`
> (le joker remplace le suffixe aléatoire que Secrets Manager ajoute à l'ARN,
> et il ne faut pas inclure de version).

---

## Étape 10 — ECS Fargate + ALB

### 10.1 Cluster ECS

```bash
aws ecs create-cluster --cluster-name csig-prod --region "$AWS_REGION"
```

### 10.2 Task definition

Fichier `task-definition.json` (adapter l'image et les ARNs) :

```json
{
  "family": "csig-dashboard",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "runtimePlatform": { "cpuArchitecture": "X86_64", "operatingSystemFamily": "LINUX" },
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/csig-ecs-execution-role",
  "taskRoleArn": "arn:aws:iam::ACCOUNT_ID:role/csig-task-role",
  "containerDefinitions": [
    {
      "name": "web",
      "image": "ACCOUNT_ID.dkr.ecr.eu-north-1.amazonaws.com/csig-dashboard:latest",
      "essential": true,
      "portMappings": [ { "containerPort": 8080, "protocol": "tcp" } ],
      "environment": [
        { "name": "DJANGO_DEBUG", "value": "False" },
        { "name": "DJANGO_ALLOWED_HOSTS", "value": "dashbord.csig.edu.gn,ALB-DNS" },
        { "name": "DJANGO_CSRF_TRUSTED_ORIGINS", "value": "https://dashbord.csig.edu.gn" },
        { "name": "SITE_URL", "value": "https://dashbord.csig.edu.gn" },
        { "name": "AWS_S3_REGION", "value": "eu-north-1" },
        { "name": "AWS_STORAGE_BUCKET_NAME", "value": "csig-media" },
        { "name": "AWS_CLOUDFRONT_DOMAIN", "value": "dXXXX.cloudfront.net" },
        { "name": "AWS_SES_REGION", "value": "eu-north-1" },
        { "name": "DEFAULT_FROM_EMAIL", "value": "noreply@csig.edu.gn" },
        { "name": "DJANGO_SECURE_SSL", "value": "1" },
        { "name": "DJANGO_HSTS", "value": "1" }
      ],
      "secrets": [
        { "name": "DJANGO_SECRET_KEY", "valueFrom": "arn:aws:ssm:eu-north-1:499243079539:parameter/csig/prod/django_secret_key" },
        { "name": "DATABASE_URL",      "valueFrom": "arn:aws:ssm:eu-north-1:499243079539:parameter/csig/prod/database_url" },
        { "name": "REDIS_URL",         "valueFrom": "arn:aws:ssm:eu-north-1:499243079539:parameter/csig/prod/redis_url" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/csig-prod",
          "awslogs-region": "eu-north-1",
          "awslogs-stream-prefix": "web"
        }
      }
    }
  ]
}
```

> Les secrets (`DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`) sont de
> préférence injectés via `secrets` → `valueFrom` (étape 9).

Enregistrer :

```bash
aws ecs register-task-definition --cli-input-json file://task-definition.json --region "$AWS_REGION"
```

> **Phase sans certificat (avant le domaine)** : le certificat ACM suppose de
> pouvoir valider le DNS de `csig.edu.gn`. Tant que ce n'est pas possible,
> démarrer l'ALB avec un listener HTTP seul sur le port 80 et mettre
> `DJANGO_SECURE_SSL=0` + `DJANGO_HSTS=0` dans l'`environment` de la task
> definition. Sans cela, `SECURE_SSL_REDIRECT` renvoie une boucle de 301 et les
> cookies `Secure` ne sont jamais renvoyés par le navigateur : **la connexion est
> impossible**. Ces deux variables sont pilotées par `settings.py`, défaut `1`
> (mode sûr). Remettre `1` (ou supprimer les lignes) dès que l'écouteur 443
> porte le certificat ACM.

> `runtimePlatform` est explicite : sans lui, Fargate prend `LATEST` par défaut,
> qui peut être un runtime retiré et faire échouer le lancement de la tâche.

### 10.3 ALB (Application Load Balancer)

```bash
# Créer l'ALB (subnets publics)
ALB_ARN=$(aws elbv2 create-load-balancer \
  --name csig-alb \
  --subnets "$SUBNET_PUB1" "$SUBNET_PUB2" \
  --security-groups "$SG_ALB" \
  --scheme internet-facing \
  --type application \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text)

# Target group (target type IP, obligatoire pour Fargate) — Health check sur /
TG_ARN=$(aws elbv2 create-target-group \
  --name csig-tg \
  --protocol HTTP \
  --port 8080 \
  --vpc-id "$VPC_ID" \
  --target-type ip \
  --health-check-protocol HTTP \
  --health-check-path /healthz/ \
  --health-check-interval-seconds 30 \
  --query 'TargetGroups[0].TargetGroupArn' --output text)
echo "TG_ARN=$TG_ARN"
```

> **Health check** : le projet expose une route de santé `GET /healthz/`
> (vérifie la connexion DB, répond 200/503 JSON). C'est le path ciblé par l'ALB.

**Listener HTTPS (443)** — certificat ACM obligatoire :

> **Région ACM** : le certificat du **ALB** doit être créé dans **la même région
> que l'ALB** (`$AWS_REGION`, ici `eu-north-1`). Seul un certificat **CloudFront**
> (distribution du CDN) se crée en `us-east-1` (obligatoire). Ne pas confondre
> les deux.

```bash
# Demander le certificat pour le domaine (validation DNS) — régional ALB
CERT_ARN=$(aws acm request-certificate \
  --domain-name dashbord.csig.edu.gn \
  --validation-method DNS \
  --region "$AWS_REGION" \
  --query 'CertificateArn' --output text)
# → ajouter le CNAME de validation chez l'hébergeur, attendre "ISSUED"

# Listener 443 → target group
aws elbv2 create-listener \
  --load-balancer-arn "$ALB_ARN" \
  --protocol HTTPS \
  --port 443 \
  --certificates "CertificateArn=$CERT_ARN" \
  --default-actions "Type=forward,TargetGroupArn=$TG_ARN"

# Redirection 80 → 443
aws elbv2 create-listener \
  --load-balancer-arn "$ALB_ARN" \
  --protocol HTTP \
  --port 80 \
  --default-actions "Type=redirect,RedirectConfig={Protocol=HTTPS,Port=443,StatusCode=HTTP_301}"
```

> **Sticky sessions** (obligatoire pour les WebSockets du channel layer) :

```bash
aws elbv2 modify-target-group-attributes \
  --target-group-arn "$TG_ARN" \
  --attributes Key=stickiness.enabled,Value=true Key=stickiness.lb_cookie.duration_seconds,Value=86400
```

Par défaut l'ALB gère HTTP/WS ; les WebSockets passent via le listener 443 avec
le(s) même(s) comportamento(s) — aucun réglage supplémentaire nécessaire.

Récupérer le DNS de l'ALB :

```bash
ALB_DNS=$(aws elbv2 describe-load-balancers --load-balancer-arns "$ALB_ARN" \
  --query 'LoadBalancers[0].DNSName' --output text)
echo "ALB_DNS=$ALB_DNS"   # ex. csig-alb-xxxx.eu-north-1.elb.amazonaws.com
```

### 10.4 Service ECS

```bash
aws ecs create-service \
  --cluster csig-prod \
  --service-name web \
  --task-definition csig-dashboard \
  --desired-count 1 \
  --launch-type FARGATE \
  --platform-version LATEST \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_PUB1,$SUBNET_PUB2],securityGroups=[$SG_ECS],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=$TG_ARN,containerName=web,containerPort=8080" \
  --region "$AWS_REGION"
```

Vérifier que les tâches passent RUNNING et que l'ALB a des cibles healthy :

```bash
aws ecs list-tasks --cluster csig-prod --service-name web --desired-status RUNNING \
  --query 'taskArns' --output text
aws ecs describe-services --cluster csig-prod --services web \
  --query 'services[0].{status:status,desired:desiredCount,running:runningCount,pending:pendingCount}'
```

---

## Étape 11 — DNS (Route 53) et accès

Une fois l'ALB opérationnel, pointer le domaine vers lui :

```
CNAME dashbord.csig.edu.gn →  <ALB_DNS>
```

Ou sur Route 53, créer un **alias record A** pointant vers l'ALB :

```bash
aws route53 change-resource-record-sets --hosted-zone-id ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "dashbord.csig.edu.gn",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "Z23TAZ6LKFMNIO",
          "DNSName": "<ALB_DNS>",
          "EvaluateTargetHealth": false
        }
      }
    }]
  }'
```

> `Z23TAZ6LKFMNIO` = hosted zone ID des ALB (eu-north-1). Seulement pour un
> **alias A** Route 53 ; en CNAME classique, aucune hosted zone ID n'est requise.

Tester :

```
curl https://dashbord.csig.edu.gn       # → 302 vers /login/ (ou 200 sur la page)
```

---

## Étape 12 — Vérifications de bout en bout

Depuis le navigateur (ou `curl -k` avant DNS) :

1. **Login** : `/login/` s'affiche, connexion admin OK.
2. **DB** : `python manage.py check` / `migrate --check` pas d'erreur (testé dans
   le conteneur, ex. `aws ecs run-task`).
3. **Emails** : créer un projet → notification part par SES (log CloudWatch).
4. **Médias** : uploader un document → le fichier arrive dans `s3://csig-media/`
   et l'URL CloudFront s'affiche, lecture OK.
5. **WebSockets** : deux onglets, marquer une tâche → mise à jour temps réel sur
   le second (channel layer Redis, sticky ALB).
6. **Statiques** : les CSS/JS se servent via WhiteNoise (collectstatic) ou
   CloudFront si on bascule les staticfiles dessus.

Logs :

```bash
aws logs tail /ecs/csig-prod --follow --region "$AWS_REGION"
```

---

## Étape 13 — Nettoyage de l'ancienne stack

Une fois tout validé sur AWS :

1. **Neon** : garder le snapshot de secours, puis supprimer quand RDS est
   stable et le `pg_dump` vérifié.
2. **Render** : désactiver le service web après la bascule DNS (garder un temps
   pour la transition).
3. **Cloudinary** : exporter les URLs stockées (elles sont déjà en base en
   format `https://res.cloudinary.com/...`) et supprimer le cloud (facultatif).
4. **Resend / SMTP** : désactiver l'API (aucune ressource serveur).

---

## Étape 14 — CI/CD : cible retenue, activation plus tard

Décision : le **premier déploiement reste manuel** (étapes 1 à 13). La cible
retenue pour la suite est **GitHub Actions + AWS OIDC**, pas CodePipeline : le
dépôt est déjà sur GitHub, le runner est gratuit, et surtout il n'y a **aucune
clé AWS à stocker dans GitHub** (OIDC échange un jeton d'identité contre des
credentials temporaires d'une heure, révocables par expiration).

Quand l'appliquer : après un premier déploiement manuel réussi, et dès que les
mises en production sont régulières. Le pipeline ne reproduira que les étapes 8
et 10 (build/push ECR + mise à jour du service).

### Ce que fera le workflow (`.github/workflows/deploy.yml`)

Sur `push` sur `master` :

1. **Garde-fou** : `manage.py check` et `makemigrations --check --dry-run`
   (le projet n'a pas de suite de tests automatisés : c'est le seul filet
   disponible, et il attrape les migrations manquantes et les erreurs de config).
2. **Authentification OIDC** : `aws-actions/configure-aws-credentials` sur le
   rôle `csig-github-actions` — aucun secret AWS dans les variables du dépôt.
3. **Image** : build Docker, tag = SHA du commit, push vers
   `$ACCOUNT_ID.dkr.ecr.eu-north-1.amazonaws.com/csig-dashboard`.
4. **Task definition** : substitution du champ `"image"` dans
   `task-definition.json`, puis `register-task-definition` (famille
   `csig-dashboard`).
5. **Déploiement** : `update-service`, puis `aws ecs wait services-stable`
   (le job échoue si le service ne converge pas).

### Rôle IAM à demander le jour venu

Un rôle **séparé** de `csig-task-role` et `csig-ecs-execution-role`, jamais
réutilisé :

- trust policy : provider OIDC GitHub (`token.actions.githubusercontent.com`),
  condition `repo:Bella5768/Dashbord_Direction:ref:refs/heads/master` — seule la
  branche `master` de ce dépôt peut donc endosser ce rôle ;
- permissions : `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`,
  `ecr:PutImage`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`,
  `ecr:CompleteLayerUpload`, `ecr:BatchGetImage`,
  `ecs:RegisterTaskDefinition`, `ecs:DescribeTaskDefinition`,
  `ecs:UpdateService`, `ecs:DescribeServices` ;
- `iam:PassRole` sur `csig-ecs-execution-role` et `csig-task-role`, conditionné
  par `iam:PassedToService = ecs-tasks.amazonaws.com`.

Ce rôle **ne doit pas** accéder aux paramètres SSM : les secrets sont lus au
runtime par le rôle d'exécution ECS, pas par la CI. Ni S3, ni RDS, ni
ElastiCache, ni IAM. Il est permanent mais étroit — c'est lui qui remplace, à
terme, la politique de déploiement temporaire de `docs/AWS_ADMIN_DEMANDE.md`.

### Ce qui reste manuel

La création de l'infrastructure (étapes 1 à 7, 9 et 11 : VPC, RDS, Redis, S3,
SES, ECS/ALB, SSM, DNS) : c'est ponctuel et sans vocation à être automatisé.
Seuls le build et le déploiement de l'image le seront.

> Si CodePipeline/CodeBuild est préféré plus tard, seules l'étape 2 et la liste
> de permissions changent : le `Dockerfile` et le `task-definition.json` sont
> réutilisables tels quels.

---

## Annexe A — Variables d'environnement finales (conteneur ECS)

Variables **non sensibles** (dans `environment` de la task definition) :

```ini
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=dashbord.csig.edu.gn,<ALB_DNS>
DJANGO_CSRF_TRUSTED_ORIGINS=https://dashbord.csig.edu.gn
SITE_URL=https://dashbord.csig.edu.gn
# Pas de AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY :
# le rôle de tâche csig-task-role fournit les credentials au conteneur.
AWS_STORAGE_BUCKET_NAME=csig-media
AWS_S3_REGION=eu-north-1
AWS_CLOUDFRONT_DOMAIN=dXYZ.cloudfront.net
AWS_SES_REGION=eu-north-1
DEFAULT_FROM_EMAIL=noreply@csig.edu.gn
# 1 = TLS et HSTS actifs (défaut). Mettre 0 / 0 uniquement tant que l'ALB
# n'a qu'un listener HTTP 80, sinon le login est impossible (cf. étape 10.2).
DJANGO_SECURE_SSL=1
DJANGO_HSTS=1
```

Variables **sensibles** — jamais en clair, injectées via `secrets[].valueFrom`
(étape 9) :

```ini
DJANGO_SECRET_KEY  <- ssm:/csig/prod/django_secret_key
DATABASE_URL       <- ssm:/csig/prod/database_url
REDIS_URL          <- ssm:/csig/prod/redis_url
```

---

## Annexe D — Droits nécessaires, par phase

Trois périmètres bien distincts, à ne pas confondre :

### Runtime — le conteneur (permanent)

Couverture par les 2 rôles ECS uniquement, sans aucune clé :

| Rôle | Politique |
|------|-----------|
| `csig-ecs-execution-role` | managée `AmazonECSTaskExecutionRolePolicy` (tirer l'image ECR, écrire les logs CloudWatch) + inline `app-secrets` (`ssm:GetParameters` sur les 3 paramètres nommés) |
| `csig-task-role` | inline `media-and-mail` (bucket `csig-media` + `ses:SendRawEmail`), bornée au bucket et à l'expéditeur |

Aucune clé AWS n'est nécessaire dans le conteneur ni dans la task definition, et
aucun secret n'y figure en clair.

### Déploiement — l'opérateur (une fois, puis retrait)

Pour exécuter les étapes 2 à 10 de ce guide, l'opérateur doit pouvoir créer les
ressources du projet. La liste exacte des actions demandées figure dans
`docs/AWS_ADMIN_DEMANDE.md` §7 ; en résumé :

`ec2` (VPC, sous-réseaux, tables de routage, groupes de sécurité),
`rds`, `elasticache`, `ecr`, `ecs`, `elasticloadbalancer`, `acm`, `cloudfront`,
`s3` (création du bucket et de sa politique), `sesv2` (identité email),
`route53`, `ssm` (écriture des 3 paramètres), et côté IAM
`iam:CreateServiceLinkedRole` + `iam:PassRole` sur les 2 rôles ECS.

Ces droits sont **ponctuels** : ils servent à créer l'infrastructure, pas à faire
tourner l'application. Deux options :

1. l'opérateur possède déjà ces droits → il exécute le guide lui-même, aucune
   demande d'accès supplémentaire ;
2. sinon, la politique explicite de la demande est accordée **pour la durée du
   déploiement**, puis retirée.

`PowerUserAccess` n'est pas nécessaire : il donne plus que requis et ne
correspond à aucun des deux périmètres ci-dessus.

> Corrélation avec `settings.py` : `DATABASE_URL` → PostgreSQL ; `REDIS_URL` →
> channel layer ; `AWS_STORAGE_BUCKET_NAME` → django-storages S3 ;
> `AWS_CLOUDFRONT_DOMAIN` → URLs médias CloudFront ; `AWS_*` + `AWS_SES_REGION`
> → `SESBackend` ; `DJANGO_CSRF_TRUSTED_ORIGINS` → CSRF ; `SITE_URL` →
> liens dans les emails.

---

## Annexe B — Commandes utiles

```bash
# Logs d'une tâche
aws logs tail /ecs/csig-prod --follow --region "$AWS_REGION"

# Shell interactif dans le conteneur (si EnableExecuteCommand)
aws ecs execute-command --cluster csig-prod --task TASK_ID --container web \
  --interactive --command "/bin/bash"

# Appliquer les migrations one-off
aws ecs run-task --cluster csig-prod --task-definition csig-dashboard \
  --overrides '{"containerOverrides":[{"name":"web","command":["python","manage.py","migrate"]}]}'

# Redéployer après un push (forcer un nouveau déploiement)
aws ecs update-service --cluster csig-prod --service web \
  --force-new-deployment --region "$AWS_REGION"

# Lister les tâches
aws ecs list-tasks --cluster csig-prod --desired-status RUNNING --query 'taskArns'
```

---

## Annexe C — Ajustements du code éventuels

- **Healthcheck** : `GET /healthz/` est exposé (`dashboard_csig/urls.py`) —
  aucun login, vérifie la DB, répond 200 `{"status":"ok"}` ou 503 si la base
  est injoignable. C'est le path ciblé par l'ALB.
- **ALLOWED_HOSTS** : l'ALB doit figurer dans `DJANGO_ALLOWED_HOSTS` sinon Django
  refuse l'accès aux requêtes (erreur 400).
- **CSRF / HSTS** : `SECURE_PROXY_SSL_HEADER` est déjà réglé ; l'ALB doit
  transmettre l'en-tête `X-Forwarded-Proto` (c'est le cas par défaut).
- **Sticky sessions** : obligatoires pour le WebSocket. Si l'ALB est remplacé
  par un NLB, les WS passeront quand même (NLB conserve la connexion TCP), mais
  l'ALB reste le choix cohérent avec HTTPS/ACM.