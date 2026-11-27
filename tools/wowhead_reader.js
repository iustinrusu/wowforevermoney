// Reads ONE Wowhead Forever page that is already open in the browser pane (docs/plans/material-coverage.md).
// Not a crawler: it never loads a page itself. The pages are opened by hand at the user's pace (CLAUDE.md: one page
// every 2 minutes, at most 20 a session, stop at the first block). Kept here because the browser tab's storage lost
// it twice (2026-11-20, 2026-11-26).
//
// Set up in the Wowhead tab (javascript_tool): localStorage.wfm_fn = <this file's text>; then per page run
// eval(localStorage.wfm_fn). It THROWS on a blocked or non-Forever page, so a batch of actions stops there.
// It keeps the page under localStorage.wfm_pages (read out later, saved to a file, then
// `python -m wfm.wowhead_items import <file>`), and the time under wfm_last (wfm_go3 waits 2 minutes from it).
//
// Kept per page: every listview whose rows carry loot counts (count / outof): item pages' Dropped by, Skinned from,
// Contained in, Fished in...; npc pages' Drops, Skinning, Pickpocketing; object pages' Contains. Rows as
// [id, count, outof, minlevel, maxlevel, location, classification, stack spread]; Classic Era rows only counted.
// A vendor's Sells tab as [item, stock a restock (-1 = unlimited), price in copper, standing, 1 if it costs a currency
// or items, how many one purchase gives].
// An npc's Quick Facts: level, health, Worth (coins a kill, from the coin icons) and the box's text.
(() => {
  const title = document.title, head = (document.body ? document.body.innerText : '').slice(0, 400);
  if (!/WoW Forever/.test(title) || !location.pathname.startsWith('/forever/') || /\b403\b|Forbidden|Access denied|Just a moment|verify you are human/i.test(title + ' ' + head)) throw new Error('STOP: blocked or not a Forever page: ' + title);
  const m = location.pathname.match(/\/forever\/(npc|item|object)=(\d+)/);
  if (!m) throw new Error('STOP: not an npc, item or object page');
  const key = m[1] + '=' + m[2];
  const spread = r => {
    if (r.pctstack) { const o = {}; String(r.pctstack).replace(/(\d+)\s*:\s*([\d.]+)/g, (_, s, p) => { o[s] = +p; }); if (Object.keys(o).length) return o; }
    if (Array.isArray(r.stack) && r.stack[0] === r.stack[1] && r.stack[0] > 1) return { [r.stack[0]]: 100 };
    return null;
  };
  // object pages' Contains rows keep the times opened only per mode: modes = {0: {count, outof}, mode: [0]}
  const outOf = r => r.outof != null ? r.outof : (r.modes && r.modes[(r.modes.mode || [0])[0]] || {}).outof;
  const tabs = {};
  let sells = null, sellsClassic = 0, sellsSample = null;
  for (const [id, lv] of Object.entries(window.g_listviews || {})) {
    const kind = { 1: 'npc', 2: 'object', 3: 'item', 7: 'zone' }[lv.template && lv.template.entityType];
    if (!kind) continue;
    const data = lv.data || [];
    if (id === 'sells') {
      sells = [];
      for (const r of data) {
        if (r.classicEra) { sellsClassic++; continue; }
        // cost: a list of ways to pay, each [copper, [[currency, amount]], [[item, count]]] (an older form: one way)
        const cost = Array.isArray(r.cost) ? (Array.isArray(r.cost[0]) ? r.cost[0] : r.cost) : [r.cost || 0];
        const other = (Array.isArray(cost[1]) && cost[1].length) || (Array.isArray(cost[2]) && cost[2].length) ? 1 : 0;
        // avail: how many a restock (-1 = unlimited); stack: how many one purchase gives (the price is for all of them)
        const stock = r.avail != null ? +r.avail : (r.stock != null ? +r.stock : -1);
        const stack = Array.isArray(r.stack) ? +r.stack[0] || 1 : +r.stack || 1;
        sells.push([+r.id, stock, +cost[0] || 0, r.standing != null ? +r.standing : 0, other, stack]);
      }
      sellsSample = data.slice(0, 2).map(r => ({ id: r.id, name: r.name, avail: r.avail, stack: r.stack, cost: r.cost, standing: r.standing, classicEra: r.classicEra }));
      continue;
    }
    if (!data.some(r => r.count != null && outOf(r) != null)) continue;      // see also, taught by, same model...: not a source
    let classic = 0; const rows = [];
    for (const r of data) {
      if (r.classicEra) { classic++; continue; }
      if (r.count == null || outOf(r) == null) continue;
      rows.push([+r.id, +r.count, +outOf(r), r.minlevel != null ? +r.minlevel : null, r.maxlevel != null ? +r.maxlevel : null,
                 r.location != null ? r.location : null, r.classification != null ? +r.classification : null, spread(r)]);
    }
    rows.sort((a, b) => b[2] - a[2] || b[1] - a[1]);
    tabs[id] = { kind, total: data.length, classic, note: String(lv.note || '').replace(/<[^>]+>/g, '').slice(0, 300), rows: rows.slice(0, 120) };
  }
  const box = [...document.querySelectorAll('.infobox')].map(e => e.innerText).join('\n');
  const qf = box.indexOf('Quick Facts') >= 0 ? box.slice(box.indexOf('Quick Facts')) : box;
  const nums = s => (s.match(/[\d,]+/g) || []).map(x => +x.replace(/,/g, '')).slice(0, 2);
  const facts = { text: qf.slice(0, 600) };
  const lvl = qf.match(/Level:\s*([^\n]+)/); if (lvl && nums(lvl[1]).length) facts.level = nums(lvl[1]);
  const hp = qf.match(/Health:\s*([^\n]+)/); if (hp && nums(hp[1]).length) facts.health = nums(hp[1]);
  const li = [...document.querySelectorAll('.infobox li')].find(l => /Worth/.test(l.innerText));
  if (li) { const c = s => { const e = li.querySelector('.money' + s); return e ? +e.innerText.replace(/\D/g, '') || 0 : 0; }; facts.worth = c('gold') * 10000 + c('silver') * 100 + c('copper'); }
  const name = (document.querySelector('h1.heading-size-1') || {}).innerText || title.split(' - ')[0];
  const page = { name: name.replace(/\s*<[^>]*>\s*$/, '').trim(), url: location.href.split('#')[0], read: new Date().toISOString().slice(0, 10), tabs };
  if (m[1] === 'npc') page.facts = facts;
  if (sells) { page.sells = sells; page.sells_classic = sellsClassic; }
  const pages = JSON.parse(localStorage.getItem('wfm_pages') || '{}');
  pages[key] = page;
  localStorage.setItem('wfm_pages', JSON.stringify(pages));
  localStorage.setItem('wfm_last', String(Date.now()));
  return { key, name: page.name, tabs: Object.fromEntries(Object.entries(tabs).map(([k, t]) => [k, t.rows.length + ' rows, ' + t.classic + ' Classic skipped, note: ' + t.note])),
           sells: sells ? sells.length + ' sold, ' + sellsClassic + ' Classic skipped' : undefined, sellsSample,
           facts: m[1] === 'npc' ? { level: facts.level, health: facts.health, worth: facts.worth } : undefined, pagesSaved: Object.keys(pages) };
})()
