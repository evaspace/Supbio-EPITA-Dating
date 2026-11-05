/* Public page of Jeudi. Idea: the colour palettes people pick for their profiles become the chapters of the page,
   and the Thursday window (18 h to 22 h, Paris time) is a live countdown ticket. Chapters use the muted grounds of
   the profile palettes; the one raspberry hue stays on actions. */
const WINDOW = { day: 4, start: 18, end: 22 }; // Thursday, Paris time
const parisParts = d => Object.fromEntries(new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Paris', weekday: 'short', hour: 'numeric', minute: 'numeric', hourCycle: 'h23' }).formatToParts(d).map(p => [p.type, p.value]));
const DAYS = { Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 7 };

export function dropState(now = new Date()) {
  const p = parisParts(now), day = DAYS[p.weekday], min = Number(p.hour) * 60 + Number(p.minute);
  const open = day === WINDOW.day && min >= WINDOW.start * 60 && min < WINDOW.end * 60;
  if (open) return { open: true, minutes: WINDOW.end * 60 - min };
  let delta = (WINDOW.day - day) * 1440 + WINDOW.start * 60 - min;
  if (delta <= 0) delta += 7 * 1440;
  return { open: false, minutes: delta };
}
const span = m => { const d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), mi = m % 60; return d ? `${d} j ${h} h` : h ? `${h} h ${String(mi).padStart(2, '0')}` : `${mi} min`; };

export function ticketText() {
  const s = dropState();
  return s.open ? { head: 'Le drop est ouvert', big: `encore ${span(s.minutes)}`, note: 'Jusqu’à 22 h, heure de Paris' } : { head: 'Prochain drop', big: `dans ${span(s.minutes)}`, note: 'Jeudi, de 18 h à 22 h' };
}

const mini = (title, lines, foot) => `<div class="tk" data-ui><div class="tk-h">${title}</div>${lines.map(l => `<div class="tk-l">${l}</div>`).join('')}<div class="tk-f">${foot}</div></div>`;

export function landing(authHtml, esc) {
  const t = ticketText();
  const mark = '<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="6" fill="#b8336a"/><circle cx="16" cy="13" r="5" fill="#fbf7f8"/><rect x="14.5" y="19" width="3" height="7" fill="#fbf7f8"/></svg>';
  const faq = [
    ['Qui peut s’inscrire ?', 'Les étudiants majeurs d’EPITA, SupBiotech, ESME, ISG et IPSA, avec leur adresse d’école. Un code arrive par email à chaque création de compte.'],
    ['Pourquoi il n’y a pas de chat ?', 'Parce qu’un match sans rendez-vous finit en « salut ça va ». Ici, le match débouche sur un lieu et une heure, et l’activité sert de brise-glace.'],
    ['Où ont lieu les rencontres ?', 'Dans des lieux publics du campus, imposés par l’appli. Tu peux prévenir un ami de l’heure et du lieu en un geste.'],
    ['Et si quelqu’un ne vient pas ?', 'Chacun confirme sa venue une heure avant, puis valide sur place avec le code du lieu. Un lapin compte contre la fiabilité ; deux lapins suspendent les réservations pendant une semaine.'],
    ['Qui voit mes photos ?', 'Personne avant un match. Ton profil public est un dessin et un style que tu choisis ; tes photos ne s’ouvrent qu’aux personnes avec qui tu as matché.'],
    ['Mes statistiques sont-elles publiques ?', 'Jamais pour une personne seule. Les classements comparent des écoles et des promos, et un groupe n’apparaît qu’à partir de dix membres.'],
    ['Combien ça coûte ?', 'Rien. Pas d’abonnement, pas de publicité.'],
  ];
  const tile = (cls, bg, ink, inner, name, line) => `<div class="tile ${cls} rv" style="--tb:${bg};--ti:${ink}"><div class="tile-art">${inner}</div><div class="tile-cap"><b>${name}</b><span>${line}</span></div></div>`;
  const chapter = (bg, ink, n, clause, card) => `<div class="field" style="--fb:${bg};--fi:${ink}">${n === 0 ? '<h2 class="field-h rv">Du match au café</h2>' : ''}<div class="field-card rv">${card}</div><p class="field-c rv">${clause}</p></div>`;
  return `<div class="lp">
  <header class="lp-nav"><a class="brand" href="#top">${mark}Jeudi</a><nav aria-label="Sections"><a href="#how">Comment ça marche</a><a href="#features">Ce que tu y trouves</a><a href="#faq">Questions</a><a href="#top" data-auth="login">Se connecter</a></nav></header>
  <section class="hero" id="top"><div class="hero-t"><h1 class="rv">Un café plutôt qu’un chat</h1><p class="rv">Chaque jeudi soir, les créneaux de la semaine s’ouvrent pour les étudiants de Lyon. Tu matches, tu choisis un lieu, tu viens.</p><a class="btn primary rv" href="#join" data-auth="signup">Créer mon compte</a></div>
    <div class="stage"><div class="stage-in"><div class="ticket" data-ui aria-live="off"><div class="tk-h" data-t="head">${t.head}</div><div class="tk-big" data-t="big">${t.big}</div><div class="tk-l" data-t="note">${t.note}</div><div class="tk-l">Quatre heures pour proposer un lieu, une heure et une activité à chacun de tes matchs.</div></div><div id="join" class="join">${authHtml}</div></div></div></section>
  <section class="strip" id="how" aria-label="Du match au café">
    ${chapter('#ffd84a', '#17120f', 0, 'D’abord, le drop s’ouvre.', mini('Jeudi 18 h', ['Le drop s’ouvre', '122 places sur 6 jours'], 'Ouvert'))}
    ${chapter('#17120f', '#ffffff', 1, 'Ensuite, tu proposes un lieu.', mini('Léa · Café', ['Vendredi, 12 h 30', 'Cafétéria'], 'En attente de sa réponse'))}
    ${chapter('#5be3b0', '#17120f', 2, 'Puis tu confirmes ta venue.', mini('Léa · Café', ['Check-in de 11 h 30 à 12 h', 'Cafétéria'], 'Je viens'))}
    ${chapter('#ff6b9d', '#17120f', 3, 'Enfin, tu valides sur place.', mini('Léa · Café', ['Code du lieu : CAFE', 'Rencontre validée'], 'Fiabilité 100 %'))}
  </section>
  <section class="board" id="features" aria-labelledby="fh"><div class="board-grid">
    <div class="tile t-head rv" style="--tb:#ffffff;--ti:#17120f"><h2 id="fh">Ce que tu y trouves</h2></div>
    ${tile('t-d', '#ff6b9d', '#17120f', '<div class="big" data-ui>CAFE</div>', 'Lieux imposés', 'Un code affiché sur place valide la rencontre')}
    ${tile('t-c', '#ffd84a', '#17120f', '<div class="big" data-ui>10</div>', 'Seuil d’anonymat', 'Un groupe apparaît à dix membres')}
    <div class="tile t-a rv" style="--tb:#5be3b0;--ti:#17120f"><div class="shutter"><img src="./assets/dessin-cafe.webp" width="640" height="640" alt="Dessin d’une tasse de café fumante, exemple de dessin de profil" loading="lazy"><img src="./assets/dessin-escalade.webp" width="640" height="640" alt="Dessin d’un mur d’escalade, exemple de dessin de profil" loading="lazy"><img src="./assets/dessin-run.webp" width="640" height="640" alt="Dessin d’un soleil au-dessus d’un chemin, exemple de dessin de profil" loading="lazy"><img src="./assets/dessin-babyfoot.webp" width="640" height="640" alt="Dessin d’un baby-foot, exemple de dessin de profil" loading="lazy"></div><div class="tile-cap"><b>Ton profil, c’est un dessin</b><span>Tu le dessines, tu choisis tes couleurs et ta police</span></div></div>
    ${tile('t-b', '#17120f', '#ffffff', '<div class="big" data-ui>100 %</div>', 'Fiabilité', 'Visible par toi seul')}
    ${tile('t-f cap-lg', '#ff8a3d', '#17120f', '', 'Photos privées', 'Ouvertes seulement après un match')}
    ${tile('t-g cap-lg', '#ff6b9d', '#17120f', '', 'Réservé aux majeurs', 'Email d’école et code à chaque inscription')}
    ${tile('t-e', '#ffd84a', '#17120f', '<div class="big sm" data-ui>Rencontres · Amis · Binôme</div>', 'Ton intention', 'On ne propose que des profils qui en partagent une')}
    ${tile('t-h', '#5be3b0', '#17120f', '<div class="big sm" data-ui>0 message</div>', 'Pas de chat', 'Le match mène à un créneau')}
  </div></section>
  <section class="faq" id="faq"><h2 class="faq-h rv">Questions</h2><div class="faq-l">${faq.map(([q, a]) => `<details name="faq" class="rv"><summary>${q}<span class="pm" aria-hidden="true"></span></summary><p>${a}</p></details>`).join('')}</div></section>
  <section class="cta"><div class="cta-t"><h2 class="rv">Rendez-vous jeudi à 18 h</h2>
    <form class="cta-f rv" data-form="cta"><label class="sr" for="cta-mail">Email d’école</label><input id="cta-mail" class="cta-in" type="email" name="email" placeholder="prenom@epita.fr" autocomplete="email" required><button class="cta-b" type="submit">Je m’inscris</button></form>
    <p class="rv">Tu reçois un code par email pour vérifier ton adresse d’école, puis tu choisis ton mot de passe.</p></div>
    <figure class="cta-p"><div class="shutter"><img src="./assets/lyon-7e-quai-victor-augagneur-reveil-de.jpg" width="1920" height="1080" alt="Les quais du Rhône à Lyon par temps clair, avec des promeneurs entre les arbres" loading="lazy"></div><figcaption>Les quais du Rhône, Lyon</figcaption></figure></section>
  <footer class="foot"><svg class="blocks" viewBox="0 0 520 120" role="img" aria-label="Jeudi"><g font-family="Baloo 2, sans-serif" font-weight="800" font-size="92"><rect x="0" y="20" width="96" height="100" fill="#ffd84a"/><text x="48" y="108" text-anchor="middle" fill="#17120f">J</text><rect x="100" y="0" width="96" height="120" fill="#5be3b0"/><text x="148" y="108" text-anchor="middle" fill="#17120f">E</text><rect x="200" y="30" width="96" height="90" fill="#ff6b9d"/><text x="248" y="108" text-anchor="middle" fill="#17120f">U</text><rect x="300" y="10" width="96" height="110" fill="#ff8a3d"/><text x="348" y="108" text-anchor="middle" fill="#17120f">D</text><rect x="400" y="40" width="120" height="80" fill="#ffd84a"/><text x="460" y="108" text-anchor="middle" fill="#17120f">I</text></g></svg>
    <div class="foot-cols"><nav aria-label="Pied de page"><a href="#how">Comment ça marche</a><a href="#features">Ce que tu y trouves</a><a href="#faq">Questions</a><a href="#top" data-auth="login">Se connecter</a></nav><p>Jeudi est un service indépendant, non affilié aux écoles. Bêta privée, réservée aux majeurs.<br>Contact : <a href="mailto:morgan@pierref.eu">morgan@pierref.eu</a></p></div>
    <p class="credits">Photo : « Lyon 7e - Quai Victor Augagneur - Réveil de la Mâchecroûte » par Romainbehar, <a href="https://creativecommons.org/publicdomain/zero/1.0/deed.en/">CC0</a>, via <a href="https://commons.wikimedia.org/w/index.php?curid=120042339">Wikimedia Commons</a>. Les dessins de profil montrés ici sont des exemples faits pour cette page.</p></footer>
  </div>`;
}

export function hydrateLanding() {
  const upd = () => { const t = ticketText(); document.querySelectorAll('[data-t]').forEach(el => { el.textContent = t[el.dataset.t]; }); };
  clearInterval(hydrateLanding.timer); hydrateLanding.timer = setInterval(upd, 30000);
  const items = document.querySelectorAll('.rv, .cta-p');
  if (!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) { items.forEach(e => e.classList.add('shown')); return; }
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('shown'); io.unobserve(e.target); } }), { threshold: 0.12 });
  items.forEach((e, i) => { e.style.setProperty('--d', `${(i % 4) * 70}ms`); io.observe(e); });
}
