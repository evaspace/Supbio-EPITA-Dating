# Spec produit — appli de rencontres de campus (Lyon)

Nom de travail : **Jeudi** (`jeudi.pierref.eu`). Le nom reste modifiable.
Ce document décrit TOUT ce qui a été décidé ou proposé. Il est écrit pour être lu par le binôme qui
code déjà l'appli : la partie « personnalisation » s'ajoute par-dessus l'existant (voir §13).

Légende : **[Décidé]** validé par Morgan. **[Proposé]** valeur par défaut proposée, à confirmer.
**[Ouvert]** à trancher.

---

## 1. Vision

Une appli web (PWA) de rencontres pour les étudiants du campus de Lyon. L'idée centrale :
**on ne chatte pas, on se rencontre**. Le match débouche sur un créneau réel (café, baby-foot,
run, séance de TP) dans un lieu du campus, à une heure précise. Pas de « salut ça va ».

Points forts voulus :
- rencontres réelles avec créneau [Décidé]
- profils très personnalisés, chacun différent [Décidé]
- compétition et statistiques entre campus, promos et écoles [Décidé]
- ambiance graphique proche de Spotify, très colorée [Décidé]

## 2. Public et périmètre

- **Écoles** [Décidé] : EPITA, Supbiotech, ESME, ISG, IPSA.
- **Campus** [Décidé] : Lyon uniquement pour l'instant. Prévoir un champ `campus` pour s'étendre.
- **Genres et orientations** [Décidé] : tous.
- **Intention** [Décidé] : dating en priorité, mais aussi amis et binôme de TP. L'intention est un
  champ **obligatoire** du profil (`dating`, `amis`, `binome`, plusieurs possibles). Le matching ne
  croise que des intentions compatibles.
- **Âge** : voir §10, point sensible.

## 3. Inscription et authentification

- Inscription par **email d'école**, domaine dans une liste blanche [Décidé] :
  `epita.fr`, `supbiotech.fr`, `esme.fr`, `isg.fr`, `ipsa.fr` (à vérifier : certaines écoles ont
  des sous-domaines étudiants, par exemple `@epita.fr` vs `@etu.…`).
- Déduction automatique de l'école et de la promo si l'email le permet.
- Confirmation par email : envoi réel via SMTP OVH, expéditeur `morgan@pierref.eu` [Décidé].
  La config `MAIL_*` existe déjà dans `/opt/pierref/share_per_projet/.env` ; la copier dans le
  `.env` du projet sans jamais l'afficher ni la commiter.
- Mot de passe haché (werkzeug/argon2), sessions en cookie sécurisé.
- Suppression de compte en libre-service (RGPD).

## 4. Profil

### 4.1 Champs de base
Prénom (ou pseudo), école, promo, date de naissance (non affichée, sert au filtre d'âge),
genre, orientation, intention (voir §2), bio courte, intérêts.

### 4.2 Intérêts
Base : `allthecategorie.md` (taxonomie large). **À normaliser avant usage** (doublons, séparer
intérêts, habitudes de vie, valeurs, préférences relationnelles). L'utilisateur choisit des
intérêts, dont **3 mis en avant**. Les intérêts alimentent un **score de compatibilité**, pas un
filtre dur.

### 4.3 Personnalisation poussée [Décidé]
Objectif : que chaque profil soit visiblement différent. Éléments :
- **Dessin de profil** : canvas libre dessiné par la personne [Décidé]. Mème possible en
  alternative [Décidé]. Le dessin est le visuel **public** du profil.
- **Couleurs** : couleur d'accent et couleur de fond du profil, choisies dans une palette.
- **Emoji signature** et statut du moment (« en partiel jusqu'à vendredi », etc.).
- **Polices flexibles** [Décidé] : l'utilisateur choisit la police de son profil dans une liste
  restreinte de familles libres de droit (une dizaine), hébergées sur le serveur. Pas de police
  uploadée (sécurité, lisibilité, modération).
- Disposition des blocs du profil (ordre des sections), phrase d'accroche, trois intérêts phares.
- Tout est stocké dans un champ `profile_style` (JSON) pour rester indépendant du reste du
  modèle (voir §13).

### 4.4 Photos [Proposé]
- 1 à 3 photos, obligatoires.
- **Privées** : jamais visibles publiquement, seulement à l'étape d'accord mutuel (§5.2).
- Vérifiées à la main par l'admin au début (humain visible, pas de contenu interdit).
- Pas de vérification par selfie au départ ; à ajouter si des faux profils apparaissent.

## 5. Matching

### 5.1 Critères avec marge (delta) [Proposé]
Chaque utilisateur déclare ses attributs et ses préférences, avec une marge réglable :
- **Âge** : tranche voulue, marge de ±2 ans par défaut.
- **Taille** : facultative, marge de ±8 cm par défaut.
- **Genre et orientation** : filtre strict, sans marge.
- **Intention** : filtre strict.
- **Intérêts** : score de compatibilité, pas un filtre.
Une paire n'est candidate que si **chacun passe les critères de l'autre**.

### 5.2 Accord mutuel sur les photos [Décidé dans le principe]
Pour les paires candidates uniquement, chacun voit l'autre (photos privées + profil) et répond
en secret « ok » / « pas ok ». Un créneau n'est proposé que si **les deux** disent ok. Aucun refus
n'est jamais révélé à l'autre.

### 5.3 Elo interne [Décidé]
- Sert à équilibrer les paires proposées, pas à être affiché.
- Elo classique (K≈32, départ 1000), mis à jour par les « ok / pas ok » reçus.
- **Jamais de score individuel affiché** à qui que ce soit. Seulement des agrégats (§8).

## 6. Rencontres : créneaux et drop

### 6.1 Drop hebdomadaire [Décidé]
Les créneaux de la semaine s'ouvrent **le jeudi soir** (fenêtre à préciser, par exemple 18h–22h).
Pas de maximum de rencontres par personne et par semaine [Décidé].

### 6.2 Créneau
Une paire validée reçoit : une **activité** (café à la cafet, baby-foot, run, séance de TP…), un
**lieu imposé** du campus [Proposé], une **heure**. L'activité sert de brise-glace. Option **duo**
(venir avec un ami) [Proposé].

### 6.3 Fiabilité et lapins [Décidé]
- **Check-in** 1 h avant, sinon annulation propre du créneau.
- **Validation sur place** : scan croisé des codes, ou code affiché au lieu du rendez-vous.
- **Score de fiabilité** par utilisateur ; il pèse dans le classement.
- **Sanction** : 2 lapins = 1 semaine de suspension [Décidé dans le principe, seuil à confirmer].
- **Retour privé** après rencontre (« à revoir ? ») pour affiner le matching.

## 7. Autres modes d'usage
- **Amis** et **binôme de TP** : mêmes créneaux, intention différente, sans filtre physique.
- **Créneaux thématiques** liés au calendrier (après un partiel, fin de projet).

## 8. Statistiques et compétition [Décidé]

- **Classements de tout type** : par campus, école, promo, filière, et entre campus à terme.
- Classement principal : **rencontres réellement validées** (récompense la présence, pas le physique).
- Autres classements possibles : fiabilité, régularité, dessin du jour…
- **Visibles seulement par les inscrits** : stats perso + classements.
- **Aucune donnée personnelle dévoilée** : on n'affiche que des agrégats, et un groupe n'apparaît
  qu'à partir d'un **seuil d'anonymat** (par exemple 10 personnes) pour que personne ne soit
  identifiable. Récompense : la gloire, rien d'autre.
- Récap hebdo ou de semestre façon « wrapped » du campus.

## 9. Modération et sécurité
- **Signalement facile** [Décidé] : bouton visible sur chaque profil, dessin et créneau.
- **Blocage** d'un utilisateur.
- **Admin** : Morgan seul pour l'instant [Décidé], d'autres modérateurs possibles plus tard
  (prévoir un rôle `moderator` dès le modèle).
- Vérification manuelle des photos au début.
- **Lieux publics uniquement** pour les créneaux, jamais un lieu privé.
- **Garde-fou** [Proposé] : un ami reçoit l'heure et le lieu du créneau ; bouton d'alerte.
- Dessins et mèmes : filtre à la création + signalement, suppression par l'admin.

## 10. Âge minimum — point à trancher
Morgan souhaite ne pas bloquer les mineurs. **Ce n'est pas anodin** :
une appli de rencontres en vrai qui met en relation un mineur et un majeur est un risque réel pour
la personne mineure et pour l'éditeur (responsabilité, RGPD : consentement numérique à 15 ans en
France). Beaucoup de premières années ont 17 ans.
Options, de la plus simple à la plus permissive :
1. **18 ans minimum**, date de naissance à l'inscription, blocage en dessous. [Recommandé]
2. Mineurs autorisés, mais **appariés uniquement entre mineurs**, sans créneau avec un majeur,
   avec consentement parental sous 15 ans. Plus lourd.
**[Ouvert]** : Morgan doit choisir. Par défaut, l'option 1.

## 11. Design

- **Mode graphique principal type Spotify** [Décidé] : cartes, grandes zones colorées, navigation
  par onglets, mise en avant du visuel (ici le dessin).
- **Très coloré** [Décidé], avec cette structure : **deux couleurs muettes** pour l'essentiel de la
  surface (fond et texte en tons de la même teinte) et **quelques touches fortes** pour les
  actions principales et les accents. Pas de dégradés, pas d'effets verre/flou.
- Le **contenu de chaque profil** (couleur d'accent, police, dessin) apporte la diversité ;
  l'interface elle-même reste sobre pour que les profils ressortent.
- Lisibilité d'abord : texte courant en encre pleine, contraste WCAG AA.
- Polices : liste restreinte, auto-hébergées, police de l'interface choisie pour le sujet.
- Pas d'emoji à la place des icônes d'interface (les emoji restent un choix de l'utilisateur
  pour son profil).

## 12. Technique

- **PWA** installable depuis le navigateur [Décidé] ; sous-domaine `jeudi.pierref.eu`.
- Plan initial : backend **FastAPI** + SQLite, front PWA. **La stack réelle est celle de ton
  binôme** : cette spec doit s'y adapter, pas l'inverse. À confirmer avec lui.
- Notifications push : Android directement, iPhone seulement après ajout à l'écran d'accueil.
- Hébergement : ce serveur (plus d'infra Hetzner), derrière Caddy, certificat automatique.
- Email : SMTP OVH, voir §3.
- Éditeur de dessin : canvas libre, export en PNG/SVG, taille limitée, nettoyage côté serveur.
- Données : minimisation, suppression de compte, mentions légales, pas de revente.

## 13. Intégration avec le code existant du binôme
La couche de personnalisation arrive **après** le socle. Pour que ce soit simple :
- Ajouter un champ `profile_style` (JSON) et un champ `drawing` sur l'utilisateur, sans toucher au
  reste du modèle.
- Le rendu du profil lit `profile_style` (couleurs, police, ordre des blocs) avec des valeurs par
  défaut si le champ est vide.
- L'éditeur de profil est un écran à part qui n'écrit que ces champs.
- Les classements et stats sont un module séparé qui ne lit que des agrégats.

## 14. Jalons proposés
1. Socle : inscription par email d'école, confirmation, profil de base, intention. (binôme)
2. Matching : critères avec marge, accord mutuel sur photos, Elo interne.
3. Créneaux : drop du jeudi, check-in, validation sur place, fiabilité, sanctions.
4. Personnalisation : dessin canvas, couleurs, polices, emoji, statut.
5. Stats et classements, avec seuil d'anonymat.
6. Modération, signalement, garde-fou, RGPD.
7. Lancement : QR codes sur le campus, BDE, bouche-à-oreille.

## 15. Idées en réserve
- Dessin du jour : un thème, chacun dessine, le campus vote.
- Saisons par semestre avec titres et badges pour les promos.
- Hall of fame des gens fiables.
- Défis inter-campus à objectif collectif (ex. 100 rencontres validées).
- QR codes contextuels sur le campus (distributeurs, salles de TP).
- Monétisation : aucune prévue, possible plus tard.

## 16. Points ouverts
- Âge minimum (§10).
- Nom définitif et sous-domaine (`jeudi` proposé).
- Seuil exact des sanctions de lapins.
- Fenêtre horaire du drop du jeudi.
- Liste exacte des domaines email par école.
- Stack du binôme et branche de départ.
