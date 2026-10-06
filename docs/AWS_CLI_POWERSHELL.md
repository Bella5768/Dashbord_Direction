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

## 1 bis. PowerShell mange les guillemets des JSON inline

Un JSON passé en **apostrophes** perd tous ses `"` au moment où PowerShell
construit la ligne de commande pour l'exécutable natif. Le CLI reçoit alors
`{containerOverrides:[...]}` et refuse :

```
ParamValidation: Error parsing parameter '--overrides': Invalid JSON:
Expecting property name enclosed in double quotes: line 1 column 2
```

Ce n'est **pas** un problème de syntaxe JSON : le document était valide.
C'est un bug de passage d'arguments de PowerShell 5.1 vers les processus natifs.

**Solution fiable : un fichier + `--cli-input-json file://...`.** C'est aussi la
seule forme lisible et rejouable.

```powershell
# 1) Ecrire le JSON dans un fichier (ici avec l'editeur, pas a la main)
aws ecs run-task --cli-input-json file://probe.runtask.json --region eu-north-1
```

Variantes évitees volontairement, pour mémoire :

| Forme | Verdict |
|-------|---------|
| `'{"a":1}'` | **cassé** — guillemets mangés |
| `'{\"a\":1}'` | fonctionne parfois, illisible, fragile |
| `` `--` `` (stop-parsing) | casse les autres variables de la ligne |
| `--cli-input-json file://x.json` | **retenu** |

Le même piège touche `--overrides`, `--container-definitions`,
`--network-configuration`, `--placement-constraints`, et toutShort form contenant
des `"`. Réflexe : dès qu'un argument contient du JSON, passer par un fichier.

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

### Alias : uniquement dans un multiselect `{...}`

JMESPath distingue deux formes, et l'alias `clé:valeur` n'existe que dans la
première :

```
--query "Subnets[].[SubnetId,State]"                        # projection : PAS d'alias
--query "Subnets[].[FreeIPs:AvailableIpAddressCount]"        # ERREUR : Expecting: comma, got: colon

--query "Subnets[].{Id:SubnetId,State:State}"               # multiselect : alias OK
--query "LoadBalancers[0].{Arn:LoadBalancerArn,Dns:DNSName}"  # idem
```

Réflexe : en cas de `Parse error`, retirer l'alias, ou passer par
`--output text` et lire les en-têtes de colonne.

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

Erreur de `create-db-subnet-group` (code API `InvalidParameterValue`, alors que
la doc annonce `InvalidSubnet` pour ce cas). **Cause la plus fréquente en
pratique : incohérence transitoire du plan de contrôle RDS**, quand les
sous-réseaux viennent d'être créés (minutes) : `describe-subnets` les renvoie
`available`, RDS ne les voit pas encore. Ce n'est **pas** une erreur de syntaxe.

La preuve : la même commande a réussi sans rien changer une fois le délai
passé, sur `csig-db-subnets` (sous-réseaux créés par l'admin, puis refusés,
puis acceptés à l'identique).

### Causes réelles, par ordre de fréquence

1. **région/provider mismatch** → le sous-réseau est dans une autre région que
   l'endpoint RDS visé (cause n°1 dans les retours d'expérience publics) ;
2. **incohérence transitoire** après création des sous-réseaux ;
3. **sous-réseaux dans deux VPC différents** → RDS exige un seul VPC par groupe ;
4. **moins de 2 AZ couvertes**, ou **2 AZ en réalité identiques** ;
5. **moins de 2 adresses IP libres** dans un sous-réseau ;
6. **Local Zone / Wavelength** → refusé par RDS (AZ ID de type `eun1-az1`
   = AZ régionale normale, donc OK) ;
7. **erreur de copie d'ID** dans la commande.

### Marche à suivre

D'abord la région et les attributs complets, avec la région forcée :

```powershell
aws configure get region
aws ec2 describe-subnets --region eu-north-1 --subnet-ids subnet-a subnet-b --query "Subnets[].{Id:SubnetId,AZ:AvailabilityZone,AZId:AvailabilityZoneId,Vpc:VpcId,State:State,Owner:OwnerId,Free:AvailableIpAddressCount}" --output table
```

Puis **la sonde à un seul sous-réseau**, qui isole la cause. Le nom est jetable :

```powershell
aws rds create-db-subnet-group --region eu-north-1 --db-subnet-group-name csig-db-probe --db-subnet-group-description probe --subnet-ids subnet-a
```

| Réponse de la sonde | Diagnostic | Suite |
|---|---|---|
| `DBSubnetGroupDoesNotCoverEnoughAZs` | sous-réseau **valide**, seul le 2e AZ manque | retester la paire |
| `InvalidParameterValue ... invalid` | ce sous-réseau précis est rejeté | vérifier région / VPC / AZ ID |
| succès | sous-réseau valide | supprimer la sonde |

Si la sonde est valide, **relancer la paire à l'identique** : c'est le test qui
distingue incohérence transitoire et rejet réel.

```powershell
aws rds create-db-subnet-group --region eu-north-1 --db-subnet-group-name csig-db-probe2 --db-subnet-group-description probe2 --subnet-ids subnet-a subnet-b
aws rds delete-db-subnet-group --region eu-north-1 --db-subnet-group-name csig-db-probe2
```

Si la paire échoue aussi avec des attributs conformes : ouvrir un ticket AWS
Support **en fournissant le `Request ID`** de l'erreur. Il est présent dans la
sortie du CLI et c'est la seule chose utile à transmettre.

Après création, confirmer le statut avant de lancer l'instance :

```powershell
aws rds describe-db-subnet-groups --region eu-north-1 --query "DBSubnetGroups[].[DBSubnetGroupName,SubnetGroupStatus,VpcId]" --output table
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