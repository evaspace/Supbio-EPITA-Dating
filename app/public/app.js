const root = document.getElementById('root');
const toastEl = document.getElementById('toast');
const SCHOOLS = ['EPITA', 'SupBiotech', 'ESME', 'ISG', 'IPSA'];
const GENDERS = ['Femme', 'Homme', 'Non-binaire', 'Autre', 'Non précisé'];
const INTENTS = [['dating', 'Rencontres'], ['amis', 'Amis'], ['binome', 'Binôme de TP']];
const FONTS = [['dm-sans', 'DM Sans'], ['bricolage', 'Bricolage'], ['fraunces', 'Fraunces'], ['caveat', 'Caveat'], ['baloo', 'Baloo'], ['playfair', 'Playfair'], ['anton', 'Anton']];
const PALETTES = [
  ['Sauge', '#e6efe8', '#1f5a3d'], ['Pierre', '#e7e9ee', '#1f3f7a'], ['Brume', '#e4ecf2', '#0f5c8a'], ['Rose', '#f9e3ea', '#b8336a'],
  ['Menthe', '#dff3ee', '#0b6b5a'], ['Brique', '#f3dcd6', '#8f2d1f'], ['Olive', '#eef0cf', '#3d4a0e'], ['Ardoise', '#1f2a33', '#f2b84b'],
];
const INKS = ['#1a1417', '#b8336a', '#0f5c8a', '#1f5a3d', '#f2b84b', '#8f2d1f', '#7a7a7a', '#ffffff'];
const BLOCK_LABELS = { bio: 'Bio', interests: 'Centres d’intérêt', status: 'Statut du moment', hook: 'Phrase d’accroche' };
const NAV = [['home', 'Accueil', 'home'], ['discover', 'Découvrir', 'compass'], ['matches', 'Matchs', 'heart'], ['slots', 'Créneaux', 'calendar'], ['ranks', 'Classement', 'trophy']];
const ICONS = {
  home: '<path d="M3 8.5 8 4l5 4.5V13H3z"/>', compass: '<circle cx="8" cy="8" r="5.5"/><path d="m10.3 5.7-1.2 3.4-3.4 1.2 1.2-3.4z"/>',
  heart: '<path d="M8 13S2.5 9.8 2.5 6.3A2.8 2.8 0 0 1 8 5.2a2.8 2.8 0 0 1 5.5 1.1C13.5 9.8 8 13 8 13z"/>', calendar: '<rect x="2.5" y="3.5" width="11" height="10" rx="1.5"/><path d="M2.5 6.5h11M5.5 2v3M10.5 2v3"/>',
  trophy: '<path d="M5 3h6v3.5a3 3 0 0 1-6 0zM5 4.5H3v1a2 2 0 0 0 2 2M11 4.5h2v1a2 2 0 0 1-2 2M8 9.5V12M5.5 13h5"/>', user: '<circle cx="8" cy="5.5" r="2.5"/><path d="M3 13.5c.6-2.6 2.6-4 5-4s4.4 1.4 5 4"/>',
  shield: '<path d="M8 2 3 4v4c0 3 2 4.8 5 6 3-1.2 5-3 5-6V4z"/>', flag: '<path d="M4 14V3M4 3.5h7l-1.5 2.5L11 8.5H4"/>', x: '<path d="m4 4 8 8M12 4l-8 8"/>', check: '<path d="m3.5 8.5 3 3 6-7"/>', menu: '<path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11"/>',
};
const icon = n => `<svg class="i" viewBox="0 0 16 16" aria-hidden="true">${ICONS[n] || ''}</svg>`;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const state = { user: null, style: null, screen: 'home', drop: null, bookings: null, me: null, matches: [], profiles: null, stats: null, interests: null, queue: null, tab: 'upcoming', auth: { step: 'email' }, menu: false };
let canvasCtx = null;

async function api(path, method = 'GET', body, form) {
  const opts = { method, headers: { 'X-Campus-Request': '1' }, credentials: 'same-origin' };
  if (form) opts.body = form;
  else if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  const r = await fetch(path, opts);
  let data = null;
  try { data = await r.json(); } catch { /* empty */ }
  if (!r.ok) {
    const d = data && data.detail;
    const e = new Error(typeof d === 'string' ? d : 'Vérifie les champs saisis');
    e.status = r.status;
    throw e;
  }
  return data;
}
function toast(msg) { toastEl.textContent = msg; toastEl.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => { toastEl.hidden = true; }, 4200); }
const lum = h => { const c = [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16) / 255).map(v => v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4); return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]; };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + .05) / (y + .05); };
const inkFor = bg => ratio(bg, '#1a1417') >= ratio(bg, '#ffffff') ? '#1a1417' : '#ffffff';
const tz = { timeZone: 'Europe/Paris' };
const fmtDay = iso => new Date(iso).toLocaleDateString('fr-FR', { ...tz, weekday: 'long', day: 'numeric', month: 'long' });
const fmtTime = iso => { const [h, m] = new Date(iso).toLocaleTimeString('fr-FR', { ...tz, hour: 'numeric', minute: '2-digit' }).split(':'); return m === '00' ? `${Number(h)} h` : `${Number(h)} h ${m}`; };
const fmtShort = iso => new Date(iso).toLocaleDateString('fr-FR', { ...tz, weekday: 'short', day: 'numeric', month: 'short' });
const dayKey = iso => new Date(iso).toLocaleDateString('sv-SE', tz);
function until(iso) {
  const ms = new Date(iso) - Date.now();
  if (ms <= 0) return 'maintenant';
  const m = Math.floor(ms / 60000), d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60);
  return d ? `${d} j ${h} h` : h ? `${h} h ${String(m % 60).padStart(2, '0')}` : `${m} min`;
}
const initial = n => esc((n || '?').trim().charAt(0).toUpperCase());

/* profile rendering in the person's own style */
function pvars(s) {
  const g = s?.ground || '#fbeef3', a = s?.accent || '#b8336a';
  return `--pg:${g};--pa:${a};--pi:${inkFor(g)};--pc:${inkFor(a)}`;
}
function art(p, cls = '') {
  const s = p.style || {};
  return s.drawing ? `<img src="${esc(s.drawing)}" alt="Dessin de ${esc(p.name)}" loading="lazy">` : `<span class="${cls}" aria-hidden="true">${initial(p.name)}</span>`;
}
function avatar(p) { return `<div class="avatar" style="${pvars(p.style)}">${p.style?.drawing ? art(p) : initial(p.name)}</div>`; }
function intentsText(s) { return (s?.intents || []).map(k => (INTENTS.find(i => i[0] === k) || [0, k])[1]).join(', '); }
function blockHtml(p, key) {
  const s = p.style || {};
  if (key === 'hook' && s.hook) return `<p class="hook">${esc(s.hook)}</p>`;
  if (key === 'status' && s.status) return `<p><span class="acc">En ce moment</span> ${esc(s.status)}</p>`;
  if (key === 'bio' && p.bio) return `<p>${esc(p.bio)}</p>`;
  if (key === 'interests' && p.interests?.length) {
    const top = (s.highlights || []).filter(h => p.interests.includes(h));
    const rest = p.interests.filter(i => !top.includes(i));
    return `<ul>${top.map(t => `<li><span class="acc">${esc(t)}</span></li>`).join('')}${rest.length ? `<li class="meta">${esc(rest.join(', '))}</li>` : ''}</ul>`;
  }
  return '';
}
function profileCard(p, actions = '', compact = false) {
  const s = p.style || {};
  const order = s.blocks?.length ? s.blocks : ['hook', 'status', 'bio', 'interests'];
  const shared = p.shared_interests?.length ? `<p class="meta">En commun : <span class="acc">${esc(p.shared_interests.join(', '))}</span></p>` : '';
  return `<article class="pcard f-${esc(s.font || 'dm-sans')}${compact ? ' compact' : ''}" style="${pvars(s)}">
    <div class="art">${art(p)}</div>
    <div class="body"><div><h2>${esc(p.name)}, ${p.age}${s.emoji ? ' ' + esc(s.emoji) : ''}</h2>
    <p class="meta">${esc(p.school)}${s.promo ? ' · ' + esc(s.promo) : ''} · ${esc(p.city)}</p></div>
    ${s.intents?.length ? `<span class="mine">${esc(intentsText(s))}</span>` : ''}
    ${order.map(k => blockHtml(p, k)).join('')}${shared}${actions}</div></article>`;
}

/* data loading */
async function loadSession() {
  try {
    state.user = await api('/api/me');
    state.style = await api('/api/me/style');
  } catch { state.user = null; }
}
async function refresh(parts) {
  const jobs = [];
  if (parts.includes('drop')) jobs.push(api('/api/drop').then(d => { state.drop = d; }));
  if (parts.includes('bookings')) jobs.push(api('/api/bookings').then(d => { state.bookings = d.bookings; state.me = d.me; }));
  if (parts.includes('matches')) jobs.push(api('/api/matches').then(d => { state.matches = d.matches; }));
  if (parts.includes('profiles')) jobs.push(api('/api/discover').then(d => { state.profiles = d.profiles; }));
  if (parts.includes('stats')) jobs.push(api('/api/stats').then(d => { state.stats = d; }));
  if (parts.includes('interests') && !state.interests) jobs.push(api('/api/interests').then(d => { state.interests = d.families; }));
  if (parts.includes('queue')) jobs.push(api('/api/admin/queue').then(d => { state.queue = d; }));
  await Promise.all(jobs);
}
const needs = { home: ['drop', 'bookings', 'matches'], discover: ['profiles', 'drop'], matches: ['matches', 'bookings', 'drop'], slots: ['bookings', 'drop'], ranks: ['stats'], profile: ['interests'], moderation: ['queue'] };
async function go(screen) {
  state.screen = screen;
  if (location.hash !== '#/' + screen) history.replaceState(null, '', '#/' + screen);
  state.menu = false;
  try { await refresh(needs[screen] || []); } catch (e) { if (e.status === 401) { state.user = null; } else toast(e.message); }
  render();
  window.scrollTo(0, 0);
}

/* shell */
function navItems() {
  const waiting = (state.matches || []).filter(m => !bookingFor(m)).length;
  return NAV.map(([id, label, ic]) => `<button data-nav="${id}" ${state.screen === id ? 'aria-current="page"' : ''}>${icon(ic)}${label}${id === 'matches' && waiting ? `<span class="count">${waiting}</span>` : ''}</button>`).join('');
}
function shell(inner) {
  const u = state.user;
  const mark = '<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="6" fill="#b8336a"/><circle cx="16" cy="13" r="5" fill="#fbf7f8"/><rect x="14.5" y="19" width="3" height="7" fill="#fbf7f8"/></svg>';
  const all = `${navItems()}`;
  return `<div class="shell">
  <aside class="side" aria-label="Navigation">
    <a class="brand" href="#/home">${mark}Jeudi</a>
    <nav class="nav">${all}</nav>
    <div class="group">Compte</div>
    <nav class="nav"><button data-nav="profile" ${state.screen === 'profile' ? 'aria-current="page"' : ''}>${icon('user')}Mon profil</button>
    ${u.is_admin ? `<button data-nav="moderation" ${state.screen === 'moderation' ? 'aria-current="page"' : ''}>${icon('shield')}Modération</button>` : ''}</nav>
    <div class="spacer"></div>
    <div class="who"><div class="avatar" style="${pvars(state.style)};width:32px;height:32px;font-size:14px">${state.style?.drawing ? `<img src="${esc(state.style.drawing)}" alt="">` : initial(u.name)}</div><div><b>${esc(u.name)}</b><span class="muted small">${esc(u.school)}</span></div></div>
  </aside>
  <div>
    <div class="topbar"><a class="brand" href="#/home">${mark}Jeudi</a><button class="btn plain" data-nav="profile" aria-label="Mon profil">${icon('user')}</button></div>
    <main class="canvas" id="main">${inner}</main>
  </div>
  <nav class="bottom" aria-label="Navigation">${NAV.map(([id, label, ic]) => `<button data-nav="${id}" ${state.screen === id ? 'aria-current="page"' : ''}>${icon(ic)}${label}</button>`).join('')}</nav>
  </div>`;
}
const head = (title, sub, actions = '') => `<div class="head"><div><h1>${title}</h1>${sub ? `<p>${sub}</p>` : ''}</div>${actions ? `<div class="row">${actions}</div>` : ''}</div>`;

/* bookings helpers */
function bookingFor(m) { return (state.bookings || []).find(b => ['proposed', 'confirmed'].includes(b.status) && b.other?.id === m.profile.id) || null; }
const statusTag = b => ({
  proposed: b.proposed_by_me ? '<span class="tag warn">Attend sa réponse</span>' : '<span class="tag accent">À accepter</span>',
  confirmed: '<span class="tag good">Confirmé</span>', cancelled: '<span class="tag">Annulé</span>', done: '<span class="tag good">Validé</span>', lapin: '<span class="tag bad">Lapin</span>',
}[b.status] || '');

/* screens */
function screenHome() {
  const d = state.drop, bs = state.bookings || [], me = state.me || {};
  const upcoming = bs.filter(b => ['proposed', 'confirmed'].includes(b.status)).sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const free = (state.matches || []).filter(m => !bookingFor(m));
  const next = upcoming[0];
  let lead, sub, cta = '';
  if (me.banned_until) { lead = 'Réservations suspendues'; sub = `Deux lapins : tu pourras de nouveau réserver le ${fmtDay(me.banned_until)}.`; }
  else if (d?.open) {
    const left = d.offers.reduce((n, o) => n + o.left, 0);
    lead = `Le drop est ouvert jusqu’à ${fmtTime(d.closes_at)}`;
    sub = `${left} places réparties sur ${new Set(d.offers.map(o => dayKey(o.starts_at))).size} jours.`;
    if (free.length) cta = `<button class="btn primary" data-act="pick-match">Choisir un créneau</button>`;
    else cta = `<button class="btn primary" data-nav="discover">Découvrir des profils</button>`;
  } else {
    lead = `Prochain drop dans <span data-count="${esc(d?.opens_at)}">${d ? until(d.opens_at) : ''}</span>`;
    sub = `Les créneaux de la semaine s’ouvrent jeudi à ${d ? fmtTime(d.opens_at) : '18 h'}, pour quatre heures.`;
    cta = `<button class="btn primary" data-nav="discover">Découvrir des profils</button>`;
  }
  const week = weekStrip(d, upcoming);
  const nextCard = next ? `<div class="card"><h2>Prochain créneau</h2><div class="list">${bookingRow(next)}</div></div>` : '';
  const freeCard = free.length ? `<div class="card"><h2>Matchs sans créneau</h2><p class="sub">${d?.open ? 'Choisis un lieu et une heure avec chacun.' : 'Tu pourras proposer un créneau à l’ouverture du prochain drop.'}</p><div class="list">${free.slice(0, 4).map(m => `<div class="item">${avatar(m.profile)}<div><div class="t">${esc(m.profile.name)}</div><div class="s">${esc(m.profile.school)}</div></div><div class="acts">${d?.open ? `<button class="btn primary" data-act="offers" data-match="${esc(m.id)}">Proposer un créneau</button>` : ''}</div></div>`).join('')}</div></div>` : '';
  const dueAction = !state.style?.configured ? `<div class="notice">Choisis ton intention et ton style pour apparaître dans la découverte. <button class="btn plain" data-nav="profile">Compléter mon profil</button></div>` : '';
  return `${head('Cette semaine', '')}<div class="stack">${dueAction}
    <section class="card"><div class="lead">${lead}</div><p class="muted" style="font-size:16px;margin-top:8px">${sub}</p><div class="row" style="margin-top:20px">${cta}</div>
    <div class="figures"><div><b>${me.meetings ?? 0}</b><span>Rencontres validées</span></div><div><b>${me.reliability == null ? '–' : me.reliability + ' %'}</b><span>Fiabilité</span></div><div><b>${me.lapins ?? 0}</b><span>Lapins</span></div></div></section>
    <section class="card"><h2>La semaine</h2><p class="sub">Le drop s’ouvre le jeudi. Tes créneaux apparaissent le jour où ils ont lieu.</p>${week}</section>
    ${nextCard && freeCard ? `<div class="cols2">${nextCard}${freeCard}</div>` : nextCard + freeCard}</div>`;
}
function weekStrip(d, upcoming) {
  const base = new Date();
  const monday = new Date(base); monday.setDate(base.getDate() - ((base.getDay() + 6) % 7));
  const names = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
  const todayKey = new Date().toLocaleDateString('sv-SE', tz);
  const cells = names.map((n, i) => {
    const day = new Date(monday); day.setDate(monday.getDate() + i);
    const key = day.toLocaleDateString('sv-SE');
    const slots = upcoming.filter(b => dayKey(b.starts_at) === key).map(b => `<div class="slot ${b.status}"><b>${fmtTime(b.starts_at)}</b> ${esc(b.activity)}<br>${esc(b.other?.name || '')}</div>`).join('');
    const isDrop = i === 3;
    return `<div class="day${key === todayKey ? ' today' : ''}${isDrop ? ' drop' : ''}"><b>${n} ${day.getDate()}</b>${isDrop && d ? `<span>Drop ${fmtTime(d.opens_at)} à ${fmtTime(d.closes_at)}</span>` : ''}${slots}</div>`;
  });
  return `<div class="week">${cells.join('')}</div>`;
}
function bookingRow(b) {
  const o = b.other || { name: '?', style: {} };
  const acts = [];
  if (b.can_accept) acts.push(`<button class="btn primary" data-act="accept" data-id="${esc(b.id)}">Accepter</button>`);
  if (b.can_checkin) acts.push(`<button class="btn primary" data-act="checkin" data-id="${esc(b.id)}">Je viens</button>`);
  if (b.can_validate) acts.push(`<form class="row" data-form="validate" data-id="${esc(b.id)}"><label class="sr" for="c${esc(b.id)}">Code affiché sur place</label><input class="in" id="c${esc(b.id)}" name="code" placeholder="Code du lieu" style="width:140px" required><button class="btn primary" type="submit">Valider sur place</button></form>`);
  if (b.can_feedback) acts.push(`<button class="btn" data-act="again" data-v="1" data-id="${esc(b.id)}">À revoir</button><button class="btn" data-act="again" data-v="0" data-id="${esc(b.id)}">Pas pour moi</button>`);
  if (['proposed', 'confirmed'].includes(b.status)) {
    acts.push(`<button class="btn" data-act="share" data-id="${esc(b.id)}">Prévenir un ami</button>`);
    acts.push(`<button class="btn danger" data-act="cancel" data-id="${esc(b.id)}">Annuler</button>`);
  }
  let hint = '';
  if (b.status === 'confirmed' && !b.my_checkin) hint = `Check-in de ${fmtTime(b.checkin_opens_at)} à ${fmtTime(b.checkin_deadline)}`;
  else if (b.status === 'confirmed' && b.my_checkin && !b.my_valid) hint = b.their_checkin ? 'Vous avez tous les deux confirmé' : 'En attente de son check-in';
  else if (b.my_valid && b.status === 'confirmed') hint = 'Ta venue est validée';
  return `<div class="item">${avatar(o)}<div><div class="t">${esc(o.name)} · ${esc(b.activity)}</div><div class="s">${esc(fmtShort(b.starts_at))}, ${fmtTime(b.starts_at)} · ${esc(b.venue)}</div>${hint ? `<div class="s">${hint}</div>` : ''}</div><div class="acts">${statusTag(b)}${acts.join('')}</div></div>`;
}
function screenSlots() {
  const bs = state.bookings || [];
  const up = bs.filter(b => ['proposed', 'confirmed'].includes(b.status)).sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const past = bs.filter(b => !['proposed', 'confirmed'].includes(b.status) || b.can_feedback);
  const list = state.tab === 'upcoming' ? up : past;
  return `${head('Créneaux', 'Un match mène à un lieu et une heure, pas à une conversation.')}
  <div class="tabs" role="tablist"><button role="tab" data-tab="upcoming" aria-selected="${state.tab === 'upcoming'}">À venir (${up.length})</button><button role="tab" data-tab="past" aria-selected="${state.tab === 'past'}">Passés (${past.length})</button></div>
  <div class="card">${list.length ? `<div class="list">${list.map(bookingRow).join('')}</div>` : `<p class="muted">${state.tab === 'upcoming' ? 'Aucun créneau prévu. Après un match, propose un lieu pendant le drop du jeudi.' : 'Aucune rencontre passée pour l’instant.'}</p>`}</div>`;
}
function screenMatches() {
  const ms = state.matches || [];
  const rows = ms.map(m => {
    const b = bookingFor(m);
    const act = b ? `<button class="btn" data-nav="slots">Voir le créneau</button>` : (state.drop?.open ? `<button class="btn primary" data-act="offers" data-match="${esc(m.id)}">Proposer un créneau</button>` : `<span class="muted small">Drop jeudi ${state.drop ? fmtTime(state.drop.opens_at) : '18 h'}</span>`);
    return `<div class="item">${avatar(m.profile)}<div><div class="t">${esc(m.profile.name)}, ${m.profile.age}</div><div class="s">${esc(m.profile.school)} · ${b ? esc(b.activity) + ', ' + esc(fmtShort(b.starts_at)) : 'pas encore de créneau'}</div></div><div class="acts"><button class="btn" data-act="view" data-match="${esc(m.id)}">Voir le profil</button>${act}</div></div>`;
  }).join('');
  return `${head('Matchs', ms.length ? `${ms.length} ${ms.length > 1 ? 'personnes' : 'personne'}` : '')}<div class="card">${rows ? `<div class="list">${rows}</div>` : '<p class="muted">Aucun match pour l’instant. Les profils que tu aimes et qui t’aiment aussi apparaissent ici, avec leurs photos privées.</p>'}</div>`;
}
function screenDiscover() {
  const ps = state.profiles;
  if (!state.style?.configured) return `${head('Découvrir', '')}<div class="notice">Choisis d’abord ton intention (rencontres, amis, binôme) dans ton profil. <button class="btn plain" data-nav="profile">Compléter mon profil</button></div>`;
  const p = ps?.[0];
  if (!p) return `${head('Découvrir', '')}<div class="card"><p>Plus aucun profil pour l’instant.</p><p class="muted" style="margin-top:6px">Élargis tes filtres dans ton profil, ou reviens après le prochain drop.</p></div>`;
  const actions = `<div class="actions"><button class="btn" data-act="pass" data-id="${esc(p.id)}">Passer</button><button class="btn primary" data-act="like" data-id="${esc(p.id)}">Ça me dit</button><button class="btn" data-act="report" data-id="${esc(p.id)}" aria-label="Signaler ${esc(p.name)}">${icon('flag')}Signaler</button><button class="btn" data-act="block" data-id="${esc(p.id)}">Bloquer</button></div>`;
  return `${head('Découvrir', `${ps.length} ${ps.length > 1 ? 'profils' : 'profil'} dans tes filtres. Les photos restent privées jusqu’au match.`)}${profileCard(p, actions)}`;
}
function screenRanks() {
  const s = state.stats;
  const rows = (s?.ranking || []).map((r, i) => `<tr><td>${esc(r.label)}</td><td class="n">${r.members}</td><td class="n">${r.meetings}</td><td class="n">${r.reliability == null ? '–' : r.reliability + ' %'}</td></tr>`).join('');
  return `${head('Classements', 'Rencontres réellement validées par école. Rien n’est affiché sur une personne seule.')}
  <div class="stack"><div class="card"><h2>Mes chiffres</h2><div class="figures" style="margin-top:12px"><div><b>${s?.me.meetings ?? 0}</b><span>Rencontres validées</span></div><div><b>${s?.me.reliability == null ? '–' : s.me.reliability + ' %'}</b><span>Fiabilité, visible par toi seul</span></div><div><b>${s?.me.lapins ?? 0}</b><span>Lapins</span></div></div></div><div class="card"><h2>Par école</h2>${rows ? `<table><thead><tr><th>École</th><th class="n">Membres</th><th class="n">Rencontres validées</th><th class="n">Fiabilité</th></tr></thead><tbody>${rows}</tbody></table>` : `<p class="muted" style="margin-top:8px">Aucune école n’atteint encore ${s?.threshold ?? 10} membres. Un groupe n’apparaît qu’à partir de ce seuil, pour que personne ne soit identifiable.</p>`}${s?.hidden_groups ? `<p class="muted small" style="margin-top:12px">${s.hidden_groups} ${s.hidden_groups > 1 ? 'groupes masqués' : 'groupe masqué'} sous le seuil.</p>` : ''}</div>
</div>`;
}

/* profile screen */
function screenProfile() {
  const u = state.user, s = state.style || {}, pref = u.preferences;
  const sw = PALETTES.map(([n, g, a]) => `<button type="button" class="swatch" style="--g:${g};--a:${a}" data-act="palette" data-g="${g}" data-a="${a}" aria-label="Palette ${n}" aria-pressed="${s.ground === g && s.accent === a}"></button>`).join('');
  const hi = u.interests.length ? u.interests.map(t => `<label class="check"><input type="checkbox" name="hi" value="${esc(t)}" ${s.highlights?.includes(t) ? 'checked' : ''}>${esc(t)}</label>`).join('') : '<p class="muted">Choisis d’abord tes centres d’intérêt plus bas.</p>';
  const blocks = (s.blocks || ['bio', 'interests', 'status', 'hook']);
  const photos = (u.photos || []).map(p => `<figure><img src="${esc(p.url)}" alt="Photo privée"><span>${p.status === 'approved' ? 'Validée' : 'En modération'}</span><span class="row"><button class="btn" data-act="photo-move" data-id="${esc(p.id)}" data-d="-1" aria-label="Déplacer vers la gauche">←</button><button class="btn" data-act="photo-move" data-id="${esc(p.id)}" data-d="1" aria-label="Déplacer vers la droite">→</button><button class="btn danger" data-act="photo-del" data-id="${esc(p.id)}" aria-label="Supprimer la photo">${icon('x')}</button></span></figure>`).join('');
  const preview = profileCard({ ...u, style: s });
  return `${head('Mon profil', state.style?.configured ? '' : 'Choisis ton intention et ton style : c’est ce qui te rend visible dans la découverte.')}
  <div id="prev" class="card" style="margin-bottom:var(--gap)"><h2>Aperçu public</h2><p class="sub">Ce que les autres voient. Tes photos restent privées jusqu’au match.</p>${preview}</div>
  <section class="setting"><div><h2>Identité</h2><p>Prénom, campus et genre.</p></div><form class="panel fields" data-form="identity">
    <div class="fields two"><label class="f">Prénom<input class="in" name="name" value="${esc(u.name)}" minlength="2" maxlength="35" required></label>
    <label class="f">Campus<select class="in" name="city"><option>Lyon</option><option ${u.city === 'Paris' ? 'selected' : ''}>Paris</option><option ${u.city === 'Rennes' ? 'selected' : ''}>Rennes</option><option ${u.city === 'Strasbourg' ? 'selected' : ''}>Strasbourg</option><option ${u.city === 'Toulouse' ? 'selected' : ''}>Toulouse</option><option ${u.city === 'Autre' ? 'selected' : ''}>Autre</option></select></label></div>
    <label class="f">Je me définis comme<select class="in" name="gender">${GENDERS.map(g => `<option ${u.gender === g ? 'selected' : ''}>${g}</option>`).join('')}</select></label>
    <label class="f">Bio<textarea class="in" name="bio" maxlength="450">${esc(u.bio)}</textarea></label>
    <label class="check"><input type="checkbox" name="visible" ${u.visible ? 'checked' : ''}>Afficher mon profil dans la découverte</label>
    <div><button class="btn primary" type="submit">Enregistrer</button></div></form></section>
  <section class="setting"><div><h2>Intention et style</h2><p>L’intention est obligatoire : on ne propose que des profils qui en partagent une. Le style s’applique à ton profil public.</p></div>
    <form class="panel fields" data-form="style">
    <fieldset class="fields" style="border:0;padding:0;margin:0"><legend style="font-weight:500;margin-bottom:8px">Je cherche</legend>${INTENTS.map(([k, l]) => `<label class="check"><input type="checkbox" name="intents" value="${k}" ${s.intents?.includes(k) ? 'checked' : ''}>${l}</label>`).join('')}</fieldset>
    <label class="f">Promo<input class="in" name="promo" value="${esc(s.promo || '')}" maxlength="20" placeholder="Par exemple 2028"></label>
    <div><div style="font-weight:500;margin-bottom:8px">Palette</div><div class="palettes">${sw}</div></div>
    <div class="colors"><label class="f">Fond<input type="color" name="ground" value="${esc(s.ground || '#fbeef3')}"></label><label class="f">Accent<input type="color" name="accent" value="${esc(s.accent || '#b8336a')}"></label><small class="muted" id="contrast"></small></div>
    <label class="f">Police du profil<select class="in" name="font">${FONTS.map(([k, l]) => `<option value="${k}" ${s.font === k ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
    <div class="fields two"><label class="f">Emoji signature<input class="in" name="emoji" value="${esc(s.emoji || '')}" maxlength="8"></label><label class="f">Statut du moment<input class="in" name="status" value="${esc(s.status || '')}" maxlength="80" placeholder="En partiel jusqu’à vendredi"></label></div>
    <label class="f">Phrase d’accroche<input class="in" name="hook" value="${esc(s.hook || '')}" maxlength="120"></label>
    <fieldset class="fields" style="border:0;padding:0;margin:0"><legend style="font-weight:500;margin-bottom:8px">Trois intérêts phares</legend>${hi}</fieldset>
    <div><div style="font-weight:500;margin-bottom:8px">Ordre des blocs</div><ol id="blocks" style="margin:0;padding:0;list-style:none;display:grid;gap:6px">${blocks.map(b => `<li class="row" data-block="${b}"><span style="width:200px">${BLOCK_LABELS[b]}</span><button type="button" class="btn" data-act="block-move" data-b="${b}" data-d="-1" aria-label="Monter ${BLOCK_LABELS[b]}">↑</button><button type="button" class="btn" data-act="block-move" data-b="${b}" data-d="1" aria-label="Descendre ${BLOCK_LABELS[b]}">↓</button></li>`).join('')}</ol></div>
    <div><button class="btn primary" type="submit">Enregistrer le style</button></div></form></section>
  <section class="setting"><div><h2>Dessin</h2><p>Ton visuel public. Dessine-le ici, il remplace ta photo dans la découverte.</p></div><div class="panel draw">
    <canvas id="pad" width="480" height="480" aria-label="Zone de dessin"></canvas>
    <div class="ink" role="group" aria-label="Couleurs">${INKS.map((c, i) => `<button type="button" style="--c:${c}" data-act="ink" data-c="${c}" aria-pressed="${i === 0}" aria-label="Couleur ${c}"></button>`).join('')}</div>
    <label class="f">Épaisseur<input type="range" id="brush" min="2" max="28" value="6"></label>
    <div class="row"><button class="btn" type="button" data-act="undo">Annuler le trait</button><button class="btn" type="button" data-act="clear">Effacer</button><button class="btn primary" type="button" data-act="save-draw">Enregistrer le dessin</button>${s.drawing ? '<button class="btn danger" type="button" data-act="del-draw">Supprimer</button>' : ''}</div></div></section>
  <section class="setting"><div><h2>Centres d’intérêt</h2><p>${u.interests.length} sur 12.</p></div><div class="panel"><div class="chips" style="margin-bottom:12px">${u.interests.map(t => `<span class="tag accent">${esc(t)}</span>`).join('') || '<span class="muted">Aucun pour l’instant</span>'}</div><button class="btn" data-act="interests">Choisir mes intérêts</button></div></section>
  <section class="setting"><div><h2>Photos privées</h2><p>Jusqu’à 6, jamais visibles avant un match, validées à la main.</p></div><div class="panel fields"><div class="photos">${photos}</div><form data-form="photo" class="row"><label class="sr" for="photo">Ajouter une photo</label><input id="photo" type="file" name="photo" accept="image/jpeg,image/png,image/webp" required><button class="btn" type="submit" ${(u.photos || []).length >= 6 ? 'disabled' : ''}>Ajouter</button></form></div></section>
  <section class="setting"><div><h2>Découverte</h2><p>Les deux profils doivent passer les critères l’un de l’autre.</p></div><form class="panel fields" data-form="prefs">
    <fieldset class="fields" style="border:0;padding:0;margin:0"><legend style="font-weight:500;margin-bottom:8px">Écoles</legend>${SCHOOLS.map(x => `<label class="check"><input type="checkbox" name="schools" value="${x}" ${pref.schools.includes(x) ? 'checked' : ''}>${x}</label>`).join('')}</fieldset>
    <fieldset class="fields" style="border:0;padding:0;margin:0"><legend style="font-weight:500;margin-bottom:8px">Genres</legend>${GENDERS.map(x => `<label class="check"><input type="checkbox" name="genders" value="${x}" ${pref.genders.includes(x) ? 'checked' : ''}>${x}</label>`).join('')}</fieldset>
    <div class="fields two"><label class="f">Âge minimum<input class="in" type="number" name="age_min" min="18" max="99" value="${pref.age_min}"></label><label class="f">Âge maximum<input class="in" type="number" name="age_max" min="18" max="99" value="${pref.age_max}"></label></div>
    <div><button class="btn primary" type="submit">Enregistrer</button></div></form></section>
  <section class="setting"><div><h2>Mes données</h2><p>Export et suppression en libre-service.</p></div><div class="panel row"><button class="btn" data-act="export">Exporter mes données</button><button class="btn" data-act="logout">Se déconnecter</button><button class="btn danger" data-act="delete">Supprimer mon compte</button></div></section>`;
}
function screenModeration() {
  const q = state.queue;
  if (!q) return head('Modération', '');
  const acc = q.accounts.map(a => `<div class="item"><div class="avatar">${initial(a.name)}</div><div><div class="t">${esc(a.name)} · ${esc(a.school)}</div><div class="s">${esc(a.email)} · âge déclaré ${a.age_declared}</div></div><div class="acts"><button class="btn primary" data-act="approve" data-id="${esc(a.id)}">Approuver après vérification</button></div></div>`).join('');
  const ph = q.photos.map(p => `<div class="item"><img src="/api/admin/photos/${esc(p.id)}" alt="Photo à modérer" width="48" height="48" style="border-radius:6px;object-fit:cover"><div class="t">Photo en attente</div><div class="acts"><button class="btn primary" data-act="photo-ok" data-id="${esc(p.id)}">Approuver</button><button class="btn danger" data-act="photo-no" data-id="${esc(p.id)}">Rejeter</button></div></div>`).join('');
  const rp = q.reports.map(r => `<div class="item"><div class="avatar">${icon('flag')}</div><div><div class="t">${esc(r.reason)}</div><div class="s">Compte signalé ${esc(r.target_id)}</div></div><div class="acts"><button class="btn" data-act="drawing-del" data-id="${esc(r.target_id)}">Supprimer son dessin</button><button class="btn primary" data-act="report-ok" data-id="${esc(r.id)}">Marquer traité</button></div></div>`).join('');
  return `${head('Modération', 'Vérifie la majorité par une procédure adaptée avant d’approuver : une date de naissance déclarée ne prouve rien.')}<div class="stack">
  <div class="card"><h2>Comptes en attente</h2>${acc ? `<div class="list">${acc}</div>` : '<p class="muted">Aucun compte en attente.</p>'}</div>
  <div class="card"><h2>Photos à modérer</h2>${ph ? `<div class="list">${ph}</div>` : '<p class="muted">Aucune photo en attente.</p>'}</div>
  <div class="card"><h2>Signalements</h2>${rp ? `<div class="list">${rp}</div>` : '<p class="muted">Aucun signalement ouvert.</p>'}</div></div>`;
}

/* auth */
function screenAuth() {
  const a = state.auth;
  const mark = '<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="6" fill="#b8336a"/><circle cx="16" cy="13" r="5" fill="#fbf7f8"/><rect x="14.5" y="19" width="3" height="7" fill="#fbf7f8"/></svg>';
  const form = a.step === 'email'
    ? `<form class="card fields" data-form="request"><h2>Connexion par email d’école</h2>
      <label class="f">École<select class="in" name="school">${SCHOOLS.map(s => `<option ${a.school === s ? 'selected' : ''}>${s}</option>`).join('')}</select></label>
      <label class="f">Email d’école<input class="in" type="email" name="email" autocomplete="email" required value="${esc(a.email || '')}"></label>
      <button class="btn primary" type="submit">Recevoir mon code</button></form>`
    : `<form class="card fields" data-form="verify"><h2>Code reçu par email</h2><p class="muted">Envoyé à ${esc(a.email)}. Il expire dans 10 minutes.</p>
      <label class="f">Code à 6 chiffres<input class="in" name="code" inputmode="numeric" pattern="\\d{6}" maxlength="6" autocomplete="one-time-code" required></label>
      <div class="fields two"><label class="f">Prénom<input class="in" name="name" minlength="2" maxlength="35" required></label><label class="f">Date de naissance<input class="in" type="date" name="birthday" required></label></div>
      <label class="f">Genre<select class="in" name="gender">${GENDERS.map(g => `<option ${g === 'Non précisé' ? 'selected' : ''}>${g}</option>`).join('')}</select></label>
      <label class="check"><input type="checkbox" name="consent" required>J’ai 18 ans ou plus</label>
      <div class="row"><button class="btn primary" type="submit">Entrer</button><button class="btn plain" type="button" data-act="auth-back">Changer d’adresse</button></div></form>`;
  return `<div class="auth"><div><div class="brand">${mark}Jeudi</div><h1>Un café plutôt qu’un chat</h1>
    <p class="lede">Chaque jeudi soir, les créneaux de la semaine s’ouvrent. Tu matches, tu choisis un lieu du campus et une heure, puis tu viens.</p>
    <ol><li>Ton profil est un dessin et un style, pas un feed</li><li>Le match débouche sur un créneau, pas sur une conversation</li><li>Les photos restent privées jusqu’au match</li></ol></div>${form}</div>`;
}

function render() {
  if (!state.user) { root.innerHTML = screenAuth(); return; }
  const screens = { home: screenHome, discover: screenDiscover, matches: screenMatches, slots: screenSlots, ranks: screenRanks, profile: screenProfile, moderation: screenModeration };
  const keepScroll = window.scrollY;
  root.innerHTML = shell((screens[state.screen] || screenHome)());
  document.title = ({ home: 'Cette semaine', discover: 'Découvrir', matches: 'Matchs', slots: 'Créneaux', ranks: 'Classements', profile: 'Mon profil', moderation: 'Modération' }[state.screen] || 'Jeudi') + ' · Jeudi';
  if (state.screen === 'profile') initPad();
  window.scrollTo(0, keepScroll);
}

/* drawing pad */
function initPad() {
  const c = document.getElementById('pad'); if (!c) return;
  const ctx = c.getContext('2d'); canvasCtx = { c, ctx, color: INKS[0], undo: [], down: false };
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height);
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  if (state.style?.drawing) { const img = new Image(); img.onload = () => ctx.drawImage(img, 0, 0, c.width, c.height); img.src = state.style.drawing; }
  const pos = e => { const r = c.getBoundingClientRect(); return [(e.clientX - r.left) * c.width / r.width, (e.clientY - r.top) * c.height / r.height]; };
  c.addEventListener('pointerdown', e => { canvasCtx.undo.push(ctx.getImageData(0, 0, c.width, c.height)); if (canvasCtx.undo.length > 20) canvasCtx.undo.shift(); canvasCtx.down = true; c.setPointerCapture(e.pointerId); const [x, y] = pos(e); ctx.strokeStyle = canvasCtx.color; ctx.lineWidth = Number(document.getElementById('brush').value); ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + .01, y); ctx.stroke(); });
  c.addEventListener('pointermove', e => { if (!canvasCtx.down) return; const [x, y] = pos(e); ctx.lineTo(x, y); ctx.stroke(); });
  const stop = () => { canvasCtx.down = false; };
  c.addEventListener('pointerup', stop); c.addEventListener('pointercancel', stop);
  updateContrast();
}
function updateContrast() {
  const f = document.querySelector('[data-form="style"]'); if (!f) return;
  const r = ratio(f.ground.value, f.accent.value);
  const el = document.getElementById('contrast');
  if (el) el.textContent = r >= 3 ? `Contraste ${r.toFixed(1)}` : `Contraste ${r.toFixed(1)}, trop faible (minimum 3)`;
}

/* dialogs */
function dialog(html) {
  const d = document.createElement('dialog'); d.innerHTML = html + '<div class="row end" style="margin-top:16px"><button class="btn" data-close>Fermer</button></div>';
  d.addEventListener('click', e => { if (e.target.matches('[data-close]') || e.target === d) d.close(); });
  d.addEventListener('close', () => d.remove());
  document.body.appendChild(d); d.showModal(); return d;
}
async function offersDialog(matchId) {
  try { await refresh(['drop']); } catch (e) { toast(e.message); return; }
  const m = state.matches.find(x => x.id === matchId);
  if (!state.drop.open) { toast('Le drop est fermé. Prochaine ouverture jeudi à 18 h'); return; }
  const byDay = {};
  state.drop.offers.forEach(o => { (byDay[dayKey(o.starts_at)] ||= []).push(o); });
  const html = Object.values(byDay).map(list => `<h3>${esc(fmtDay(list[0].starts_at))}</h3>${list.map(o => `<button class="offer" data-act="book" data-match="${esc(matchId)}" data-offer="${esc(o.id)}" ${o.left <= 0 ? 'disabled' : ''}><b>${fmtTime(o.starts_at)}</b><span>${esc(o.activity)} · ${esc(o.venue)}</span><span class="muted small">${o.left > 0 ? o.left + ' ' + (o.left > 1 ? 'places' : 'place') : 'Complet'}</span></button>`).join('')}`).join('');
  const d = dialog(`<h2>Créneau avec ${esc(m?.profile.name || '')}</h2><p class="muted">Tu proposes, ${esc(m?.profile.name || 'la personne')} accepte. Aucun message n’est échangé.</p><div class="offers">${html}</div>`);
  d.dataset.kind = 'offers';
}
function interestsDialog() {
  const sel = new Set(state.user.interests);
  const d = dialog(`<h2>Centres d’intérêt</h2><p class="muted"><span id="ni">${sel.size}</span> sur 12</p><div class="interests offers" style="max-height:55vh">${state.interests.map(f => `<div><h3>${esc(f.name)}</h3><div class="chips">${f.tags.map(t => `<button type="button" data-tag="${esc(t)}" aria-pressed="${sel.has(t)}">${esc(t)}</button>`).join('')}</div></div>`).join('')}</div><div class="row"><button class="btn primary" data-act="save-interests">Enregistrer</button></div>`);
  d.addEventListener('click', e => {
    const b = e.target.closest('[data-tag]'); if (!b) return;
    const t = b.dataset.tag;
    if (sel.has(t)) sel.delete(t); else if (sel.size < 12) sel.add(t); else { toast('Maximum 12 centres d’intérêt'); return; }
    b.setAttribute('aria-pressed', sel.has(t)); d.querySelector('#ni').textContent = sel.size;
  });
  d.addEventListener('click', async e => {
    if (!e.target.closest('[data-act="save-interests"]')) return;
    try { state.user = await api('/api/me', 'PATCH', { interests: [...sel] }); d.close(); toast('Centres d’intérêt enregistrés'); render(); } catch (err) { toast(err.message); }
  });
}

/* actions */
const acts = {
  async 'pick-match'() { const free = state.matches.filter(m => !bookingFor(m)); if (free.length === 1) return offersDialog(free[0].id); const d = dialog(`<h2>Avec qui ?</h2><div class="list">${free.map(m => `<div class="item">${avatar(m.profile)}<div class="t">${esc(m.profile.name)}</div><div class="acts"><button class="btn primary" data-act="offers" data-match="${esc(m.id)}">Choisir</button></div></div>`).join('')}</div>`); d.dataset.kind = 'pick'; },
  async offers(b) { document.querySelectorAll('dialog').forEach(x => x.close()); await offersDialog(b.dataset.match); },
  async book(b) {
    try { await api('/api/bookings', 'POST', { match_id: b.dataset.match, offer_id: b.dataset.offer }); document.querySelectorAll('dialog').forEach(x => x.close()); toast('Créneau proposé, en attente de sa réponse'); await go('slots'); } catch (e) { toast(e.message); }
  },
  async accept(b) { await act(() => api(`/api/bookings/${b.dataset.id}/accept`, 'POST'), 'Créneau confirmé'); },
  async cancel(b) { if (confirm('Annuler ce créneau ?')) await act(() => api(`/api/bookings/${b.dataset.id}/cancel`, 'POST'), 'Créneau annulé'); },
  async checkin(b) { await act(() => api(`/api/bookings/${b.dataset.id}/checkin`, 'POST'), 'Check-in enregistré'); },
  async again(b) { await act(() => api(`/api/bookings/${b.dataset.id}/feedback`, 'POST', { again: b.dataset.v === '1' }), 'Merci pour ton retour'); },
  async share(b) {
    const bk = state.bookings.find(x => x.id === b.dataset.id);
    const text = `Je rencontre quelqu’un le ${fmtShort(bk.starts_at)} à ${fmtTime(bk.starts_at)} : ${bk.activity}, ${bk.venue}.`;
    if (navigator.share) { try { await navigator.share({ text }); } catch { /* cancelled */ } } else { await navigator.clipboard?.writeText(text); toast('Message copié, envoie-le à un ami'); }
  },
  async like(b) { await swipe(b.dataset.id, 'like'); },
  async pass(b) { await swipe(b.dataset.id, 'pass'); },
  async report(b) { const reason = prompt('Pourquoi signales-tu ce profil ?'); if (reason && reason.trim().length >= 5) { try { await api('/api/reports', 'POST', { target_id: b.dataset.id, reason: reason.trim() }); toast('Signalement transmis à la modération'); } catch (e) { toast(e.message); } } },
  async block(b) { if (confirm('Bloquer ce profil ?')) { try { await api('/api/blocks', 'POST', { target_id: b.dataset.id }); state.profiles = state.profiles.filter(p => p.id !== b.dataset.id); render(); } catch (e) { toast(e.message); } } },
  view(b) { const m = state.matches.find(x => x.id === b.dataset.match); const ph = (m.profile.photos || []).map(p => `<img src="${esc(p.url)}" alt="Photo de ${esc(m.profile.name)}" style="width:100%;border-radius:6px;margin-top:8px">`).join(''); dialog(profileCard(m.profile, '', true) + (ph ? `<h3 style="margin-top:16px">Photos privées</h3>${ph}` : '')); },
  palette(b) { const f = document.querySelector('[data-form="style"]'); f.ground.value = b.dataset.g; f.accent.value = b.dataset.a; document.querySelectorAll('.swatch').forEach(x => x.setAttribute('aria-pressed', x === b)); updateContrast(); },
  'block-move'(b) { const li = b.closest('li'), ol = li.parentElement, d = Number(b.dataset.d); const sib = d < 0 ? li.previousElementSibling : li.nextElementSibling; if (sib) d < 0 ? ol.insertBefore(li, sib) : ol.insertBefore(sib, li); },
  ink(b) { canvasCtx.color = b.dataset.c; document.querySelectorAll('[data-act="ink"]').forEach(x => x.setAttribute('aria-pressed', x === b)); },
  undo() { const p = canvasCtx.undo.pop(); if (p) canvasCtx.ctx.putImageData(p, 0, 0); },
  clear() { const { ctx, c } = canvasCtx; canvasCtx.undo.push(ctx.getImageData(0, 0, c.width, c.height)); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height); },
  async 'save-draw'() {
    canvasCtx.c.toBlob(async blob => { const f = new FormData(); f.append('drawing', blob, 'dessin.png'); try { await api('/api/me/drawing', 'POST', undefined, f); state.style = await api('/api/me/style'); toast('Dessin enregistré'); render(); } catch (e) { toast(e.message); } }, 'image/png');
  },
  async 'del-draw'() { await api('/api/me/drawing', 'DELETE'); state.style = await api('/api/me/style'); render(); },
  async interests() { await refresh(['interests']); interestsDialog(); },
  async 'photo-del'(b) { if (confirm('Supprimer cette photo ?')) { await api(`/api/me/photos/${b.dataset.id}`, 'DELETE'); state.user = await api('/api/me'); render(); } },
  async 'photo-move'(b) { const ids = state.user.photos.map(p => p.id), i = ids.indexOf(b.dataset.id), j = i + Number(b.dataset.d); if (j < 0 || j >= ids.length) return; [ids[i], ids[j]] = [ids[j], ids[i]]; await api('/api/me/photos/order', 'PATCH', { photo_ids: ids }); state.user = await api('/api/me'); render(); },
  async export() { const data = await api('/api/account/export'); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })); a.download = 'jeudi-mes-donnees.json'; a.click(); },
  async logout() { await api('/api/auth/logout', 'POST'); state.user = null; state.auth = { step: 'email' }; render(); },
  async delete() { if (confirm('Supprimer définitivement ton compte et toutes tes données ?')) { await api('/api/account', 'DELETE'); state.user = null; render(); } },
  'auth-back'() { state.auth = { step: 'email' }; render(); },
  async approve(b) { await modAct(() => api(`/api/admin/accounts/${b.dataset.id}`, 'PATCH', { approved: true })); },
  async 'photo-ok'(b) { await modAct(() => api(`/api/admin/photos/${b.dataset.id}`, 'PATCH', { status: 'approved' })); },
  async 'photo-no'(b) { await modAct(() => api(`/api/admin/photos/${b.dataset.id}`, 'PATCH', { status: 'rejected' })); },
  async 'report-ok'(b) { await modAct(() => api(`/api/admin/reports/${b.dataset.id}`, 'PATCH', { status: 'reviewed' })); },
  async 'drawing-del'(b) { await modAct(() => api(`/api/admin/drawings/${b.dataset.id}`, 'DELETE')); },
};
async function act(fn, msg) { try { await fn(); await refresh(['bookings', 'drop', 'matches']); toast(msg); render(); } catch (e) { toast(e.message); } }
async function modAct(fn) { try { await fn(); await refresh(['queue']); toast('Modération mise à jour'); render(); } catch (e) { toast(e.message); } }
async function swipe(id, action) {
  try {
    const r = await api('/api/swipes', 'POST', { target_id: id, action });
    const p = state.profiles.find(x => x.id === id);
    state.profiles = state.profiles.filter(x => x.id !== id);
    if (r.matched) { await refresh(['matches', 'drop']); const d = dialog(`<h2>Match avec ${esc(p.name)}</h2><p class="muted">${state.drop.open ? 'Le drop est ouvert : choisis un lieu et une heure.' : 'Les créneaux s’ouvrent jeudi à 18 h. Tu pourras proposer un lieu à ce moment.'}</p>${state.drop.open ? `<div class="row" style="margin-top:12px"><button class="btn primary" data-act="offers" data-match="${esc(r.match_id)}">Choisir un créneau</button></div>` : ''}`); d.dataset.kind = 'match'; }
    render();
  } catch (e) { toast(e.message); if (e.status === 404 || e.status === 409) { state.profiles = state.profiles.filter(x => x.id !== id); render(); } }
}

/* forms */
const forms = {
  async request(f) {
    const school = f.school.value, email = f.email.value.trim().toLowerCase();
    try { const r = await api('/api/auth/request-code', 'POST', { email, school }); state.auth = { step: 'code', email, school }; if (r.local_demo_code) toast('Code local : ' + r.local_demo_code); render(); } catch (e) { toast(e.message); }
  },
  async verify(f) {
    try {
      const r = await api('/api/auth/verify-code', 'POST', { email: state.auth.email, school: state.auth.school, code: f.code.value, name: f.name.value, birthday: f.birthday.value, gender: f.gender.value, city: 'Lyon', adult_consent: f.consent.checked });
      state.user = r.user; state.style = await api('/api/me/style'); await go(state.style.configured ? 'home' : 'profile');
      if (!state.style.configured) toast('Dernière étape : ton intention et ton style');
    } catch (e) { toast(e.message); }
  },
  async identity(f) {
    try { state.user = await api('/api/me', 'PATCH', { name: f.name.value, city: f.city.value, gender: f.gender.value, bio: f.bio.value, visible: f.visible.checked }); toast('Profil enregistré'); render(); } catch (e) { toast(e.message); }
  },
  async style(f) {
    const intents = [...f.querySelectorAll('[name=intents]:checked')].map(x => x.value);
    if (!intents.length) { toast('Choisis au moins une intention'); return; }
    const highlights = [...f.querySelectorAll('[name=hi]:checked')].map(x => x.value);
    if (highlights.length > 3) { toast('Trois intérêts phares au maximum'); return; }
    const blocks = [...document.querySelectorAll('#blocks li')].map(li => li.dataset.block);
    try { state.style = await api('/api/me/style', 'PUT', { intents, promo: f.promo.value, accent: f.accent.value, ground: f.ground.value, font: f.font.value, emoji: f.emoji.value, status: f.status.value, hook: f.hook.value, highlights, blocks }); toast('Style enregistré'); render(); } catch (e) { toast(e.message); }
  },
  async photo(f) { const fd = new FormData(); fd.append('photo', f.photo.files[0]); try { await api('/api/me/photos', 'POST', undefined, fd); state.user = await api('/api/me'); toast('Photo ajoutée, en attente de validation'); render(); } catch (e) { toast(e.message); } },
  async prefs(f) {
    try { const r = await api('/api/me/preferences', 'PUT', { schools: [...f.querySelectorAll('[name=schools]:checked')].map(x => x.value), genders: [...f.querySelectorAll('[name=genders]:checked')].map(x => x.value), age_min: Number(f.age_min.value), age_max: Number(f.age_max.value), city: state.user.preferences.city || 'Toutes' }); state.user.preferences = r.preferences; toast('Filtres enregistrés'); } catch (e) { toast(e.message); }
  },
  async validate(f) { await act(() => api(`/api/bookings/${f.dataset.id}/validate`, 'POST', { code: f.code.value }), 'Venue validée'); },
};
document.addEventListener('submit', e => { const f = e.target.closest('[data-form]'); if (f && forms[f.dataset.form]) { e.preventDefault(); forms[f.dataset.form](f); } });
document.addEventListener('input', e => { if (e.target.closest('[data-form="style"]') && e.target.type === 'color') updateContrast(); });
document.addEventListener('click', e => {
  const nav = e.target.closest('[data-nav]'); if (nav) { document.querySelectorAll('dialog').forEach(d => d.close()); go(nav.dataset.nav); return; }
  const tab = e.target.closest('[data-tab]'); if (tab) { state.tab = tab.dataset.tab; render(); return; }
  const a = e.target.closest('[data-act]'); if (a && acts[a.dataset.act]) { Promise.resolve(acts[a.dataset.act](a)).catch(err => toast(err.message)); }
});
window.addEventListener('hashchange', () => { const s = location.hash.replace('#/', ''); if (state.user && s && s !== state.screen && needs[s]) go(s); });
setInterval(() => document.querySelectorAll('[data-count]').forEach(el => { el.textContent = until(el.dataset.count); }), 30000);

(async function start() {
  await loadSession();
  if (state.user) { const s = location.hash.replace('#/', ''); await go(needs[s] ? s : (state.style?.configured ? 'home' : 'profile')); } else render();
  if ('serviceWorker' in navigator) { /* no offline cache: private data must not be stored */ }
})();
