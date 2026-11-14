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
const daysText = (d) => `${num(d, d < 10 ? 1 : 0)} ${Math.abs(d - 1) < 0.05 ? 'day' : 'days'}`;
const ago = (ts) => { if (!ts) return 'never'; const s = Date.now() / 1000 - ts; if (s < 90) return `${Math.round(s)}s ago`; if (s < 5400) return `${Math.round(s / 60)} min ago`; if (s < 172800) return `${(s / 3600).toFixed(1)} h ago`; return `${(s / 86400).toFixed(1)} days ago`; };
const KIND = {mob_spot: 'Mob farming', farm_zone: 'Farming spot', craft: 'Craft', vendor_flip: 'Vendor → AH', ah_to_vendor: 'AH → vendor', realm_dip: 'Cheap relist', gather: 'Farm', fishing_zone: 'Fishing spot', fishing_spot: 'Fishing spot'};
const FLAGS = {
  none_listed: ['warn', 'nothing listed now', 'No listings on your realm right now; price is the market average'],
  no_realm_data: ['warn', 'region price only', 'No realm data; using the region average'],
  sells_lower: ['warn', 'sells for less', 'Listed well above what it actually sells for (region average sale price): at the lowest buyout it may not sell. Settings can value it at actual sales instead'],
  no_sales_data: ['bad', 'no sales data', 'TSM has no recorded sales for this item'],
  above_region: ['warn', 'above region', 'Lowest listing is far above the region average'],
  slow_seller: ['bad', 'slow seller', 'Sells less often than your minimum'],
  hard_to_sell: ['bad', 'barely sells', 'Under 1 sold a day in the whole region, under 1 in 10 listings sells, or your realm already has over 10 days of the region\'s sales listed. Never suggested; open the row for the numbers'],
  slow_to_sell: ['warn', 'slow to sell', 'Under 1 in 4 listings sells: expect to relist (and pay the deposit) a few times. Ranked lower'],
  crowded: ['warn', 'crowded', 'Your realm already has over 3 days of the whole region\'s sales listed: expect undercutting and waiting. Ranked lower'],
  cant_afford: ['bad', "can't afford", 'Costs more than the gold you have set'],
  unverified_recipe: ['bad', 'unverified recipe', 'Not in SkillUpForever\'s list of obtainable recipes'],
  skill_estimated: ['', 'skill level estimated', 'Exact skill requirement unknown; estimated'],
  sell_to_vendor: ['good', 'vendor sale', 'Selling to a vendor beats the AH'],
  mat_not_listed: ['warn', 'an ingredient isn\'t listed', 'An ingredient has no listings right now'],
  limited_mat: ['warn', 'ingredient in limited stock', 'An ingredient comes from a limited-stock vendor'],
  limited_stock: ['warn', 'limited stock', 'Vendor has limited stock that restocks over time'],
  other_profession: ['', 'other profession', 'You don\'t have this profession'],
  snapshot: ['warn', 'one listing, last scan', 'Based on one listing at the last scan; check in game'],
  often_below_vendor: ['good', 'often below vendor price', 'Usually listed below vendor price'],
  risky: ['bad', 'speculative', 'Speculative: depends on prices recovering'],
  small_sample: ['warn', 'small sample', 'Not many catches/loots logged here yet'],
  vendor_price_unconfirmed: ['', 'vendor price from game files', 'Base price from the game files; open the vendor once with ForeverMoneyBridge to confirm the real price'],
  listed_far_above_sales: ['warn', 'listings far above sales', 'Every listing on your realm is over 3x what it actually sells for across the region (a wall of wishful prices): valued at the region average sale price instead of the lowest listing'],
  price_looks_off: ['warn', 'price looks off', "Only a few listings, far from the realm's recent average: valued at the recent average until more listings confirm the new price"],
  old_snapshot: ['warn', 'old Wowhead data', 'The Wowhead Forever counts for this zone are over 30 days old: re-read the zone page'],
  craft_limited_demand: ['warn', 'limited demand', 'Valued by crafting it into something whose market only absorbs a limited number per day; beyond that it is worth its sale price'],
  more_with_skill: ['', 'more with skill', "A recipe you can't make yet would make it worth more (see details); valued at what you can do now"],
  event_vendor: ['bad', 'event vendor', 'Every vendor selling it is event-only (Darkmoon Faire, holidays) or has no known location: check it is there now. Kept out of Top picks'],
  black_market: ['bad', 'black market vendor', 'Black Market agents charge more than the game-file price (e.g. Frilled Lichen: 4g 50s, not 1s 20c). Visit once to record the real price'],
  your_log: ['', 'your loot log', 'What you looted here, from ForeverMoneyBridge. No gold per hour: the time logged in a zone includes questing, travel and breaks, so it is not a farming rate'],
  assumed_rate: ['', 'casts/hour from Settings', 'Catches per hour use your casts-per-hour number in Settings, with every bite clicked in time; your own fishing time is never used, because time in a zone includes travel and breaks'],
  classic_unconfirmed: ['bad', 'Classic, unconfirmed', 'A Classic WoW 1.12 table (cMaNGOS), not Forever data. Forever often differs (see Data health). Never used in Top picks.'],
  classic_incomplete: ['warn', 'Classic table incomplete', 'The Classic table explains under 90% of catches here; the rest is unknown'],
  forever_only: ['good', 'Forever only', 'A zone Classic does not have; entirely from Forever data'],
  wowhead_forever: ['good', 'Wowhead Forever', 'Uses WoW: Forever counts (catches, drops, skins or gathers) read by hand from Wowhead Forever pages'],
  forever_change: ['warn', 'differs from Classic', 'Your Forever catches include fish Classic does not list here, or lack a common Classic fish'],
  seasonal: ['', 'seasonal', 'Part of the value is a seasonal fish (Classic schedule; Forever may differ)'],
  classic_getaway: ['warn', 'some fish get away', "Your effective fishing skill (skill + the pole, gear and lure bonus in Settings) is below what this zone needs to keep every fish, so some get away (the game's rule, with WoW Classic zone skills). A lure raises it"],
  dungeon: ['', 'dungeon', 'Inside a dungeon'],
  pools_extra: ['', 'pool loot extra', 'Pool loot (trunks, Stranglekelp, Rumsey Rum) is not in this gold/hour, because pools have to be found first. Open the row to see what pools add, or count them in Settings.'],
  contents_unknown: ['warn', 'contents unknown', 'Can be opened, but what it contains in Forever is unknown: valued as a floor. Open one with ForeverMoneyBridge enabled, or read its Wowhead Forever page'],
  open_it: ['good', 'open it', 'Worth more opened than sold (expected value of its Forever contents at current prices)'],
  locked: ['', 'locked', 'Needs Lockpicking or a key to open'],
  no_value: ['bad', 'no known value', 'No AH price, vendor price, recipe or contents known'],
  short_history: ['', 'short history', 'Under a day of our own price snapshots: the trend is first vs latest scan and can swing a lot'],
  slow_sale_rate: ['warn', 'slow to sell', 'Under 10% of listings sell (TSM region sale rate): you may wait a long time to sell'],
  skins_partial: ['warn', 'some skins not counted', 'Some skinning items are not read from Wowhead Forever yet (the row names them), so mobs that give them are worth a bit more than shown'],
  skill_classic_rule: ['', 'skill: Classic rule', 'Skinning skill per mob level uses the WoW Classic rule (level x 5 above level 20); Forever may differ'],
  assumed_kill_rate: ['', 'skins/hour from Settings', 'Gold per hour uses your skins-per-hour number in Settings (60 by default); your own skinning time is never used, because time in a zone includes questing and travel'],
  cooldown: ['', 'cooldown', 'The recipe has a cooldown in the game data (Transmute: Arcanite 47 hours, Mooncloth 95 hours): per day counts only the crafts it allows'],
  shared_cooldown: ['warn', 'shared cooldown', 'Shares one cooldown with other recipes (all Forever transmutes share Transmute - Alchemy): doing one blocks the rest, so Top picks only suggest the best of them'],
  classic_yields: ['bad', 'Classic yields', 'What a node gives comes (at least partly) from WoW Classic loot tables, not Forever data; kept out of Top picks until the Wowhead Forever pages of its herbs, ores, stones and gems (or the node itself) are read'],
  forever_yields_partial: ['warn', 'partly Forever yields', 'Some of what these nodes give is from Wowhead Forever pages read by hand, the rest still from WoW Classic tables (each item in the details says which)'],
  drops_partial: ['warn', 'only some drops counted', 'Only the drops whose Wowhead Forever item pages are read so far count (mostly materials): coins, gray items, gear and the other drops are not, so a kill is worth more than shown'],
  kills_from_settings: ['', 'kills/hour from Settings', 'Gold per hour uses the kills-per-hour number in Settings (60 by default); your own time is never used, because time in a zone includes questing and travel'],
  elite: ['warn', 'elite', 'An elite, rare elite or boss: hard to kill alone and few of them, so it is kept out of Top picks'],
  skin_extra: ['', 'skinnable', 'Can be skinned, but not with your Skinning skill (or you do not have Skinning): the skin is not counted. The row says what it would add'],
  classic_gathers: ['', 'gathers per node: Classic', 'A vein can be mined more than once before it is used up; how many times comes from the WoW Classic tables (Forever may differ). Wowhead counts each gather on its own'],
  assumed_node_rate: ['', 'nodes/hour from Settings', 'Gold per hour uses your nodes-per-hour number in Settings; your own gathering time is never used, because time in a zone includes questing and travel'],
  yield_unknown: ['warn', 'some yields unknown', 'A node here is not in the Classic tables (new in Forever?): counted as one of its herb or ore'],
  rare_nodes_extra: ['', 'rare node extra', 'Black Lotus spawns here but is rare (few of its spawn points are active at once): listed, not counted in the average'],
  not_worth_time: ['bad', 'not worth your time', 'Earns less a day than the time it takes is worth (half of what your best farming earns an hour; Settings can set your own value). Kept out of Top picks'],
  ah_price_doubtful: ['warn', 'AH price doubtful', 'Listed with no recorded sales or far above the region: counted at its sale price instead'],
};
const rankCell = (r) => `<td class="rk">${r <= 3 ? `<span class="medal m${r}" title="${['', 'Gold', 'Silver', 'Bronze'][r]}: #${r}">${r}</span>` : `<span class="rank">${r}</span>`}</td>`;
const RANK_TIP = 'Ranked by expected profit (per day; per hour for activities; per purchase for snipes) x how sure we are (data quality and how well it sells) x risk (what you would lose if it does not sell, vs the profit) x whether you can do it now. Problems such as barely selling sink a row. Click a row to see its numbers.';
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
  loadPurse();
  $('#status').textContent = `Prices from ${tsm && tsm.data_time ? ago(tsm.data_time) : '?'} · updated ${ago(STATE.generated_at)} · ${STATE.settings.realm}`;
}

async function loadPurse() {
  const el = $('#purse');
  try {
    const p = await api('/api/purse');
    const m = p.me;
    if (!m) { el.innerHTML = '<span class="pill">gold: needs Syndicator or the addon</span>'; return; }
    const extra = m.bags_bank + m.mail + m.auctions;
    el.innerHTML = `<div class="purse-gold">${money(m.money)}</div><div class="purse-sub">+ ${esc(moneyText(extra))} in items · ≈ ${esc(moneyText(m.total))} total</div>`;
    el.title = `${p.character}: ${moneyText(m.money)} gold\nBags + bank: ≈ ${moneyText(m.bags_bank)}\nMail: ≈ ${moneyText(m.mail)}\nOn the AH: ≈ ${moneyText(m.auctions)} (${m.auction_count} listings${m.expired_auctions ? `, ${m.expired_auctions} expired` : ''})\nAll ${p.all.characters} characters: ${moneyText(p.all.money)} gold, ≈ ${moneyText(p.all.total)} with items\n\n${p.note}\nClick for your bags.`;
  } catch (e) { el.innerHTML = ''; }
}
$('#purse').onclick = () => { TAB = 'bags'; localStorage.setItem('tab', TAB); render(); };

// ---------- tables ----------
function oppTable(rows, opts = {}) {
  if (!rows.length) return `<div class="empty">${esc(opts.empty || 'Nothing here right now.')}</div>`;
  const id = opts.id || 't' + Math.random().toString(36).slice(2, 7);
  const cols = (opts.rank === false ? [] : ['rank']).concat(opts.cols || ['title', 'profit_unit', 'cost_unit', 'units_day', 'daily', 'effort', 'sells', 'cooldown', 'flags'])
    .filter((c) => c !== 'cooldown' || rows.some((o) => (o.detail || {}).cooldown_hours))    // only where a row has one
    .filter((c) => c !== 'effort' || rows.some((o) => (o.detail || {}).effort));
  const ranks = opts.ranks || new Map(rows.map((o, i) => [o.key, i + 1]));
  const H = {...{title: 'What to do', profit_unit: 'Profit each', cost_unit: 'Cost each', units_day: 'Sales a day (you)', daily: 'Profit a day', profit_avg: 'At average sale', every: 'One sale every', gph: 'Gold / hour', gph_pools: 'Gold / hour with pools', sells: 'Sells (region)', cooldown: 'Cooldown', effort: 'Time a day', flags: 'Notes', profession: 'Profession', kind: 'Type'}, ...(opts.heads || {})};
  const st = sortState[id];
  const sortVal = (o) => st.k === 'rank' ? -ranks.get(o.key) : (st.k === 'sells' ? ((o.detail || {}).liquidity || {}).sold_per_day : (st.k === 'cooldown' ? (o.detail || {}).cooldown_hours : o[st.k]));
  if (st) rows = [...rows].sort((a, b) => ((sortVal(a) ?? -1e18) < (sortVal(b) ?? -1e18) ? -1 : 1) * (st.dir));
  const numeric = new Set(['profit_unit', 'cost_unit', 'units_day', 'daily', 'gph', 'gph_pools', 'sells', 'cooldown', 'profit_avg', 'every', 'effort']);
  const HT = {units_day: 'How many you can expect to sell (or make) a day: what the whole region buys a day x your share (Settings, 20%), capped by your gold, vendor stock and ingredients. Under 1 means less than one a day.',
    daily: 'Profit each x sales a day: what this earns on an average day if you keep doing it.',
    profit_unit: 'Profit on one, after the AH cut, at the current lowest listing.',
    profit_avg: "Profit on one if it sells at the region's average sale price instead of the lowest listing.",
    every: 'How long one sale takes on average at your share of the region\'s sales.',
    effort: 'Estimated minutes of play a day: posting auctions (and reposting the ones that expire), buying ingredients, crafting, one vendor trip. Below it: what that time earns per hour.',
    flags: 'Warnings and facts about this row. Hover one, or read the list under the table.', ...(opts.headTips || {})};
  const head = cols.map((c) => c === 'rank' ? `<th data-k="rank" class="rk" title="${esc(RANK_TIP)}">#</th>` : `<th data-k="${c}" class="${numeric.has(c) ? 'num' : ''}"${HT[c] ? ` title="${esc(HT[c])}"` : ''}>${H[c] || c}${HT[c] ? ' <span class="qmark">?</span>' : ''}</th>`).join('');
  const body = rows.map((o) => {
    const cells = cols.map((c) => {
      if (c === 'title') {
        const name = o.name || o.title;
        const label = ['fishing_zone', 'fishing_spot', 'skin_spot', 'herb_spot', 'mine_spot', 'farm_zone', 'mob_spot'].includes(o.kind) ? esc(o.title) : esc(o.title).replace(esc(name), itemLink(o.item_id, name, o.quality));
        return `<td>${label}${o.needs ? `<div class="needs">needs ${esc(o.needs)}</div>` : ''}${o.tip ? `<div class="pill">💡 ${esc(o.tip)}</div>` : ''}</td>`;
      }
      if (c === 'rank') return rankCell(ranks.get(o.key));
      if (c === 'cooldown') { const dd = o.detail || {}, h = dd.cooldown_hours; return h ? `<td class="num" title="${esc(dd.cooldown_group ? 'Shared cooldown: ' + dd.cooldown_group : 'Recipe cooldown from the game data')}">${h >= 1 ? num(h, 0) + ' h' : num(h * 60, 0) + ' min'}${dd.cooldown_group ? ' 🔗' : ''}<div class="pill">max ${num(24 / h, h > 12 ? 2 : 0)}/day</div></td>` : '<td class="num pill">–</td>'; }
      if (c === 'flags') return `<td>${flagHtml(o.flags)}</td>`;
      if (c === 'units_day') return `<td class="num">${o.units_day >= 1 || !o.units_day ? num(o.units_day) : `1 every ${daysText(1 / o.units_day)}`}</td>`;
      if (c === 'effort') { const ef = (o.detail || {}).effort; return ef ? `<td class="num" title="About ${ef.minutes} minutes of play a day; earns ${moneyText(ef.per_hour)} per hour of your time">~${num(ef.minutes, ef.minutes < 10 ? 1 : 0)} min<div class="pill">${esc(moneyText(ef.per_hour))}/h</div></td>` : '<td class="num pill">–</td>'; }
      if (c === 'every') return `<td class="num">${o.units_day > 0 ? (o.units_day >= 1 ? `${num(o.units_day, 1)} a day` : daysText(1 / o.units_day)) : '–'}</td>`;
      if (c === 'profit_avg') { const v = (o.detail || {}).profit_at_avg_sale; return `<td class="num">${v === undefined ? '<span class="pill">–</span>' : money(v)}</td>`; }
      if (c === 'sells') { const l = (o.detail || {}).liquidity; return l ? `<td class="num" title="${esc(l.why || 'sells well')}">${num(l.sold_per_day, 0)}/day<div class="pill">${l.sale_rate === null || l.sale_rate === undefined ? '' : (l.sale_rate * 100).toFixed(0) + '% sell · '}${l.listed} listed</div></td>` : '<td class="num pill">–</td>'; }
      if (c === 'kind') return `<td>${esc(KIND[o.kind] || o.kind)}</td>`;
      if (c === 'profession') return `<td>${esc(o.profession || '')}</td>`;
      return `<td class="num">${money(o[c])}</td>`;
    }).join('');
    return `<tr class="row ${o.doable ? '' : 'notdoable'}" data-key="${esc(o.key)}" data-item="${o.item_id}">${cells}</tr>`;
  }).join('');
  const exp = opts.export !== false ? `<button class="btn" data-export="${id}">Copy item list for TSM</button>` : '';
  setTimeout(() => wireTable(id, rows, {...opts, ranks}), 0);
  const used = [...new Set(rows.flatMap((o) => o.flags || []))].filter((f) => FLAGS[f]);
  const legend = used.length ? `<details class="how legend"><summary>What the notes in this table mean</summary><ul>${used.map((f) => `<li><span class="flag ${FLAGS[f][0]}">${esc(FLAGS[f][1])}</span> ${esc(FLAGS[f][2])}</li>`).join('')}</ul></details>` : '';
  const inner = `<div class="tablewrap"><table id="${id}"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div><div class="controls" style="margin-top:6px">${exp}<span class="pill">${rows.length} rows</span></div>${legend}`;
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

// ---------- market tab ----------
const moneyText = (c) => { if (c === null || c === undefined || isNaN(c)) return '–'; c = Math.round(c); const g = Math.floor(c / 10000), s = Math.floor(c / 100) % 100, cc = c % 100; return g ? `${g.toLocaleString()}g ${s}s` : (s ? `${s}s ${cc}c` : `${cc}c`); };
const MK = {pts: [], W: 900};
const RANGES = {'24h': 86400, '7d': 7 * 86400, '30d': 30 * 86400, all: Infinity};

function dailyCandles(pts) {
  const days = new Map();
  for (const s of pts) {
    if (s.daily && s.close > 0) { days.set('d' + s.ts, {t0: s.ts, t1: s.ts, o: s.open, h: s.high, l: s.low, c: s.close}); continue; }
    if (!(s.min_buyout > 0)) continue;
    const d = new Date(s.ts * 1000); const k = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
    const c = days.get(k);
    if (!c) days.set(k, {t0: s.ts, t1: s.ts, o: s.min_buyout, h: s.min_buyout, l: s.min_buyout, c: s.min_buyout});
    else { c.t1 = s.ts; c.h = Math.max(c.h, s.min_buyout); c.l = Math.min(c.l, s.min_buyout); c.c = s.min_buyout; }
  }
  return [...days.values()];
}

function marketChart(series, range, mode, longTerm) {
  const now = Date.now() / 1000;
  const pts = series.filter((s) => now - s.ts <= RANGES[range]);
  MK.pts = [];
  if (pts.length < 2) return '<div class="empty">Not enough snapshots in this range yet. The app saves one per TSM realm scan (about hourly) while it is running.</div>';
  const W = MK.W, padL = 8, padR = 74, top = 12, priceH = 240, volTop = 280, volH = 56, H = 360;
  const t0 = pts[0].ts, t1 = pts[pts.length - 1].ts;
  const candles = mode === 'candles' ? dailyCandles(pts) : [];
  const useCandles = candles.length >= 2;
  const vals = pts.flatMap((s) => [s.min_buyout, s.market, s.region_sale]).concat(longTerm > 0 ? [longTerm] : []).filter((v) => v > 0);
  if (!vals.length) return '<div class="empty">No prices recorded in this range.</div>';
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (hi === lo) { hi *= 1.05; lo *= 0.95; }
  const pad = (hi - lo) * 0.08; lo = Math.max(0, lo - pad); hi += pad;
  const x = (ts) => padL + (ts - t0) / ((t1 - t0) || 1) * (W - padL - padR);
  const y = (v) => top + (1 - (v - lo) / (hi - lo)) * priceH;
  const path = (k) => { let d = '', pen = false; for (const s of pts) { if (s[k] > 0) { d += `${pen ? 'L' : 'M'}${x(s.ts).toFixed(1)},${y(s[k]).toFixed(1)}`; pen = true; } else pen = false; } return d; };
  let g = '';
  for (let i = 0; i <= 4; i++) {
    const v = lo + (hi - lo) * i / 4, yy = y(v).toFixed(1);
    g += `<line x1="${padL}" x2="${W - padR}" y1="${yy}" y2="${yy}" stroke="#2a2f3a"/><text x="${W - padR + 6}" y="${(+yy + 4).toFixed(1)}" fill="#9aa3b2" font-size="11">${esc(moneyText(v))}</text>`;
  }
  const spanS = t1 - t0;
  for (let i = 0; i <= 4; i++) {
    const ts = t0 + spanS * i / 4, xx = x(ts).toFixed(1), d = new Date(ts * 1000);
    const label = spanS < 2 * 86400 ? d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}) : d.toLocaleDateString([], {month: 'short', day: 'numeric'});
    g += `<line x1="${xx}" x2="${xx}" y1="${top}" y2="${volTop + volH}" stroke="#20242c"/><text x="${xx}" y="${H - 4}" fill="#9aa3b2" font-size="11" text-anchor="middle">${esc(label)}</text>`;
  }
  const maxL = Math.max(1, ...pts.map((s) => s.num_auctions || 0));
  const bw = Math.max(1.5, (W - padL - padR) / pts.length * 0.7);
  let vol = '';
  for (const s of pts) { const hgt = (s.num_auctions || 0) / maxL * volH; vol += `<rect x="${(x(s.ts) - bw / 2).toFixed(1)}" y="${(volTop + volH - hgt).toFixed(1)}" width="${bw.toFixed(1)}" height="${hgt.toFixed(1)}" fill="#3a4150"/>`; }
  vol += `<text x="${W - padR + 6}" y="${volTop + 10}" fill="#9aa3b2" font-size="11">${maxL} listed</text>`;
  let main = '';
  if (useCandles) {
    const cw = Math.max(3, (W - padL - padR) / Math.max(candles.length, 1) * 0.55);
    for (const c of candles) {
      const cx = x((c.t0 + c.t1) / 2), col = c.c >= c.o ? '#5fcf80' : '#ef6b6b';
      main += `<line x1="${cx.toFixed(1)}" x2="${cx.toFixed(1)}" y1="${y(c.h).toFixed(1)}" y2="${y(c.l).toFixed(1)}" stroke="${col}"/>`;
      main += `<rect x="${(cx - cw / 2).toFixed(1)}" y="${y(Math.max(c.o, c.c)).toFixed(1)}" width="${cw.toFixed(1)}" height="${Math.max(1, Math.abs(y(c.o) - y(c.c))).toFixed(1)}" fill="${col}"/>`;
    }
  } else {
    main += `<path d="${path('min_buyout')}" fill="none" stroke="#e8c060" stroke-width="2"/>`;
  }
  if (longTerm > 0) main += `<line x1="${padL}" x2="${W - padR}" y1="${y(longTerm).toFixed(1)}" y2="${y(longTerm).toFixed(1)}" stroke="#b58cf0" stroke-dasharray="2 4" stroke-width="1.2"/>`;
  main += `<path d="${path('market')}" fill="none" stroke="#6ea8fe" stroke-width="1.5"/><path d="${path('region_sale')}" fill="none" stroke="#9aa3b2" stroke-width="1.2" stroke-dasharray="5 4"/>`;
  MK.pts = pts.map((s) => ({...s, x: x(s.ts)}));
  const note = mode === 'candles' && !useCandles ? '<div class="hint">Candles need at least 2 days of history; showing the line for now.</div>' : '';
  return `${note}<div class="chartwrap"><svg id="mk-svg" class="mk" viewBox="0 0 ${W} ${H}" role="img" aria-label="Price history chart">${g}${vol}${main}
    <line id="mk-cross" x1="0" x2="0" y1="${top}" y2="${volTop + volH}" stroke="#e6e6e6" stroke-opacity=".5" visibility="hidden"/>
    <rect x="${padL}" y="0" width="${W - padL - padR}" height="${H}" fill="transparent" id="mk-hit"/></svg><div id="mk-tip" class="mk-tip hidden"></div></div>
    <div class="legend"><span><b style="color:#e8c060">━</b> lowest listing${useCandles ? ' (daily candles: open, high, low, close)' : ''}</span><span><b style="color:#6ea8fe">━</b> realm 14-day average (TSM market value)</span><span><b style="color:#9aa3b2">╌</b> region average sale price</span><span><b style="color:#3a4150">█</b> listed on your realm</span>${longTerm > 0 ? '<span><b style="color:#b58cf0">┈</b> TSM long-term realm average</span>' : ''}</div>`;
}

function marketBody(d) {
  const p = d.prices || {}, s = d.sentiment, liq = d.liquidity || {};
  const range = localStorage.getItem('mkRange') || '7d', mode = localStorage.getItem('mkMode') || 'line';
  const watching = (STATE.settings.watchlist || []).includes(d.id);
  const cls = s.label === 'Bullish' ? 'up' : (s.label === 'Bearish' ? 'down' : 'flat');
  const icon = (sc) => sc === null || sc === undefined ? '<span class="pill">·</span>' : (sc > 0 ? '<span class="up">▲</span>' : (sc < 0 ? '<span class="down">▼</span>' : '<span class="pill">●</span>'));
  const stat = (label, val, sub) => `<div class="stat"><span class="pill">${label}</span><b>${val}</b>${sub ? `<span class="pill">${sub}</span>` : ''}</div>`;
  const tr = (t) => t && t.change !== null && t.change !== undefined ? chg(t.change, 1) : '<span class="pill">–</span>';
  return `<div class="panel"><h2>${itemLink(d.id, d.name, d.quality)} <button class="btn" id="mk-watch">${watching ? 'Watching' : 'Watch price'}</button> <button class="btn" id="mk-details">Full details</button></h2>
      <div class="stats">${stat('Lowest listing', money(p.numAuctions ? p.minBuyout : null), `${num(p.numAuctions || 0, 0)} listed on your realm`)}${stat('Realm 14-day average', money(p.marketValue))}${stat('Region average sale', money(p.regionSale))}
      ${stat('Sold per day (region)', num(liq.sold_per_day, 1), liq.sale_rate !== null && liq.sale_rate !== undefined ? `${(liq.sale_rate * 100).toFixed(0)}% of listings sell` : '')}${stat('Vendor pays', money(d.vendor_sell))}
      ${stat('Change', tr(d.trend_24h), `24 h · 7 d ${tr(d.trend_7d)} · all ${tr(d.trend_all)}`)}
      ${stat('TSM long-term average', money(p.historical), `realm; region ${moneyText(p.regionHistorical)}`)}${stat('TSM recent value', money(p.marketValueRecent), 'realm, from the latest scan data')}</div></div>
    <div class="grid2"><div class="panel"><h2>Price history <small>lowest listing on your realm, one snapshot per TSM scan</small></h2>
      <div class="controls seg">${Object.keys(RANGES).map((r) => `<button class="btn ${r === range ? 'active' : ''}" data-range="${r}">${r === 'all' ? 'All' : r}</button>`).join('')}
      <span style="width:12px"></span>${['line', 'candles'].map((m) => `<button class="btn ${m === mode ? 'active' : ''}" data-mode="${m}">${m === 'line' ? 'Line' : 'Candles'}</button>`).join('')}</div>
      ${marketChart(d.series || [], range, mode, p.historical)}
      <div class="hint">Every TSM scan is kept for 14 days; older days are kept as one daily candle for a year. Snapshots are only saved while the app is running.</div></div>
    <div class="panel"><h2>Market sentiment <span class="sent ${cls}">${esc(s.label)}</span></h2>
      <table><tbody>${d.signals.map((g) => `<tr><td>${icon(g.score)}</td><td><b>${esc(g.name)}</b></td><td>${esc(g.reading)}</td></tr>`).join('')}</tbody></table>
      <div class="hint">Signals from Forever data only: TSM's numbers now and this app's own price history. ▲ points up, ▼ down, ● steady, · not enough data. Overall: Bullish at +2 or more, Bearish at −2 or less (${s.signals_with_data} of ${s.signals} signals have data). It describes the market now; it is not a forecast.</div></div></div>`;
}

function wireMarket() {
  const inp = $('#mq'), list = $('#ac-list');
  let items = [], sel = -1, timer, seq = 0;
  const show = () => {
    list.innerHTML = items.map((r, i) => `<div class="ac-item ${i === sel ? 'sel' : ''}" data-i="${i}"><span class="q${r.quality}">${esc(r.name)}</span> <span class="pill">${esc(r.category || '')}${r.min_buyout ? ' · ' + esc(moneyText(r.min_buyout)) : ''}${r.sold_per_day ? ' · ' + num(r.sold_per_day, 0) + '/day' : ''}</span></div>`).join('');
    list.classList.toggle('hidden', !items.length);
    list.querySelectorAll('.ac-item').forEach((el) => el.onmousedown = (e) => { e.preventDefault(); pick(items[+el.dataset.i]); });
  };
  const pick = (r) => { sessionStorage.setItem('marketItem', r.id); render(); };
  inp.oninput = () => {
    clearTimeout(timer);
    const q = inp.value.trim();
    if (q.length < 2) { items = []; show(); return; }
    timer = setTimeout(async () => { const mine = ++seq; const res = await api('/api/search?limit=12&q=' + encodeURIComponent(q)); if (mine !== seq) return; items = res; sel = items.length ? 0 : -1; show(); }, 150);
  };
  inp.onkeydown = (e) => {
    if (e.key === 'ArrowDown') { sel = Math.min(items.length - 1, sel + 1); show(); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { sel = Math.max(0, sel - 1); show(); e.preventDefault(); }
    else if (e.key === 'Enter' && items[sel]) pick(items[sel]);
    else if (e.key === 'Escape') { items = []; show(); }
  };
  inp.onblur = () => setTimeout(() => list.classList.add('hidden'), 150);
  inp.onfocus = () => { inp.select(); if (items.length) list.classList.remove('hidden'); };
  if (!sessionStorage.getItem('marketItem')) inp.focus();
  document.querySelectorAll('[data-range]').forEach((b) => b.onclick = () => { localStorage.setItem('mkRange', b.dataset.range); render(); });
  document.querySelectorAll('[data-mode]').forEach((b) => b.onclick = () => { localStorage.setItem('mkMode', b.dataset.mode); render(); });
  const id = +sessionStorage.getItem('marketItem');
  if ($('#mk-details')) $('#mk-details').onclick = () => openItem(id);
  if ($('#mk-watch')) $('#mk-watch').onclick = async () => {
    const wl = new Set(STATE.settings.watchlist || []), on = !wl.has(id);
    if (on) wl.add(id); else wl.delete(id);
    await api('/api/settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({watchlist: [...wl]})});
    await loadState(); toast(on ? "Watching: you'll get an alert on big price moves" : 'No longer watching'); render();
  };
  const svg = $('#mk-svg'), tip = $('#mk-tip'), cross = $('#mk-cross');
  if (svg && MK.pts.length) {
    svg.onmousemove = (e) => {
      const r = svg.getBoundingClientRect(), vx = (e.clientX - r.left) / r.width * MK.W;
      let best = MK.pts[0];
      for (const pt of MK.pts) if (Math.abs(pt.x - vx) < Math.abs(best.x - vx)) best = pt;
      cross.setAttribute('x1', best.x); cross.setAttribute('x2', best.x); cross.setAttribute('visibility', 'visible');
      tip.innerHTML = `<b>${new Date(best.ts * 1000).toLocaleString()}</b><br>Lowest listing: ${esc(moneyText(best.min_buyout || null))}<br>Realm 14-day avg: ${esc(moneyText(best.market))}<br>Region avg sale: ${esc(moneyText(best.region_sale))}<br>Listed: ${best.num_auctions ?? '–'}`;
      tip.classList.remove('hidden');
      const px = best.x / MK.W * r.width;
      tip.style.left = (px > r.width / 2 ? px - tip.offsetWidth - 12 : px + 12) + 'px';
      tip.style.top = '10px';
    };
    svg.onmouseleave = () => { tip.classList.add('hidden'); cross.setAttribute('visibility', 'hidden'); };
  }
}

const GATHER = [
  {k: 'fishing', label: 'Fishing', icon: '🎣', prof: 'Fishing', type: 'secondary', what: 'Anyone can fish'},
  {k: 'skinning', label: 'Skinning', icon: '🔪', prof: 'Skinning', type: 'primary', what: 'Skin beasts you kill'},
  {k: 'herbalism', label: 'Herbalism', icon: '🌿', prof: 'Herbalism', type: 'primary', what: 'Pick herbs'},
  {k: 'mining', label: 'Mining', icon: '⛏️', prof: 'Mining', type: 'primary', what: 'Mine ore veins'},
  {k: 'mobs', label: 'Mob farming', icon: '⚔️', prof: null, type: 'anyone', what: 'Kill mobs for coins and drops'},
  {k: 'materials', label: 'Materials', icon: '📦', prof: null, type: 'worth each', what: 'What each farmed material is worth'},
];

// gold/hour if you also fish the pools you come across (open water + pool loot; time spent finding pools not included)
const withPools = (rows) => rows.map((o) => ({...o, gph_pools: o.detail && o.detail.forever ? (o.detail.gph_with_pools || o.gph) : null}));
// sections about later show what a pick earns per day once you have the gold for it
const ifAffordable = (rows) => rows.map((o) => ({...o, daily: (o.detail && o.detail.daily_if_affordable !== undefined) ? o.detail.daily_if_affordable : o.daily}));
const POOL_HINT = '"Gold / hour with pools" adds the trunks, Stranglekelp and Rumsey Rum from the pools you come across. It doesn\'t count the time spent finding pools, so treat it as a ceiling.';

// ---------- plan for today ----------
const PLAN_ICON = {cash_ah: '💰', cash_open: '📦', cash_vendor: '🪙', cooldown: '⏳', routine: '🔁', snipe: '🎯', farm: '🌿', big_flip: '💎', goal: '🎓'};
const minsText = (m) => m >= 60 ? `${num(m / 60, 1)} hour${m === 60 ? '' : 's'}` : `${num(m, m < 10 ? 1 : 0)} min`;
const PLAN_HOW = `<b>How this plan is made.</b> It works like a seasoned gold-maker's checklist. First, <b>cash in what you already have</b>: things in your bags, bank and mailbox that sell on the auction house (only as many as the market buys in about two days at your share), containers worth more opened, and junk a vendor pays for. Then <b>cooldown crafts</b> of a profession you have, your best <b>daily routines</b> (crafts and vendor flips that sell about once a day or more), a <b>snipe</b> if one was listed far below its usual price at the last scan, one <b>farming hour</b> backed by Forever data (never Classic loot tables), and one <b>occasional big flip</b>.<br><br>Each step gets a value for today: what it should earn, times how sure we are (snipes count half, because the listing may be gone), minus the minutes it takes times what your time is worth. Steps that are not worth their time are left out, each kind is limited (at most three routines and one farming hour) so the plan stays varied, and the best eight make the list. They are shown in order of <b>gold per hour of your time</b>: quick wins first, the long farming hour last. The long-term goal at the end is not ranked against the rest. Things you probably use yourself (potions, food, poisons, Flash Powder, your Skinning Knife) are never counted as things to sell.`;
function planItems(a) {
  const rows = a.items || [];
  if (!rows.length) return '';
  const n = rows.length + (a.more || 0);
  const more = a.more ? `<div class="pill">and ${a.more} more (see the My bags tab)</div>` : '';
  let head, body;
  if (a.type === 'cash_ah') {
    head = '<th>Item</th><th class="num" title="How many to list now, of how many you have">List</th><th class="num" title="Price to list each at: today\'s lowest listing, or the usual sale price where nobody pays the listing">List at</th><th class="num" title="What you get for them after the AH cut">You get</th>';
    body = rows.map((r) => `<tr><td>${itemLink(r.item_id, r.name, r.quality)}</td><td class="num">${r.count}${r.have > r.count ? ` of ${r.have}` : ''}</td><td class="num">${money(r.list_at)}</td><td class="num">${money(r.total)}</td></tr>`).join('');
  } else if (a.type === 'cash_open') {
    head = '<th>Container</th><th class="num">How many</th><th class="num" title="Expected value of the contents at today\'s prices">Worth opened</th><th>Mostly holds</th>';
    body = rows.map((r) => `<tr><td>${itemLink(r.item_id, r.name, r.quality)}${r.locked ? ' <span class="flag">locked</span>' : ''}</td><td class="num">${r.count}</td><td class="num">${money(r.total)}</td><td>${esc((r.contents || []).join(', '))}</td></tr>`).join('');
  } else {
    head = '<th>Item</th><th class="num">How many</th><th class="num" title="What a vendor pays for all of them">Vendor pays</th>';
    body = rows.map((r) => `<tr><td>${itemLink(r.item_id, r.name, r.quality)}</td><td class="num">${r.count}</td><td class="num">${money(r.total)}</td></tr>`).join('');
  }
  return `<details class="plan-items"><summary>Show the ${n} item${n === 1 ? '' : 's'}</summary><div class="tablewrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>${more}</details>`;
}
function planCard(a, goal) {
  const chip = (label, val, tip) => `<span class="chip" title="${esc(tip)}"><small>${label}</small>${val}</span>`;
  const expected = Math.round(a.gain * a.confidence);
  const chips = goal ? chip('Per day, once unlocked', money(a.gain), 'What this recipe would earn a day once you have the skill and the gold for it') : [
    chip('Expected', money(expected), `What this should earn: ${moneyText(a.gain)} if the numbers hold, times how sure we are (${Math.round(a.confidence * 100)}%).`),
    chip('Time', minsText(a.minutes), 'Estimated minutes of play, including posting and reposting auctions, buying, crafting and walking to a vendor.'),
    a.per_hour ? chip('Per hour of your time', money(a.per_hour), 'Expected gold divided by the time it takes: how well this pays for your time.') : '',
    a.gold_needed ? chip('Gold needed', money(a.gold_needed), 'Gold you spend up front (ingredients or the item to resell); you get it back when it sells.') : '',
    chip('How sure', `${Math.round(a.confidence * 100)}%`, 'How much we trust these numbers: data quality, how well it sells, and for snipes the chance the listing is gone.'),
  ].join('');
  const badge = goal ? '<span class="plan-goal-badge">🎓</span>' : (a.rank <= 3 ? `<span class="medal m${a.rank}" title="#${a.rank}">${a.rank}</span>` : `<span class="rank">${a.rank}</span>`);
  return `<div class="plan-card${goal ? ' goal' : ''}${a.rank && a.rank <= 3 ? ' top' + a.rank : ''}" data-key="${esc(a.key || '')}" data-item="${a.item_id || ''}" data-type="${esc(a.type)}">
    <div class="plan-rank">${badge}</div>
    <div class="plan-body"><div class="plan-label">${PLAN_ICON[a.type] || ''} ${esc(a.label)}</div>
      <div class="plan-title">${esc(a.title)}</div><div class="plan-why">${esc(a.why)}</div>
      <div class="plan-chips">${chips}</div>${planItems(a)}</div></div>`;
}
function planPanel(p) {
  if (!p) return '';
  const acts = p.actions || [];
  const tv = STATE.time_value_source;
  const sum = acts.length ? `About <b>${money(p.total_gain)}</b> expected for about <b>${minsText(p.total_minutes)}</b> of play, in ${acts.length} steps.` : 'Nothing is worth your time right now: check back after the next price update.';
  const gold = p.gold_needed ? ` The steps need ${money(p.gold_needed)} up front${p.short_of_gold ? `, more than the ${money(p.gold_now)} you have: do them in order and reinvest as things sell` : ` (you have ${money(p.gold_now)})`}.` : '';
  const timeNote = ` Your time is counted at ${money(p.time_value)} an hour${tv ? ` (${esc(tv)})` : ''}.`;
  const bags = p.holdings_found ? '' : '<div class="hint">⚠ Your bags are not read (needs the Syndicator addon), so the "cash in what you have" steps are missing.</div>';
  return `<div class="panel plan"><h2>Your plan for today <small>the best things to do now, quick wins first</small></h2>
    <div class="hint">${sum}${gold}${timeNote} Click a step for its full numbers.</div>${bags}
    <details class="how"><summary>How this plan is made</summary><div>${PLAN_HOW}</div></details>
    <div class="plan-list">${acts.map((a) => planCard(a)).join('')}</div>
    ${p.goal ? `<h3>Long-term goal <small>not ranked against the steps above</small></h3><div class="plan-list">${planCard(p.goal, true)}</div>` : ''}</div>`;
}
function wirePlan() {
  document.querySelectorAll('#view .plan-card').forEach((el) => el.onclick = (e) => {
    if (e.target.closest('a, details')) return;
    const k = el.dataset.key;
    if (el.dataset.type.startsWith('cash_')) { TAB = 'bags'; localStorage.setItem('tab', TAB); render(); return; }
    const row = k && Object.values(STATE.top || {}).flat().find((o) => o.key === k);
    if (row) openOpp(row); else if (+el.dataset.item) openItem(+el.dataset.item);
  });
}

// ---------- views ----------
const VIEWS = {
  async top() {
    const t = STATE.top || {};
    const e = STATE.effective, who = STATE.detected.character;
    const noProfs = !Object.keys(e.professions || {}).length;
    const tsm = (STATE.freshness || []).find((f) => f.name === 'tsm');
    const stale = tsm && tsm.status !== 'ok' ? `<div class="panel" style="border-color:#e8c060">⚠ Prices may be out of date: ${esc(tsm.note)}. Check that the TSM desktop app is running; picks below use the last prices it downloaded.</div>` : '';
    const unknown = (!who || noProfs) ? `<div class="panel" style="border-color:#e8c060">⚠ ${!who ? "Your character isn't detected yet" : 'No professions are known for your character'}, so the profession picks below are empty or incomplete. In WoW: at the character screen click <b>AddOns</b>, tick <b>ForeverMoneyBridge</b> (and "Load out of date AddOns" if it says out of date), log in and type <b>/reload</b>. The app picks it up within seconds. Or type your professions in <b>Settings</b>.</div>` : '';
    return `${stale}${unknown}
      <div class="hint">${who ? `Playing <b>${esc(who)}</b> (detected)` : 'Using your manual settings'}: ${num(e.gold, 2)}g to invest, level ${e.level}, realm ${esc(e.realm)}. Everything updates when TSM syncs or you log out / /reload. Click any row for details.</div>
      ${planPanel(STATE.plan)}
      <details class="how"><summary>How to read this page</summary><div>Every list is <b>ranked</b>: 🥇🥈🥉 mark the best three, and the order weighs expected profit, how sure the numbers are, how well the item sells, what you would lose if it doesn't sell, and whether you can do it now. <b>Click any row</b> for the full numbers and "Why it's ranked here". The coloured <b>notes</b> explain warnings: hover one to read it. <b>Per day</b> assumes you sell a realistic share of what the whole region buys each day (Settings). Prices follow your realm's lowest listing, except where nobody actually pays that.</div></details>
      <div class="panel"><h2>Daily routines <small>crafts and vendor flips you can do today: each sells about once a day or more, ranked by profit a day</small></h2>${oppTable(t.now || [])}</div>
      <div class="panel"><h2>Occasional big flips <small>worth a lot per sale, but you'd sell less than one a day</small></h2>
        <div class="hint">These sell slowly: list one and expect to wait. Each shows the profit at the lowest listing and at what it actually sells for across the region, which is often less. Ranked by profit per sale and how sure the numbers are.</div>
        ${oppTable(t.slow || [], {cols: ['title', 'profit_unit', 'profit_avg', 'cost_unit', 'every', 'sells', 'flags'], empty: 'No slow, valuable flips right now.'})}</div>
      <div class="panel"><h2>Fishing & farming spots <small>gold per hour: open water, and with the pools you come across</small></h2>${oppTable(withPools(t.hourly || []), {cols: ['title', 'profit_unit', 'gph', 'gph_pools', 'flags'], export: false, heads: {profit_unit: 'Per catch / each'}})}
        <div class="hint">${POOL_HINT}</div>
        <div class="hint">Only spots with enough Forever data appear here (Wowhead Forever counts; your own catch logs only if you turn that on in Settings). Fishing gold/hour is open water; pool loot is a bonus shown in the details. Catches per hour use ${num(STATE.settings.casts_per_hour || 240, 0)} casts/hour (Settings). All spots, including unconfirmed Classic ones, are on the Farming tab.</div></div>
      <div class="panel"><h2>Snipes <small>single cheap listings at the last scan; check them in game first</small></h2>${oppTable(t.snipes || [], {cols: ['title', 'kind', 'profit_unit', 'cost_unit', 'sells', 'flags']})}</div>
      <div class="grid2">
        <div class="panel"><h2>Unlock by levelling a profession you have</h2>${oppTable(ifAffordable(t.level_up || []), {cols: ['title', 'profit_unit', 'daily', 'sells', 'cooldown', 'flags'], heads: {daily: 'Per day (with the gold)'}, empty: noProfs ? 'No professions known yet: see the note at the top.' : 'Nothing worth it a few skill points away right now.'})}</div>
        <div class="panel"><h2>Worth switching professions for <small>at least ${num(STATE.settings.switch_bonus, 1)}× your best</small></h2>${oppTable(ifAffordable(t.switch || []), {cols: ['title', 'profession', 'daily', 'sells', 'cooldown', 'flags'], heads: {daily: 'Per day (with the gold)'}, empty: 'No other profession beats yours by enough right now.'})}</div>
      </div>`;
  },
  async craft() {
    const profs = STATE.professions_available.filter((p) => !/Racial|Riding|Test|Poison|Swim|Lockpick|Compreh|Survival|Horseman|Piloting/.test(p));
    const sel = sessionStorage.getItem('craftProf') || '';
    const doable = sessionStorage.getItem('craftDoable') === '1';
    const sellsOnly = sessionStorage.getItem('sellsOnly') !== '0';
    const rows = await api(`/api/opps?kind=craft&profession=${encodeURIComponent(sel)}&doable=${doable ? 1 : ''}&hide=${sellsOnly ? 'hard_to_sell,no_sales_data' : ''}&limit=800`);
    return `<div class="panel"><h2>Crafting profit <small>ingredients bought at the cheapest of vendor / AH; product sold at the better of AH (after cut) / vendor</small></h2>
      <div class="controls"><select id="cp"><option value="">All professions</option>${[...new Set(profs)].map((p) => `<option ${p === sel ? 'selected' : ''}>${esc(p)}</option>`).join('')}</select>
      <label class="chk"><input type="checkbox" id="cd" ${doable ? 'checked' : ''}> only what I can craft now</label>
      <label class="chk" title="Hides items that barely sell: under 1 a day in the whole region, under 1 in 10 listings selling, or over 10 days of sales already listed on your realm"><input type="checkbox" class="sells-only" ${sellsOnly ? 'checked' : ''}> hide items that barely sell</label></div>
      ${oppTable(rows, {cols: ['title', 'profession', 'profit_unit', 'cost_unit', 'units_day', 'daily', 'effort', 'sells', 'cooldown', 'flags']})}</div>`;
  },
  async flips() {
    const sellsOnly = sessionStorage.getItem('sellsOnly') !== '0', hide = sellsOnly ? '&hide=hard_to_sell,no_sales_data' : '';
    const [vf, av, dip] = await Promise.all([api('/api/opps?kind=vendor_flip' + hide), api('/api/opps?kind=ah_to_vendor'), api('/api/opps?kind=realm_dip' + hide)]);
    return `<div class="controls"><label class="chk"><input type="checkbox" class="sells-only" ${sellsOnly ? 'checked' : ''}> hide items that barely sell</label></div><div class="panel"><h2>Buy from a vendor, sell on the AH</h2><div class="hint">Vendors are checked against Questie's Forever database and filtered to your faction. Limited-stock vendors restock over time.</div>${oppTable(vf)}</div>
      <div class="panel"><h2>Buy on the AH, sell to a vendor</h2><div class="hint">Listings below what a vendor pays, at the last scan. TSM's Sniper catches these live in game.</div>${oppTable(av, {cols: ['title', 'profit_unit', 'cost_unit', 'flags']})}</div>
      <div class="panel"><h2>Cheap listings to relist</h2><div class="hint">Lowest listing under 60% of the lowest of realm market value, region market value and region average sale price. Speculative.</div>${oppTable(dip, {cols: ['title', 'profit_unit', 'cost_unit', 'flags']})}</div>`;
  },
  async gather() {
    const profs = (STATE.effective || {}).professions || {};
    const has = (p) => p && profs[p] !== undefined;
    const sel = sessionStorage.getItem('gatherSel') || (GATHER.find((g) => has(g.prof)) || GATHER[0]).k;
    const g = GATHER.find((x) => x.k === sel) || GATHER[0];
    const pills = GATHER.map((x) => `<button class="gpill ${x.k === sel ? 'active' : ''}" data-gsel="${x.k}" title="${esc(x.what)}"><span class="gicon">${x.icon}</span><span>${x.label}<small>${x.type}</small></span>${has(x.prof) ? `<span class="gskill" title="your skill">${profs[x.prof]}</span>` : ''}</button>`).join('');
    const intro = `<div class="panel"><h2>Gathering <small>where your time earns the most, per hour</small></h2>
      <div class="hint">You can learn <b>two primary professions</b>: gathering ones (Herbalism, Mining, Skinning) or crafting ones (Alchemy, Blacksmithing, Enchanting, Engineering, Leatherworking, Tailoring). The <b>secondary professions</b> (Fishing, Cooking, First Aid) are open to everyone on top of those. Pick an activity; a number on the button is your skill.</div>
      <div class="gpills">${pills}</div></div>`;
    const how = (text) => `<details class="how"><summary>How this is worked out</summary><div>${text}</div></details>`;
    const measured = async (act) => (await api('/api/opps?kind=farm_zone&limit=200')).filter((o) => (o.detail || {}).activity === act);
    const doable = sessionStorage.getItem('gatherDoable') === '1';
    const onlyDoable = (rows) => doable ? rows.filter((o) => o.doable) : rows;
    const doableBox = `<label class="chk"><input type="checkbox" id="gd" ${doable ? 'checked' : ''}> only what I can do now</label>`;
    const measuredPanel = (rows, what) => rows.length ? `<div class="panel"><h2>Measured by your addon <small>real time and loot from ForeverMoneyBridge: the most reliable numbers here</small></h2>${oppTable(rows, {cols: ['title', 'profit_unit', 'gph', 'flags'], export: false, heads: {profit_unit: `Per ${what}`}})}</div>` : '';
    let body = '';
    if (sel === 'fishing') {
      const zones = await api('/api/opps?kind=fishing_spot&limit=600');
      const fishConfirmed = sessionStorage.getItem('fishConfirmed') === '1';
      const isClassic = (o) => o.flags.includes('classic_unconfirmed') ? 1 : 0;
      const fz = onlyDoable(zones).filter((o) => !fishConfirmed || !isClassic(o))
        .sort((a, b) => (isClassic(a) - isClassic(b)) || ((b.score || 0) - (a.score || 0)));   // Forever data first, then rank
      body = `<div class="panel"><h2>Fishing spots <small>Forever data first; Classic tables only where there is none yet</small></h2>
        ${how('"Fish in …" rows are Forever data: Wowhead Forever catch counts and your own logs. "Classic table: …" rows are WoW Classic 1.12 tables (cMaNGOS): <b>not Forever data</b>, often different in Forever (Data health shows how much), never in Top picks. Gold/hour = worth per catch × catches per hour (your measured pace, else the casts/hour setting). Pools are a bonus column, since you have to find them first.')}
        <div class="controls">${doableBox}<label class="chk"><input type="checkbox" id="fc" ${fishConfirmed ? 'checked' : ''}> hide Classic tables</label></div>
        ${oppTable(withPools(fz), {cols: ['title', 'profit_unit', 'gph', 'gph_pools', 'flags'], export: false, heads: {profit_unit: 'Per catch'}})}
        <div class="hint">${POOL_HINT}</div></div>`;
    } else if (sel === 'skinning') {
      const [m, spots] = await Promise.all([measured('skinning'), api('/api/opps?kind=skin_spot&limit=200')]);
      body = measuredPanel(m, 'skin') + `<div class="panel"><h2>Skinning spots <small>Wowhead Forever skinning counts</small></h2>
        ${how(`Per zone: the mobs you can skin (Classic skill rule: level × 5 above level 20) and kill (up to 3 levels above you), weighted by how often each was skinned in Forever. Gold/hour = value per skin × skins per hour (${num(STATE.settings.kills_per_hour || 60, 0)} from Settings until your addon has 10+ minutes of skinning). Only leathers and Light/Medium Hide were read from Wowhead so far, so values are a floor.`)}
        <div class="controls">${doableBox}</div>${oppTable(onlyDoable(spots), {cols: ['title', 'profit_unit', 'gph', 'flags'], export: false, heads: {profit_unit: 'Per skin'}, empty: 'No skinning data yet.'})}</div>`;
    } else if (sel === 'herbalism' || sel === 'mining') {
      const kind = sel === 'herbalism' ? 'herb_spot' : 'mine_spot';
      const [m, spots] = await Promise.all([measured(sel), api(`/api/opps?kind=${kind}&limit=200`)]);
      body = measuredPanel(m, 'node') + `<div class="panel"><h2>${g.label} spots <small>where the nodes are (Forever) and what a node gives (Classic, until measured)</small></h2>
        ${how(`Node locations come from QuestieDB's Forever data. What one node gives comes from <b>Wowhead Forever</b> pages read by hand where they are read (an ore's or herb's "Mined from" / "Gathered from" counts, or the node's own page), and from the <b>WoW Classic</b> loot tables (cMaNGOS) for the rest; a spot with any Classic part is labelled and kept out of Top picks. How many times a vein can be gathered comes from the Classic tables. Black Lotus is listed but left out of the per-node average: it has many spawn points but few active at once. Gold/hour = value per node × nodes per hour (${num(STATE.settings[sel === 'herbalism' ? 'herb_nodes_per_hour' : 'ore_nodes_per_hour'] || 40, 0)} from Settings until measured). Skill per node uses the Classic table.`)}
        <div class="controls">${doableBox}</div>${oppTable(onlyDoable(spots), {cols: ['title', 'profit_unit', 'gph', 'flags'], export: false, heads: {profit_unit: 'Per node'}, empty: 'No node data yet.'})}</div>`;
    } else if (sel === 'mobs') {
      const [m, mobs] = await Promise.all([measured('mobs'), api('/api/opps?kind=mob_spot&limit=300')]);
      body = `<div class="panel"><h2>Mob farming <small>Wowhead Forever drop counts</small></h2>
        ${how(`One row per mob. Value per kill = for each drop, how often it dropped in Forever (Wowhead's "Dropped by" counts: drops / times looted) × its average stack × what it is worth to you, plus a skin if you can skin it (Classic skill rule: level × 5 above level 20). Only drops whose Wowhead Forever item pages are read count so far (materials first), so coins, gray items and gear are missing and every value is a floor. Gold/hour = value per kill × kills per hour (${num(STATE.settings.kills_per_hour || 60, 0)} from Settings). Mobs up to 3 levels above you count as doable. Elites, bosses, dungeon mobs and mobs looted fewer than 50 times stay out of Top picks.`)}
        <div class="controls">${doableBox}</div>${oppTable(onlyDoable(mobs), {cols: ['title', 'profit_unit', 'gph', 'flags'], export: false, heads: {profit_unit: 'Per kill'}, empty: 'No Wowhead Forever drop counts read yet.'})}</div>`
        + (m.length ? `<div class="panel"><h2>Your loot log <small>what ForeverMoneyBridge saw you loot: a log, never a rate</small></h2>${oppTable(m, {cols: ['title', 'profit_unit', 'flags'], export: false})}</div>` : '');
    } else {
      const rows = await api('/api/opps?kind=gather&limit=600');
      body = `<div class="panel"><h2>What farmed materials are worth <small>per unit: best of selling on AH, to a vendor, or crafting it</small></h2>
        ${how('Each material is valued at the best of: the AH (lowest listing after the cut, or what it actually sells for if listings are far above sales), a vendor, or a recipe you can make with it. Set how many you gather per hour in an item\'s details to get gold/hour.')}
        ${oppTable(rows, {cols: ['title', 'profession', 'profit_unit', 'units_day', 'gph', 'flags']})}</div>`;
    }
    return intro + body;
  },
  async bags() {
    const inv = await api('/api/inventory');
    if (!inv.length) return '<div class="panel empty">No bag data yet. Syndicator saves it when you log out or /reload.</div>';
    return inv.map((c) => `<div class="panel"><h2>${esc(c.character)} <small>bags + bank worth ${money(c.total)}</small></h2>
      <div class="tablewrap"><table><thead><tr><th class="rk">#</th><th>Item</th><th class="num">Count</th><th>Best thing to do</th><th class="num">Each</th><th class="num">Total</th><th>Notes</th></tr></thead><tbody>
      ${c.items.map((i, n) => `<tr class="row" data-item="${i.item_id}">${rankCell(n + 1)}<td>${itemLink(i.item_id, i.name, i.quality)}</td><td class="num">${i.count}</td><td>${esc(i.action)}</td><td class="num">${money(i.unit_value)}</td><td class="num">${money(i.total)}</td><td>${flagHtml(i.flags)}</td></tr>`).join('')}
      </tbody></table></div></div>`).join('');
  },
  async invest() {
    const d = await api('/api/investments');
    const p = d.progression || {tiers: []};
    const tiers = p.tiers.map((t) => `<div class="tier"><div>${itemLink(t.id, t.name, 1)} <span class="pill">levels ${esc(t.levels)}</span></div>
      <div class="bar"><span style="width:${(t.share * 100).toFixed(1)}%"></span></div><div class="num">${chg(t.share, 1, false)}</div>
      <div class="num pill">${num(t.sold_per_day, 0)}/day${t.share_then !== null && t.share_then !== undefined ? ` · was ${(t.share_then * 100).toFixed(1)}%` : ''}</div></div>`).join('');
    const risk = {low: 'good', medium: 'warn', high: 'bad'};
    const rows = d.items.map((r, i) => {
      const t = r.trend || {};
      const span = t.scans ? `${t.scans} snapshots, ${new Date(t.from_ts * 1000).toLocaleString()} to ${new Date(t.to_ts * 1000).toLocaleString()}` : 'not enough snapshots yet';
      return `<tr class="row" data-item="${r.item_id}">${rankCell(i + 1)}<td>${itemLink(r.item_id, r.name, r.quality)} <span class="pill">${esc(r.category)}</span>
        <div class="thesis">${esc(r.thesis)}</div><div class="pill">When: ${esc(r.horizon)} · Risk: ${esc(r.risk_note)}</div>
        ${r.used_in_count ? `<div class="pill" title="${esc(r.used_in.join(', '))}">Used in ${r.used_in_count} Forever recipes</div>` : ''}</td>
        <td class="num">${money(r.buy)}<div class="pill">${num(r.listings, 0)} listed</div></td>
        <td class="num" title="Lowest listing compared with TSM's 14-day realm market value">${chg(r.vs_market)}<div class="pill">avg ${money(r.market)}</div></td>
        <td class="num" title="Buy price now compared with TSM's long-term realm average: below it is cheaper than usual">${chg(r.vs_long_term)}<div class="pill">avg ${money(r.long_term)}</div></td>
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
      <div class="tablewrap"><table><thead><tr><th class="rk" title="Ranked by how cheap it is vs its long-term average x how well it sells x risk">#</th><th>Item and idea</th><th class="num">Buy now</th><th class="num">vs 14-day avg</th><th class="num">vs long-term avg</th><th class="num">Trend</th><th class="num">7 days</th><th class="num">Sold/day (region)</th><th class="num">Worst case</th><th>Risk</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="hint">Trend: our own price snapshots (lowest listing); with a day or more of history each end is a 12-hour median, so one odd listing can't swing it. 7 days appears after a week. Worst case: what you'd lose if the price fell to what a vendor pays. Click a row for the item's details and price chart; Watch alerts you on big price moves.</div>${dropped}</div>`;
  },
  async market() {
    const id = +(sessionStorage.getItem('marketItem') || 0);
    let d = null;
    if (id) { try { d = await api('/api/market?id=' + id); } catch (e) { sessionStorage.removeItem('marketItem'); } }
    return `<div class="panel"><h2>Market <small>search any item: price history, trend and market signals</small></h2>
      <div class="ac"><input id="mq" placeholder="Type an item name…" autocomplete="off" spellcheck="false" value="${d ? esc(d.name) : ''}"><div id="ac-list" class="ac-list hidden"></div></div></div>
      ${d ? marketBody(d) : '<div class="empty">Start typing an item name, then pick it from the list (arrow keys and Enter work too).</div>'}`;
  },
  async search() {
    const q = sessionStorage.getItem('search') || '';
    const rows = q ? await api('/api/search?q=' + encodeURIComponent(q)) : [];
    return `<div class="panel"><h2>Every item in the game</h2><div class="controls"><input id="sq" placeholder="Item name or id…" value="${esc(q)}" style="width:320px"><button class="btn primary" id="sb">Search</button></div>
      ${rows.length ? `<div class="tablewrap"><table><thead><tr><th class="rk">#</th><th>Item</th><th>Type</th><th class="num">Lowest</th><th class="num">Market</th><th class="num">Listings</th><th class="num">Sold/day (region)</th><th class="num">Vendor pays</th></tr></thead><tbody>
      ${rows.map((r, n) => `<tr class="row" data-item="${r.id}">${rankCell(n + 1)}<td>${itemLink(r.id, r.name, r.quality)}</td><td>${esc(r.category)}</td><td class="num">${money(r.min_buyout)}</td><td class="num">${money(r.market)}</td><td class="num">${num(r.listings, 0)}</td><td class="num">${num(r.sold_per_day)}</td><td class="num">${money(r.vendor_sell)}</td></tr>`).join('')}
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
      <div>Hide items selling under</div><div><input type="number" step="0.5" id="s-minspd" value="${s.min_sold_per_day}"> per day <span class="pill">in the whole region; never below 1. Items where under 1 in 10 listings sells, or with over 10 days of sales already listed on your realm, are never suggested either</span></div>
      <div>Switch factor</div><div><input type="number" step="0.1" id="s-switch" value="${s.switch_bonus}"></div>
      <div>Fishing casts per hour</div><div><input type="number" id="s-casts" value="${s.casts_per_hour || 240}"></div>
      <div>Fishing skill bonus</div><div><input type="number" id="s-fbonus" placeholder="auto" value="${s.fishing_skill_bonus ?? ''}"> <span class="pill">leave empty to work it out from your bags, bank and gear (best pole + best lure + fishing hat and boots); type a number to override. Fewer fish get away when your skill plus this beats the zone's skill</span></div>
      <div>Herb nodes per hour</div><div><input type="number" id="s-hph" value="${s.herb_nodes_per_hour || 40}"> <span class="pill">until ForeverMoneyBridge has 10+ minutes of your herbalism</span></div>
      <div>Ore nodes per hour</div><div><input type="number" id="s-oph" value="${s.ore_nodes_per_hour || 40}"> <span class="pill">until ForeverMoneyBridge has 10+ minutes of your mining</span></div>
      <div>Your time is worth</div><div><input type="number" step="0.5" id="s-tv" value="${s.time_value_gold || ''}" placeholder="auto"> gold an hour <span class="pill">blank = half your best measured farming. Routines that earn less than their time is worth are marked "not worth your time"</span></div>
      <div>Kills per hour</div><div><input type="number" id="s-kph" value="${s.kills_per_hour || 60}"> <span class="pill">mobs you kill (and skin) in an hour of farming: used for skinning and mob farming gold per hour</span></div>
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
  wirePlan();
  refreshTooltips();
}

function wireView() {
  document.querySelectorAll('#view tr.row[data-item]').forEach((tr) => { if (!tr.dataset.key) tr.onclick = (e) => { if (!e.target.closest('a') && tr.dataset.item) openItem(+tr.dataset.item); }; });
  if (TAB === 'craft') { $('#cp').onchange = (e) => { sessionStorage.setItem('craftProf', e.target.value); render(); }; $('#cd').onchange = (e) => { sessionStorage.setItem('craftDoable', e.target.checked ? '1' : ''); render(); }; }
  document.querySelectorAll('.sells-only').forEach((c) => c.onchange = (e) => { sessionStorage.setItem('sellsOnly', e.target.checked ? '1' : '0'); render(); });
  if (TAB === 'market') wireMarket();
  if (TAB === 'search') { const go = () => { sessionStorage.setItem('search', $('#sq').value); render(); }; $('#sb').onclick = go; $('#sq').onkeydown = (e) => { if (e.key === 'Enter') go(); }; $('#sq').focus(); }
  if (TAB === 'gather') {
    document.querySelectorAll('[data-gsel]').forEach((b) => b.onclick = () => { sessionStorage.setItem('gatherSel', b.dataset.gsel); render(); });
    if ($('#gd')) $('#gd').onchange = (e) => { sessionStorage.setItem('gatherDoable', e.target.checked ? '1' : ''); render(); };
    if ($('#fc')) $('#fc').onchange = (e) => { sessionStorage.setItem('fishConfirmed', e.target.checked ? '1' : ''); render(); };
  }
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
        casts_per_hour: +$('#s-casts').value, fishing_skill_bonus: $('#s-fbonus').value === '' ? null : +$('#s-fbonus').value, kills_per_hour: +$('#s-kph').value, time_value_gold: $('#s-tv').value === '' ? null : +$('#s-tv').value, herb_nodes_per_hour: +$('#s-hph').value, ore_nodes_per_hour: +$('#s-oph').value, own_logs_for_rates: $('#s-ownrates').checked, sale_price_basis: $('#s-basis').value, fishing_pools: $('#s-pools').checked,
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
  const notes = (o.flags || []).filter((f) => FLAGS[f]);
  let html = `<h3>${esc(o.title)} <small>${esc(KIND[o.kind] || o.kind)}</small></h3>${notes.length ? `<ul class="notes">${notes.map((f) => `<li><span class="flag ${FLAGS[f][0]}">${esc(FLAGS[f][1])}</span> ${esc(FLAGS[f][2])}</li>`).join('')}</ul>` : ''}
    <div class="kv" style="margin-top:8px">${['fishing_spot', 'fishing_zone', 'farm_zone', 'skin_spot', 'herb_spot', 'mine_spot', 'mob_spot'].includes(o.kind) ? '' : `<div>Profit each</div><div>${money(o.profit_unit)}</div><div>Cost each</div><div>${money(o.cost_unit)}</div>
    <div>Per day (estimate)</div><div>${num(o.units_day)} → ${money(o.daily)}/day</div>`}${o.gph ? `<div>Gold per hour</div><div>${money(o.gph)}</div>` : ''}
    ${o.needs ? `<div>Needs</div><div class="needs">${esc(o.needs)}</div>` : ''}</div>`;
  const ef = d.effort;
  if (ef) html += `<h3>Your time</h3><div class="kv"><div>About</div><div>${num(ef.minutes, 1)} minutes a day (${num(ef.posts, 0)} auction posts incl. reposts, ingredients, crafting, a vendor trip: estimates)</div><div>Earns</div><div>${money(ef.per_hour)} per hour of your time</div><div>Your time is worth</div><div>${money(ef.time_value)} an hour <span class="pill">half your best measured farming; change it in Settings</span></div></div>`;
  const rk = d.rank;
  if (rk) {
    const f = (v) => `×${(+v).toFixed(2)}`;
    html += `<h3>Why it's ranked here</h3><div class="kv"><div>Starts from</div><div>${money(rk.base)} ${esc(rk.basis)}</div>
      <div>How sure we are</div><div>${f(rk.confidence)} <span class="pill">data quality and how well it sells (the notes)</span></div>
      <div>Risk</div><div>${f(rk.risk)} <span class="pill">${rk.downside ? `you'd lose up to ${moneyText(rk.downside)} each if it doesn't sell` : 'little to lose'}</span></div>
      <div>Can you do it now</div><div>${f(rk.doable)}</div>
      ${rk.problems.length ? `<div>Problems</div><div>×0.20 <span class="pill">${rk.problems.map((p) => esc((FLAGS[p] || ['', p])[1])).join(', ')}</span></div>` : ''}
      ${rk.preferred > 1 ? '<div>Preferred profession</div><div>×1.10</div>' : ''}
      <div>Score</div><div><b>${money(rk.score)}</b></div></div>`;
  }
  const liq = d.liquidity;
  if (liq) html += `<h3>How well it sells <small>TSM, whole Forever EU region</small></h3><div class="kv"><div>Sold per day</div><div>${num(liq.sold_per_day, 1)}</div>
    <div>Listings that sell</div><div>${liq.sale_rate === null || liq.sale_rate === undefined ? '–' : (liq.sale_rate * 100).toFixed(0) + '%'}</div>
    <div>Listed on your realm</div><div>${liq.listed}${liq.days_of_supply !== null && liq.days_of_supply !== undefined ? ` (${num(liq.days_of_supply, 1)} days of the region's sales)` : ''}</div></div>${liq.why ? `<div class="hint">${esc(liq.why)}</div>` : ''}`;
  if (o.kind === 'craft') {
    html += `<h3>Ingredients <small>per craft</small></h3><table><tbody>${d.mats.map((m) => `<tr><td>${m.count}×</td><td>${itemLink(m.item_id, m.name)}</td><td class="num">${money(m.unit)}</td><td>${esc(m.source)} ${flagHtml(m.flags)}</td></tr>`).join('')}</tbody></table>
      <div class="kv" style="margin-top:8px"><div>Sells for (total)</div><div>${money(d.revenue)} via ${esc(d.sell_channel)} (${esc(d.sell_source)})</div>
      <div>Skill needed</div><div>${d.skill_required}${d.skill_exact ? '' : ' (estimated)'} ${d.thresholds ? `<span class="pill">orange/yellow/green/grey: ${d.thresholds.join(' / ')}</span>` : ''}</div>
      <div>Learn it</div><div>${d.learn ? (d.learn.how === 'trainer' ? `Trainer, ${money(d.learn.cost)}` : `${esc(d.learn.name || 'recipe')}: ${d.learn.cost !== null ? money(d.learn.cost) : 'not on AH / vendor'} (${esc(d.learn.source || '')})`) : 'unknown / already known'}</div>
      <div>Region sold/day</div><div>${num(d.sold_per_day)}</div>
      ${d.cooldown_hours ? `<div>Cooldown</div><div>${num(d.cooldown_hours, 1)} hours (game data): at most ${num(24 / d.cooldown_hours, 2)} a day${d.cooldown_group ? `<div class="needs">Shared with ${d.cooldown_shared_with} other recipes (${esc(d.cooldown_group)}): doing any of them starts this cooldown too</div>` : ''}</div>` : ''}</div>`;
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
  if (o.kind === 'herb_spot' || o.kind === 'mine_spot') {
    html += `<div class="kv" style="margin-top:8px"><div>Nodes in this zone</div><div>${num(d.node_count, 0)} spawn points</div><div>Nodes per hour</div><div>${num(d.nodes_per_hour, 0)} <span class="pill">${esc(d.pace_source)}</span></div><div>Sources</div><div class="pill">${esc(d.source)}</div></div>
      <h3>Nodes here <small>value per node at current prices</small></h3><table><thead><tr><th>Node</th><th class="num">Spawns</th><th class="num">Skill</th><th class="num">Per node</th><th>Gives (per node)</th></tr></thead><tbody>
      ${d.nodes.map((n) => `<tr><td>${esc(n.name)}${n.rare ? ' <span class="pill">rare, not averaged</span>' : ''}${n.can ? '' : ' <span class="needs">need skill</span>'}</td><td class="num">${n.count}</td><td class="num">${n.skill ?? '?'}</td><td class="num">${money(n.value)}</td>
        <td>${n.items.map((i) => `${itemLink(i.item_id, i.name)} ×${num(i.per_node, 2)}${i.source === 'forever' ? '' : ` <span class="pill" title="${i.source === 'classic' ? 'From the WoW Classic node loot table, not Forever data' : 'Not in any table: counted as one of its herb or ore'}">${i.source === 'classic' ? 'Classic' : 'assumed'}</span>`}`).join(', ')}</td></tr>`).join('')}</tbody></table>
      <p class="note">Items without a label come from Wowhead Forever pages read by hand: what each gather gave, over all gathers Wowhead counted${d.nodes.some((n) => n.gathers_per_node !== 1) ? ', times the gathers a node allows (WoW Classic number)' : ''}. Items labelled Classic come from the WoW Classic node loot table and keep this spot out of Top picks until their Forever pages are read.</p>`;
  }
  if (o.kind === 'skin_spot') {
    html += `<div class="kv" style="margin-top:8px"><div>Mob levels</div><div>${esc(d.levels)}</div><div>Skins per hour</div><div>${num(d.skins_per_hour, 0)} <span class="pill">${esc(d.pace_source)}</span></div>
      <div>Forever skins counted</div><div>${num(d.skins, 0)} <span class="pill">${esc(d.source)}</span></div>
      ${(d.skins_not_read || []).length ? `<div>Not read yet</div><div>${d.skins_not_read.map(esc).join(', ')} <span class="pill">mobs that give these are worth a bit more than shown</span></div>` : ''}</div>
      <h3>Mobs here <small>value per skin at current prices</small></h3><table><thead><tr><th>Mob</th><th>Level</th><th class="num">Skinned</th><th class="num">Per skin</th><th>Gives</th></tr></thead><tbody>
      ${d.mobs.map((m) => `<tr><td>${esc(m.name)}${m.can_skin ? '' : ` <span class="needs">Skinning ${m.skill_needed}</span>`}${m.can_kill ? '' : ' <span class="needs">too high</span>'}</td><td>${esc(m.levels)}</td><td class="num">${num(m.skinned, 0)}</td><td class="num">${money(m.value)}</td>
        <td>${m.items.slice(0, 3).map((i) => `${itemLink(i.item_id, i.name)} ${(i.share * 100).toFixed(0)}%`).join(', ')}</td></tr>`).join('')}</tbody></table>`;
  }
  if (o.kind === 'mob_spot') {
    html += `<div class="kv" style="margin-top:8px"><div>Mob level</div><div>${esc(d.levels)}</div><div>Kills per hour</div><div>${o.gph == null ? 'not worked out: an elite, boss or dungeon mob can\'t be killed at your kills-per-hour pace, so only the value per kill is shown' : `${num(d.kills_per_hour, 0)} <span class="pill">${esc(d.pace_source)}</span>`}</div>
      <div>Times looted in Forever</div><div>${num(d.looted, 0)} <span class="pill">${esc(d.source)}</span></div>
      <div>Drops worth</div><div>${money(d.drop_value)} a kill</div>
      ${d.skin_value ? `<div>Skin worth</div><div>${money(d.skin_value)} a skin ${d.can_skin ? '' : `<span class="needs">not counted: needs Skinning ${d.skin_needed}</span>`}</div>` : ''}</div>
      <h3>Drops counted <small>chance per kill × average stack, at current prices</small></h3><table><thead><tr><th>Item</th><th class="num">Per kill</th><th class="num">Worth each</th><th class="num">Seen</th></tr></thead><tbody>
      ${d.drops.map((x) => `<tr class="row" data-item="${x.item_id}"><td>${itemLink(x.item_id, x.name)}</td><td class="num">${num(x.per_kill, 3)}</td><td class="num">${money(x.value)}</td><td class="num">${num(x.count, 0)} of ${num(x.looted, 0)}</td></tr>`).join('')}</tbody></table>
      <p class="note">Only items whose Wowhead Forever pages are read are counted (materials first); coins, gray items and gear are not, so a kill is worth more than this.</p>`;
  }
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
    <div>Zone skill (Classic)</div><div>${d.zone_skill ?? 'unknown'} · you: ${d.your_skill} <span class="pill">${d.skill_bonus ? `your skill + ${d.skill_bonus}: ` : 'no bonus: '}${esc(d.skill_bonus_from || '')}</span></div>
    <div>Fish kept when hooked</div><div>${pct(d.keep)} <span class="pill">${esc(d.keep_source)}</span></div>
    <div>Catches per hour</div><div>${num(d.catches_per_hour, 0)} <span class="pill">${esc(d.pace_source === 'setting' ? `${d.casts_per_hour} casts/hour setting` : d.pace_source)}</span></div>
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
function openOpp(o) { if (!o) return; if (['fishing_zone', 'fishing_spot', 'skin_spot', 'herb_spot', 'mine_spot', 'mob_spot'].includes(o.kind)) { openDrawer(oppDetail(o)); wireDrawer(); return; } openItem(o.item_id, o); }

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
    <button class="btn" id="watch">${watching ? 'Stop watching' : 'Watch price'}</button> <button class="btn" id="to-market">Market chart</button>
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
  $('#to-market').onclick = () => { sessionStorage.setItem('marketItem', id); TAB = 'market'; localStorage.setItem('tab', TAB); $('#drawer').classList.add('hidden'); render(); };
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
