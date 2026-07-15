# Configuration Neon PostgreSQL

Ce guide explique comment configurer et utiliser Neon PostgreSQL comme base de données principale pour le projet CSIG Dashboard.

## Pourquoi Neon ?

- **Serverless PostgreSQL** : Pas de gestion de serveur, scalabilité automatique
- **Haute disponibilité** : Réplication automatique et backups
- **Performance** : Optimisé pour les applications modernes
- **Coût** : Modèle de paiement à l'usage, gratuit pour le développement

## Configuration

### 1. Créer un compte Neon

1. Allez sur [https://neon.tech](https://neon.tech)
2. Créez un compte gratuit
3. Créez un nouveau projet PostgreSQL
4. Copiez la chaîne de connexion (Connection String)

### 2. Configurer les variables d'environnement

Ajoutez la variable `DATABASE_URL` dans votre fichier `.env` :

```bash
DATABASE_URL=postgresql://user:password@ep-xxx.aws.neon.tech/neondb?sslmode=require
```

**Format de l'URL :**
```
postgresql://[user]:[password]@[host]/[database]?sslmode=require
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

Les dépendances nécessaires sont déjà incluses dans `requirements.txt` :
- `psycopg2-binary>=2.9.9` : Driver PostgreSQL
- `dj-database-url>=2.1.0` : Configuration simplifiée des bases de données

## Priorité des bases de données

Le projet utilise la priorité suivante pour les bases de données :

1. **Neon PostgreSQL** (si `DATABASE_URL` est défini) - **CHOIX PRINCIPAL**
2. **MySQL** (si `MYSQL_HOST` est défini) - Option de repli
3. **SQLite** (par défaut) - Développement local

## Migration des données existantes

### Prérequis

- Avoir une sauvegarde de vos données actuelles
- Avoir configuré `DATABASE_URL` dans votre `.env`
- Avoir les dépendances installées

### Étapes de migration

1. **Exporter les données depuis la base actuelle**

```bash
python manage.py dumpdata core > data_export.json
```

2. **Exécuter les migrations sur Neon**

```bash
python manage.py migrate
```

3. **Importer les données dans Neon**

```bash
python manage.py loaddata data_export.json
```

### Script de migration automatisé

Un script `migrate_to_neon.py` est disponible pour automatiser la migration :

```bash
python migrate_to_neon.py
```

Ce script :
- Vérifie la connexion à la base source
- Vérifie la configuration Neon
- Exporte les données
- Exécute les migrations
- Importe les données

## Vérification

### Tester la connexion

```bash
python manage.py dbshell
```

Si vous êtes connecté à Neon, vous verrez l'invite de commande PostgreSQL.

### Vérifier les données

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User
print(User.objects.count())  # Vérifier le nombre d'utilisateurs
```

## Déploiement

### Pour la production

1. Configurez `DATABASE_URL` dans les variables d'environnement de votre hébergeur
2. Assurez-vous que `DJANGO_DEBUG=False`
3. Redémarrez l'application

### Exemple de configuration Render

```bash
DATABASE_URL=postgresql://user:password@ep-xxx.aws.neon.tech/neondb?sslmode=require
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=votre_cle_secrete
DJANGO_ALLOWED_HOSTS=votre-domaine.com
```

## Dépannage

### Erreur de connexion SSL

Si vous rencontrez une erreur SSL, assurez-vous que l'URL inclut `sslmode=require`.

### Erreur de timeout

Neon a un timeout de connexion par défaut. Si vous avez des requêtes longues, ajustez `conn_max_age` dans `settings.py`.

### Migration échouée

Si la migration échoue :
1. Vérifiez que l'URL Neon est correcte
2. Assurez-vous que les permissions sont correctes
3. Vérifiez les logs Django pour plus de détails

## Ressources

- [Documentation Neon](https://neon.tech/docs)
- [Django PostgreSQL](https://docs.djangoproject.com/en/stable/ref/databases/#postgresql-notes)
- [dj-database-url](https://github.com/jazzband/dj-database-url)

## Support

Pour toute question sur la configuration Neon, consultez la documentation officielle ou contactez l'équipe de développement.
