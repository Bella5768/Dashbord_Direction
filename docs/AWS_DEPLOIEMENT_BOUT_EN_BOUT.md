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
| 0 | IAM                   | `csig-deploy`, rôles ECS | accès et permissions |
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

### 1.1 Utilisateur de déploiement `csig-deploy`

Obligatoire pour : pousser l'image ECR, créer/updater les tâches ECS, lire les
logs CloudWatch. D'autres services (RDS, SES, S3) sont créés avec le même
utilisateur dans ce guide.

```bash
# Créer l'utilisateur sans console (accès programme uniquement)
aws iam create-user --user-name csig-deploy
```

Politique attachée directement (customer managed simple, en attendant une
stratégie plus fine) :

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": ["ecr:GetAuthorizationToken"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["s3:*"], "Resource": ["arn:aws:s3:::csig-media", "arn:aws:s3:::csig-media/*"] },
    { "Effect": "Allow", "Action": ["ses:SendEmail", "ses:SendRawEmail"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["elasticache:DescribeCacheClusters", "elasticache:DescribeReplicationGroups"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["rds:DescribeDBInstances"], "Resource": "*" }
  ]
}
```

```bash
# Enregistrer la politique par défaut (s3 + ses + ecr) :
# → soit via un fichier policy.json, soit directement inline :
aws iam put-user-policy \
  --user-name csig-deploy \
  --policy-name csig-deploy-policy \
  --policy-document '{"Version":"2012-10-17","Statement":[
    {"Effect":"Allow","Action":["ecr:GetAuthorizationToken"],"Resource":"*"},
    {"Effect":"Allow","Action":["s3:*"],"Resource":["arn:aws:s3:::csig-media","arn:aws:s3:::csig-media/*"]},
    {"Effect":"Allow","Action":["ses:SendEmail","ses:SendRawEmail"],"Resource":"*"}
  ]}'
```

Créer l'Access Key (gardée dans le secret du CI ou le `.env` du conteneur) :

```bash
aws iam create-access-key --user-name csig-deploy
# → noter AccessKeyId + SecretAccessKey (affiché une seule fois)
```

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

Le conteneur a besoin de S3 (médias) et de SES (emails) **au runtime** :

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
      {"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListBucket"],
       "Resource":["arn:aws:s3:::csig-media","arn:aws:s3:::csig-media/*"]},
      {"Effect":"Allow","Action":["ses:SendEmail","ses:SendRawEmail"],"Resource":"*"}
    ]
  }'

CSIG_TASK_ROLE_ARN=$(aws iam get-role --role-name csig-task-role --query 'Role.Arn' --output text)
echo "$CSIG_TASK_ROLE_ARN"
```

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

### Subnets privés (RDS, ElastiCache, tâches) — 2 AZ

RDS et ElastiCache **exigent** des subnets privés (le groupe de subnets DB
accepte les sous-réseaux privés uniquement). On les crée ici avec un NAT
Gateway pour que les tâches Fargate privées puissent sortir (pull ECR, SES) :

```bash
SUBNET_PRI1=$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block 10.0.10.0/24 --availability-zone "${AWS_REGION}a" --query 'Subnet.SubnetId' --output text)
SUBNET_PRI2=$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block 10.0.11.0/24 --availability-zone "${AWS_REGION}b" --query 'Subnet.SubnetId' --output text)

# EIP + NAT Gateway (réside dans un subnet public)
EIP_NAT=$(aws ec2 allocate-address --domain vpc --query 'AllocationId' --output text)
NAT_ID=$(aws ec2 create-nat-gateway --subnet-id "$SUBNET_PUB1" --allocation-id "$EIP_NAT" --query 'NatGateway.NatGatewayId' --output text)
aws ec2 wait nat-gateway-available --nat-gateway-ids "$NAT_ID"

# Route table privée → NAT Gateway (sortie internet)
RT_PRI=$(aws ec2 create-route-table --vpc-id "$VPC_ID" --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id "$RT_PRI" --destination-cidr-block 0.0.0.0/0 --nat-gateway-id "$NAT_ID"
aws ec2 associate-route-table --subnet-id "$SUBNET_PRI1" --route-table-id "$RT_PRI"
aws ec2 associate-route-table --subnet-id "$SUBNET_PRI2" --route-table-id "$RT_PRI"

echo "SUBNET_PRI1=$SUBNET_PRI1"; echo "SUBNET_PRI2=$SUBNET_PRI2"
```

Par simplicité, ce guide place les **tâches Fargate dans les subnets publics**
(`assignPublicIp=ENABLED`), l'ALB restant le point d'entrée. Pour une
architecture de production stricte, passer les tâches en privé
(`assignPublicIp=DISABLED`, subnets ci-dessus — NAT déjà en place).

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

Le projet choisit le backend SES dès que `AWS_ACCESS_KEY_ID` +
`AWS_SECRET_ACCESS_KEY` + `AWS_SES_REGION` sont définies
(`core.email_backend.SESBackend`, qui utilise `send_raw_email`).

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

## Étape 9 — Secrets (optionnel mais recommandé)

Les mots de passe (DB, Django SECRET_KEY) ne doivent pas traîner en clair dans
le JSON de la task definition. Les stocker dans **Secrets Manager** :

```bash
aws secretsmanager create-secret \
  --name csig/prod \
  --secret-string "$(cat <<'EOF'
{
  "DJANGO_SECRET_KEY": "une-cle-tres-longue-et-aleatoire",
  "DJANGO_ADMIN_PASSWORD": "mot-de-passe-admin-fort",
  "DATABASE_URL": "postgresql://csig_admin:FortMotDePasse!2026@$RDS_ENDPOINT:5432/csigdb?sslmode=require",
  "REDIS_URL": "rediss://$CACHE_ENDPOINT:6379/0"
}
EOF
)"
```

Dans la task definition, ces variables seront référencées via
`valueFrom: arn:aws:secretsmanager:...:secret:csig/prod:key::`. Sur Windows la
construction `$(cat <<EOF)` n'est pas disponible — utiliser un fichier JSON
temporaire (voir `echo '{"DJANGO_SECRET_KEY":"..."}' > secret.json`).

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
        { "name": "AWS_SES_REGION", "value": "eu-north-1" },
        { "name": "DEFAULT_FROM_EMAIL", "value": "noreply@csig.edu.gn" },
        { "name": "AWS_ACCESS_KEY_ID", "value": "AKIA.." },
        { "name": "AWS_SECRET_ACCESS_KEY", "value": ".." }
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

## Annexe A — Variables d'environnement finales (conteneur ECS)

```ini
DJANGO_SECRET_KEY=<secret>                         # ou via Secrets Manager
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=dashbord.csig.edu.gn,<ALB_DNS>
DJANGO_CSRF_TRUSTED_ORIGINS=https://dashbord.csig.edu.gn
SITE_URL=https://dashbord.csig.edu.gn
DATABASE_URL=postgresql://csig_admin:...@csig-db...:5432/csigdb?sslmode=require
REDIS_URL=rediss://csig-...cache.amazonaws.com:6379/0
AWS_ACCESS_KEY_ID=AKIA...      # clés csig-deploy (ou via taskRole/pod identity)
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=csig-media
AWS_S3_REGION=eu-north-1
AWS_CLOUDFRONT_DOMAIN=dXYZ.cloudfront.net
AWS_SES_REGION=eu-north-1
DEFAULT_FROM_EMAIL=noreply@csig.edu.gn
```

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