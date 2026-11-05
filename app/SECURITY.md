# Sécurité — limites et opérations requises

## Mesures incluses

- Sessions opaques aléatoires, HMAC en BDD, cookie Secure/HttpOnly/SameSite strict (mode production) ; vérification des autorisations sur les objets match/photo.
- En-tête custom `X-Campus-Request` sur les écritures, contrôles d'origine et CSP, politiques anti-iframe/no-sniff/referrer, HSTS si HTTPS.
- Codes email HMAC, 10 minutes, 5 essais par code, limite de fréquence par adresse/IP. L'adresse IP est hachée pour les limites en base. Le reverse proxy remplace X-Real-IP et l'API n'est pas exposée directement.
- Non-exposition des contenus non approuvés, limitation des types/tailles photo, décodage et ré-encodage.
- Accès DB uniquement sur réseau Docker interne, aucun port PostgreSQL exposé.
- Option de validation manuelle des comptes obligatoire dans le compose de production, contrôle de modération par email admin.

## Reste à auditer, AVANT ouverture publique

- Âge : l'âge déclaré n'est pas une preuve. Choisir une solution conforme pour une vérification effective, avec conservation minimale.
- RGPD : responsable de traitement, DPO si nécessaire, droits, durée de conservation, localisation des hébergements, privacy policy, demandes de retrait, sauvegardes et purge des données supprimées.
- Opérations de modération : responsables, délais de traitement, escalade, bannissement, alertes, procédure de sécurité et recours.
- Attaques : revue de dépendances, tests SAST/DAST, fuzzing, traçabilité et télémétrie respectueuse de la vie privée, protection anti-bot sur codes email, quotas messages et uploads, coût d'email.
- Résilience : migrations Alembic, tests PostgreSQL en CI, tâches d'entretien (OTP/session/rate buckets), stockage durable avec réplication et backup chiffré.
- Modèle SQL : pour la production à échelle et en multi-worker, le WebSocket en mémoire doit passer sur un bus Redis/pubsub.
- L'autorisation par domaine d'email prouve le contrôle d'une boîte académique, pas l'inscription actuelle ou l'âge.

## Pas de publication de secrets

Ne pas committer `.env`, secrets SMTP, mots de passe, données utilisateur ou sauvegardes SQL. Inspecter `docker compose config` : la commande imprime les secrets si lancée sans `--quiet`.
