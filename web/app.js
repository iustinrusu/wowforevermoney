'use strict';
// ---------- helpers ----------
const $ = (s, el = document) => el.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const api = async (path, opts) => { const r = await fetch(path, opts); if (!r.ok) throw new Error(await r.text()); return r.json(); };
function money(c) {
  if (c === null || c === undefined || isNaN(c)) return '<span class="pill">–</span>';
  const neg = c < 0; c = Math.round(Math.abs(c));
  const g = Math.floor(c / 10000), s = Math.floor(c / 100) % 100, cc = c % 100;
  let out = '';
  if (g) out += `<span class="g">${g.toLocaleString()}g</span> `;
  if (g || s) out += `<span class="s">${s}s</span> `;
  if (!g) out += `<span class="c">${cc}c</span>`;
  return `<span class="money${neg ? ' neg' : ''}">${neg ? '-' : ''}${out.trim()}</span>`;
}
const num = (v, d = 1) => (v === null || v === undefined) ? '–' : Number(v).toLocaleString(undefined, {maximumFractionDigits: d});
const chg = (v, d = 0, color = true) => (v === null || v === undefined) ? '<span class="pill">–</span>' : `<span class="${color ? (v > 0.005 ? 'up' : (v < -0.005 ? 'down' : '')) : ''}">${v > 0 && color ? '+' : ''}${(v * 100).toFixed(d)}%</span>`;
const ago = (ts) => { if (!ts) return 'never'; const s = Date.now() / 1000 - ts; if (s < 90) return `${Math.round(s)}s ago`; if (s < 5400) return `${Math.round(s / 60)} min ago`; if (s < 172800) return `${(s / 3600).toFixed(1)} h ago`; return `${(s / 86400).toFixed(1)} days ago`; };
const KIND = {farm_zone: 'Farming spot', craft: 'Craft', vendor_flip: 'Vendor → AH', ah_to_vendor: 'AH → vendor', realm_dip: 'Cheap relist', gather: 'Farm', fishing_zone: 'Fishing spot', fishing_spot: 'Fishing spot'};
const FLAGS = {
  none_listed: ['warn', 'none listed now', 'No listings on your realm right now; price is the market average'],
  no_realm_data: ['warn', 'region price only', 'No realm data; using the region average'],
  sells_lower: ['warn', 'sells for less', 'Listed well above what it actually sells for (region average sale price): at the lowest buyout it may not sell. Settings can value it at actual sales instead'],
  no_sales_data: ['bad', 'no sales data', 'TSM has no recorded sales for this item'],
  above_region: ['warn', 'above region', 'Lowest listing is far above the region average'],
  slow_seller: ['bad', 'slow seller', 'Sells less often than your minimum'],
  cant_afford: ['bad', "can't afford", 'Costs more than the gold you have set'],
  unverified_recipe: ['bad', 'unverified recipe', 'Not in SkillUpForever\'s list of obtainable recipes'],
  skill_estimated: ['', 'skill ~', 'Exact skill requirement unknown; estimated'],
  sell_to_vendor: ['good', 'vendor sale', 'Selling to a vendor beats the AH'],
  mat_not_listed: ['warn', 'mat not listed', 'An ingredient has no listings right now'],
  limited_mat: ['warn', 'limited mat', 'An ingredient comes from a limited-stock vendor'],
  limited_stock: ['warn', 'limited stock', 'Vendor has limited stock that restocks over time'],
  other_profession: ['', 'other profession', 'You don\'t have this profession'],
  snapshot: ['warn', 'snapshot', 'Based on one listing at the last scan; check in game'],
  often_below_vendor: ['good', 'often', 'Usually listed below vendor price'],
  risky: ['bad', 'risky', 'Speculative: depends on prices recovering'],
  small_sample: ['warn', 'small sample', 'Not many catches/loots logged here yet'],
  vendor_price_unconfirmed: ['', 'vendor price from game files', 'Base price from the game files; open the vendor once with ForeverMoneyBridge to confirm the real price'],
  price_looks_off: ['warn', 'price looks off', "Only a few listings, far from the realm's recent average: valued at the recent average until more listings confirm the new price"],
  old_snapshot: ['warn', 'old Wowhead data', 'The Wowhead Forever counts for this zone are over 30 days old: re-read the zone page'],
  craft_limited_demand: ['warn', 'limited demand', 'Valued by crafting it into something whose market only absorbs a limited number per day; beyond that it is worth its sale price'],
  more_with_skill: ['', 'more with skill', "A recipe you can't make yet would make it worth more (see details); valued at what you can do now"],
  event_vendor: ['bad', 'event vendor', 'Every vendor selling it is event-only (Darkmoon Faire, holidays) or has no known location: check it is there now. Kept out of Top picks'],
  black_market: ['bad', 'black market vendor', 'Black Market agents charge more than the game-file price (e.g. Frilled Lichen: 4s 50c, not 1s 20c). Visit once to record the real price'],
  measured: ['good', 'measured', 'Gold/hour from real time spent (ForeverMoneyBridge)'],
  not_enough_time: ['warn', 'needs more time', 'Under 5 minutes logged; gold/hour not shown yet'],
  assumed_rate: ['warn', 'assumed casts/hour', 'No timed fishing logs yet (ForeverMoneyBridge); uses your casts-per-hour setting'],
  measured_pace: ['', 'your pace', 'Catches per hour from your timed fishing in other zones'],
  classic_unconfirmed: ['bad', 'Classic, unconfirmed', 'A Classic WoW 1.12 table (cMaNGOS), not Forever data. Forever often differs (see Data health). Never used in Top picks.'],
  classic_incomplete: ['warn', 'Classic table incomplete', 'The Classic table explains under 90% of catches here; the rest is unknown'],
  forever_only: ['good', 'Forever only', 'A zone Classic does not have; entirely from Forever data'],
  wowhead_forever: ['good', 'Wowhead Forever', 'Includes Forever catch counts read by hand from Wowhead Forever'],
  forever_change: ['warn', 'differs from Classic', 'Your Forever catches include fish Classic does not list here, or lack a common Classic fish'],
  seasonal: ['', 'seasonal', 'Part of the value is a seasonal fish (Classic schedule; Forever may differ)'],
  classic_getaway: ['warn', 'got-away rate: Classic formula', 'No logs at this zone skill yet; Classic formula used, which your Forever logs suggest is too harsh'],
  dungeon: ['', 'dungeon', 'Inside a dungeon'],
  pools_extra: ['', 'pool loot extra', 'Pool loot (trunks, Stranglekelp, Rumsey Rum) is not in this gold/hour, because pools have to be found first. Open the row to see what pools add, or count them in Settings.'],
  contents_unknown: ['warn', 'contents unknown', 'Can be opened, but what it contains in Forever is unknown: valued as a floor. Open one with ForeverMoneyBridge enabled, or read its Wowhead Forever page'],
  open_it: ['good', 'open it', 'Worth more opened than sold (expected value of its Forever contents at current prices)'],
  locked: ['', 'locked', 'Needs Lockpicking or a key to open'],
  no_value: ['bad', 'no known value', 'No AH price, vendor price, recipe or contents known'],
  short_history: ['', 'short history', 'Under a day of our own price snapshots: the trend is first vs latest scan and can swing a lot'],
  slow_sale_rate: ['warn', 'slow to sell', 'Under 10% of listings sell (TSM region sale rate): you may wait a long time to sell'],
  ah_price_doubtful: ['warn', 'AH price doubtful', 'Listed with no recorded sales or far above the region: counted at its sale price instead'],
};
const flagHtml = (flags) => (flags || []).map((f) => { const d = FLAGS[f] || ['', f, f]; return `<span class="flag ${d[0]}" title="${esc(d[2])}">${esc(d[1])}</span>`; }).join('');
const itemLink = (id, name, q) => `<a class="q${q ?? 1}" href="https://www.wowhead.com/forever/item=${id}" target="_blank" rel="noopener" data-wowhead="item=${id}&domain=forever">${esc(name)}</a>`;
function toast(text) { const t = document.createElement('div'); t.className = 'toast'; t.textContent = text; $('#toasts').appendChild(t); setTimeout(() => t.remove(), 9000); }
function refreshTooltips() { try { window.$WowheadPower && window.$WowheadPower.refreshLinks(); } catch (e) { /* optional */ } }

// ---------- state ----------
let STATE = null;
let TAB = localStorage.getItem('tab') || 'top';
const sortState = {};

async function loadState() {
  STATE = await api('/api/state');
  const worst = (STATE.freshness || []).map((f) => f.status);
  const audit = STATE.audit_summary || {};
  const dot = $('#health-dot');
  dot.className = 'dot ' + (worst.includes('stale') || worst.includes('error') || audit.fail ? 'stale' : (worst.includes('warn') || audit.warn ? 'warn' : 'ok'));
  const tsm = (STATE.freshness || []).find((f) => f.name === 'tsm');
  $('#status').textContent = `Prices from ${tsm && tsm.data_time ? ago(tsm.data_time) : '?'} · updated ${ago(STATE.generated_at)} · ${STATE.settings.realm}`;
}

// ---------- tables ----------
function oppTable(rows, opts = {}) {
  if (!rows.length) return `<div class="empty">${esc(opts.empty || 'Nothing here right now.')}</div>`;
  const id = opts.id || 't' + Math.random().toString(36).slice(2, 7);
  const cols = opts.cols || ['title', 'profit_unit', 'cost_unit', 'units_day', 'daily', 'flags'];
  const H = {...{title: 'What to do', profit_unit: 'Profit each', cost_unit: 'Cost each', units_day: 'Per day', daily: 'Per day profit', gph: 'Gold / hour', gph_pools: 'Gold / hour with pools', flags: 'Notes', profession: 'Profession', kind: 'Type'}, ...(opts.heads || {})};
  const st = sortState[id];
  if (st) rows = [...rows].sort((a, b) => ((a[st.k] ?? -1e18) < (b[st.k] ?? -1e18) ? -1 : 1) * (st.dir));
  const numeric = new Set(['profit_unit', 'cost_unit', 'units_day', 'daily', 'gph', 'gph_pools']);
  const head = cols.map((c) => `<th data-k="${c}" class="${numeric.has(c) ? 'num' : ''}">${H[c] || c}</th>`).join('');
  const body = rows.map((o) => {
    const cells = cols.map((c) => {
      if (c === 'title') {
        const name = o.name || o.title;
        const label = (o.kind === 'fishing_zone' || o.kind === 'fishing_spot') ? esc(o.title) : esc(o.title).replace(esc(name), itemLink(o.item_id, name, o.quality));
        return `<td>${label}${o.needs ? `<div class="needs">needs ${esc(o.needs)}</div>` : ''}${o.tip ? `<div class="pill">💡 ${esc(o.tip)}</div>` : ''}</td>`;
      }
      if (c === 'flags') return `<td>${flagHtml(o.flags)}</td>`;
      if (c === 'units_day') return `<td class="num">${num(o.units_day)}</td>`;
      if (c === 'kind') return `<td>${esc(KIND[o.kind] || o.kind)}</td>`;
      if (c === 'profession') return `<td>${esc(o.profession || '')}</td>`;
      return `<td class="num">${money(o[c])}</td>`;
    }).join('');
    return `<tr class="row ${o.doable ? '' : 'notdoable'}" data-key="${esc(o.key)}" data-item="${o.item_id}">${cells}</tr>`;
  }).join('');
  const exp = opts.export !== false ? `<button class="btn" data-export="${id}">Copy item list for TSM</button>` : '';
  setTimeout(() => wireTable(id, rows, opts), 0);
  const inner = `<div class="tablewrap"><table id="${id}"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div><div class="controls" style="margin-top:6px">${exp}<span class="pill">${rows.length} rows</span></div>`;
  return opts.inner ? inner : `<div id="wrap-${id}">${inner}</div>`;
}
function wireTable(id, rows, opts) {
  const t = document.getElementById(id); if (!t) return;
  t.querySelectorAll('th').forEach((th) => th.onclick = () => {
    const k = th.dataset.k; const cur = sortState[id];
    sortState[id] = {k, dir: cur && cur.k === k ? -cur.dir : -1};
    document.getElementById('wrap-' + id).innerHTML = oppTable(rows, {...opts, id, inner: true});
  });
  t.querySelectorAll('tr.row').forEach((tr) => tr.onclick = (e) => { if (e.target.closest('a')) return; const o = rows.find((r) => r.key === tr.dataset.key); openOpp(o); });
  const b = document.querySelector(`[data-export="${id}"]`);
  if (b) b.onclick = async () => {
    const res = await api('/api/export?keys=' + encodeURIComponent(rows.slice(0, 200).map((r) => r.key).join('|')));
    try { await navigator.clipboard.writeText(res.tsm); toast('Copied. In TSM: Groups → Import → paste.'); } catch (e) { prompt('Copy this into TSM (Groups → Import):', res.tsm); }
  };
  refreshTooltips();
}

// gold/hour if you also fish the pools you come across (open water + pool loot; time spent finding pools not included)
const withPools = (rows) => rows.map((o) => ({...o, gph_pools: o.detail && o.detail.forever ? (o.detail.gph_with_pools || o.gph) : null}));
// sections about later show what a pick earns per day once you have the gold for it
const ifAffordable = (rows) => rows.map((o) => ({...o, daily: (o.detail && o.detail.daily_if_affordable !== undefined) ? o.detail.daily_if_affordable : o.daily}));
const POOL_HINT = '"Gold / hour with pools" adds the trunks, Stranglekelp and Rumsey Rum from the pools you come across. It doesn\'t count the time spent finding pools, so treat it as a ceiling.';

// ---------- views ----------
const VIEWS = {
  async top() {
    const t = STATE.top || {};
    const e = STATE.effective, who = STATE.detected.character;
    const tsm = (STATE.freshness || []).find((f) => f.name === 'tsm');
    const stale = tsm && tsm.status !== 'ok' ? `<div class="panel" style="border-color:#e8c060">⚠ Prices may be out of date: ${esc(tsm.note)}. Check that the TSM desktop app is running; picks below use the last prices it downloaded.</div>` : '';
    return `${stale}
      <div class="hint">${who ? `Playing <b>${esc(who)}</b> (detected)` : 'Using your manual settings'}: ${num(e.gold, 2)}g to invest, level ${e.level}, realm ${esc(e.realm)}. Everything updates when TSM syncs or you log out / /reload. Click any row for details.</div>
      <div class="panel"><h2>Do these now <small>things you can do today, ranked by expected profit per day</small></h2>${oppTable(t.now || [])}</div>
      <div class="panel"><h2>Fishing & farming spots <small>gold per hour: open water, and with the pools you come across</small></h2>${oppTable(withPools(t.hourly || []), {cols: ['title', 'profit_unit', 'gph', 'gph_pools', 'flags'], export: false, heads: {profit_unit: 'Per catch / each'}})}
        <div class="hint">${POOL_HINT}</div>
        <div class="hint">Only spots with enough Forever data appear here (Wowhead Forever counts; your own catch logs only if you turn that on in Settings). Fishing gold/hour is open water; pool loot is a bonus shown in the details. "measured" uses real time from ForeverMoneyBridge; otherwise ${num(STATE.settings.casts_per_hour || 240, 0)} casts/hour (Settings). All spots, including unconfirmed Classic ones, are on the Farming tab.</div></div>
      <div class="panel"><h2>Snipes <small>single cheap listings at the last scan; check them in game first</small></h2>${oppTable(t.snipes || [], {cols: ['title', 'kind', 'profit_unit', 'cost_unit', 'flags']})}</div>
      <div class="grid2">
        <div class="panel"><h2>Unlock by levelling a profession you have</h2>${oppTable(ifAffordable(t.level_up || []), {cols: ['title', 'profit_unit', 'daily', 'flags'], heads: {daily: 'Per day (with the gold)'}, empty: 'Nothing worth it a few skill points away right now.'})}</div>
        <div class="panel"><h2>Worth switching professions for <small>at least ${num(STATE.settings.switch_bonus, 1)}× your best</small></h2>${oppTable(ifAffordable(t.switch || []), {cols: ['title', 'profession', 'daily', 'flags'], heads: {daily: 'Per day (with the gold)'}, empty: 'No other profession beats yours by enough right now.'})}</div>
      </div>`;
  },
  async craft() {
    const profs = STATE.professions_available.filter((p) => !/Racial|Riding|Test|Poison|Swim|Lockpick|Compreh|Survival|Horseman|Piloting/.test(p));
    const sel = sessionStorage.getItem('craftProf') || '';
    const doable = sessionStorage.getItem('craftDoable') === '1';
    const rows = await api(`/api/opps?kind=craft&profession=${encodeURIComponent(sel)}&doable=${doable ? 1 : ''}&limit=800`);
    return `<div class="panel"><h2>Crafting profit <small>ingredients bought at the cheapest of vendor / AH; product sold at the better of AH (after cut) / vendor</small></h2>
      <div class="controls"><select id="cp"><option value="">All professions</option>${[...new Set(profs)].map((p) => `<option ${p === sel ? 'selected' : ''}>${esc(p)}</option>`).join('')}</select>
      <label class="chk"><input type="checkbox" id="cd" ${doable ? 'checked' : ''}> only what I can craft now</label></div>
      ${oppTable(rows, {cols: ['title', 'profession', 'profit_unit', 'cost_unit', 'units_day', 'daily', 'flags']})}</div>`;
  },
  async flips() {
    const [vf, av, dip] = await Promise.all([api('/api/opps?kind=vendor_flip'), api('/api/opps?kind=ah_to_vendor&sort=profit_unit'), api('/api/opps?kind=realm_dip&sort=profit_unit')]);
    return `<div class="panel"><h2>Buy from a vendor, sell on the AH</h2><div class="hint">Vendors are checked against Questie's Forever database and filtered to your faction. Limited-stock vendors restock over time.</div>${oppTable(vf)}</div>
      <div class="panel"><h2>Buy on the AH, sell to a vendor</h2><div class="hint">Listings below what a vendor pays, at the last scan. TSM's Sniper catches these live in game.</div>${oppTable(av, {cols: ['title', 'profit_unit', 'cost_unit', 'flags']})}</div>
      <div class="panel"><h2>Cheap listings to relist</h2><div class="hint">Lowest listing under 60% of the lowest of realm market value, region market value and region average sale price. Speculative.</div>${oppTable(dip, {cols: ['title', 'profit_unit', 'cost_unit', 'flags']})}</div>`;
  },
  async gather() {
    const [zones, g] = await Promise.all([api('/api/opps?kind=fishing_spot&sort=gph&limit=600'), api('/api/opps?kind=gather&sort=profit_unit&limit=600')]);
    const fishDoable = sessionStorage.getItem('fishDoable') === '1', fishConfirmed = sessionStorage.getItem('fishConfirmed') === '1';
    const isClassic = (o) => o.flags.includes('classic_unconfirmed') ? 1 : 0;
    const fz = zones.filter((o) => (!fishDoable || o.doable) && (!fishConfirmed || !isClassic(o)))
      .sort((a, b) => (isClassic(a) - isClassic(b)) || ((b.gph || 0) - (a.gph || 0)));   // Forever data first
    return `<div class="panel"><h2>Fishing spots <small>Forever data first; Classic tables only where there is none yet</small></h2>
      <div class="hint">"Fish in …" rows are Forever data: your own catches (ForeverAngler, ForeverMoneyBridge) and Wowhead Forever counts. "Classic table: …" rows are WoW Classic 1.12 tables (cMaNGOS): <b>not Forever data</b>, often wrong for Forever (Data health shows how far off), and never in Top picks. Click a row for the fish list and every source.</div>
      <div class="controls"><label class="chk"><input type="checkbox" id="fd" ${fishDoable ? 'checked' : ''}> only spots I can fish now</label>
      <label class="chk"><input type="checkbox" id="fc" ${fishConfirmed ? 'checked' : ''}> hide Classic tables</label></div>
      ${oppTable(withPools(fz), {cols: ['title', 'profit_unit', 'gph', 'gph_pools', 'flags'], export: false, heads: {profit_unit: 'Per catch'}})}
      <div class="hint">${POOL_HINT}</div></div>
      <div class="panel"><h2>What farmed materials are worth <small>per unit: best of selling on AH, to a vendor, or crafting it</small></h2>
      <div class="hint">Set how many you gather per hour in an item's details to get gold/hour.</div>${oppTable(g, {cols: ['title', 'profession', 'profit_unit', 'units_day', 'gph', 'flags']})}</div>`;
  },
  async bags() {
    const inv = await api('/api/inventory');
    if (!inv.length) return '<div class="panel empty">No bag data yet. Syndicator saves it when you log out or /reload.</div>';
    return inv.map((c) => `<div class="panel"><h2>${esc(c.character)} <small>bags + bank worth ${money(c.total)}</small></h2>
      <div class="tablewrap"><table><thead><tr><th>Item</th><th class="num">Count</th><th>Best thing to do</th><th class="num">Each</th><th class="num">Total</th><th>Notes</th></tr></thead><tbody>
      ${c.items.map((i) => `<tr class="row" data-item="${i.item_id}"><td>${itemLink(i.item_id, i.name, i.quality)}</td><td class="num">${i.count}</td><td>${esc(i.action)}</td><td class="num">${money(i.unit_value)}</td><td class="num">${money(i.total)}</td><td>${flagHtml(i.flags)}</td></tr>`).join('')}
      </tbody></table></div></div>`).join('');
  },
  async invest() {
    const d = await api('/api/investments');
    const p = d.progression || {tiers: []};
    const tiers = p.tiers.map((t) => `<div class="tier"><div>${itemLink(t.id, t.name, 1)} <span class="pill">levels ${esc(t.levels)}</span></div>
      <div class="bar"><span style="width:${(t.share * 100).toFixed(1)}%"></span></div><div class="num">${chg(t.share, 1, false)}</div>
      <div class="num pill">${num(t.sold_per_day, 0)}/day${t.share_then !== null && t.share_then !== undefined ? ` · was ${(t.share_then * 100).toFixed(1)}%` : ''}</div></div>`).join('');
    const risk = {low: 'good', medium: 'warn', high: 'bad'};
    const rows = d.items.map((r) => {
      const t = r.trend || {};
      const span = t.scans ? `${t.scans} snapshots, ${new Date(t.from_ts * 1000).toLocaleString()} to ${new Date(t.to_ts * 1000).toLocaleString()}` : 'not enough snapshots yet';
      return `<tr class="row" data-item="${r.item_id}"><td>${itemLink(r.item_id, r.name, r.quality)} <span class="pill">${esc(r.category)}</span>
        <div class="thesis">${esc(r.thesis)}</div><div class="pill">When: ${esc(r.horizon)} · Risk: ${esc(r.risk_note)}</div>
        ${r.used_in_count ? `<div class="pill" title="${esc(r.used_in.join(', '))}">Used in ${r.used_in_count} Forever recipes</div>` : ''}</td>
        <td class="num">${money(r.buy)}<div class="pill">${num(r.listings, 0)} listed</div></td>
        <td class="num" title="Lowest listing compared with TSM's 14-day realm market value">${chg(r.vs_market)}<div class="pill">avg ${money(r.market)}</div></td>
        <td class="num" title="${esc(span)}">${chg(t.change)}</td>
        <td class="num">${chg(t.change_7d)}</td>
        <td class="num">${num(r.sold_per_day, 0)}<div class="pill">${r.sale_rate !== null && r.sale_rate !== undefined ? (r.sale_rate * 100).toFixed(0) + '% sell' : ''}</div></td>
        <td class="num" title="What you'd lose if the price fell to what a vendor pays">${chg(r.downside)}<div class="pill">vendor ${money(r.vendor_sell)}</div></td>
        <td><span class="flag ${risk[r.risk] || ''}">${esc(r.risk)} risk</span>${flagHtml(r.flags)}</td>
        <td><button class="btn" data-watch="${r.item_id}">${r.watching ? 'Watching' : 'Watch'}</button></td></tr>`;
    }).join('');
    const dropped = d.dropped.length ? `<div class="hint">Left out because the item id no longer matches its name: ${d.dropped.map((x) => `${x.id} (expected ${esc(x.expected)}, found ${esc(x.found || 'nothing')})`).join(', ')}</div>` : '';
    return `<div class="panel banner"><b>Speculation, not advice.</b> The ideas below come from how these items went in WoW Classic and from how players progress, not from Forever data, and nothing here promises a return. The prices, trends, sales and recipes shown are Forever data (TSM, this app's own price history, Forever's recipe table). Buying to resell must beat the ${num(STATE.settings.ah_cut * 100, 0)}% AH cut: the price has to rise ${(d.break_even * 100).toFixed(1)}% just to break even, before deposits.</div>
      <div class="panel"><h2>How far the server has levelled <small>each cloth tier's share of the region's cloth sales per day</small></h2>${tiers}
      <div class="hint">More Runecloth traded means more players near level 60, when raid and endgame demand starts. A rough sign only: sales mix supply and demand. ${p.then_ts ? `"was" = at the first price snapshot, ${new Date(p.then_ts * 1000).toLocaleDateString()}.` : 'A comparison over time appears after a day of price history.'}</div></div>
      <div class="panel"><h2>Candidates <small>list checked ${esc(d.checked || '?')} · price history since ${d.history_from ? new Date(d.history_from * 1000).toLocaleString() : 'none yet'}</small></h2>
      <div class="tablewrap"><table><thead><tr><th>Item and idea</th><th class="num">Buy now</th><th class="num">vs 14-day avg</th><th class="num">Trend</th><th class="num">7 days</th><th class="num">Sold/day (region)</th><th class="num">Worst case</th><th>Risk</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="hint">Trend: our own price snapshots (lowest listing); with a day or more of history each end is a 12-hour median, so one odd listing can't swing it. 7 days appears after a week. Worst case: what you'd lose if the price fell to what a vendor pays. Click a row for the item's details and price chart; Watch alerts you on big price moves.</div>${dropped}</div>`;
  },
  async search() {
    const q = sessionStorage.getItem('search') || '';
    const rows = q ? await api('/api/search?q=' + encodeURIComponent(q)) : [];
    return `<div class="panel"><h2>Every item in the game</h2><div class="controls"><input id="sq" placeholder="Item name or id…" value="${esc(q)}" style="width:320px"><button class="btn primary" id="sb">Search</button></div>
      ${rows.length ? `<div class="tablewrap"><table><thead><tr><th>Item</th><th>Type</th><th class="num">Lowest</th><th class="num">Market</th><th class="num">Listings</th><th class="num">Sold/day (region)</th><th class="num">Vendor pays</th></tr></thead><tbody>
      ${rows.map((r) => `<tr class="row" data-item="${r.id}"><td>${itemLink(r.id, r.name, r.quality)}</td><td>${esc(r.category)}</td><td class="num">${money(r.min_buyout)}</td><td class="num">${money(r.market)}</td><td class="num">${num(r.listings, 0)}</td><td class="num">${num(r.sold_per_day)}</td><td class="num">${money(r.vendor_sell)}</td></tr>`).join('')}
      </tbody></table></div>` : (q ? '<div class="empty">No items found.</div>' : '<div class="hint">Search any of the ~32,000 items. Click one to see everything about it.</div>')}</div>`;
  },
  async changes() {
    const ev = await api('/api/events');
    return `<div class="panel"><h2>What changed <small>new top picks, snipes and watchlist moves, newest first</small></h2>
      ${ev.length ? `<table><tbody>${ev.map((e) => `<tr class="row" data-item="${e.item_id || ''}"><td class="pill" style="white-space:nowrap">${new Date(e.ts * 1000).toLocaleString()}</td><td>${esc(e.text)}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">Nothing yet. Changes appear after the next TSM price update.</div>'}</div>`;
  },
  async health() {
    const [audit, scans] = await Promise.all([api('/api/audit'), api('/api/scans')]);
    const fr = STATE.freshness.map((f) => `<div class="check"><div class="st ${f.status}">${esc(f.status.toUpperCase())}</div><div><b>${esc(f.label)}</b> ${f.version ? `<span class="pill">v${esc(String(f.version).replace(/^v/, ''))}</span>` : ''}<div class="pill">${esc(f.note)}</div>
      <div class="pill">${f.data_time ? 'data from ' + ago(f.data_time) + ' · ' : ''}${f.file_time ? 'file changed ' + ago(f.file_time) + ' · ' : ''}loaded ${ago(f.loaded_at)}</div></div></div>`).join('');
    const au = audit.map((a) => `<div class="check"><div class="st ${a.status}">${esc(a.status.toUpperCase())}</div><div><b>${esc(a.name)}</b><div class="pill">${esc(a.detail)}</div>${a.examples.length ? `<ul class="examples">${a.examples.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}</div></div>`).join('');
    return `<div class="grid2"><div class="panel"><h2>Data sources <small>re-read automatically when files change</small></h2>${fr}
      <div class="controls" style="margin-top:10px"><button class="btn" id="refresh">Check for game data updates now</button></div></div>
      <div class="panel"><h2>Accuracy checks <small>cross-checks between sources</small></h2>${au}</div></div>
      <div class="panel"><h2>Price history <small>one snapshot per TSM realm scan</small></h2>${scans.length ? scans.slice(0, 30).map((s) => `<span class="flag">${new Date(s.ts * 1000).toLocaleString()}</span>`).join('') : '<div class="empty">No snapshots yet.</div>'}
      <div class="hint">How TSM numbers are used: "market value" is a 14-day average of realm <i>listings</i>; "region sold/day" and "region sale price" come from TSM users' sales records, so treat sold/day as a liquidity indicator, not an exact count.</div></div>`;
  },
  async settings() {
    const s = STATE.settings, det = STATE.detected || {}, chars = STATE.characters || {};
    const profs = ['First Aid', 'Cooking', 'Fishing', 'Skinning', 'Leatherworking', 'Herbalism', 'Mining', 'Tailoring', 'Alchemy', 'Blacksmithing', 'Engineering', 'Enchanting'];
    const auto = (k) => det[k] !== undefined ? `<span class="flag good" title="Detected from your saved addon data; your manual value is the fallback">auto: ${esc(k === 'gold' ? num(det[k], 2) + 'g' : (k === 'faction' ? (det[k] === 'H' ? 'Horde' : 'Alliance') : det[k]))}</span>` : '';
    const detProfs = det.professions || {};
    return `<div class="panel"><h2>Detected from your game <small>read from ForeverMoneyBridge and TSM when you log out or /reload</small></h2>
      <div class="controls"><label class="chk"><input type="checkbox" id="s-auto" ${s.auto_detect !== false ? 'checked' : ''}> fill in my settings automatically</label>
      <label class="chk">character <select id="s-char"><option value="">last played (${esc(STATE.active_character || 'unknown')})</option>${Object.keys(chars).map((n) => `<option ${n === s.character ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select></label>
      <label class="chk">gold counts <select id="s-gscope"><option value="faction" ${s.gold_scope !== 'character' ? 'selected' : ''}>all my characters on this faction</option><option value="character" ${s.gold_scope === 'character' ? 'selected' : ''}>only this character</option></select></label></div>
      ${Object.keys(chars).length ? `<table><thead><tr><th>Character</th><th>Level</th><th class="num">Gold</th><th>Professions</th><th>From</th></tr></thead><tbody>${Object.entries(chars).map(([n, c]) => `<tr><td>${esc(n)}</td><td>${c.level ?? '<span class="pill">needs addon</span>'}</td><td class="num">${money(c.money)}</td><td>${Object.entries(c.professions || {}).map(([p, v]) => `${esc(p)} ${v.rank}`).join(', ')}</td><td class="pill">${esc(c.source)}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">No characters detected yet.</div>'}
      <div class="hint">The ForeverMoneyBridge addon was installed into your AddOns folder. Enable it at the character screen; it saves level, gold, professions and what you loot where (with time spent). The values below are only used when nothing is detected.</div></div>
      <div class="panel"><h2>Your situation <small>manual fallback</small></h2><div class="kv">
      <div>Gold available</div><div><input type="number" step="0.01" id="s-gold" value="${s.gold}"> g ${auto('gold')}</div>
      <div>Character level</div><div><input type="number" id="s-level" value="${s.level}"> ${auto('level')}</div>
      <div>Realm (from TSM)</div><div><select id="s-realm">${(STATE.realms.length ? STATE.realms : [s.realm]).map((r) => `<option ${r === s.realm ? 'selected' : ''}>${esc(r)}</option>`).join('')}</select></div>
      <div>Faction</div><div><select id="s-faction"><option value="H" ${s.faction === 'H' ? 'selected' : ''}>Horde</option><option value="A" ${s.faction === 'A' ? 'selected' : ''}>Alliance</option></select> ${auto('faction')}</div>
      </div></div>
      <div class="panel"><h2>Professions <small>leave blank if you don't have it</small></h2><div class="kv">
      ${profs.map((p) => `<div>${p}${(s.preferred || []).includes(p) ? ' ★' : ''}</div><div><input type="number" class="s-prof" data-p="${p}" value="${s.professions[p] ?? ''}" placeholder="—"> ${det.professions ? (detProfs[p] !== undefined ? `<span class="flag good">auto: ${detProfs[p]}</span>` : (det.source === 'ForeverMoneyBridge' ? '<span class="flag">auto: not learned</span>' : '<span class="pill">not tracked by TSM; using your value</span>')) : ''}</div>`).join('')}
      </div><div class="hint">★ = preferred. Other professions only show as "worth switching" when they earn at least the switch factor more.</div></div>
      <div class="panel"><h2>Assumptions <small>change these if the numbers feel off</small></h2><div class="kv">
      <div>AH cut</div><div><input type="number" step="0.01" id="s-cut" value="${s.ah_cut}"></div>
      <div>Your share of daily sales</div><div><input type="number" step="0.05" id="s-share" value="${s.market_share}"> <span class="pill">0.2 = you expect to sell 20% of the region's tracked daily volume</span></div>
      <div>Hide items selling under</div><div><input type="number" step="0.5" id="s-minspd" value="${s.min_sold_per_day}"> per day</div>
      <div>Switch factor</div><div><input type="number" step="0.1" id="s-switch" value="${s.switch_bonus}"></div>
      <div>Fishing casts per hour</div><div><input type="number" id="s-casts" value="${s.casts_per_hour || 240}"></div>
      <div>AH sale price</div><div><select id="s-basis"><option value="min_buyout" ${s.sale_price_basis !== 'actual_sales' ? 'selected' : ''}>current lowest buyout (what you'd list at)</option><option value="actual_sales" ${s.sale_price_basis === 'actual_sales' ? 'selected' : ''}>what items actually sell for (more conservative)</option></select> <span class="pill">nothing listed: the average sale price either way</span></div>
      <div>Fishing drop rates</div><div><label class="chk"><input type="checkbox" id="s-ownrates" ${s.own_logs_for_rates ? 'checked' : ''}> also use my own catch logs</label> <span class="pill">off: Wowhead Forever's big samples only; your logs still give your pace and got-away rate</span></div>
      <div>Fishing pools</div><div><label class="chk"><input type="checkbox" id="s-pools" ${s.fishing_pools ? 'checked' : ''}> count pool loot in gold/hour</label> <span class="pill">off: open water only; trunks, Stranglekelp and Rumsey Rum from pools shown as a bonus, since pools have to be found first</span></div>
      <div>Unverified recipes</div><div><label class="chk"><input type="checkbox" id="s-unver" ${s.include_unverified_recipes ? 'checked' : ''}> include</label></div>
      <div>Desktop alerts</div><div><label class="chk"><input type="checkbox" id="s-alerts" ${s.alerts.enabled ? 'checked' : ''}> on</label> when a new pick makes at least <input type="number" id="s-alertmin" value="${s.alerts.min_daily_profit_gold}"> g/day</div>
      <div>Stale after</div><div>realm prices <input type="number" id="s-stale-r" value="${s.stale_hours.realm}"> h, region <input type="number" id="s-stale-g" value="${s.stale_hours.region}"> h</div>
      </div><div class="controls" style="margin-top:12px"><button class="btn primary" id="save">Save and recalculate</button>
      <button class="btn" id="notif">Allow browser notifications</button></div></div>`;
  },
};

async function render() {
  document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('active', b.dataset.tab === TAB));
  const view = $('#view');
  try { view.innerHTML = await VIEWS[TAB](); } catch (e) { view.innerHTML = `<div class="panel">Could not load: ${esc(e.message)}</div>`; }
  wireView();
  refreshTooltips();
}

function wireView() {
  document.querySelectorAll('#view tr.row[data-item]').forEach((tr) => { if (!tr.dataset.key) tr.onclick = (e) => { if (!e.target.closest('a') && tr.dataset.item) openItem(+tr.dataset.item); }; });
  if (TAB === 'craft') { $('#cp').onchange = (e) => { sessionStorage.setItem('craftProf', e.target.value); render(); }; $('#cd').onchange = (e) => { sessionStorage.setItem('craftDoable', e.target.checked ? '1' : ''); render(); }; }
  if (TAB === 'search') { const go = () => { sessionStorage.setItem('search', $('#sq').value); render(); }; $('#sb').onclick = go; $('#sq').onkeydown = (e) => { if (e.key === 'Enter') go(); }; $('#sq').focus(); }
  if (TAB === 'gather') { $('#fd').onchange = (e) => { sessionStorage.setItem('fishDoable', e.target.checked ? '1' : ''); render(); }; $('#fc').onchange = (e) => { sessionStorage.setItem('fishConfirmed', e.target.checked ? '1' : ''); render(); }; }
  if (TAB === 'invest') document.querySelectorAll('[data-watch]').forEach((b) => b.onclick = async (e) => {
    e.stopPropagation();
    const id = +b.dataset.watch, wl = new Set(STATE.settings.watchlist || []), on = !wl.has(id);
    if (on) wl.add(id); else wl.delete(id);
    await api('/api/settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({watchlist: [...wl]})});
    await loadState(); toast(on ? "Watching: you'll get an alert on big price moves" : 'No longer watching'); render();
  });
  if (TAB === 'health') $('#refresh').onclick = async () => { await api('/api/refresh', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'}); toast('Checking for updates…'); };
  if (TAB === 'settings') {
    $('#notif').onclick = () => Notification.requestPermission().then((p) => toast('Notifications: ' + p));
    $('#save').onclick = async () => {
      const professions = {};
      document.querySelectorAll('.s-prof').forEach((i) => { if (i.value !== '') professions[i.dataset.p] = +i.value; });
      const body = {auto_detect: $('#s-auto').checked, character: $('#s-char').value || null, gold_scope: $('#s-gscope').value, gold: +$('#s-gold').value, level: +$('#s-level').value, realm: $('#s-realm').value, faction: $('#s-faction').value, professions,
        ah_cut: +$('#s-cut').value, market_share: +$('#s-share').value, min_sold_per_day: +$('#s-minspd').value, switch_bonus: +$('#s-switch').value,
        casts_per_hour: +$('#s-casts').value, own_logs_for_rates: $('#s-ownrates').checked, sale_price_basis: $('#s-basis').value, fishing_pools: $('#s-pools').checked,
        include_unverified_recipes: $('#s-unver').checked,
        alerts: {enabled: $('#s-alerts').checked, min_daily_profit_gold: +$('#s-alertmin').value},
        stale_hours: {realm: +$('#s-stale-r').value, region: +$('#s-stale-g').value}};
      await api('/api/settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      toast('Saved. Recalculating…');
    };
  }
}

// ---------- details drawer ----------
function openDrawer(html) { $('#drawer-body').innerHTML = html; $('#drawer').classList.remove('hidden'); refreshTooltips(); }
$('#drawer-close').onclick = () => $('#drawer').classList.add('hidden');
$('#drawer').onclick = (e) => { if (e.target.id === 'drawer') $('#drawer').classList.add('hidden'); };
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') $('#drawer').classList.add('hidden'); });

function oppDetail(o) {
  const d = o.detail || {};
  let html = `<h3>${esc(o.title)} <small>${esc(KIND[o.kind] || o.kind)}</small></h3><div>${flagHtml(o.flags)}</div>
    <div class="kv" style="margin-top:8px">${['fishing_spot', 'fishing_zone', 'farm_zone'].includes(o.kind) ? '' : `<div>Profit each</div><div>${money(o.profit_unit)}</div><div>Cost each</div><div>${money(o.cost_unit)}</div>
    <div>Per day (estimate)</div><div>${num(o.units_day)} → ${money(o.daily)}/day</div>`}${o.gph ? `<div>Gold per hour</div><div>${money(o.gph)}</div>` : ''}
    ${o.needs ? `<div>Needs</div><div class="needs">${esc(o.needs)}</div>` : ''}</div>`;
  if (o.kind === 'craft') {
    html += `<h3>Ingredients <small>per craft</small></h3><table><tbody>${d.mats.map((m) => `<tr><td>${m.count}×</td><td>${itemLink(m.item_id, m.name)}</td><td class="num">${money(m.unit)}</td><td>${esc(m.source)} ${flagHtml(m.flags)}</td></tr>`).join('')}</tbody></table>
      <div class="kv" style="margin-top:8px"><div>Sells for (total)</div><div>${money(d.revenue)} via ${esc(d.sell_channel)} (${esc(d.sell_source)})</div>
      <div>Skill needed</div><div>${d.skill_required}${d.skill_exact ? '' : ' (estimated)'} ${d.thresholds ? `<span class="pill">orange/yellow/green/grey: ${d.thresholds.join(' / ')}</span>` : ''}</div>
      <div>Learn it</div><div>${d.learn ? (d.learn.how === 'trainer' ? `Trainer, ${money(d.learn.cost)}` : `${esc(d.learn.name || 'recipe')}: ${d.learn.cost !== null ? money(d.learn.cost) : 'not on AH / vendor'} (${esc(d.learn.source || '')})`) : 'unknown / already known'}</div>
      <div>Region sold/day</div><div>${num(d.sold_per_day)}</div></div>`;
  }
  if (o.kind === 'vendor_flip') {
    html += `<h3>Where to buy</h3><table><tbody>${(d.vendors || []).map((v) => `<tr><td>${esc(v.name)}</td><td>${esc(v.zone)}</td><td>${v.coords ? v.coords.map((c) => (+c).toFixed(1)).join(', ') : ''}</td><td>${v.stock ? 'stock ' + v.stock : ''}</td></tr>`).join('')}</tbody></table>
      <div class="pill">${d.vendor_count > (d.vendors || []).length ? `+${d.vendor_count - d.vendors.length} more vendors` : ''}</div>`;
  }
  if (o.kind === 'fishing_zone') {
    html += `<h3>Your catches here <small>${d.casts} casts, ${d.caught} caught, ${d.got_away} got away</small></h3><table><thead><tr><th>Fish</th><th class="num">Caught</th><th class="num">Per cast</th><th class="num">Worth each</th></tr></thead><tbody>
      ${d.fish.map((f) => `<tr class="row" data-item="${f.item_id}"><td>${itemLink(f.item_id, f.name)}</td><td class="num">${f.count}</td><td class="num">${(f.share * 100).toFixed(1)}%</td><td class="num">${money(f.value)}</td></tr>`).join('')}</tbody></table>`;
  }
  if (o.kind === 'fishing_spot') html += fishingDetail(o);
  if (o.kind === 'realm_dip') {
    html += `<div class="kv" style="margin-top:8px"><div>Lowest listing</div><div>${money(d.min_buyout)}</div><div>Realm market</div><div>${money(d.realm_market)}</div><div>Region market</div><div>${money(d.region_market)}</div><div>Region avg sale</div><div>${money(d.region_sale)}</div><div>Relist at</div><div>${money(d.relist_at)}</div></div>`;
  }
  return html;
}
const pct = (v) => (v === null || v === undefined) ? '–' : (v * 100).toFixed(v < 0.01 ? 2 : 1) + '%';
function fishingDetail(o) {
  const d = o.detail || {};
  const has = (v) => v !== null && v !== undefined;
  const src = (d.confirmed_by || []).length ? `<span class="flag good">confirmed in Forever by ${esc(d.confirmed_by.join(' and '))}</span>`
    : (d.forever ? '<span class="flag warn">Forever data, small sample</span>' : '<span class="flag bad">Classic WoW 1.12 table, not confirmed in Forever</span>');
  let h = `<div class="kv" style="margin-top:8px">
    <div>Sources</div><div>${esc((d.sources || []).join(' + '))} ${src}</div>
    ${d.forever ? `<div>Classic table used</div><div>${d.classic_spot ? `${esc(d.classic_spot)} <span class="pill">only while Forever data is thin: weighs ${(100 - d.weight * 100).toFixed(0)}%</span>` : '<span class="pill">none (no Classic table matches what is caught here in Forever)</span>'}</div>` : ''}
    ${d.subzones && d.subzones.length ? `<div>Where</div><div>${esc(d.subzones.join(', '))}</div>` : ''}
    <div>Worth per catch</div><div>${money(d.value_per_catch)} ${has(d.classic_value) ? `<span class="pill">Classic table: ${money(d.classic_value)}</span>` : ''} ${has(d.observed_value) ? `<span class="pill">Forever catches: ${money(d.observed_value)}</span>` : ''}</div>
    <div>Your catches here</div><div>${d.casts ? `${d.casts} casts, ${d.caught} caught, ${d.got_away} got away` : (d.caught ? `${d.caught} caught` : 'none logged yet')}${d.forever && !d.own_logs_used ? ' <span class="pill">used for your pace and got-away rate, not drop rates (Settings)</span>' : ''}</div>
    ${(d.pool_loot || []).length ? `<div>Pool loot</div><div>${pct(d.pool_share)} of Forever catches here were pool loot (${d.pool_loot.slice(0, 4).map((f) => esc(f.name)).join(', ')}). ${d.pools_counted ? 'Counted in gold/hour (Settings).' : `Not counted, because pools have to be found first. If you fish every pool you pass: ${money(d.value_with_pools)} per catch${d.gph_with_pools ? `, about ${money(d.gph_with_pools)}/hour before the time spent finding them` : ''}.`}</div>` : ''}
    ${d.wowhead_fished ? `<div>Wowhead Forever</div><div>${num(d.wowhead_fished, 0)} catches in this zone <span class="pill">read by hand ${esc(d.wowhead_checked)}</span> <a href="${esc(d.wowhead_url)}" target="_blank" rel="noopener">source</a></div>` : ''}
    <div>Zone skill (Classic)</div><div>${d.zone_skill ?? 'unknown'} · you: ${d.your_skill}</div>
    <div>Fish kept when hooked</div><div>${pct(d.keep)} <span class="pill">${esc(d.keep_source)}</span></div>
    <div>Catches per hour</div><div>${num(d.catches_per_hour, 0)} <span class="pill">${esc(d.pace_source === 'setting' ? `${d.casts_per_hour} casts/hour setting` : d.pace_source)}${d.landed_share ? ` · you land ${pct(d.landed_share)} of casts` : ''}</span></div>
    ${has(d.coverage) && d.coverage < 0.9 ? `<div>Classic table</div><div class="needs">explains only ${pct(d.coverage)} of catches here; the rest is unknown</div>` : ''}
    ${!o.doable ? `<div>If you had the skill</div><div>${money(d.gph_if_skilled)}/hour</div>` : ''}
  </div>`;
  if ((d.new_in_forever || []).length) h += `<div class="panel">New in Forever here (not in the Classic tables or pools): ${d.new_in_forever.map((f) => `${itemLink(f.item_id, f.name)} ×${f.count}`).join(', ')}</div>`;
  if ((d.classic_missing || []).length) h += `<div class="panel">Classic says these are common here, but you haven't caught any: ${d.classic_missing.map((f) => `${itemLink(f.item_id, f.name)} (${pct(f.classic_share)})`).join(', ')}</div>`;
  if (d.wowhead_check) h += `<div class="pill">Wowhead Forever check ${esc(d.wowhead_check.checked || '')}: ${esc((d.wowhead_check.zones || []).join(', '))}${d.wowhead_check.note ? ' · ' + esc(d.wowhead_check.note) : ''}</div>`;
  h += `<h3>Fish <small>share per catch</small></h3><table><thead><tr><th>Fish</th><th class="num">Classic</th><th class="num">Forever</th><th class="num">Used</th><th class="num">Worth each</th><th>Notes</th></tr></thead><tbody>
    ${(d.fish || []).map((f) => `<tr class="row" data-item="${f.item_id}"><td>${itemLink(f.item_id, f.name)}</td><td class="num">${pct(f.classic_share)}</td><td class="num">${has(f.observed_share) ? `${pct(f.observed_share)} <span class="pill" title="your catches / Wowhead Forever">${f.count}${f.wowhead_count ? ' / ' + num(f.wowhead_count, 0) : ''}</span>` : '–'}</td><td class="num">${pct(f.share)}</td><td class="num">${money(f.value)}</td>
      <td>${f.quest ? '<span class="flag">quest item</span>' : ''}${f.seasonal ? `<span class="flag" title="Classic season schedule">${esc(f.seasonal)}${f.in_season === false ? ' (out of season)' : (f.in_season ? ' (in season)' : '')}</span>` : ''}${(f.pools || []).length ? `<span class="flag" title="${esc(f.pools.join(', '))}">from pools</span>` : ''}</td></tr>`).join('')}</tbody></table>`;
  return h;
}
function openOpp(o) { if (!o) return; if (o.kind === 'fishing_zone' || o.kind === 'fishing_spot') { openDrawer(oppDetail(o)); wireDrawer(); return; } openItem(o.item_id, o); }

function spark(hist) {
  const pts = hist.filter((h) => h.min_buyout || h.market);
  if (pts.length < 2) return '<div class="hint">Price history builds up with every TSM scan (about hourly).</div>';
  const W = 700, H = 120, t0 = pts[0].ts, t1 = pts[pts.length - 1].ts;
  const vals = pts.flatMap((p) => [p.min_buyout, p.market, p.region_market].filter(Boolean));
  const lo = Math.min(...vals), hi = Math.max(...vals) || 1;
  const x = (t) => 6 + (W - 12) * (t - t0) / Math.max(1, t1 - t0), y = (v) => H - 8 - (H - 16) * (v - lo) / Math.max(1, hi - lo);
  const line = (k, color) => `<polyline fill="none" stroke="${color}" stroke-width="2" points="${pts.filter((p) => p[k]).map((p) => `${x(p.ts).toFixed(1)},${y(p[k]).toFixed(1)}`).join(' ')}"/>`;
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${line('region_market', '#6b7280')}${line('market', '#6ea8fe')}${line('min_buyout', '#e8c060')}</svg>
    <div class="legend"><span style="color:#e8c060">● lowest listing</span><span style="color:#6ea8fe">● realm market</span><span style="color:#9ca3af">● region market</span><span class="pill">${money(lo)} – ${money(hi)}</span></div>`;
}

async function openItem(id, opp) {
  openDrawer('<div class="empty">Loading…</div>');
  const it = await api('/api/item?id=' + id);
  const p = it.prices || {};
  const farm = (STATE.settings.farm_rates || {})[id] ?? '';
  const watching = (STATE.settings.watchlist || []).includes(id);
  let html = `<h2>${itemLink(it.id, it.name, it.quality)} <small>${esc(it.category)} · item ${it.id}</small></h2>
    <div class="controls"><a class="btn" href="${it.wowhead}" target="_blank" rel="noopener">Open on Wowhead (comments, tips)</a>
    <button class="btn" id="watch">${watching ? 'Stop watching' : 'Watch price'}</button>
    <label class="chk">I gather <input type="number" id="farmrate" value="${farm}" placeholder="—"> per hour</label> <button class="btn" id="saverate">Save</button></div>
    ${it.tip ? `<div class="panel">💡 ${esc(it.tip.summary || '')}${it.tip.source ? `<div class="pill">from ${esc(it.tip.source)}</div>` : ''}</div>` : ''}
    ${opp ? oppDetail(opp) : ''}
    <h3>Prices on your realm</h3><div class="kv">
      <div>Realistic sale price</div><div>${money(it.ah_sell)} <span class="pill">${esc(it.ah_sell_source || '')}</span> ${flagHtml(it.ah_sell_flags)}</div>
      <div>Lowest listing</div><div>${money(p.minBuyout)} (${num(p.numAuctions || 0, 0)} listings)</div>
      <div>Realm market value</div><div>${money(p.marketValue)} <span class="pill">14-day listing average</span></div>
      <div>Realm 60-day</div><div>${money(p.historical)}</div>
      <div>Region market / 60-day</div><div>${money(p.regionMarketValue)} / ${money(p.regionHistorical)}</div>
      <div>Region avg sale price</div><div>${money(p.regionSale)} <span class="pill">TSM users' sales</span></div>
      <div>Region sold/day · sale rate</div><div>${num(p.regionSoldPerDay)} · ${p.regionSalePercent !== undefined ? (p.regionSalePercent * 100).toFixed(1) + '%' : '–'}</div>
      <div>Vendor pays</div><div>${money(it.vendor_sell)}</div>
      ${it.vendor_price ? `<div>Vendor sells for</div><div>${money(it.vendor_price)}</div>` : ''}
      ${it.best_use ? `<div>Best crafting use</div><div>${money(it.best_use.value)} each via ${esc(it.best_use.profession)}: ${esc(it.best_use.recipe)}${it.best_use.doable ? '' : ' <span class="pill">(you can\'t yet)</span>'}</div>` : ''}
      <div>Required level · item level</div><div>${it.req_level ?? '–'} · ${it.item_level ?? '–'}</div>
    </div>${spark(it.history)}`;
  if (it.opportunities.length && !opp) html += `<h3>Ways to make money with it</h3>${oppTable(it.opportunities, {cols: ['title', 'profit_unit', 'daily', 'flags'], export: false})}`;
  if (it.vendors.length) html += `<h3>Sold by <small>your faction</small></h3><table><tbody>${it.vendors.slice(0, 15).map((v) => `<tr><td>${esc(v.name)}</td><td>${esc(v.zone)}</td><td>${v.coords ? v.coords.map((c) => (+c).toFixed(1)).join(', ') : ''}</td><td>${v.stock ? 'limited: ' + v.stock : ''}</td></tr>`).join('')}</tbody></table>`;
  if ((it.fished_in || []).length) html += `<h3>Where to catch it <small>share per catch; Classic rows are unconfirmed in Forever</small></h3><table><tbody>${it.fished_in.map((f) => `<tr><td>${esc(f.title)}</td><td class="num">${pct(f.share)}</td><td>${f.count ? `<span class="pill">you caught ${f.count}</span>` : ''}${flagHtml(f.flags.filter((x) => ['classic_unconfirmed', 'wowhead_forever', 'forever_only', 'seasonal', 'forever_change'].includes(x)))}</td><td class="pill">zone skill ${f.zone_skill ?? '?'}</td></tr>`).join('')}</tbody></table>`;
  if (it.drops.length) html += `<h3>Dropped by <small>NPCs from QuestieDB Forever; drop % is Wowhead <b>Classic</b> data bundled with QuestieDB, Forever may differ</small></h3><table><tbody>${it.drops.slice(0, 20).map((d) => `<tr><td>${esc(d.name)}</td><td>${esc(d.zone)}</td><td>lvl ${esc(d.level)}</td><td class="num">${d.rate ? d.rate.toFixed(1) + '%' : ''}</td></tr>`).join('')}</tbody></table>`;
  if (it.objects.length) html += `<h3>Found in</h3><table><tbody>${it.objects.map((o) => `<tr><td>${esc(o.name)}</td><td>${esc(o.zone)}</td></tr>`).join('')}</tbody></table>`;
  if (it.made_by.length) html += `<h3>Made by</h3><table><tbody>${it.made_by.map((r) => `<tr><td>${esc(r.profession)}</td><td>${esc(r.name)}${r.count !== 1 ? ' ×' + r.count : ''}</td><td>${r.mats.map((m) => `${m.count}× ${itemLink(m.item_id, m.name)}`).join(', ')}</td><td class="pill">${r.thresholds ? r.thresholds.join('/') : ''}</td></tr>`).join('')}</tbody></table>`;
  if (it.used_in.length) html += `<h3>Used in <small>${it.used_in.length} recipes</small></h3><table><tbody>${it.used_in.slice(0, 30).map((r) => `<tr class="row" data-item="${r.product_id}"><td>${esc(r.profession)}</td><td>${r.count}× → ${itemLink(r.product_id, r.product)}</td></tr>`).join('')}</tbody></table>`;
  openDrawer(html);
  $('#watch').onclick = async () => {
    const wl = new Set(STATE.settings.watchlist || []); watching ? wl.delete(id) : wl.add(id);
    await api('/api/settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({watchlist: [...wl]})});
    await loadState(); toast(watching ? 'No longer watching' : 'Watching: you\'ll get an alert on big price moves'); openItem(id, opp);
  };
  $('#saverate').onclick = async () => {
    const rates = {...(STATE.settings.farm_rates || {})}; const v = $('#farmrate').value;
    if (v === '') delete rates[id]; else rates[id] = +v;
    await api('/api/settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({farm_rates: rates})});
    toast('Saved your gather rate; gold/hour will update');
  };
  wireDrawer();
}
function wireDrawer() { document.querySelectorAll('#drawer-body tr.row[data-item]').forEach((tr) => tr.onclick = (e) => { if (!e.target.closest('a')) openItem(+tr.dataset.item); }); }

// ---------- live updates ----------
function connect() {
  const es = new EventSource('/api/stream');
  es.addEventListener('update', async (e) => {
    const data = JSON.parse(e.data);
    const rb = $('#refresh-now'); if (rb.disabled) { rb.disabled = false; rb.textContent = 'Refresh now'; toast('Refreshed. Prices are from the latest TSM download.'); }
    await loadState();
    if (!['settings', 'search'].includes(TAB)) render();
    (data.events || []).forEach((ev) => {
      toast(ev.text);
      if (ev.important && window.Notification && Notification.permission === 'granted') new Notification('WoW Forever Money', {body: ev.text});
    });
  });
  es.addEventListener('tick', async () => { await loadState(); });
  es.onerror = () => { $('#status').textContent = 'Lost connection to the app. Is it still running?'; };
}

$('#refresh-now').onclick = async () => {
  const b = $('#refresh-now'); b.disabled = true; b.textContent = 'Refreshing...';
  try { await api('/api/refresh', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'}); } catch (e) { toast('Refresh failed: ' + e.message); }
  setTimeout(() => { b.disabled = false; b.textContent = 'Refresh now'; }, 4000);
};
document.querySelectorAll('#tabs button').forEach((b) => b.onclick = () => { TAB = b.dataset.tab; localStorage.setItem('tab', TAB); render(); });
(async () => { await loadState(); await render(); connect(); })();
