# TODO — appli campus (nom de travail : Supbio-EPITA-Dating)

Décisions validées : PWA (site installable), FastAPI, email d'école obligatoire, Elo interne,
stats et compétition inter-campus, rencontres avec créneau, critères avec delta.

## Concept
- [ ] Rencontre réelle avec créneau (café, baby-foot, run) plutôt que chat libre
- [ ] Drop hebdomadaire le jeudi soir, places limitées
- [ ] Profil public = petit dessin fait par la personne (ou mème) ; photo privée
- [ ] Accord mutuel secret sur les photos, seulement entre paires qui passent les critères
- [ ] Critères déclarés avec delta (âge, taille, genre/orientation, campus)
- [ ] Brise-glace = l'activité proposée, pas de « salut ça va »

## Fiabilité (lapins)
- [ ] Check-in 1 h avant, sinon annulation propre
- [ ] Validation sur place (scan croisé ou code du lieu)
- [ ] Score de fiabilité, 2 lapins = 1 semaine de suspension
- [ ] Lieux imposés par l'app, option duo avec un ami
- [ ] Retour privé après rencontre (« à revoir ? ») pour affiner le matching

## Stats et compétition
- [ ] Elo interne uniquement, jamais de score individuel affiché
- [ ] Classement inter-campus / promo / filière sur les rencontres VALIDÉES
- [ ] Seuil d'anonymat : groupe affiché à partir de 10 personnes
- [ ] Récap hebdo / de semestre façon « wrapped » du campus

## Technique
- [ ] Choisir le dossier du projet et le port sur le serveur (pas d'infra Hetzner)
- [ ] Backend FastAPI + SQLite pour démarrer, front PWA
- [ ] Inscription par email d'école (domaines autorisés en liste)
- [ ] Envoi d'email : copier MAIL_* depuis /opt/pierref/share_per_projet/.env
      (OVH, expéditeur morgan@pierref.eu) vers le .env du projet, sans afficher le mot de passe
- [ ] Éditeur de dessin canvas (pixel art 32x32 ou 64x64) + upload de mème avec modération
- [ ] Notifications push (Android direct, iOS seulement après ajout à l'écran d'accueil)
- [ ] Taxonomie d'intérêts : normaliser allthecategorie.md avant usage
- [ ] Signalement, blocage, bouton de sécurité, partage du créneau à un ami
- [ ] RGPD : suppression de compte, minimisation des données, mentions légales

## Autres idées
- [ ] Dessin du jour : un thème, chacun dessine, le campus vote
- [ ] Créneaux « binôme de TP » : entrée sans connotation dating, public plus large
- [ ] Créneaux thématiques liés au calendrier (survivants d'un partiel, fin de semaine de projet)
- [ ] Saisons par semestre avec titres et badges pour les promos
- [ ] Hall of fame des gens fiables
- [ ] Défis inter-campus à objectif collectif (ex. 100 rencontres validées)
- [ ] Mode « garde-fou » : un ami reçoit l'heure et le lieu, bouton d'alerte

## Décisions (réponses aux 20 questions)
- Écoles : EPITA, Supbiotech, ESME, ISG, IPSA. Campus de Lyon uniquement pour l'instant
- Tous genres et orientations. Dating en priorité, plus amis et binôme de TP : l'intention
  (dating / amis / binôme) est un champ obligatoire du profil
- Pas de maximum de rencontres par semaine. Drop le jeudi
- Sanction des lapins : oui (suspension)
- Personnalisation poussée du profil : couleurs, emoji, dessin sur canvas libre, autres éléments,
  pour que chaque profil soit différent
- Signalement facile. Modération : Morgan seul pour l'instant, autres modos possibles plus tard
- Classements de tout type, visibles seulement par les inscrits (stats perso + classements),
  sans dévoiler d'info personnelle. Récompense : la gloire
- Lancement : QR codes sur le campus, BDE, bouche-à-oreille. Pas de date
- Pas de monétisation prévue (possible plus tard)
- Domaine : sous-domaine de pierref.eu
- À trancher : nom, critères avec delta, règles photos, âge minimum (voir échange)
