/** Smoke test without a browser or third-party dependencies: node tests/smoke.cjs */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert');
const path = require('node:path');
const root = path.join(__dirname, '..');
let html = '', stored = {};
const app = {get innerHTML(){return html},set innerHTML(value){html=value},addEventListener(){}};
const toast = {textContent:'',classList:{add(){},remove(){}}};
const sandbox = {
  document:{documentElement:{style:{setProperty(){},removeProperty(){}},dataset:{}},querySelector(){return null},getElementById(id){return id==='app'?app:id==='toast'?toast:null}},
  localStorage:{setItem(k,v){stored[k]=v},getItem(k){return stored[k]||null},removeItem(k){delete stored[k]}},
  window:{scrollTo(){},addEventListener(){},scrollY:0,matchMedia(){return {matches:false,addEventListener(){}}}},navigator:{},location:{protocol:'file:'},
  fetch:async()=>{throw new Error('offline')},console,Intl,Date,setTimeout,clearTimeout,Blob,URL
};
const catalog = fs.readFileSync(path.join(root,'catalog.js'),'utf-8').replace(/\bexport /g,'');
const source = fs.readFileSync(path.join(root,'app.js'),'utf-8').replace(/^import[^\n]+\n/,'');
vm.createContext(sandbox);
vm.runInContext(catalog+'\n'+source,sandbox);
assert(html.includes('Explorer le prototype'));
vm.runInContext('handleAction("demo",{dataset:{}})',sandbox);
assert(html.includes('Tableau de bord') || html.includes('Votre campus') || html.includes('Vos connexions')); vm.runInContext('go("discover")',sandbox); assert(html.includes('v5-deck-photo'));
vm.runInContext('handleAction("like",{dataset:{}})',sandbox);
for(const [screen,needle] of [
  ['likes','Qui vous a liké'],['details','Ce que je recherche'],['filters','Rennes'],
  ['interests','40 catégories'],['settings','Exporter mes données'],
  ['messages','Messages'],['profile','Informations personnelles']
]) {vm.runInContext(`go(${JSON.stringify(screen)})`,sandbox);assert(html.includes(needle),screen+' missing '+needle);}
vm.runInContext('state.details={intentions:["Nouvelles amitiés"]};store();go("profile")',sandbox);
assert(html.includes('Nouvelles amitiés'));
// V3 appearance, favorites and moments are part of the UI and must not crash.
vm.runInContext('go("appearance")',sandbox);
assert(html.includes('Studio d’apparence'));
assert(html.includes('Sakura'));
vm.runInContext('setLook("palette","sakura")',sandbox);
assert(stored['campus-connect-look-v4'].includes('sakura'));
vm.runInContext('setLook("mode","dark")',sandbox);
assert(sandbox.document.documentElement.dataset.lookMode==='dark');
vm.runInContext('go("bookmarks")',sandbox);
assert(html.includes('favoris')||html.includes('Favoris'));
vm.runInContext('go("moments")',sandbox);
assert(html.includes('Moments du campus'));
console.log('PASS · UI V3: accueil, swipe, filtres, profil, studio couleurs, mode sombre, favoris, moments.');
