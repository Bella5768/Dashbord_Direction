# Pièges PowerShell + AWS CLI — CSIG Dashboard

Notes prises pendant le déploiement réel (CLI 2.37.5, PowerShell 5.1, région
`eu-north-1`). Elles évitent de répéter les erreurs déjà commises.

> Le poste est sous **Windows / PowerShell 5.1**, pas bash. C'est la source de
> presque toutes les erreurs ci-dessous.

---

## 1. Virgule ≠ espace (le piège n° 1)

PowerShell n'éclate **pas** les tableaux vers les commandes natives : `$A,$B`
arrive comme **un seul** argument `"a,b"`.

```powershell
# FAUX : le CLI reçoit "subnet-a,subnet-b" -> InvalidSubnet
aws elbv2 create-load-balancer --name csig-alb --subnets $PUB_A,$PUB_B ...

# JUSTE : deux arguments distincts (elbv2, ec2)
aws elbv2 create-load-balancer --name csig-alb --subnets "$PUB_A" "$PUB_B" ...
```

Mais certains services veulent l'inverse, une **chaîne unique** comma-séparée :

| Cas | Forme attendue |
|-----|----------------|
| `--subnets` (elbv2, ec2) | arguments **séparés** : `"$A" "$B"` |
| `--security-groups` (elbv2, ec2) | arguments **séparés** : `"$A" "$B"` |
| `--subnet-ids` (rds) | une chaîne : `"$A,$B"` |
| `--vpc-security-group-ids` (rds) | une chaîne : `"$SG"` |
| `--exclude-availability-zone` (rds) | une chaîne |
| `--group-ids` (elbv2 describe) | une chaîne |
| `--exclude-parameters` (cloudformation) | une chaîne |

Règle : se renseigner sur la forme attendue de l'argument avant de l'écrire.
`aws <service> <commande> help` affiche la syntaxe exacte.

---

## 2. Raccourcis `--option clé=valeur` : certains exigent la valeur

Un raccourci sans `=` est accepté uniquement par le parseur de JMESPath du CLI,
et seulement si la valeur est merchandée :

```powershell
--matcher HttpCode=200          # elbv2 : OBLIGATOIRE sinon "expected one argument"
--default-actions "Type=forward,TargetGroupArn=$TG_ARN"   # là c'est une chaîne parsée, OK
--tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=csig-vpc}]"
```

Quand le membre est une **structure** (liste d'objets), la paire `clé=valeur`
n'est pas acceptée : il faut la forme `Key=...,Value=...` :

```powershell
# FAUT : pairs clé=valeur -> "Unknown parameter in Attributes[0]: stickiness.enabled"
aws elbv2 modify-target-group --attributes stickiness.enabled=true

# JUSTE : sous-commande dédiée + structure Attribute
aws elbv2 modify-target-group-attributes --target-group-arn $TG_ARN `
  --attributes Key=stickiness.enabled,Value=true `
               Key=stickiness.type,Value=lb_cookie `
               Key=stickiness.lb_cookie.duration_seconds,Value=86400
```

Attention aussi au **nom de la sous-commande** : la sous-commande existe en
version `-attributes`. Vérifier avec `aws elbv2 help | findstr target-group`.

---

## 3. `--cli-input-json` = forme JSON **exacte** de l'API

C'est le mode le plus piégeux : il n'accepte aucunenotation abrégée. Tout ce
que le CLI construit lui-même (listes simples, `--origin-domain-name`, etc.) est
rejeté.

```json
{
  "DistributionConfig": {
    "CallerReference": "csig-media-EFU1DJREXAHE6",
    "Enabled": true,
    "Origins": { "Quantity": 1, "Items": [ { "Id": "...", "S3OriginConfig": { "OriginAccessIdentity": "" } } ] },
    "DefaultCacheBehavior": {
      "AllowedMethods": { "Quantity": 2, "Items": ["GET","HEAD"],
                          "CachedMethods": { "Quantity": 2, "Items": ["GET","HEAD"] } },
      "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6"
    }
  }
}
```

Règles apprises :

- **enveloppe obligatoire** : `{"DistributionConfig": {...}}`, sinon
  `Missing required parameter in input: "DistributionConfig"` ;
- **listes = objets** `{"Quantity": n, "Items": [...]}`, pas `[...]` ;
- `CachedMethods` est **imbriqué** dans `AllowedMethods`, pas au même niveau ;
- `CallerReference` est obligatoire (identifiant unique de tentative, ≤ 128 caractères) ;
- le squelette exact s'obtient avec
  `aws cloudfront create-distribution --generate-cli-skeleton input`.

Mieux vaut éviter ce mode quand la commande accepte des options scalaires.

---

## 4. Écrire un JSON depuis PowerShell sans BOM

`Set-Content -Encoding UTF8` / `Out-File` écrivent un **BOM** en PS 5.1, que le
CLI peut refuser. `[System.IO.File]::WriteAllText` écrit en UTF-8 sans BOM.

```powershell
$json = @"                      # @" ... "@ = interpole $variables
{
  "DistributionConfig": { "Comment": "$OAC" }
}
"@                              # le "@ de fin doit être SEUL en début de ligne
[System.IO.File]::WriteAllText("$PWD\cf.json", $json)
```

`'@` ... `'@` = littéral (pas d'interpolation), utile quand le JSON contient `$`.

---

## 5. JMESPath : deux-points, jamais égale

```
--query "Vpcs[0].VpcId"                                  # OK
--query "LoadBalancers[0].{Arn:LoadBalancerArn,Dns:DNSName}"   # OK : colon
--query "Distribution.{Domaine=DomainName}"              # FAUX : Bad jmespath expression
--query "RouteTables[].[Tags[?Key=='Name'].Value|[0],Routes[].GatewayId]"
        # FAUX : "Row should have 1 elements" (Routes[] aplati d'un coup)
        # JUSTE : Routes[].[NatGatewayId,GatewayId,DestinationCidrBlock]
```

En cas de doute sur un `--query`, l'enlever et lire la sortie brute
`--output json`, ou passer par `--output text` + `ConvertFrom-Json`.

---

## 6. Erreurs de validation = rien n'a été créé

`ParamValidation` et les erreurs JMESPath sont levée **avant** l'appel API :
aucune ressource créée, aucun nettoyage, il suffit de corriger et relancer.

En revanche une erreur **serveur** (`InvalidSubnet`, `EntityAlreadyExists`)
signifie qu'une ressource a pu être créée : ne jamais relancer un `create-*` à
l'aveugle, vérifier d'abord avec `list-*` / `describe-*`.

```powershell
aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='csig-media'].Id" --output text
```

---

## 7. Droits asymétriques : `Create*` accordé, `List*` refusé

Le profil peut créer une ressource sans pouvoir la relister ni la décrire. Conséquence
directe : **un ID qu'on ne récupère pas est perdu** (impossible de le retrouver
ensuite).

Règle : dès qu'un `create-*` renvoie un ID, le **stocker immédiatement** dans une
variable, et ne jamais compter sur un `list-*` pour le récupérer après coup.

Constaté sur ce compte :

| Action refusée | Effet |
|----------------|-------|
| `elasticache:DescribeCacheClusters` | cache Redis non créable |
| `iam:ListRoles`, `iam:GetRole` | rôles ECS non vérifiables |
| `ec2:DescribeNatGateways` | contrôle « pas de NAT » impossible |
| `cloudfront:ListOriginAccessControls` | OAC créé non retrouvable |
| `elasticloadbalancing:DescribeTargetGroupAttributes` | sticky non vérifiable |

Alternatives quand un `list-*` est refusé : créer directement l'ID manquant,
demander le droit à l'admin, ou vérifier par le comportement observed.

---

## 8. Hygiène PowerShell / secrets

```powershell
# Ne pas laisser un secret dans l'environnement de la session
$DBPASS = $null
Remove-Item Env:DJANGO_DEBUG, Env:DJANGO_SECURE_SSL

# Guillemets systématiques : évite qu'une valeur vide disparaisse
"ALB DNS = $($ALB.Dns)"

# Convertir une sortie JSON du CLI en objet exploitable
$ALB = aws elbv2 create-load-balancer ... --output json | ConvertFrom-Json
```

---

## 9. Vérifier le nom exact de la sous-commande

Les noms d'opérations ne sont pas devinables, et l'erreur du CLI dit souvent
juste ce qu'il faut :

```
[ERROR]: Found invalid choice 'describe-orderable-db-instance-engines'
Maybe you meant:
  * describe-orderable-db-instance-options
```

Erreurs de nom déjà commises sur ce déploiement :

| Faux | Vrai |
|------|------|
| `rds describe-orderable-db-instance-engines` | `rds describe-orderable-db-instance-options` |
| `elbv2 modify-target-group --attributes k=v` | `elbv2 modify-target-group-attributes --attributes Key=..,Value=..` |
| `--default-root-object ""` | option à omettre (valeur vide refusée) |

```
aws <service> help                      # liste des opérations du service
aws <service> <operation> help          # syntaxe complète + arguments requis
```

---

## 10. RDS : `Some input subnets are invalid`

Erreur de `create-db-subnet-group`. Les sous-réseaux existent pourtant (ils
apparaissent dans `describe-subnets`), donc causes possibles :

1. **sous-réseaux dans deux VPC différents** → RDS exige un seul VPC par groupe ;
2. **VPC ou sous-réseaux encore en `pending`** (créés il y a quelques minutes) →
   attendre que `State` passe à `available` ;
3. **moins de 2 adresses IP libres** dans un sous-réseau ;
4. **erreur de copie d'ID** dans la commande.

Toujours vérifier avant de recréer :

```powershell
aws ec2 describe-subnets --subnet-ids "$A,$B" --query "Subnets[].[SubnetId,VpcId,State,AvailabilityZone,AvailableIpAddressCount]" --output table
aws ec2 describe-vpcs --vpc-ids vpc-xxx --query "Vpcs[].[VpcId,State,CidrBlock]" --output table
```

Après création, confirmer le statut avant de lancer l'instance :

```powershell
aws rds describe-db-subnet-groups --query "DBSubnetGroups[].[DBSubnetGroupName,SubnetGroupStatus,VpcId]" --output table
```

Erreur en cascade à ne pas diagnostiquer séparément :
`CreateDBInstance` → `DBSubnetGroupNotFoundFault` n'est que la conséquence du
groupe de sous-réseaux non créé. Idem `DBInstanceNotFound` à `describe-db-instances`
après un échec de création.

---

## 11. Avant de coller un bloc de commandes

1. On est en **PowerShell**, pas bash : pas de `\` en fin de ligne.
2. Chaque argument de liste : virgule ou espace ? (voir § 1).
3. Chaque raccourci `--x` : valeur obligatoire ? structure `Key=,Value=` ?
4. Si `--cli-input-json` : squelette exact de l'API (§ 3).
5. Après chaque `create-*` : vérifier avec `describe-*`, et capturer l'ID.
6. Ne pas relancer un `create-*` sans avoir vérifié qu'il n'a pas déjà réussi.