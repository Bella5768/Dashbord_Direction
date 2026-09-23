# Migration AWS — CSIG Dashboard

Migration de la stack de déploiement vers AWS :

| Avant | Après |
|---|---|
| Render | Amazon ECS Fargate (Docker) |
| Neon PostgreSQL | Amazon RDS PostgreSQL |
| Redis externe | Amazon ElastiCache Redis |
| Resend / SMTP | Amazon SES |
| Cloudinary | Amazon S3 + CloudFront |

Le code est déjà prêt (commit `15c92a1`). Ce guide couvre la création des
ressources et la configuration.

> Prérequis : compte AWS, AWS CLI installé et configuré
> (`aws configure`), Docker installé en local pour le build de l'image.

---

## 1. Identité et accès (IAM)

Créer un utilisateur programme + un rôle de tâche ECS.

**1.1 Utilisateur (credentials pour CI/CD et tests locaux)**

Créer un utilisateur `csig-deploy` avec la politique suivante (attachée
directement, en attendant une politique gérée) :

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Resource": ["arn:aws:s3:::csig-media", "arn:aws:s3:::csig-media/*"]
    },
    {
      "Effect": "Allow",
      "Action": ["ses:SendEmail", "ses:SendRawEmail"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["ecr:GetAuthorizationToken", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
      "Resource": "*"
    }
  ]
}
```

Générer une **Access Key** → elle alimente `AWS_ACCESS_KEY_ID` /
`AWS_SECRET_ACCESS_KEY` dans le conteneur et le `.env` local.

**1.2 Rôle de tâche ECS**

Créer un rôle `csig-task-role` (trust policy ECS tasks, `ecs-tasks.amazonaws.com`)
avec les mêmes droits S3/SES (le conteneur a besoin de boto3).

---

## 2. Base de données (RDS PostgreSQL)

```bash
aws rds create-db-instance \
  --db-instance-identifier csig-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 16.3 \
  --master-username csig_admin \
  --master-user-password 'CHANGER-MOI' \
  --allocated-storage 20 \
  --multi-az false \
  --publicly-accessible false \
  --backup-retention-period 7 \
  --vpc-security-group-ids sg-XXXX
```

Dans le groupe de sécurité **RDS**, autoriser le port 5432 en entrée depuis le
groupe de sécurité du service ECS (pas depuis 0.0.0.0/0).

**Migration des données depuis Neon** (une seule fois) :

```bash
pg_dump "postgresql://neondb_owner:...@ep-....neon.tech/neondb?sslmode=require" \
  --no-owner --no-privileges \
  | psql "postgresql://csig_admin:...@csig-db.XXXX.rds.amazonaws.com:5432/csigdb?sslmode=require"
```

Puis appliquer les séquences et migrations :

```bash
python manage.py migrate
python manage.py create_admin --password 'XYZ'  # si dispo
```

Variables `.env` :
```
DATABASE_URL=postgresql://csig_admin:PASS@csig-db.XXXX.rds.amazonaws.com:5432/csigdb?sslmode=require
```

---

## 3. Redis (ElastiCache)

```bash
aws elasticache create-cache-cluster \
  --cache-cluster-id csig-cache \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --num-cache-nodes 1 \
  --engine-version 7.1 \
  --security-group-ids sg-XXXX
```

Le groupe de sécurité doit accepter le port 6379 depuis le SG du service ECS.

Variables `.env` :
```
REDIS_URL=rediss://csig-cache.XXXX.cache.amazonaws.com:6379/0
```

---

## 4. Stockage médias (S3 + CloudFront)

**4.1 Bucket S3 (privé)** :

```bash
aws s3 mb s3://csig-media --region us-east-1
```

Le bucket reste **privé** : l'upload passe par des Presigned POST et la lecture
par CloudFront. Ajouter une politique S3 qui n'autorise que CloudFront (Origin
Access Control), voir §4.3.

**4.2 CloudFront** :

- Create Distribution → Origin = bucket S3 `csig-media` avec **Origin Access
  Control (OAC)**.
- Behavior `uploads/*` (ou `*`) → GET autorisé (lecture seule publique).
- **Cache policy** : si tu branches un domaine custom, CNAME + certificat ACM.
- Récupérer le domaine CloudFront `dXYZ.cloudfront.net`.

**4.3 Écrire l'OAI/OAC** :

```bash
aws cloudfront create-origin-access-control --origin-access-control-config \
  Name=csig-oac,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3
```

Bucket policy (remplacer l'ID du OAC et le bucket) :

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudfront.amazonaws.com"
      },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::csig-media/*",
      "Condition": {
        "StringEquals": {
          "AWS:SourceArn": "arn:aws:cloudfront::123456789012:distribution/EXXXXXXX"
        }
      }
    }
  ]
}
```

Variables `.env` :
```
AWS_STORAGE_BUCKET_NAME=csig-media
AWS_S3_REGION=us-east-1
AWS_CLOUDFRONT_DOMAIN=dXYZ.cloudfront.net
```

---

## 5. Email (Amazon SES)

1. **Vérifier le domaine** : SES → Identities → Create identity → *Domain* →
   `csig.edu.gn`. SES fournit 3 enregistrements DNS (SPF/DKIM).
2. Ajouter ces enregistrements chez ton hébergeur DNS (d'où que le domaine
   soit géré). Valider dans SES (3 enregistrements verts).
3. Optionnel : configurer `MAIL FROM` (bounce) et un gestionnaire de feedback
   si tu veux les plaintes de spam.

Variables `.env` :
```
AWS_SES_REGION=us-east-1
DEFAULT_FROM_EMAIL=noreply@csig.edu.gn
```

> Si le domaine n'est pas encore vérifié, tu peux d'abord cibler une adresse
> de test vérifiée (Email addresses → verify) dans le même `AWS_SES_REGION`.

---

## 6. Registre d'images (ECR)

```bash
# Créer le registre
aws ecr create-repository --repository-name csig-dashboard

# Build local
docker build -t csig-dashboard .

# Login + push
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
docker tag csig-dashboard ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/csig-dashboard:latest
docker push ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/csig-dashboard:latest
```

Le gendre du rôle de tâche permet au conteneur de tirer l'image.

> En dev, le Dockerfile fait `compilemessages` et `collectstatic` au build et
> daphne expose le port 8080.

---

## 7. Service ECS Fargate

**7.1 Cluster**

```bash
aws ecs create-cluster --cluster-name csig-prod
```

**7.2 Task definition** (`task-definition.json`) — point clé :

- `executionRoleArn` : rôle ECS (tire l'image ECR).
- `taskRoleArn` : `csig-task-role` (S3 + SES).
- Conteneur : image ECR, `portMappings` → `containerPort: 8080, hostPort: 8080`.
- Variables d'environnement (secrets) : `DJANGO_SECRET_KEY`, `DATABASE_URL`,
  `REDIS_URL`, `AWS_*`, `DJANGO_ALLOWED_HOSTS`, `SITE_URL`, `DEBUG=False`.
  Les mots de passe passent par **Secrets Manager** si possible.
- `healthCheck` : `CMD-SHELL` curl sur `/healthz` si tu as une route ; sinon
  utiliser le healthcheck HTTP du Load Balancer.

**7.3 Load Balancer (ALB)** — indispensable pour le HTTPS et les WebSockets :

- Target group derrière le port 8080.
- **Sticky sessions activées** (les notifications temps réel utilisent
  `ws/notifications/`) : target group → `stickiness 24h`.
- Listeners 443 (ACM) → target group ; redirection 80 → 443.

**7.4 Service** :

```bash
aws ecs create-service \
  --cluster csig-prod \
  --service-name web \
  --task-definition csig-dashboard \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-XXX,subnet-YYY],securityGroups=[sg-XXX],assignPublicIp=ENABLED|DISABLED}"
```

Mettre `desired-count` ≥ 2 pour la haute disponibilité (les tâches sont sans
état grâce à S3 + RDS + Redis).

---

## 8. Variables d'environnement finales (conteneur ECS)

```ini
DJANGO_SECRET_KEY=<fort, généré>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=dashbord.csig.edu.gn,<ALB DNS>
DJANGO_CSRF_TRUSTED_ORIGINS=https://dashbord.csig.edu.gn
SITE_URL=https://dashbord.csig.edu.gn
DATABASE_URL=postgresql://...@....rds.amazonaws.com:5432/csigdb?sslmode=require
REDIS_URL=rediss://....cache.amazonaws.com:6379/0
AWS_ACCESS_KEY_ID=AKIA...      # ou via taskRole
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=csig-media
AWS_S3_REGION=us-east-1
AWS_CLOUDFRONT_DOMAIN=dXYZ.cloudfront.net
AWS_SES_REGION=us-east-1
DEFAULT_FROM_EMAIL=noreply@csig.edu.gn
```

---

## 9. Tests de vérification

1. `python manage.py check` → 0 erreurs.
2. Connexion RDS : `python manage.py migrate` OK.
3. Email : déclencher une notification (ex. création de projet) → doit partir
   via SES avec le logo et le PDF joints.
4. Upload : créer un document via l'UI → le fichier doit arriver dans S3
   (`aws s3 ls s3://csig-media/uploads/`) et l'URL CloudFront s'afficher.
5. Redis : ouvrir 2 onglets, marquer une tâche → le second met à jour en temps
   réel via WebSocket.
6. Téléchargement : cliquer « Télécharger » → nom de fichier correct, en-tête
   `Content-Disposition: attachment`.

---

## 10. Nettoyage des anciens services

Une fois la nouvelle stack validée :

1. **Cloudinary** : exporter une sauvegarde des URLs (déjà stockées en base),
   supprimer le cloud (facultatif). Les URLs `res.cloudinary.com` déjà en base
   restent affichables en lecture tant que le compte existe.
2. **Neon** : garder le snapshot de secours un temps, puis supprimer quand
   RDS est stable.
3. **Render** : désactiver le service web (garder le DNS un moment pour la
   transition).
4. **Resend** : aucune ressource à supprimer côté serveur (clé API seulement).

---

## Commandes utiles

```bash
# Logs du service
aws ecs describe-tasks --cluster csig-prod --tasks TASK_ID

# Lancer une tâche one-off
aws ecs run-task --cluster csig-prod --task-definition csig-dashboard \
  --overrides '{"containerOverrides":[{"name":"web","command":["python","manage.py","migrate"]}]}'

# Copier le shell interactif
aws ssm start-session --target TASK_ID   # si SSM agent activé dans l'image
```