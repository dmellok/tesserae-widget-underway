/* Underway: the shared page for the four widgets. Each widget's client.js imports this and
   names its page. The server hands over the vessels with their pictures as data URIs, so
   nothing is fetched here; the page is markup and CSS alone. */

import { buildSheet } from './sheet.js';

const PAPER = { cream: '#f3ead6', white: '#ffffff', aged: '#e9dcc0', blueprint: '#1d3f73', sea: 'linear-gradient(180deg,#e4ecef 0%,#f0efe8 60%,#dfe7e4 100%)' };
const INK = { cream: '#2a2116', white: '#111111', aged: '#2a2116', blueprint: '#eaf0f8', sea: '#1f3038' };
/* Silhouettes seen from above, bow up, in a 200 by 200 box. */
const SIL = {
  cargo: 'M100 8 C112 20 118 40 118 70 L118 176 C118 186 112 192 100 192 C88 192 82 186 82 176 L82 70 C82 40 88 20 100 8 Z M86 150 h28 v22 h-28 Z M88 72 h24 v6 h-24 Z M88 92 h24 v6 h-24 Z M88 112 h24 v6 h-24 Z M88 132 h24 v6 h-24 Z',
  tanker: 'M100 6 C114 20 120 42 120 72 L120 178 C120 188 112 194 100 194 C88 194 80 188 80 178 L80 72 C80 42 86 20 100 6 Z M96 30 h8 v120 h-8 Z M86 156 h28 v24 h-28 Z M84 60 h32 v4 h-32 Z M84 100 h32 v4 h-32 Z',
  passenger: 'M100 10 C114 24 122 46 122 76 L122 174 C122 186 112 192 100 192 C88 192 78 186 78 174 L78 76 C78 46 86 24 100 10 Z M86 44 h28 v120 h-28 Z M92 60 h16 v8 h-16 Z M92 96 h16 v8 h-16 Z M92 130 h16 v8 h-16 Z',
  tug: 'M100 34 C118 48 126 70 126 96 L126 150 C126 166 114 172 100 172 C86 172 74 166 74 150 L74 96 C74 70 82 48 100 34 Z M86 90 h28 v34 h-28 Z M94 60 h12 v12 h-12 Z',
  fishing: 'M100 24 C114 40 120 62 120 90 L120 160 C120 172 110 178 100 178 C90 178 80 172 80 160 L80 90 C80 62 86 40 100 24 Z M90 120 h20 v30 h-20 Z M97 40 h6 v70 h-6 Z M70 70 h60 v4 h-60 Z',
  sail: 'M100 12 C110 36 116 66 116 100 L116 160 C116 176 108 184 100 184 C92 184 84 176 84 160 L84 100 C84 66 90 36 100 12 Z M97 40 h6 v110 h-6 Z M100 50 L100 120 L128 120 Z M100 60 L100 118 L76 118 Z',
  pleasure: 'M100 20 C110 36 116 60 116 96 L116 156 C116 170 108 176 100 176 C92 176 84 170 84 156 L84 96 C84 60 90 36 100 20 Z M90 96 h20 v40 h-20 Z M93 70 h14 v14 h-14 Z',
  service: 'M100 24 C114 40 120 62 120 92 L120 158 C120 172 110 178 100 178 C90 178 80 172 80 158 L80 92 C80 62 86 40 100 24 Z M88 80 h24 v40 h-24 Z M94 60 h12 v8 h-12 Z M92 140 h16 v8 h-16 Z',
  naval: 'M100 6 C110 22 116 46 116 78 L116 176 C116 188 108 194 100 194 C92 194 84 188 84 176 L84 78 C84 46 90 22 100 6 Z M92 60 h16 v60 h-16 Z M96 36 h8 v12 h-8 Z M97 130 h6 v40 h-6 Z',
  other: 'M100 16 C112 30 118 52 118 84 L118 168 C118 182 110 188 100 188 C90 188 82 182 82 168 L82 84 C82 52 88 30 100 16 Z M90 100 h20 v40 h-20 Z',
  visitor: 'M60 120 C70 90 130 90 140 120 C150 150 110 160 100 140 C90 160 50 150 60 120 Z M40 150 C50 130 70 140 60 170 Z M160 150 C150 130 130 140 140 170 Z M86 112 a5 5 0 1 0 0.1 0 Z M114 112 a5 5 0 1 0 0.1 0 Z',
};
/* The colours of the modern looks, by the vessel's trade: paper-safe, dark enough for white ink. */
const TRADE = {
  cargo: { p: '#1f4e79', s: '#c8552b', t: '#e6edf4', sh: '#122d47', th: '#7a9bb8' },
  tanker: { p: '#7a1f1f', s: '#2b2b2b', t: '#f2e6e3', sh: '#4a1212', th: '#b86a5a' },
  passenger: { p: '#0f3d5e', s: '#d9a441', t: '#e5eef3', sh: '#0a2538', th: '#5f8fae' },
  tug: { p: '#8a3b12', s: '#1d1d1d', t: '#f3e9e1', sh: '#4f2109', th: '#c9865a' },
  fishing: { p: '#2f5d3a', s: '#b9893b', t: '#e6efe8', sh: '#1b3822', th: '#7aa485' },
  sail: { p: '#24343f', s: '#a8432e', t: '#e8ecee', sh: '#131d24', th: '#7d8f9a' },
  pleasure: { p: '#1b5e6b', s: '#e0b14b', t: '#e2eef0', sh: '#0f3a42', th: '#6ea6b0' },
  service: { p: '#b35a12', s: '#1c2a33', t: '#f5ece2', sh: '#6b350a', th: '#dc9a5e' },
  naval: { p: '#3b4652', s: '#8e9aa6', t: '#e9ebed', sh: '#222a32', th: '#6f7b87' },
  other: { p: '#24333b', s: '#55666f', t: '#e9ecee', sh: '#101a1f', th: '#8a9aa3' },
};

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

async function predecode(src) {
  if (!src || typeof Image === 'undefined') return;
  try { const img = new Image(); img.src = src; await Promise.race([img.decode(), new Promise((r) => setTimeout(r, 6000))]); } catch { /* shown as it is */ }
}

function sil(cls) {
  return `<svg class="uw-sil" viewBox="0 0 200 200" fill="currentColor" aria-hidden="true"><path d="${SIL[cls] || SIL.other}"/></svg>`;
}

function flag(a, cls = '') {
  return a.flag ? `<span class="uw-flag ${cls}">${esc(a.flag)}</span>` : '';
}

function head(d, where = 'top') {
  if (d.header === 'hidden' || (d.header === 'bottom') !== (where === 'bottom')) return '';
  const bits = [d.title, d.area, d.period].filter(Boolean).map(esc).join(' · ');
  const line = `<div class="ph"><span class="ph-k">${bits}</span><b class="ph-d">${esc(d.time)} · ${esc(d.date)}</b></div>`;
  return where === 'bottom' ? `<div class="ph-rule"></div>${line}` : `${line}<div class="ph-rule"></div>`;
}

function foot(d, extra = []) {
  const mode = d.footer || 'show';
  if (mode === 'hide') return '';
  const bits = [...(mode === 'credits' ? [] : [...(d.notices || []), ...(d.status || []), ...extra]), ...(d.credits || []), d.attribution].filter(Boolean);
  return bits.length ? `<div class="credit">${bits.map(esc).join(' · ')}</div>` : '';
}

function message(d, title, body, hint) {
  return `${head(d)}<div class="msg"><div class="msg-t">${esc(title)}</div><div class="msg-b">${esc(body)}</div>${hint ? `<div class="msg-h">${esc(hint)}</div>` : ''}</div>${foot(d)}`;
}

function lines(a) {
  return (a.lines || []).map((t, i) => `<span class="ln${i === 0 ? ' ln-first' : ''}">${esc(t)}</span>`).join('');
}

const SIL_URL = (cls) => 'data:image/svg+xml;utf8,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="400" height="400" fill="#7a7a7a"><path d="${SIL[cls] || SIL.other}"/></svg>`);

const IMPRESSION = 'an impression from her particulars, not from a photograph';

function impression(a, cls = 'uw-imp') {
  return a.pic && a.pic.src && a.pic.impression ? `<span class="${cls}" title="${IMPRESSION}">impression</span>` : '';
}

function picture(a, cls = '') {
  if (a.pic && a.pic.src) return `<img class="uw-pic ${cls}${a.pic.whole ? ' whole' : ' cut'}" src="${a.pic.src}" alt="${esc(a.typ)}" decoding="sync">`;
  return `<span class="uw-pic uw-nopic ${cls}">${sil(a.cls)}</span>`;
}

function sub(a) {
  return `${esc(a.typ)}${a.flag ? ` <span>· ${esc(a.flag)}</span>` : ''}`;
}

/* The full-bleed photograph: the nearest vessel fills the page, the rest along a strip. */
function photoPage(d) {
  const hero = d.vessels[0];
  const rest = d.vessels.slice(1);
  const bg = hero.pic && hero.pic.src ? `<div class="fb-bg" style="background-image:url('${hero.pic.src}');background-size:${d.photo_fit || 'cover'}"></div>` : `<div class="fb-bg fb-none">${sil(hero.cls)}</div>`;
  const strip = rest.length ? `<ul class="fb-strip">${rest.map((a) => `<li>${a.pic && a.pic.src ? `<span class="fb-th" style="background-image:url('${a.pic.src}')"></span>` : `<span class="fb-th fb-th-none">${sil(a.cls)}</span>`}<span class="fb-th-t"><b>${esc(a.shown_name)}</b><span>${esc(a.typ)}</span><span>${esc(a.speed_text)} · ${esc(a.where)}</span></span></li>`).join('')}</ul>` : '';
  const top = d.header === 'hidden' ? '' : `<div class="fb-top"><span>${esc(d.title)} · ${esc(d.area)}</span><span>${esc(d.time)} · ${esc(d.date)}</span></div>`;
  return `${bg}<div class="fb-shade"></div>${top}<div class="fb-main">${flag(hero, 'fb-flag')}<div class="fb-cs">${esc(hero.shown_name)}</div><div class="fb-typ">${sub(hero)}</div><div class="fb-r">${lines(hero).replace(/<\/span><span/g, '</span> · <span')}</div></div>${strip}${foot(d).replace('class="credit"', 'class="credit fb-credit"')}`;
}

/* The modern looks for one vessel: boarding pass, tiles, poster and split, in the trade's colours. */
const DIRS = { N: 'north', NE: 'north-east', E: 'east', SE: 'south-east', S: 'south', SW: 'south-west', W: 'west', NW: 'north-west' };

function palette(d, a) {
  if (d.colours === 'type' && TRADE[a.cls]) return { ...TRADE[a.cls], ink: '#fff', ink2: '#fff' };
  return { ...TRADE.other, ink: '#fff', ink2: '#fff' };
}

function statRows(a) {
  const c = a.cog >= 0 ? a.cog : a.hdg;
  return [
    ['Speed', a.sog >= 0.5 ? `${a.sog} kt` : a.speed_text, a.sog >= 0.5 ? 'over the ground' : ''],
    ['Course', c >= 0 && a.moving ? `${String(c).padStart(3, '0')}°` : '', a.status],
    ['Distance', `${a.km} km`, `to the ${DIRS[a.compass] || a.compass || ''}`],
    ['Length', a.len ? `${a.len} m` : '', a.beam ? `${a.beam} m beam` : ''],
  ].filter((r) => r[1]);
}

function stat([label, value, sub2], cls = '') {
  return `<div class="md-st ${cls}"><small>${esc(label)}</small><b>${esc(value)}</b>${sub2 ? `<em>${esc(sub2)}</em>` : ''}</div>`;
}

function routeBlock(a) {
  if (a.dest) return `<div class="md-rt"><b><small>bound for</small>${esc(a.dest)}</b>${a.eta ? `<i></i><b><small>ETA</small>${esc(a.eta)}</b>` : ''}</div>`;
  return `<div class="md-rt md-rt-text"><b>${esc(a.dest_text)}</b></div>`;
}

function modPic(a, cls = '') {
  if (!a.pic || !a.pic.src) return `<div class="md-pic md-none ${cls}">${sil(a.cls)}</div>`;
  return `<div class="md-pic ${cls}${a.pic.whole ? ' whole' : ' cut'}" style="background-image:url('${a.pic.src}')"></div>`;
}

function modernPage(d) {
  const a = d.vessels[0];
  const c = palette(d, a);
  const portrait = (d.cell_h || 1) > (d.cell_w || 1);
  const vars = `--p:${c.p};--s:${c.s};--t:${c.t};--sh:${c.sh};--th:${c.th};--pink:${c.ink};--sink:${c.ink2}`;
  const top = d.header === 'hidden' ? '' : `${esc(d.title)} · ${esc(d.time)}`;
  const when = `${esc(d.time)} · ${esc(d.date)}`;
  const credit = `${esc(a.typ)}${a.flag ? ` · ${esc(a.flag)}` : ''}${a.pic && a.pic.impression ? ' · an impression' : ''}${a.pic && a.pic.credit && d.footer !== 'hide' ? ` · ${esc(a.pic.credit)}` : ''}`;
  const typ = `${esc(a.typ)}${a.flag ? ` · <span class="nb">${esc(a.flag)}</span>` : ''}${a.imo ? ` · IMO ${esc(a.imo)}` : ''}`;
  const st = statRows(a);
  const contact = d.visitor && d.visitor.pic ? `<figure class="vis md-vis"><img src="${d.visitor.pic.src}" alt="" decoding="sync"><figcaption>${esc(d.visitor.typ)} · ${esc(d.visitor.lines[1])}</figcaption></figure>` : '';
  const notes = d.footer === 'hide' ? [] : [...(d.notices || []), ...(d.status || [])];
  const note = notes.length ? `<div class="md-note">${notes.map(esc).join(' · ')}</div>` : '';
  let body;
  if (d.look === 'pass') {
    body = `<div class="md-ph">${modPic(a)}${top ? `<div class="md-top">${top}</div>` : ''}<div class="md-cap">${credit}</div>${contact}</div>
      <div class="md-side">${flag(a)}<div class="md-cs">${esc(a.shown_name)}</div><div class="md-typ">${esc(a.typ)}</div>${routeBlock(a)}<div class="md-chips">${st.map((r, i) => stat(r, i === 0 ? 'on-s' : 'on-t')).join('')}</div></div>`;
  } else if (d.look === 'tiles') {
    const tone = ['on-p', 'on-s', 'on-th', 'on-sh'];
    body = `<div class="md-bar">${flag(a)}<div class="md-bar-t"><div class="md-cs">${esc(a.shown_name)}</div><div class="md-typ">${typ}</div></div><div class="md-when">${top ? `${esc(d.title)}<br>` : ''}${when}</div></div>
      <div class="md-grid">${modPic(a, 'md-card')}<div class="md-tiles">${routeBlock(a)}${st.map((r, i) => stat(r, tone[i])).join('')}</div>${contact}</div>${note}`;
  } else if (d.look === 'poster') {
    body = `${modPic(a, 'md-bg')}<div class="md-shade"></div><div class="md-top md-top-row"><span>${top || when}</span>${flag(a)}</div>${contact}
      <div class="md-main"><div class="md-cs">${esc(a.shown_name)}</div><div class="md-typ">${typ}</div><div class="md-row">${routeBlock(a)}<div class="md-stats">${st.slice(0, 3).map((r) => stat(r, 'glass')).join('')}</div></div></div>${note}`;
  } else {
    body = `<div class="md-frame-wrap">${modPic(a, 'md-frame')}<span class="md-pill">${esc(a.status)}</span>${contact}</div>
      <div class="md-r"><div class="md-hd"><span>${top || when}</span>${flag(a)}</div><div class="md-cs">${esc(a.shown_name)}</div><div class="md-typ">${typ}</div>${routeBlock(a)}<div class="md-stats4">${st.map((r, i) => stat(r, i === 0 ? 'on-s' : i === 1 ? 'on-th' : 'dim')).join('')}</div>${note}</div>`;
  }
  return `<div class="md md-${esc(d.look)}${portrait ? ' portrait' : ''}" style="${vars}">${body}</div>`;
}

/* The plate: one vessel, large, in a ruled frame, with her particulars beside her. */
function platePage(d) {
  const a = d.vessels[0];
  const rows = [
    ['Bound', a.dest_text],
    ['Speed', a.sog >= 0.5 ? `${a.sog} kt, ${a.status}` : a.status],
    ['Where', `${a.where}${a.course_text ? `, ${a.course_text}` : ''}`],
    ['Size', a.length_text],
    ['Flag', a.flag],
  ].filter((r) => r[1]);
  const portrait = (d.cell_h || 1) > (d.cell_w || 1);
  const contact = d.visitor && d.visitor.pic ? `<figure class="vis"><img src="${d.visitor.pic.src}" alt="" decoding="sync"><figcaption>${esc(d.visitor.typ)} · ${esc(d.visitor.lines[1])}</figcaption></figure>` : '';
  return `${head(d)}<div class="pl${portrait ? ' portrait' : ''}"><div class="pl-plate"><div class="pl-frame"><i class="tl"></i><i class="tr"></i><i class="bl"></i><i class="br"></i></div>${contact}${picture(a, 'pl-pic')}${impression(a, 'uw-imp pl-imp')}<div class="pl-fig">Fig. 1. ${esc(a.shown_name)}, ${esc(a.typ)}${a.pic && a.pic.impression ? ', an impression' : ''}${a.pic && a.pic.credit ? `, ${esc(a.pic.credit)}` : ''}</div></div><div class="pl-note"><div class="pl-cs">${esc(a.shown_name)}</div><div class="pl-typ">${esc(a.typ)}${a.imo ? ` <i>· IMO ${esc(a.imo)}</i>` : ''}</div><dl>${rows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join('')}</dl><p class="pl-about">${esc(a.about)}</p></div></div>${head(d, 'bottom')}${foot(d)}`;
}

/* The fleet: every vessel painted and cut out, sized by her length, packed; or, with
   photographs, a log of cards. */
function fleetPage(d) {
  const n = d.vessels.length;
  const cols = n <= 2 ? n : n <= 4 ? 2 : n <= 6 ? 3 : 4;
  return `${head(d)}<div class="lg-grid" style="--cols:${cols}">${d.vessels.map((a) => `<article class="lg-card">${a.pic && a.pic.src ? `<div class="lg-pic${a.pic.whole ? '' : ' lg-cut'}" style="background-image:url('${a.pic.src}')"></div>` : `<div class="lg-pic lg-none">${sil(a.cls)}</div>`}<div class="lg-row"><b>${esc(a.shown_name)}${impression(a, 'uw-imp lg-imp')}</b>${(d.labels || []).includes('flag') ? '' : flag(a, 'lg-flag')}</div><div class="lg-lines">${lines(a)}</div></article>`).join('')}</div>${head(d, 'bottom')}${foot(d)}`;
}

/* ---- building the sheet without holding the page ----
   The packer runs in one module worker (OffscreenCanvas) so the page, and an editor showing it,
   stay responsive while the sheet is built; the page builds the sheet itself where workers are
   missing or one fails. A sheet is kept by a key of everything that decides it, so a page drawn
   again from the same data (an editor's refresh while pictures are on the way) is not packed
   again. */
const WORKER_PATH = './sheet.js';
let WORKER = null;
let CHAIN = Promise.resolve();
function packOffThread(args) {
  if (typeof Worker === 'undefined' || typeof OffscreenCanvas === 'undefined') return buildSheet(args);
  const run = () => new Promise((resolve) => {
    try { if (!WORKER) WORKER = new Worker(new URL(WORKER_PATH, import.meta.url), { type: 'module' }); } catch { resolve(buildSheet(args)); return; }
    const w = WORKER;
    let done = false;
    const finish = (sheet) => { if (done) return; done = true; clearTimeout(timer); w.onmessage = null; w.onerror = null; resolve(sheet); };
    const drop = () => { if (WORKER === w) WORKER = null; try { w.terminate(); } catch { /* gone */ } };
    const timer = setTimeout(() => { drop(); finish(buildSheet(args)); }, 60000);
    w.onmessage = (e) => { if (e.data && e.data.kind === 'cut') return; finish(e.data && e.data.ok ? e.data.sheet : buildSheet(args)); };
    w.onerror = () => { drop(); finish(buildSheet(args)); };
    w.postMessage(args);
  });
  CHAIN = CHAIN.then(run, run);
  return CHAIN;
}
const fnv = (s) => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0).toString(36); };
function keyOf(a) {
  const parts = a.specimens.map((x) => `${x.name}|${x.sci}|${x.src ? x.src.length : 0}|${x.whole ? 1 : 0}|${x.factor}|${x.aspect}|${(x.lines || []).join('/')}`);
  return `sh1:${a.ratio.toFixed(4)}:${a.size}:${a.label.toFixed(4)}:${a.paper}:${a.packer || ''}:${a.zoom}:${a.budget}:${fnv(parts.join(';'))}`;
}
const SHEETS = new Map();
const SHEETS_MAX = 8;

/* A silhouette as a PNG, drawn once per kind: a worker cannot decode the SVG itself. */
const SIL_PNG = new Map();
async function silPng(cls) {
  const k = SIL[cls] ? cls : 'other';
  if (SIL_PNG.has(k)) return SIL_PNG.get(k);
  let out = SIL_URL(k);
  try {
    const img = new Image();
    img.src = SIL_URL(k);
    await img.decode();
    const cv = document.createElement('canvas');
    cv.width = 400; cv.height = 400;
    cv.getContext('2d').drawImage(img, 0, 0, 400, 400);
    out = cv.toDataURL('image/png');
  } catch { /* the SVG as it is */ }
  SIL_PNG.set(k, out);
  return out;
}

async function packFleet(d) {
  const w = d.cell_w || 800, h = d.cell_h || 480;
  const specimens = await Promise.all(d.vessels.map(async (a) => {
    const pic = a.pic || {};
    const src = pic.src || await silPng(a.cls);
    const whole = !!pic.src && !!pic.whole;
    return {
      name: a.shown_name, sci: a.mmsi || a.shown_name, src, cut: whole ? null : src, on_paper: false, classic: false, whole, neutral: false, no_flip: true,
      factor: Math.pow(Math.max(8, a.len || 40) / 120, 0.4), aspect: pic.aspect > 0 ? pic.aspect : 3, paper: null,
      lines: [a.shown_name + (pic.impression ? ' (impression)' : ''), ...(a.lines || [])],
    };
  }));
  const label = Math.max(0.017, 13 / h) * ((Number(d.text_size) || 100) / 100);
  const zoom = Math.max(0.4, Math.min(1, (Number(d.scale) || 100) / 100));
  // while pictures are still on the way the page is drawn again soon: a quicker arrangement
  const budget = Number(d.live_refresh_s) > 0 ? 1500 : 4000;
  const args = { specimens, ratio: w / h, size: 1400, label, paper: d.paper === 'white' ? 'white' : d.paper === 'aged' ? 'aged' : 'cream', ink: INK[d.paper] || INK.cream, layout: 'cluster', facing: 'inward', zoom , budget };
  const key = keyOf(args);
  if (SHEETS.has(key)) return SHEETS.get(key);
  try {
    const made = await packOffThread(args);
    if (made && made.src) {
      SHEETS.set(key, made);
      while (SHEETS.size > SHEETS_MAX) SHEETS.delete(SHEETS.keys().next().value);
    }
    return made;
  } catch (e) { console.warn('underway: packing failed', e); return null; }
}

function packedPage(d, made) {
  const tags = made.items.map((m) => {
    const ls = m.lines || [];
    if (!ls.length) return '';
    return `<span class="sh-l" style="left:${(m.at[0] * 100).toFixed(2)}%;top:${(m.at[1] * 100).toFixed(2)}%"><span class="sh-ln sh-name">${esc(ls[0])}</span>${ls.slice(1).map((t) => `<span class="sh-ln sh-sm">${esc(t)}</span>`).join('')}</span>`;
  }).join('');
  const page = `<div class="sh-page" style="--r:${made.ratio};--lf:${made.label}"><img src="${made.src}" alt="" decoding="sync">${tags}</div>`;
  return `${head(d)}<div class="sh">${page}</div>${head(d, 'bottom')}${foot(d)}`;
}

/* The scene: one whole painting across the page, the particulars set over it. */
function scenePage(d) {
  const a = d.vessels[0];
  const art = a.pic && a.pic.src ? `<div class="sc-bg" style="background-image:url('${a.pic.src}');background-size:${a.pic.whole ? 'cover' : 'contain'}"></div>` : `<div class="sc-bg sc-none">${sil(a.cls)}</div>`;
  const top = d.header === 'hidden' ? '' : `<div class="sc-top"><span>${esc(d.title)} · ${esc(d.area)}</span><span>${esc(d.time)} · ${esc(d.date)}</span></div>`;
  const contact = d.visitor && d.visitor.pic ? `<figure class="vis sc-vis"><img src="${d.visitor.pic.src}" alt="" decoding="sync"><figcaption>${esc(d.visitor.typ)} · ${esc(d.visitor.lines[1])}</figcaption></figure>` : '';
  return `${art}${contact}${top}<div class="sc-main">${flag(a, 'sc-flag')}<div class="sc-cs">${esc(a.shown_name)}</div><div class="sc-typ">${sub(a)}${a.pic && a.pic.impression ? ' <span>· an impression</span>' : ''}</div><div class="sc-r">${lines(a).replace(/<\/span><span/g, '</span> · <span')}</div></div>${foot(d).replace('class="credit"', 'class="credit sc-credit"')}`;
}

export async function render(shadow, ctx, widget) {
  const d = ctx.data || {};
  const size = ctx.cell?.size || 'md';
  d.cell_w = ctx.cell?.w; d.cell_h = ctx.cell?.h;
  let body;
  if (!d.widget && !d.error) body = `<div class="msg"><div class="msg-t">Underway</div><div class="msg-b">No data from the server yet.</div></div>`;
  else if (d.state === 'error' || d.error) body = message(d, d.title || 'Underway', d.error || 'Something went wrong.', d.hint);
  else if (d.state === 'empty') body = message(d, d.title || 'Underway', 'Nothing on the water within reach.', d.hint);
  else if (d.state === 'listening') body = message(d, d.title || 'Underway', 'Listening for the first vessels.', d.hint);
  else if (d.state === 'painting') body = message(d, d.title || 'Underway', 'Nothing painted yet.', d.hint);
  else {
    for (const a of d.vessels) if (a.pic && a.pic.src) await predecode(a.pic.src);
    if (widget === 'fleet' && d.pictures === 'paintings' && typeof document !== 'undefined') {
      const made = await packFleet(d);
      if (made && made.src) { await predecode(made.src); body = packedPage(d, made); }
      else body = fleetPage(d);
    } else body = widget === 'photo' ? photoPage(d) : widget === 'plate' ? (['pass', 'tiles', 'poster', 'split'].includes(d.look) ? modernPage(d) : platePage(d)) : widget === 'scene' ? scenePage(d) : fleetPage(d);
  }
  const paper = PAPER[d.paper] || PAPER.cream;
  const ink = INK[d.paper] || INK.cream;
  const fonts = {
    fell: "--serif: 'IM Fell English', Georgia, serif; --sc: 'IM Fell English SC', Georgia, serif; --sans: 'Archivo Narrow', Arial, sans-serif;",
    archivo: "--serif: 'Archivo Narrow', Arial, sans-serif; --sc: 'Archivo Narrow', Arial, sans-serif; --sans: 'Archivo Narrow', Arial, sans-serif;",
    georgia: "--serif: Georgia, 'Times New Roman', serif; --sc: Georgia, 'Times New Roman', serif; --sans: Georgia, 'Times New Roman', serif;",
    page: "--serif: inherit; --sc: inherit; --sans: inherit;",
  }[d.font] || '';
  const dark = widget === 'photo' && d.state === 'ok';
  shadow.innerHTML = `
    <style>${d.font_css || ''}</style>
    <div class="uw ${esc(widget)} font-${esc(d.font || 'fell')} paper-${esc(d.paper || 'cream')} size-${esc(size)} lv-${esc(d.panel || 'colour')}${dark ? ' dark' : ''}" style="--paper:${paper};--ink:${ink};--ts:${(Number(d.text_size) || 100) / 100};${fonts}">${body}</div>
    <style>
      :host { display: block; height: 100%; }
      .uw { container-type: size; height: 100%; width: 100%; overflow: hidden; position: relative; display: flex; flex-direction: column; background: var(--paper); color: var(--ink);
        font-family: var(--serif); font-variant-numeric: tabular-nums; }
      .uw.font-page { font-family: inherit; }
      .uw.font-archivo .ph-k, .uw.font-archivo .pl-cs, .uw.font-archivo .pl-note dt, .uw.font-archivo .sh-name, .uw.font-archivo .uw-flag, .uw.font-georgia .ph-k, .uw.font-page .ph-k { text-transform: uppercase; letter-spacing: .1em; }
      .vis { position: absolute; right: 7%; top: 9%; width: 13%; margin: 0; display: flex; flex-direction: column; align-items: center; gap: .3cqmin; z-index: 1; }
      .vis img { width: 100%; mix-blend-mode: multiply; } .sc-vis img { mix-blend-mode: normal; }
      .vis figcaption { font-family: var(--sc); font-size: calc(var(--ts) * 1.7cqmin); letter-spacing: .08em; text-align: center; white-space: nowrap; }
      .sc-vis { right: 6%; top: 12%; width: 11%; } .sc-vis figcaption { font-family: var(--sans); text-transform: uppercase; color: #fff; text-shadow: 0 1px 3px rgba(0,0,0,.7); }
      .sh { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; padding: 0 .6cqmin; }
      .sh-page { position: relative; aspect-ratio: var(--r); max-width: 100%; max-height: 100%; width: min(100%, calc((100cqh - 9cqmin) * var(--r))); container-type: size; }
      .sh-page > img { display: block; width: 100%; height: 100%; }
      .sh-l { position: absolute; transform: translate(-50%, 12%); white-space: nowrap; text-align: center; line-height: 1.15; font-family: var(--sc); font-size: calc(var(--lf) * 100cqh); letter-spacing: .04em; color: var(--ink); }
      .sh-ln { display: block; }
      .sh-sm { font-family: var(--serif); font-style: italic; letter-spacing: 0; font-size: .88em; opacity: .85; }
      .sh-l, .pl-fig { --halo: var(--paper); text-shadow: .06em 0 0 var(--halo), -.06em 0 0 var(--halo), 0 .06em 0 var(--halo), 0 -.06em 0 var(--halo), .045em .045em 0 var(--halo), -.045em .045em 0 var(--halo), .045em -.045em 0 var(--halo), -.045em -.045em 0 var(--halo), .09em 0 0 var(--halo), -.09em 0 0 var(--halo); }
      .sc-main, .sc-top, .sc-credit { --halo: rgba(255,255,255,.92); text-shadow: .06em 0 0 var(--halo), -.06em 0 0 var(--halo), 0 .06em 0 var(--halo), 0 -.06em 0 var(--halo), .045em .045em 0 var(--halo), -.045em .045em 0 var(--halo), .045em -.045em 0 var(--halo), -.045em -.045em 0 var(--halo); }
      .uw.paper-blueprint .sh-l { --halo: #1d3f73; }
      .lv-mono .sh-l { -webkit-text-stroke: .3px currentColor; }
      .uw.dark { background: #000; color: #fff; }
      .lv-mono { --ink: #000; }
      .uw.lv-mono .uw-pic.cut, .uw.lv-gray4 .uw-pic.cut { filter: contrast(1.15); }
      .ph { display: flex; justify-content: space-between; align-items: baseline; gap: 2cqmin; padding: 1.2cqmin 2.4cqmin .3cqmin; flex: 0 0 auto; font-size: calc(var(--ts) * 1em); }
      .ph-k { font-family: var(--sc); font-size: 2.4cqmin; letter-spacing: .13em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .ph-d { font-weight: 400; font-size: 3cqmin; letter-spacing: .04em; white-space: nowrap; }
      .ph-rule { border-top: 1px solid var(--ink); position: relative; margin: 0 2.4cqmin .2cqmin; flex: 0 0 auto; }
      .ph-rule::after { content: ""; position: absolute; left: 0; right: 0; top: 2px; border-top: 1px solid var(--ink); }
      .credit { flex: 0 0 auto; font-size: 1.7cqmin; opacity: .7; padding: .3cqmin 2.4cqmin .7cqmin; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-style: italic; }
      .msg { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 1.4cqmin; padding: 4cqmin 6cqmin; text-align: center; }
      .msg-t { font-family: var(--sc); font-size: 5cqmin; letter-spacing: .06em; } .msg-b { font-size: 3.4cqmin; } .msg-h { font-size: 2.6cqmin; font-style: italic; opacity: .75; }
      .uw-nopic { position: relative; display: block; overflow: hidden; }
      /* the mark on a painting made from her particulars alone */
      .uw-imp { font-family: var(--sans); font-size: calc(var(--ts) * 1.9cqmin); letter-spacing: .14em; text-transform: uppercase; border: 1px solid var(--ink); padding: .25em .7em; opacity: .75; }
      .pl-imp { position: absolute; left: 2.6cqmin; top: 2.6cqmin; } .lg-imp { margin-left: .6em; font-size: calc(var(--ts) * 1.4cqmin); padding: .15em .5em; vertical-align: middle; letter-spacing: .1em; }
      .uw-sil { position: absolute; inset: 0; width: 100%; height: 100%; opacity: .3; }
      .uw-flag { font-family: var(--sc); letter-spacing: .1em; font-size: .8em; }
      .ln { display: block; }
      /* the photograph */
      .fb-bg { position: absolute; inset: 0; background-position: center; background-repeat: no-repeat; background-color: #000; }
      .fb-none { color: #fff; } .fb-none .uw-sil { inset: 15cqmin; width: auto; height: auto; }
      .fb-shade { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,.45) 0, rgba(0,0,0,0) 22%, rgba(0,0,0,0) 48%, rgba(0,0,0,.8) 100%); }
      .fb-top, .fb-main, .fb-strip, .fb-credit { position: absolute; font-family: var(--sans); text-shadow: 0 1px 3px rgba(0,0,0,.6); }
      .fb-top { top: 2.6cqmin; left: 2.6cqmin; right: 2.6cqmin; display: flex; justify-content: space-between; font-size: 2.6cqmin; letter-spacing: .1em; text-transform: uppercase; }
      .fb-main { left: 2.6cqmin; bottom: 3cqmin; max-width: 58%; }
      .fb-flag { display: block; font-size: 2.6cqmin; text-transform: uppercase; margin-bottom: 1cqmin; }
      .fb-cs { font-size: calc(var(--ts) * 10cqmin); font-weight: 700; line-height: .95; }
      .fb-typ { font-size: calc(var(--ts) * 3.8cqmin); font-weight: 600; margin-top: .8cqmin; } .fb-typ span { font-weight: 400; opacity: .85; }
      .fb-r { font-size: calc(var(--ts) * 3cqmin); margin-top: .4cqmin; } .fb-r .ln { display: inline; }
      .fb-strip { right: 2.4cqmin; bottom: 3cqmin; width: 36%; list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 1cqmin; }
      .fb-strip li { display: flex; gap: 1.2cqmin; align-items: center; background: rgba(0,0,0,.42); padding: .7cqmin; border-radius: .5cqmin; }
      .fb-th { width: 10cqmin; height: 6.5cqmin; background-size: cover; background-position: center; border-radius: .3cqmin; flex: none; } .fb-th-none { position: relative; color: #fff; }
      .fb-th-t { display: flex; flex-direction: column; line-height: 1.15; font-size: 2cqmin; min-width: 0; } .fb-th-t b { font-size: 2.6cqmin; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; } .fb-th-t span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .fb-credit { right: 2.6cqmin; top: 6cqmin; left: auto; max-width: 70%; padding: 0; opacity: .85; font-size: 1.8cqmin; background: none; }
      .uw.photo.size-sm .fb-strip, .uw.photo.size-xs .fb-strip { display: none; }
      /* the plate */
      .pl { flex: 1; min-height: 0; display: grid; grid-template-columns: 62fr 38fr; gap: 2cqmin; padding: 1.5cqmin 2.4cqmin; }
      .pl.portrait { grid-template-columns: 1fr; grid-template-rows: 60fr 40fr; }
      .pl-plate { position: relative; display: flex; align-items: center; justify-content: center; min-height: 0; padding: 4cqmin; }
      .pl-frame { position: absolute; inset: 1cqmin; border: 1.5px solid var(--ink); outline: 1px solid var(--ink); outline-offset: 4px; }
      .pl-frame i { position: absolute; width: 4cqmin; height: 4cqmin; border: 1.5px solid var(--ink); }
      .pl-frame i.tl { left: -1.3cqmin; top: -1.3cqmin; border-right: 0; border-bottom: 0; } .pl-frame i.tr { right: -1.3cqmin; top: -1.3cqmin; border-left: 0; border-bottom: 0; }
      .pl-frame i.bl { left: -1.3cqmin; bottom: -1.3cqmin; border-right: 0; border-top: 0; } .pl-frame i.br { right: -1.3cqmin; bottom: -1.3cqmin; border-left: 0; border-top: 0; }
      .pl-pic { max-width: 92%; max-height: 82%; object-fit: contain; mix-blend-mode: multiply; } .pl-pic.whole { mix-blend-mode: normal; max-height: 90%; }
      .uw-nopic.pl-pic { width: 60%; aspect-ratio: 1; }
      .pl-fig { position: absolute; left: 0; right: 0; bottom: 2.2cqmin; text-align: center; font-size: calc(var(--ts) * 1.9cqmin); font-style: italic; padding: 0 3cqmin; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .pl-note { display: flex; flex-direction: column; gap: .8cqmin; min-width: 0; padding-top: 1cqmin; }
      .pl-cs { font-family: var(--sc); font-size: calc(var(--ts) * 5.2cqmin); letter-spacing: .04em; line-height: 1.05; }
      .pl-typ { font-size: calc(var(--ts) * 3cqmin); } .pl-typ i { opacity: .8; }
      .pl-note dl { margin: .6cqmin 0 0; display: grid; grid-template-columns: auto 1fr; gap: .5cqmin 1.6cqmin; font-size: calc(var(--ts) * 2.5cqmin); }
      .pl-note dt { font-family: var(--sc); letter-spacing: .08em; font-size: .8em; opacity: .8; padding-top: .3em; } .pl-note dd { margin: 0; }
      .pl-about { font-size: calc(var(--ts) * 2.4cqmin); line-height: 1.3; margin: .6cqmin 0 0; font-style: italic; opacity: .9; }
      /* the modern looks */
      .md { flex: 1; min-height: 0; position: relative; display: grid; font-family: var(--sans); color: #111; overflow: hidden; }
      .uw.font-fell .md, .uw.font-georgia .md { --sans: 'Archivo Narrow', Arial, sans-serif; }
      .md .uw-flag { font-family: var(--sans); font-size: 2.8cqmin; letter-spacing: .12em; text-transform: uppercase; }
      .md-cs { font-weight: 700; line-height: .95; letter-spacing: -.01em; font-size: calc(var(--ts) * 9.5cqmin); overflow-wrap: anywhere; }
      .md-typ { font-size: calc(var(--ts) * 3.9cqmin); opacity: .9; }
      .md .nb { white-space: nowrap; }
      .md-pic { background-position: center; background-repeat: no-repeat; background-size: cover; } .md-pic.cut { background-size: contain; background-color: var(--t); }
      .md-none { position: relative; background: var(--t); } .md-none .uw-sil { inset: 12%; width: auto; height: auto; }
      .md-rt { display: flex; align-items: center; gap: 2.5cqmin; min-width: 0; } .md-rt b { font-size: calc(var(--ts) * 5.4cqmin); font-weight: 700; line-height: 1.05; min-width: 0; overflow-wrap: anywhere; } .md-rt small { display: block; font-size: calc(var(--ts) * 2.4cqmin); opacity: .85; font-weight: 400; letter-spacing: .1em; text-transform: uppercase; margin-bottom: .4cqmin; }
      .md-rt i { flex: 0 0 8cqmin; border-top: .45cqmin dashed currentColor; opacity: .7; }
      .md-rt-text b { font-size: calc(var(--ts) * 4.6cqmin); }
      .md-st { border-radius: 1.9cqmin; padding: 1.6cqmin 2.1cqmin; display: flex; flex-direction: column; justify-content: flex-end; min-width: 0; } .md-st small { font-size: calc(var(--ts) * 2.3cqmin); letter-spacing: .12em; text-transform: uppercase; opacity: .8; } .md-st b { font-size: calc(var(--ts) * 4.4cqmin); line-height: 1.1; white-space: nowrap; } .md-st em { font-style: normal; font-size: calc(var(--ts) * 2.4cqmin); opacity: .85; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .md-st.on-p { background: var(--p); color: var(--pink); } .md-st.on-s { background: var(--s); color: var(--sink); } .md-st.on-th { background: var(--th); color: #fff; } .md-st.on-sh { background: var(--sh); color: #fff; } .md-st.on-t { background: var(--t); color: #111; } .md-st.on-t small { color: var(--sh); opacity: 1; }
      .md-st.dim { background: rgba(255,255,255,.1); color: #fff; } .md-st.glass { background: rgba(255,255,255,.16); color: #fff; border-top: .8cqmin solid var(--s); }
      .md-top { font-size: calc(var(--ts) * 2.8cqmin); letter-spacing: .14em; text-transform: uppercase; }
      .md-note { position: absolute; right: 2.4cqmin; bottom: 1.2cqmin; font-size: 2.2cqmin; opacity: .8; font-style: italic; color: inherit; }
      .md-vis { right: 4%; top: 10%; width: 11%; } .md-vis figcaption { font-family: var(--sans); font-size: 2cqmin; text-transform: uppercase; letter-spacing: .08em; color: #fff; text-shadow: 0 1px 3px rgba(0,0,0,.7); }
      .md-pass { grid-template-columns: 62fr 38fr; background: var(--t); } .md-pass.portrait { grid-template-columns: 1fr; grid-template-rows: 52fr 48fr; }
      .md-ph { position: relative; min-height: 0; overflow: hidden; } .md-ph .md-pic { position: absolute; inset: 0; } .md-ph::after { content: ""; position: absolute; inset: 0; background: linear-gradient(180deg, transparent 55%, color-mix(in srgb, var(--p) 92%, transparent) 100%); pointer-events: none; }
      .md-ph .md-top { position: absolute; left: 4.6cqmin; top: 3.3cqmin; color: #fff; text-shadow: 0 1px 3px rgba(0,0,0,.5); z-index: 1; } .md-cap { position: absolute; left: 4.6cqmin; right: 4.6cqmin; bottom: 3.6cqmin; color: #fff; font-size: calc(var(--ts) * 3cqmin); opacity: .92; z-index: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .md-side { background: var(--p); color: var(--pink); padding: 4.6cqmin 5cqmin; display: flex; flex-direction: column; gap: 2cqmin; border-left: 1.7cqmin solid var(--s); min-height: 0; } .md-pass.portrait .md-side { border-left: 0; border-top: 1.7cqmin solid var(--s); }
      .md-side .md-rt { margin-top: 1.6cqmin; }
      .md-chips { display: grid; grid-template-columns: 1fr 1fr; gap: 1.7cqmin; margin-top: auto; } .md-chips .md-st em { display: none; }
      .md.md-tiles { background: var(--t); padding: 3.3cqmin 3.7cqmin; grid-template-rows: auto 1fr; gap: 2.5cqmin; }
      .md-bar { display: flex; align-items: center; gap: 3cqmin; background: var(--p); color: var(--pink); border-radius: 2.9cqmin; padding: 2cqmin 3.3cqmin; min-width: 0; } .md-bar .md-cs { font-size: calc(var(--ts) * 6.4cqmin); } .md-bar .md-typ { font-size: calc(var(--ts) * 3.3cqmin); } .md-bar-t { min-width: 0; } .md-bar-t > div { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .md-when { margin-left: auto; text-align: right; font-size: calc(var(--ts) * 2.7cqmin); letter-spacing: .08em; text-transform: uppercase; opacity: .9; white-space: nowrap; }
      .md-grid { display: grid; grid-template-columns: 1.25fr 1fr; gap: 2.5cqmin; min-height: 0; position: relative; } .md-tiles.portrait .md-grid { grid-template-columns: 1fr; grid-template-rows: 1fr 1fr; }
      .md-card { border-radius: 2.9cqmin; overflow: hidden; min-height: 0; }
      .md-tiles .md-tiles { display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: auto 1fr 1fr; gap: 2cqmin; min-height: 0; }
      .md-tiles .md-rt { grid-column: 1 / -1; background: #fff; color: #111; border-radius: 2.5cqmin; padding: 2cqmin 2.9cqmin; border-left: 1.25cqmin solid var(--s); } .md-tiles .md-rt small { color: var(--sh); } .md-tiles .md-rt i { border: 0; height: .8cqmin; background: linear-gradient(90deg, var(--p), var(--th)); border-radius: .4cqmin; opacity: 1; }
      .md-tiles .md-st b { font-size: calc(var(--ts) * 6.2cqmin); }
      .md-poster { color: #fff; background: var(--sh); } .md-bg { position: absolute; inset: 0; } .md-bg.cut { background-size: 70%; background-position: center 30%; background-color: transparent; }
      .md-shade { position: absolute; inset: 0; background: linear-gradient(180deg, color-mix(in srgb, var(--sh) 60%, transparent) 0%, transparent 35%, transparent 45%, color-mix(in srgb, var(--p) 95%, transparent) 100%); }
      .md-top-row { position: absolute; left: 5cqmin; right: 5cqmin; top: 3.7cqmin; display: flex; justify-content: space-between; align-items: center; }
      .md-main { position: absolute; left: 5cqmin; right: 5cqmin; bottom: 4.6cqmin; } .md-poster .md-cs { font-size: calc(var(--ts) * 12cqmin); letter-spacing: -.02em; line-height: .9; } .md-poster .md-typ { font-size: calc(var(--ts) * 4.2cqmin); margin: 1.2cqmin 0 2.5cqmin; }
      .md-row { display: flex; align-items: flex-end; gap: 5cqmin; } .md-poster .md-rt i { border: 0; border-top: .6cqmin solid var(--s); opacity: 1; }
      .md-stats { display: flex; gap: 2cqmin; margin-left: auto; } .md-stats .md-st em { display: none; } .md-stats .md-st:nth-child(2) { border-color: var(--th); } .md-stats .md-st:nth-child(3) { border-color: var(--t); }
      .md-poster.portrait .md-row { flex-direction: column; align-items: flex-start; gap: 2.5cqmin; } .md-poster.portrait .md-stats { margin-left: 0; }
      .md-split { background: var(--sh); color: #fff; grid-template-columns: 1fr 1fr; padding: 4.2cqmin; gap: 4.2cqmin; } .md-split.portrait { grid-template-columns: 1fr; grid-template-rows: 50fr 50fr; }
      .md-frame-wrap { position: relative; min-height: 0; } .md-frame { position: absolute; inset: 0; border-radius: 3.7cqmin; border: .6cqmin solid var(--p); overflow: hidden; }
      .md-pill { position: absolute; left: 2.9cqmin; top: 2.5cqmin; background: var(--p); color: var(--pink); font-size: calc(var(--ts) * 2.5cqmin); padding: .8cqmin 1.9cqmin; border-radius: 99cqmin; letter-spacing: .1em; text-transform: uppercase; }
      .md-r { display: flex; flex-direction: column; gap: 1.6cqmin; min-height: 0; min-width: 0; } .md-hd { display: flex; align-items: center; justify-content: space-between; gap: 2cqmin; } .md-hd span { font-size: calc(var(--ts) * 2.7cqmin); letter-spacing: .14em; text-transform: uppercase; opacity: .8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .md-split .md-cs { font-size: calc(var(--ts) * 10cqmin); } .md-split .md-typ { opacity: .85; }
      .md-split .md-rt { margin: 2cqmin 0; background: var(--p); color: var(--pink); border-radius: 2.9cqmin; padding: 2.5cqmin 3.3cqmin; }
      .md-stats4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.7cqmin; margin-top: auto; } .md-stats4 .md-st em { display: none; } .md-stats4 .md-st b { font-size: calc(var(--ts) * 4.2cqmin); }
      .md-split.portrait .md-stats4 { grid-template-columns: 1fr 1fr; }
      /* the log of cards */
      .lg-grid { flex: 1; min-height: 0; display: grid; grid-template-columns: repeat(var(--cols), 1fr); grid-auto-rows: 1fr; gap: 1.2cqmin; padding: 1cqmin 2cqmin; font-family: var(--sans); }
      .lg-card { display: flex; flex-direction: column; min-height: 0; background: rgba(255,255,255,.55); border: 1px solid rgba(0,0,0,.18); overflow: hidden; }
      .lg-pic { flex: 1 1 55%; min-height: 0; background-size: cover; background-position: center; } .lg-cut { background-size: contain; background-repeat: no-repeat; } .lg-none { position: relative; } .lg-none .uw-sil { inset: 2cqmin; width: auto; height: auto; }
      .lg-row { display: flex; justify-content: space-between; align-items: baseline; gap: 1cqmin; padding: .7cqmin 1cqmin 0; min-width: 0; } .lg-row b { font-size: calc(var(--ts) * 2.8cqmin); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .lg-flag { font-size: calc(var(--ts) * 1.8cqmin); white-space: nowrap; }
      .lg-lines { padding: .3cqmin 1cqmin .8cqmin; font-size: calc(var(--ts) * 2cqmin); line-height: 1.2; } .lg-lines .ln { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; } .lg-lines .ln-first { font-weight: 600; }
      /* the scene */
      .sc-bg { position: absolute; inset: 0; background-position: center; background-repeat: no-repeat; } .sc-none .uw-sil { inset: 15cqmin; width: auto; height: auto; }
      .sc-top, .sc-main, .sc-credit { position: absolute; font-family: var(--sans); }
      .sc-top { top: 2.6cqmin; left: 2.6cqmin; right: 2.6cqmin; display: flex; justify-content: space-between; font-size: 2.6cqmin; letter-spacing: .1em; text-transform: uppercase; }
      .sc-main { right: 3cqmin; bottom: 7cqmin; text-align: right; max-width: 60%; }
      .sc-flag { display: block; font-size: 2.6cqmin; text-transform: uppercase; margin-bottom: 1cqmin; }
      .sc-cs { font-size: calc(var(--ts) * 9cqmin); font-weight: 700; line-height: .95; }
      .sc-typ { font-size: calc(var(--ts) * 3.6cqmin); font-weight: 600; margin-top: .8cqmin; } .sc-typ span { font-weight: 400; opacity: .75; }
      .sc-r { font-size: calc(var(--ts) * 2.8cqmin); margin-top: .4cqmin; } .sc-r .ln { display: inline; }
      .sc-credit { left: 2.6cqmin; right: auto; bottom: 2cqmin; max-width: 50%; padding: 0; }
    </style>`;
}
