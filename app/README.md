# Campus Connect — application connectée, déployable, 100 % gratuite

**EPITA × SupBiotech.** Frontend responsive + API FastAPI + PostgreSQL + HTTPS Caddy + SMTP. Projet indépendant des établissements. Pas d'abonnement, paiement, publicité ni paywall.

## Ce qui est réel

- Connexion avec code à 6 chiffres envoyé à un email étudiant (domaine vérifié côté serveur), code stocké uniquement sous forme de HMAC, expiration 10 minutes, 5 tentatives et limites par IP/email.
- Compte et préférences persistants dans PostgreSQL ; session HttpOnly + Secure + SameSite Strict en production.
- Découverte filtrée avec exclusions (profils déjà vus, bloqués, non approuvés/suspendus), swipes et like réciproque = match.
- Conversations liées aux matchs, messages enregistrés, WebSocket pour notifier (un seul worker), vérification d'identité à chaque opération.
- Photos JPEG/PNG/WebP reformatées en WebP (limite 5 Mo), privées tant qu'elles ne sont pas approuvées par un modérateur ; six photos maximum, ordre personnalisable.
- Blocage, signalement, annulation des matchs, export et suppression de compte, gestion de la visibilité.
- Interface de modération pour les comptes, photos et signalements (admin autorisé par email).
- Application française responsive avec cartes à photos glissables et match animé, toutes options gratuites.

## Déploiement VPS + nom de domaine HTTPS

1. Prévoir un **VPS Linux** compatible Docker, un **nom de domaine** et un **compte SMTP autorisé à envoyer des emails**. Pointer le DNS du nom de domaine vers l'adresse IP du serveur.
2. Installer Docker Engine et Docker Compose v2, ouvrir les ports **80 et 443** dans le pare-feu.
3. Mettre le contenu du dossier `CampusConnect-PRODUCTION` sur le VPS (ex. via `git clone` ou `scp`).
4. Dans ce dossier : `cp .env.example .env`. Éditer `DOMAIN`, `SMTP_*`, `ADMIN_EMAILS`, `AUTH_SECRET` et `POSTGRES_PASSWORD`.
5. Générer les secrets sans les recopier dans une conversation : `python3 -c "import secrets; print(secrets.token_hex(48))"` pour `AUTH_SECRET`, et `secrets.token_hex(24)` pour PostgreSQL.
6. Lancer :
   ```bash
   docker compose config --quiet
   docker compose up -d --build
   docker compose ps
   ```
7. Ouvrir `https://TON-DOMAINE`. Caddy obtient/renouvelle les certificats HTTPS automatiquement quand le DNS et les ports sont corrects.

**Important :** ne pas héberger seulement `index.html` sur GitHub Pages ou Netlify Drop. Ces hébergements statiques ne fournissent pas la base de données, les emails ou les API. Ici le site doit être servi **avec son backend**, derrière Caddy.

### Compte administrateur, majorité et modération

- L'administrateur doit posséder une adresse de l'un des domaines académiques autorisés, renseignée dans `ADMIN_EMAILS` avant son inscription.
- Le compte admin est approuvé à l'inscription après réception du code email. Pour les autres comptes, `REQUIRE_ACCOUNT_APPROVAL=true` : les comptes restent en attente jusqu'à validation.
- Sur le site, un admin connecté ouvre le bouton **Modération** (menu latéral sur ordinateur) pour approuver des comptes et des photos, traiter les signalements. La validation d'âge nécessite un **processus externe réellement adapté et respectueux de la confidentialité** : une simple date de naissance déclarée ne suffit pas. **Ne pas approuver des comptes avant cette vérification.**
- Photos : chaque nouvelle photo a le statut `pending`. Aucun autre utilisateur ne la voit avant la validation manuelle.
- **Les domaines étudiants peuvent différer dans la réalité.** Vérifier les domaines officiels des deux établissements avant d'inviter du public ; si nécessaire modifier `SCHOOLS` dans `backend/main.py`.

### Vérifications nécessaires avant ouverture publique

Cette archive fournit une **base déployable sécurisée**, pas une garantie d'absence de vulnérabilités ni une conformité juridique clé en main. Faire réaliser : revue de sécurité indépendante, tests de charge, validation robuste de l'âge 18+, traitement et escalade des signalements, politique de confidentialité et de conservation, mentions légales, CGU, information/consentement RGPD, suivi des demandes de suppression, procédure anti-harcèlement et sauvegardes chiffrées. Ne pas utiliser de vraies données personnelles avant ces validations.

### Sauvegarder et mettre à jour

- Base SQL : `docker compose exec -T db pg_dump -U campus -d campus | gzip > campus-backup-$(date +%Y%m%d).sql.gz`.
- Sauvegarder **également** le volume `user_photos`, séparément et de façon chiffrée, sans l'exposer sur Internet.
- Les modifications de modèles SQL sur une base existante requièrent des **migrations versionnées** (Alembic) : `create_all()` ne met pas à jour une table déjà présente. Faire un backup avant tout upgrade.
- Pour le développement local sans Docker, voir `DEV.md`.

## Sécurité

Voir `SECURITY.md`. Les secrets ne sont jamais inclus dans le ZIP et `/.env` est ignoré par Git.

## Licence

Code original produit pour ce projet. Les images de profil sont celles téléversées par les utilisateurs ; aucune image de démonstration d'une personne réelle n'est intégrée à la version connectée.
