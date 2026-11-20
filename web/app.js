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
  unverified_recipe: ['bad', 'unverified recipe', 'Not in ForeverRecipes\' list of recipes you can learn in Forever (SkillUpForever\'s, when ForeverRecipes is not installed)'],
  skill_estimated: ['', 'skill level estimated', 'Exact skill requirement unknown; estimated'],
  sell_to_vendor: ['good', 'vendor sale', 'Selling to a vendor beats the AH'],
  mat_not_listed: ['warn', 'an ingredient isn\'t listed', 'An ingredient has no listings right now'],
  limited_mat: ['warn', 'ingredient in limited stock', 'An ingredient comes from a limited-stock vendor'],
  limited_stock: ['warn', 'limited stock', 'Vendor has limited stock that restocks over time'],
  other_profession: ['', 'other profession', 'You don\'t have this profession'],
  classic_disenchant: ['warn', 'Classic disenchant table', 'Its profit comes from disenchanting the product, valued with a WoW Classic reference table (ForeverRecipes, provisional estimates), not Forever data. Never a Top pick or part of your plan; check what you really get in game'],
  disenchant_more: ['', 'may be worth more disenchanted', 'A WoW Classic disenchant table (ForeverRecipes, an estimate) says its materials are worth more than selling it: open the item for the materials and the Enchanting skill needed'],
  needs_tool: ['warn', 'needs the tool', 'Made by using a tool you keep (like the Salt Shaker), and your bags, bank and gear do not have one. You buy it once; open the row for its price'],
  tool_unchecked: ['', 'needs the tool', 'Made by using a tool you keep (like the Salt Shaker). The app cannot see your bags (Syndicator), so it does not know whether you have one'],
  snapshot: ['warn', 'one listing, last scan', 'Based on one listing at the last scan; check in game'],
  often_below_vendor: ['good', 'often below vendor price', 'Usually listed below vendor price'],
  risky: ['bad', 'speculative', 'Speculative: depends on prices recovering'],
  small_sample: ['warn', 'small sample', 'Not many catches/loots logged here yet'],
  vendor_price_tsm: ['good', 'vendor price from TSM', 'What a vendor charges, from TSM\'s merchant records (read in game by ForeverMoneyBridge)'],
  vendor_price_wowhead: ['good', 'vendor price from Wowhead Forever', 'What a vendor charges, from its Wowhead Forever page (its Sells tab, read by hand)'],
  vendor_price_unconfirmed: ['', 'vendor price from game files', 'Base price from the game files; open the vendor once with ForeverMoneyBridge to confirm the real price'],
  price_check_fails: ['bad', 'only pays at odd prices', 'Second opinion: at typical prices (the median of the realm and region listing averages and the usual sale price) this loses money. It only pays at today\'s unusual prices, so it is kept out of Top picks and the plan. The details show the numbers'],
  price_check: ['warn', 'check the price', 'Second opinion: at typical prices (the median of the realm and region listing averages and the usual sale price) this makes under a third of the profit shown. Check the prices in game before acting; the details show the numbers'],
  sale_price_outlier: ['warn', 'odd sale prices', 'Nothing is listed on your realm, and the region average sale price is over 3x what it is listed for across the region: a few sales at odd prices on a rarely traded item. Valued at the region listing average instead'],
  listed_far_above_sales: ['warn', 'listings far above sales', 'Every listing on your realm is over 3x what it actually sells for across the region (a wall of wishful prices): valued at the region average sale price instead of the lowest listing'],
  price_looks_off: ['warn', 'price looks off', "Only a few listings, far from the realm's recent average: valued at the recent average until more listings confirm the new price"],
  old_snapshot: ['warn', 'old Wowhead data', 'The Wowhead Forever counts for this zone are over 30 days old: re-read the zone page'],
  everloot: ['warn', 'Everloot rates', 'Some drop rates here come from Everloot (everloot.app, players\' uploads, CC BY-SA 4.0), where the Wowhead Forever pages read have none: only rates from 30+ loot windows, one item per drop. Kept out of Top picks until a Wowhead Forever page confirms them'],
  stock_unknown: ['warn', 'stock unknown', 'Nothing says how many this vendor has: some vendors sell only a few at a time and restock slowly. Open the vendor once in game (the addon records its stock) and the app caps the amount if it is limited'],
  done_today: ['', 'done today', 'You ticked this as done for today: it leaves the plan and Top picks until tomorrow, and the next best takes its place. Untick it in the Done today list on Top picks'],
  craft_limited_demand: ['warn', 'limited demand', 'Valued by crafting it into something whose market only takes a limited number a day (or whose recipe has a cooldown). The crafted worth counts only for that many a day; every one beyond that counts at its sale price, in this row and everywhere else'],
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
  seasonal_confirmed: ['', 'seasonal fish', 'Part of the value is a seasonal fish that recent Forever catches show is in season now: counted as it is today, but this spot is worth less once the season ends'],
  seasonal: ['', 'seasonal', 'Part of the value is a seasonal fish (Classic schedule; Forever may differ)'],
  lure_cost: ['', 'lure cost counted', 'Your best lure keeps more fish here than it costs, so gold per hour assumes you use it and takes the lures you burn in an hour off (details: which lure, how many, what they cost)'],
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
  zone_above_you: ['warn', 'zone above your level', 'Most of the mobs in this zone (QuestieDB, Forever) are more than 3 levels above you: gathering here means fighting or dodging them. The same reach as for mob farming.'],
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
  fillCharPick();
  $('#status').textContent = `Prices from ${tsm && tsm.data_time ? ago(tsm.data_time) : '?'} · updated ${ago(STATE.generated_at)} · ${STATE.settings.realm}`;
}

// header dropdown: which character the app plans for (setting 'character'; empty = the last one you played)
function fillCharPick() {
  const sel = $('#char-pick'), chars = Object.keys(STATE.characters || {}), picked = STATE.settings.character || '';
  if (!chars.length) { sel.style.display = 'none'; return; }
  sel.style.display = '';
  const desc = (n) => { const c = STATE.characters[n] || {}; return `${n}${c.level ? ` (${c.level})` : ''}`; };
  sel.innerHTML = `<option value="" ${picked ? '' : 'selected'}>Last played: ${esc(STATE.last_played || '?')}</option>`
    + chars.map((n) => `<option value="${esc(n)}" ${n === picked ? 'selected' : ''}>${esc(desc(n))}</option>`).join('');
  sel.onchange = async () => {
    await api('/api/settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({character: sel.value || null})});
    toast(`Planning for ${sel.value || 'the character you played last'}. Recalculating…`);
    await loadState(); render();
  };
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
  const H = {...{title: 'What to do', profit_unit: 'Profit each', cost_unit: 'Cost each', units_day: 'Sales a day (you)', daily: 'Profit a day', profit_avg: 'At average sale', every: 'One sale every', gph: 'Gold / hour', gph_pools: 'Gold / hour with pools', sells: 'Sells (region)', cooldown: 'Cooldown', effort: 'Time a day', flags: 'Notes', profession: 'Profession', kind: 'Type', good_day: 'On a good day', own: 'With your own materials'}, ...(opts.heads || {})};
  const st = sortState[id];
  const sortVal = (o) => st.k === 'rank' ? -ranks.get(o.key) : (st.k === 'sells' ? ((o.detail || {}).liquidity || {}).sold_per_day : (st.k === 'cooldown' ? (o.detail || {}).cooldown_hours : st.k === 'good_day' ? (o.detail || {}).good_day : st.k === 'own' ? ((o.detail || {}).own || {}).per_craft : o[st.k]));
  if (st) rows = [...rows].sort((a, b) => ((sortVal(a) ?? -1e18) < (sortVal(b) ?? -1e18) ? -1 : 1) * (st.dir));
  const numeric = new Set(['good_day', 'own', 'profit_unit', 'cost_unit', 'units_day', 'daily', 'gph', 'gph_pools', 'sells', 'cooldown', 'profit_avg', 'every', 'effort']);
  const HT = {units_day: 'How many you can expect to sell (or make) a day: what the whole region buys a day x your share (Settings, 20%), capped by your gold, vendor stock and ingredients. Under 1 means less than one a day.',
    daily: 'Profit each x sales a day: what this earns on an average day if you keep doing it. "up to": the same at the current lowest listing.',
    profit_unit: STATE.settings.sale_price_basis === 'min_buyout' ? 'Profit on one, after the AH cut, at the current lowest listing.'
      : STATE.settings.sale_price_basis === 'actual_sales' ? 'Profit on one, after the AH cut, at what it actually sells for (never above the realm listing average or the region average sale price).'
      : STATE.settings.sale_price_basis === 'lower' ? 'Profit on one, after the AH cut, at the lower of the current lowest listing and its usual sale price across the region: what you can count on. "up to" below it: if it sells at the current lowest listing instead.'
      : 'Profit on one, after the AH cut, at your realm\'s current lowest listing (what you would list at). "at usual" below it: the same at what it usually sells for across the region, when that is less.',
    good_day: 'Optimistic: the profit if at least one sells today at your realm\'s price, even if it usually sells less than once a day (big sales like a 65g piece of gear count here). "Profit a day" is the average day.',
    own: 'If you gather the materials you can gather yourself: the gold each craft brings in (product minus the materials you still buy), and below it what crafting adds over selling those materials raw, and the gold per hour of farming and crafting (from the best spot with Forever data for each material, at the Settings paces). Your materials are never counted as free.',
    profit_avg: "Profit on one if it sells at the region's average sale price instead of the lowest listing.",
    every: 'How long one sale takes on average at your share of the region\'s sales.',
    effort: 'Estimated minutes of play a day: posting auctions (and reposting the ones that expire), buying ingredients, crafting, one vendor trip. Below it: what that time earns per hour.',
    flags: 'Warnings and facts about this row. Hover one, or read the list under the table.',
    title: 'What to do, in plain steps. Click a row for the details: where to buy, what goes in, how each number is worked out.',
    cost_unit: "What one costs you: the ingredients (the cheaper of a vendor and your realm's AH) for a craft, the vendor's price for a flip.",
    gph: 'Gold an hour while you do it: what one kill, node, skin or catch is worth x how many you do in an hour (your pace in Settings, never your own logged time). Click the row for each part.',
    gph_pools: POOL_HINT,
    sells: "How easily it sells across the whole region (TSM): how many sell a day, and the share of listings that sell. 'Sales a day (you)' is your share of that.",
    cooldown: 'How long the recipe waits between crafts (from the game data). Crafts that share a cooldown cannot all be done.',
    profession: 'The profession it needs.',
    kind: 'What kind of money-maker it is: a craft, a flip, a farming spot.', ...(opts.headTips || {})};
  const head = cols.map((c) => c === 'rank' ? `<th data-k="rank" class="rk" title="${esc(RANK_TIP)}">#</th>` : `<th data-k="${c}" class="${numeric.has(c) ? 'num' : ''}"${HT[c] ? ` title="${esc(HT[c])}"` : ''}>${H[c] || c}${HT[c] ? ' <span class="qmark">?</span>' : ''}</th>`).join('');
  rows.forEach((o) => { ROWS[o.key] = o; });
  const body = rows.map((o) => {
    const cells = cols.map((c) => {
      if (c === 'title') {
        const name = o.name || o.title;
        const label = ['fishing_zone', 'fishing_spot', 'skin_spot', 'herb_spot', 'mine_spot', 'farm_zone', 'mob_spot'].includes(o.kind) ? esc(o.title) : esc(o.title).replace(esc(name), itemLink(o.item_id, name, o.quality));
        return `<td>${tickButton(o.key, o.kind)}${label}${o.needs ? `<div class="needs">needs ${esc(o.needs)}</div>` : ''}${o.tip ? `<div class="pill">💡 ${esc(o.tip)}</div>` : ''}${doneNote(o)}</td>`;
      }
      if (c === 'rank') return rankCell(ranks.get(o.key));
      if (c === 'cooldown') { const dd = o.detail || {}, h = dd.cooldown_hours; return h ? `<td class="num" title="${esc(dd.cooldown_group ? 'Shared cooldown: ' + dd.cooldown_group : 'Recipe cooldown from the game data')}">${h >= 1 ? num(h, 0) + ' h' : num(h * 60, 0) + ' min'}${dd.cooldown_group ? ' 🔗' : ''}<div class="pill">max ${num(24 / h, h > 12 ? 2 : 0)}/day</div></td>` : '<td class="num pill">–</td>'; }
      if (c === 'flags') return `<td>${flagHtml(o.flags)}</td>`;
      if (c === 'units_day') return `<td class="num">${o.units_day >= 1 || !o.units_day ? num(o.units_day) : `1 every ${daysText(1 / o.units_day)}`}</td>`;
      if (c === 'effort') { const ef = (o.detail || {}).effort; return ef ? `<td class="num" title="About ${ef.minutes} minutes of play a day for its profit a day (posting, reposting, buying, crafting, a vendor trip). No hourly figure: the market only takes so many, so more time would not earn more.">~${num(ef.minutes, ef.minutes < 10 ? 1 : 0)} min</td>` : '<td class="num pill">–</td>'; }
      if (c === 'every') return `<td class="num">${o.units_day > 0 ? (o.units_day >= 1 ? `${num(o.units_day, 1)} a day` : daysText(1 / o.units_day)) : '–'}</td>`;
      if ((c === 'profit_unit' || c === 'daily') && (o.detail || {}).at_usual) {
        const u = o.detail.at_usual;
        return `<td class="num">${money(o[c])}<div class="pill" title="${esc(`At your realm's lowest listing (${moneyText(u.price_used)}) as shown; across the region it usually sells for ${moneyText(u.price)}, which would give this. Region sales are the only sales data TSM has.`)}">at usual ${esc(moneyText(c === 'daily' ? u.daily : u.profit_unit))}</div></td>`;
      }
      if ((c === 'profit_unit' || c === 'daily') && (o.detail || {}).upside) {
        const u = o.detail.upside;
        return `<td class="num">${money(o[c])}<div class="pill" title="${esc(`If it sells at the current lowest listing (${moneyText(u.price)}) instead of its usual price (${moneyText(u.price_used)}). Listings this far above usual sales may sit unsold, so the number above is what you can count on.`)}">up to ${esc(moneyText(c === 'daily' ? u.daily : u.profit_unit))}</div></td>`;
      }
      if (c === 'good_day') return `<td class="num">${(o.detail || {}).good_day === undefined ? '<span class="pill">–</span>' : money(o.detail.good_day)}</td>`;
      if (c === 'own') {
        const w = (o.detail || {}).own;
        if (!w) return '<td class="num"><span class="pill" title="No material here is one you could gather">–</span></td>';
        const tip = `Gatherable: ${w.materials.join(', ')} (worth ${moneyText(w.mats_value)} sold raw).` + (w.no_rate.length ? ` No Forever spot rate yet for ${w.no_rate.join(', ')}, so no time estimate.` : ` About ${num(w.hours * 60, 0)} minutes of farming per craft.`);
        return `<td class="num" title="${esc(tip)}">${money(w.per_craft)}<div class="pill">adds ${esc(moneyText(w.adds))}${w.gph ? ` · ${esc(moneyText(w.gph))}/h` : ''}</div></td>`;
      }
      if (c === 'profit_avg') { const v = (o.detail || {}).profit_at_avg_sale; return `<td class="num">${v === undefined ? '<span class="pill">–</span>' : money(v)}</td>`; }
      if (c === 'sells') { const l = (o.detail || {}).liquidity; return l ? `<td class="num" title="${esc(l.why || 'sells well')}">${num(l.sold_per_day, 0)}/day<div class="pill">${l.sale_rate === null || l.sale_rate === undefined ? '' : (l.sale_rate * 100).toFixed(0) + '% sell · '}${l.listed} listed</div></td>` : '<td class="num pill">–</td>'; }
      if (c === 'kind') return `<td>${esc(KIND[o.kind] || o.kind)}</td>`;
      if (c === 'profession') return `<td>${esc(o.profession || '')}</td>`;
      return `<td class="num">${money(o[c])}</td>`;
    }).join('');
    return `<tr class="row ${o.doable ? '' : 'notdoable'}${(o.flags || []).includes('done_today') ? ' done' : ''}" data-key="${esc(o.key)}" data-item="${o.item_id}">${cells}</tr>`;
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
      ${d.starter_until ? `<div class="hint" title="A new install has no price history of its own: the app ships daily prices recorded by the app's author, used only for days before your own snapshots of this item begin">Up to ${new Date(d.starter_until * 1000).toLocaleDateString()}: starter history that comes with the app (daily prices from another player's copy, ${esc(STATE.settings.realm || 'same region')}); after that, your own snapshots.</div>` : ''}
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
    head = '<th>Container</th><th class="num">How many</th><th class="num" title="Expected value of the contents at today\'s prices">Worth opened</th><th title="The three contents worth the most per opening; Worth opened counts every content Forever data lists">Mostly holds</th>';
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
    a.type === 'farm' ? chip('Gold an hour', money(a.gain), 'This step is an hour of farming: what that hour earns at the paces in Settings.') : '',
    a.gold_needed ? chip('Gold needed', money(a.gold_needed), 'Gold you spend up front (ingredients or the item to resell); you get it back when it sells.') : '',
    chip('How sure', `${Math.round(a.confidence * 100)}%`, 'How much we trust these numbers: data quality, how well it sells, and for snipes the chance the listing is gone.'),
  ].join('');
  const badge = goal ? '<span class="plan-goal-badge">🎓</span>' : (a.rank <= 3 ? `<span class="medal m${a.rank}" title="#${a.rank}">${a.rank}</span>` : `<span class="rank">${a.rank}</span>`);
  return `<div class="plan-card${goal ? ' goal' : ''}${a.rank && a.rank <= 3 ? ' top' + a.rank : ''}" data-key="${esc(a.key || '')}" data-item="${a.item_id || ''}" data-type="${esc(a.type)}">
    <div class="plan-rank">${badge}</div>
    <div class="plan-body"><div class="plan-label">${goal ? '' : tickButton(a.key || `plan:${a.type}:${a.title}`, a.type, a)}${PLAN_ICON[a.type] || ''} ${esc(a.label)}</div>
      <div class="plan-title">${a.item_name ? esc(a.title).replace(esc(a.item_name), itemLink(a.item_id, a.item_name, a.quality)) : esc(a.title)}</div><div class="plan-why">${esc(a.why)}</div>
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
// Biggest markets (markets.py, the user's idea 2026-11-19): every item that sells, ranked by price and market size;
// a glowing gold border marks the ones you can get now (a craft, flip or farming spot you can do)
async function marketsPanel() {
  const sort = sessionStorage.getItem('mkSort') || 'score';
  const filt = sessionStorage.getItem('mkFilter') || 'all';
  const limit = +(sessionStorage.getItem('mkLimit') || 100);
  const d = await api(`/api/markets?sort=${sort}&filter=${filt}&limit=${limit}`);
  const way = (r) => r.ways.length ? r.ways.map((w) => `<div><span class="pill">${esc(w.kind)}</span> ${esc(w.title)}: ${money(w.value)} ${esc(w.per)}${w.doable ? '' : ` <span class="needs">${esc(w.needs || 'not yet')}</span>`}</div>`).join('')
    : '<span class="hint">none in the app yet</span>';
  const body = (d.rows || []).map((r) => `<tr class="row${r.yours ? ' yours' : ''}" data-item="${r.item_id}" ${r.yours ? 'title="You can get this now: a craft, flip or farming spot you can do (see Your way in)"' : ''}>${rankCell(r.rank)}<td>${itemLink(r.item_id, r.name, r.quality)}<div class="hint">${esc(r.category)}${r.yours ? ' · <b class="yours-tag">you can get this</b>' : ''}</div></td>
    <td class="num">${money(r.price)}</td><td class="num">${num(r.sold_per_day, r.sold_per_day < 10 ? 1 : 0)}</td><td class="num">${money(r.gold_a_day)}</td><td class="num">${num(r.listed, 0)}</td>
    <td>${r.sources.length ? esc(r.sources.join('; ')) : '<span class="hint">not in the data the app reads (often a dungeon or world drop)</span>'}</td>
    <td>${way(r)}</td><td><a href="${esc(r.wowhead)}" target="_blank" rel="noopener" title="How to get it, on Wowhead's WoW: Forever pages">Wowhead</a></td></tr>`).join('');
  const opt = (v, label, cur) => `<option value="${v}" ${v === cur ? 'selected' : ''}>${label}</option>`;
  const shown = (d.rows || []).length;
  return `<div class="panel"><h2>Biggest markets <small>every item that sells, by what it is worth and how much of it sells</small></h2>
    <div class="controls">
      <label class="chk">Order <select id="mk-sort">${opt('score', 'Price and market size (best first)', sort)}${opt('gold', 'Gold traded a day', sort)}${opt('price', 'Price each', sort)}</select></label>
      <label class="chk">Show <select id="mk-filter">${opt('all', `All items (${num(d.all, 0)})`, filt)}${opt('yours', `Ones you can get now (${num(d.yours, 0)})`, filt)}${opt('way', `Ones the app has a way into (${num(d.way, 0)})`, filt)}${opt('noway', `Ones the app has no way into yet (${num(d.all - d.way, 0)})`, filt)}</select></label>
    </div>
    <div class="hint"><span class="yours-sample">Glowing gold border</span>: you can get it now, with a craft, flip or farming spot the app found that you can do.</div>
    ${shown ? `<div class="tablewrap"><table><thead><tr><th class="rk">#</th><th title="The item: click the row for everything about it">Item</th>
      <th class="num" title="What one usually sells for (TSM region sale average, odd ones left out)">Price each</th>
      <th class="num" title="Sold a day in the whole region (TSM)">Sold a day</th>
      <th class="num" title="Sold a day times the price: how big the market is, not what you would earn">Gold traded a day</th>
      <th class="num" title="Listings on your realm at the last scan">Listed</th>
      <th title="What the data the app reads says about getting it: recipes, vendors, QuestieDB mobs and objects, containers">How it is obtained</th>
      <th title="The app's rows that supply this item, best first: a craft or flip with its profit a day, a farming spot with its gold an hour">Your way in</th><th title="Its page on Wowhead Forever: how to get it, who drops or sells it">Look it up</th></tr></thead><tbody>${body}</tbody></table></div>
      <div class="controls"><span class="hint">Showing ${num(shown, 0)} of ${num(d.total, 0)}.</span>${shown < d.total ? ' <button class="btn" id="mk-more">Show 100 more</button>' : ''}</div>`
      : '<div class="empty">No items found.</div>'}
    <details class="how"><summary>How this is worked out</summary><div>Every item with sales recorded in the region (TSM). "Price and market size" ranks by the price of one times the square root of how many sell a day: an expensive item that sells a few times a day ranks with a cheaper one that sells many times more, and a cheap item with a huge market (cloth) does not crowd out the valuable ones. "Gold traded a day" is sold a day times the price: the size of the market, not your income (your share of the sales is about ${num((d.share || 0.2) * 100, 0)}%, and other sellers compete). "How it is obtained" lists what the game data and your addons say: the recipes that make it, a vendor that sells it, the mobs and objects QuestieDB lists as dropping it (who, not how often), and containers read on Wowhead Forever. "Your way in" is the app's own rows for it: crafts and vendor flips with their profit a day, farming spots with their gold an hour (a spot gives other items too); a gold border means at least one of them is something you can do now. When there is none, or the item comes from somewhere the app does not read (dungeon bosses, world drops), its Wowhead Forever page says how to get it; tell Claude what you find and it can be added. Click a row for everything about the item.</div></details></div>`;
}
// Levelling planner (strategy item 2; overhauled 2026-11-19): the cheapest path from one skill to another, with what
// the materials cost, what the products bring back (AH, vendor, disenchant) and a shopping list
async function levellingPanel() {
  const prof = sessionStorage.getItem('levelProf') || '';
  const skill = sessionStorage.getItem('levelSkill') || '';
  const target = sessionStorage.getItem('levelTarget') || '';
  const useDe = sessionStorage.getItem('levelDe') !== '0';
  const d = await api(`/api/levelling?profession=${encodeURIComponent(prof)}&skill=${encodeURIComponent(skill)}&target=${encodeURIComponent(target)}&de=${useDe ? 1 : 0}`);
  if (d.error) return `<div class="panel"><h2>Levelling a profession</h2><div class="hint">${esc(d.error)}</div></div>`;
  const opts = d.professions.map((p) => `<option value="${esc(p)}" ${p === d.profession ? 'selected' : ''}>${esc(p)}${d.yours[p] !== undefined ? ` (you: ${d.yours[p]})` : ''}</option>`).join('');
  const OWN = `<span class="pill" title="Your gathering profession gives this (Forever data: Wowhead Forever skinning pages, QuestieDB with GatherLite's ore and herb nodes): counted at what you would get for selling it, not at what it costs to buy">yours</span>`;
  const mats = (st) => st.mats.map((m) => `${m.count}× ${itemLink(m.item_id, m.name)}${m.own ? ` ${OWN}` : ''}`).join(', ');
  const ch = (st) => {
    const c = st.channels;
    const de = c.disenchant ? ` · disenchant ${money(c.disenchant)}${c.disenchant_can ? '' : ' (no one can yet)'} <span class="pill" title="WoW Classic table (ForeverRecipes), an estimate">Classic</span>` : '';
    return `AH ${c.AH ? money(c.AH) : '–'}${c.AH && st.ah_cap ? ` (the AH takes about ${num(st.ah_cap, st.ah_cap < 10 ? 1 : 0)} in ${num(d.ah_days, 0)} days at your share)` : ''} · vendor ${money(c.vendor)}${de}`;
  };
  // a product that sells less than about once every 2 days at your share: said under Back (the user, 2026-11-19)
  const slow = (st) => {
    const every = st.ah_per_day > 0 ? Math.round(1 / st.ah_per_day) : 0;
    return st.channels.AH && /^AH/.test(st.back_how) && every >= 2 ? `<div class="hint" title="Your share (${num(STATE.settings.market_share * 100, 0)}%) of the region's sales of this product, from TSM. The path counts only the sales within ${num(d.ah_days, 0)} days; the rest go to a vendor or disenchanting.">slow: about 1 sale every ${every} days</div>` : '';
  };
  const FIND = {drop: 'it only drops', quest: 'a quest reward', vendor: 'sold for another currency, not gold', unknown: 'no source known'};
  const at = (n) => `${esc(n.name)}${n.zone ? ` (${esc(n.zone)}${n.x != null ? ` ${num(n.x, 0)}, ${num(n.y, 0)}` : ''})` : ''}`;
  const where = (st) => {
    if (st.known) return '<div class="hint">You know this recipe.</div>';
    const s = st.sources;
    if (!s) return '';
    const parts = [];
    if (s.automatic) parts.push('comes with the profession');
    if (s.trainer_count) parts.push(`a trainer${s.fee != null ? ` for ${money(s.fee)}` : ''}${s.fee_skill ? ` (at skill ${s.fee_skill})` : ''}: ${s.trainers.map(at).join(', ')}${s.trainer_count > s.trainers.length ? ` and ${s.trainer_count - s.trainers.length} more` : ''}`);
    s.items.forEach((i) => { if (i.ah) parts.push(`${itemLink(i.item_id, i.name)} on the AH for ${money(i.ah.cost)} (${esc(i.ah.source)})`); });
    if (s.sold_by.length) parts.push(`sold by ${s.sold_by.slice(0, 3).map((v) => `${at(v)} for ${v.copper != null ? money(v.copper) : esc(v.cost_text || 'a price not known')}${v.limited ? ' <span class="pill" title="Limited stock: the vendor has only a few, and restocks after a while">limited</span>' : ''}`).join(', ')}${s.sold_by.length > 3 ? ` and ${s.sold_by.length - 3} more` : ''}`);
    if (s.dropped_by.length) parts.push(`drops from ${s.dropped_by.map((r) => `${at(r)}${r.chance != null ? ` ${num(r.chance, 2)}%` : ''}`).join(', ')}`);
    if (s.other_drops.length) parts.push(`found in ${s.other_drops.slice(0, 4).map((o) => esc(o.name)).join(', ')}`);
    if (s.quests.length) parts.push(`quest reward: ${s.quests.map((q) => `${esc(q.name)}${q.level ? ` (level ${q.level})` : ''}${q.start ? `, from ${esc(q.start)}${q.zone ? ` in ${esc(q.zone)}` : ''}` : ''}`).join('; ')}`);
    return `<div class="hint">Where to learn it: ${parts.length ? parts.join(' · ') : 'no source known'} <span class="pill" title="Trainers, vendors, drop chances (the top 5 recorded, in %) and quests come from the ForeverRecipes addon: Forever client data plus its author's observations, some of it WoW Classic reference data. Vendors also from QuestieDB; AH prices from TSM.">ForeverRecipes</span></div>`;
  };
  const WAIT = `<span class="pill flag" title="No one is selling this pattern on your realm's AH now: its price is TSM's market value (or the region's). You may have to wait for one to be listed, or get it another way (under the recipe). The price still counts in the totals.">may have to wait</span>`;
  const learnCell = (st) => st.find ? `<span class="pill flag" title="You can't buy this with gold now (${esc(FIND[st.find] || st.find)}): the path uses it only where no recipe you can buy gives a point. Its cost isn't in the totals. Where to find it: under the recipe.">find it: ${esc(FIND[st.find] || st.find)}</span>` : st.learn ? `${money(st.learn)} <span class="pill">${esc(st.learn_how)}</span>${st.learn_wait ? ` ${WAIT}` : ''}` : '';
  // the next profession rank (Journeyman to pass 75, Expert 150, Artisan 225), where the path needs it (2026-11-19)
  const CLASSIC_RANK = `<span class="pill" title="The fee, the skill and the level come from SkillUpForever's tables, which take them from the WoW Classic database (CMaNGOS classic-db; fees before any reputation discount), and so does which trainers teach the rank: not checked for Forever. Names and places of the trainers: ForeverRecipes, QuestieDB. If the trainer asks for something else, tell Claude.">Classic database</span>`;
  const FOREVER_BOOK = `<span class="pill" title="The book, the rank it teaches and the skill it asks for come from the game's own tables for the Forever client (read by SkillUpForever); its price is the cheapest of the AH and a vendor, else its list price.">Forever game files</span>`;
  const CLASSIC_QUEST = `<span class="pill" title="That this quest teaches the rank comes from the WoW Classic database (SkillUpForever's tables); the quest's name, who gives it and the skill and level it asks for come from QuestieDB's Forever data.">Classic database, quest from QuestieDB</span>`;
  const trainRow = (t) => {
    const how = t.how === 'trainer' ? `at a trainer for ${money(t.cost)}${t.trainers.length ? ` (${t.trainers.map(at).join(', ')}${t.trainer_count > t.trainers.length ? ` and ${t.trainer_count - t.trainers.length} more` : ''})` : ''}`
      : t.how === 'unknown' ? ''
      : t.how === 'book' ? `by reading the book ${itemLink(t.item_id, t.book_name)}, ${money(t.cost)} (${esc(t.source)})`
      : `from a quest: ${t.quest_name ? `<b>${esc(t.quest_name)}</b>` : `quest ${t.quest}`}${(t.givers || []).length ? `, from ${t.givers.map(at).join(' or ')}` : ''}`;
    const needs = [t.skill ? `skill ${t.skill}` : '', t.level ? `character level ${t.level}${t.level_short ? ` (you are ${d.level})` : ''}` : ''].filter(Boolean).join(' and ');
    return `<tr class="train"><td class="num">${t.at}</td><td colspan="5"><b>Train ${esc(t.name)}</b>: your skill stops at ${t.at} until you do, then it can go up to ${t.cap}. ${t.how === 'unknown' ? 'Where to learn it and what it costs are not known: they came from SkillUpForever\'s tables, and it is not installed. Not counted in the totals.' : `Learn it ${how}.`}${needs ? ` It asks for ${needs}.` : ''}${t.level_short ? ` <span class="pill flag" title="Your character's level is below what this rank asks for: the path stops here until you level up">level too low</span>` : ''} ${t.how === 'unknown' ? '' : t.how === 'book' ? FOREVER_BOOK : t.how === 'quest' ? (t.forever_quest ? CLASSIC_QUEST : CLASSIC_RANK) : CLASSIC_RANK}</td>
      <td class="num">${t.how === 'unknown' ? '?' : `<b>${money(t.cost)}</b>`}</td><td class="num">${money(t.cumulative)}</td><td></td></tr>`;
  };
  const rows = d.steps.map((st) => `${st.train ? trainRow(st.train) : ''}<tr><td class="num">${st.from}–${st.to}</td>
    <td>${itemLink(st.product_id, st.recipe)}<div class="hint">each craft: ${mats(st)}</div></td>
    <td><span class="pill lvl-${st.color}" title="Its colour when you start this stretch: orange always gives a point, yellow usually, green sometimes">${esc(st.color)}</span></td>
    <td class="num">${num(st.crafts, 1)}<div class="hint">buy for ${st.crafts_to_buy}</div></td>
    <td class="num">${money(st.mats_cost)}</td>
    <td class="num">${money(st.back)}<div class="hint">${esc(st.back_how)}</div>${slow(st)}</td>
    <td class="num"><b>${money(st.cost)}</b></td><td class="num">${money(st.cumulative)}</td>
    <td>${learnCell(st)}</td></tr>
    <tr class="sub"><td></td><td colspan="8" class="hint">One product sells back for: ${ch(st)}${where(st)}</td></tr>`).join('');
  const shop = (d.shopping || []).map((m) => `<tr><td>${itemLink(m.item_id, m.name)}${m.own ? ` ${OWN}` : ''}</td><td class="num">${num(m.count, 0)}</td><td class="num">${money(m.each)}</td><td class="num">${money(m.total)}</td></tr>`).join('');
  const unlocks = d.unlocks.length ? `<h3>What it unlocks on the way</h3><table><thead><tr><th class="num" title="The skill this craft needs">Skill</th><th title="A craft the path unlocks, from the Crafting table">Craft</th><th class="num" title="Profit a day once you have the skill (and the gold), from the Crafting table">Profit a day</th><th class="num" title="The path's total cost from your skill to this one (a minus: you would earn that much on the way)">Cost to get there</th></tr></thead><tbody>${d.unlocks.map((u) => `<tr class="row" data-item="${u.item_id}"><td class="num">${u.skill}</td><td>${esc(u.title)}</td><td class="num">${money(u.daily)}</td><td class="num">${u.cost_to_reach == null ? '–' : money(u.cost_to_reach)}</td></tr>`).join('')}</tbody></table>` : '';
  const ench = d.profession === 'Enchanting' ? `<div class="hint">⚠ Enchantments make no item, so they are not in the game's recipe tables this tool reads: the path below uses only the Enchanting crafts that make an item (rods, wands, oils, essences), so a real Enchanting path, with enchantments, may well be cheaper. Check it by hand.</div>` : '';
  const end = ench + (d.stuck_at ? `<div class="hint">⚠ The path stops at <b>${d.stuck_at}</b>: no recipe in the game gives a skill point there (not even one that only drops), or its materials have no price.</div>` : '')
    + (d.to_find.length ? `<div class="hint">⚠ ${d.to_find.length === 1 ? 'One recipe' : `${d.to_find.length} recipes`} on this path can't be bought with gold now: ${d.to_find.map((f) => `<b>${esc(f.recipe)}</b> (from skill ${f.from}: ${esc(FIND[f.how] || f.how)})`).join(', ')}. ${d.to_find.length === 1 ? "The path uses it only where nothing you can buy gives a point; what it costs you isn't in the totals. Where to find it" : "The path uses them only where nothing you can buy gives a point; what they cost you isn't in the totals. Where to find each"}: under the recipe below.</div>` : '')
    + ((d.to_wait || []).length ? `<div class="hint">⚠ ${d.to_wait.length === 1 ? 'One pattern' : `${d.to_wait.length} patterns`} on this path ${d.to_wait.length === 1 ? 'is' : 'are'} not on your realm's AH now: ${d.to_wait.map((f) => `<b>${esc(f.recipe)}</b> (from skill ${f.from})`).join(', ')}. ${d.to_wait.length === 1 ? 'Its price is' : 'Their price is'} TSM's market value, so you may have to wait for one to be listed, or get it another way (under the recipe).</div>` : '')
    + (d.training || []).filter((t) => t.level_short).map((t) => `<div class="hint">⚠ ${esc(t.name)} asks for character level ${t.level} and you are ${d.level}: the path stops at ${t.at} until you level up.</div>`).join('');
  const card = (label, value, hint) => `<div class="stat"><div class="hint">${label}</div><div class="v">${value}</div>${hint ? `<div class="hint">${hint}</div>` : ''}</div>`;
  const deNote = d.enchanter ? `${esc(d.enchanter.name)} has Enchanting ${d.enchanter.skill}` : 'none of your characters has Enchanting';
  return `<div class="panel" id="levelling"><h2>Levelling a profession <small>the cheapest path from one skill to another, at today's prices</small></h2>
    <div class="controls"><select id="lp">${opts}</select> <label class="chk">from skill <input id="ls" type="number" min="1" max="299" value="${d.skill}" style="width:5em" title="Where you start: your skill now, or any skill"></label> <label class="chk">to skill <input id="lt" type="number" min="2" max="300" value="${d.target}" style="width:5em" title="Where you want to get to (300 is the most)"></label>
      <label class="chk" title="Count disenchanting a product where one of your characters has the Enchanting skill for it (${deNote}). Its value comes from a WoW Classic table (ForeverRecipes, an estimate), not Forever data."><input type="checkbox" id="lde" ${useDe ? 'checked' : ''}> count disenchanting (Classic table)</label></div>
    ${d.steps.length ? `<div class="stats">${card('Skill', `${d.skill} → <b>${d.reached}</b>${d.reached < d.target && !d.stuck_at ? ` of ${d.target}` : ''}`, `about ${num(d.crafts, 0)} crafts`)}
      ${card('Materials to buy', money(d.materials_total), 'every craft on the path')}
      ${card('Back from the products', money(d.back_total), 'sold on the AH, to a vendor or disenchanted, whichever pays most')}
      ${card('Learning', money(d.learn_total + (d.train_total || 0)), `recipes ${money(d.learn_total)} (trainer fees and patterns, once each${d.to_find.length ? `; plus ${d.to_find.length} to find, no gold price` : ''})${(d.training || []).some((t) => t.how !== 'unknown') ? `; ranks ${money(d.train_total)} (${d.training.filter((t) => t.how !== 'unknown').map((t) => esc(t.name)).join(', ')}: Classic database fees)` : ''}${(d.training || []).some((t) => t.how === 'unknown') ? '; rank training fees not known (not counted)' : ''}`)}
      ${card('Net cost', `<b>${money(d.total)}</b>`, d.total < 0 ? 'a minus: you would earn that much on the way' : 'materials - back + learning')}</div>` : `<div class="hint">Nothing to plan from here.</div>`}
    <div class="hint">Recipes you know: ${d.known} (${esc(d.known_source)}).</div>
    ${end}
    ${d.steps.length ? `<div class="tablewrap"><table class="level"><thead><tr><th class="num" title="The skill points this stretch covers, from - to">Skill</th><th title="The recipe to craft for these points; under it, what one craft takes and where to learn it">Recipe</th><th title="Its colour when you start the stretch: orange always gives a point, yellow usually, green sometimes">Colour</th><th class="num" title="Expected crafts for this stretch (a yellow or green recipe does not always give a point), and how many to buy materials for">Crafts</th><th class="num" title="What the materials for these crafts cost (cheapest of vendor and AH; your own gathered materials at what they would sell for)">Materials</th><th class="num" title="What the products bring back, and how: the AH, at the lower of the lowest listing and its usual sale price, for as many as your share of ${num(d.ah_days, 0)} days of its sales; then the better of a vendor and disenchanting">Back</th><th class="num" title="Materials minus what comes back, plus learning: what this stretch really costs">Net</th><th class="num" title="Net cost from your skill to the end of this stretch">Total so far</th><th title="What learning it costs, paid once: a trainer's fee or the pattern (AH or vendor)">Learn</th></tr></thead><tbody>${rows}</tbody></table></div>` : ''}
    ${shop ? `<h3>Shopping list <small>everything to buy for the whole path (whole crafts)</small></h3><table><thead><tr><th title="What to buy (or gather) for the whole path">Material</th><th class="num" title="How many, for whole crafts">Count</th><th class="num" title="Price each: the cheaper of a vendor and your realm's AH; what you gather yourself at what it would sell for">Each</th><th class="num" title="Count x each">Total</th></tr></thead><tbody>${shop}</tbody></table>` : ''}
    ${unlocks}
    <details class="how"><summary>How this is worked out</summary><div>The path is chosen as a whole, not point by point: start with the recipes you know and the ones that come with the profession, then learn the recipe that saves the most over every skill point it would take, minus what it costs to learn (a trainer fee, or the pattern on the AH or from a vendor), and drop any learned recipe that no longer pays for itself; repeat until nothing changes. Each skill point then uses the cheapest recipe you have. A point's cost is one craft's net cost (materials, at the cheapest of vendor and AH, a material your gathering gives${d.own_materials.length ? ` (${esc(d.own_materials.join(', '))})` : ''} at what it would sell for (marked "yours", only where Forever data says your gathering gives it: Wowhead Forever's skinning pages, QuestieDB's ore and herb nodes as GatherLite types them, and bars smelted from them), minus what the product brings back) divided by the chance that the craft gives a point. That chance follows the WoW Classic rule (not checked for Forever): orange always, then from yellow to grey (grey − skill) ÷ (grey − yellow), grey never; the colours are SkillUpForever's Forever thresholds, with ForeverRecipes filling the gaps. A product brings back the best of: the AH after the cut, at the lower of your realm's lowest listing and the region's usual sale price (a listing above what buyers usually pay can sit unsold), but only for as many as your share of ${num(d.ah_days, 0)} days of its sales takes (${num(STATE.settings.market_share * 100, 0)}% of the region's; Settings, "Levelling: AH sales within"), then the better of a vendor and disenchanting it. So a product that sells once every few days counts at most once on the AH, and "slow" under Back says how often it sells: a path should not rest on sales that take a week to come. Disenchanting counts only where one of your characters has the Enchanting skill (${deNote}) and the box is ticked; its value is a WoW Classic table (ForeverRecipes calls it a provisional estimate). Then the path is worked out again with how many of each product it really makes, so the AH's limit is counted. Every recipe in the game is considered, not only the ones you know: trainer recipes, patterns on the AH (TSM's price) or from a vendor, and patterns you can't buy with gold now (they only drop, come from a quest, or cost another currency). Those have no price, so the path uses one only where no recipe you can buy gives a point, and as few as it can; a recipe with no known source at all comes last. Under each recipe: where to learn it (trainers and their fee, the pattern on the AH, vendors and their price, the top recorded drop chances, quests), from the ForeverRecipes addon. A pattern that no one is selling on your realm now is priced at TSM's market value (or the region's) and marked "may have to wait". Crafts with a cooldown (Mooncloth, transmutes) are left out: one craft every few days. Training the next rank (Journeyman to go past 75, Expert past 150, Artisan past 225) is a row on the path where you need it, with its fee (a book or a quest for Cooking's and First Aid's higher ranks), the skill and character level it asks for, and who teaches it; those come from SkillUpForever's tables, taken from the WoW Classic database (not checked for Forever). SkillUpForever is optional: without it, the row only says where your skill stops, and the fee is not counted. A rank your addon shows you have${d.cap ? ` (your ${esc(d.profession)} can go up to ${d.cap} now)` : ''} is left out. Not counted: AH deposits, and buying many of one ingredient (each at the lowest listing). ${d.options} recipes considered.</div></details>
  </div>`;
}

// ---------- done for today (done.py): tick a suggestion, the next best takes its place ----------
const ROWS = {};
const TICK_KINDS = new Set(['craft', 'vendor_flip', 'routine', 'cooldown', 'big_flip', 'farm', 'cash_ah', 'cash_vendor',
  'cash_open', 'cash_mail', 'fishing_spot', 'skin_spot', 'herb_spot', 'mine_spot', 'mob_spot']);
const tickButton = (key, kind, plan) => key && TICK_KINDS.has(kind)
  ? `<button class="tick" data-tick="${esc(key)}" ${plan ? `data-plan="${esc(JSON.stringify({title: plan.title, count: plan.count || plan.quantity || null, kind}))}"` : ''} title="Done for today: it leaves the plan and Top picks, and the next best takes its place">✓</button>` : '';
const doneNote = (o) => { const t = (o.detail || {}).done_today; return t && t.done < t.of ? `<div class="pill">done today: ${num(t.done, 0)} of ${num(t.of, 0)}; ${num(o.units_day, 1)} left</div>` : ''; };
function tickDialog(key, plan) {
  const o = ROWS[key];
  const title = (plan && plan.title) || (o && o.title) || key;
  const sells = o && ['craft', 'vendor_flip'].includes(o.kind);
  const rec = sells ? Math.max(1, Math.round(o.units_day || 1)) : (plan && plan.count) || 1;
  const box = document.createElement('div');
  box.className = 'modal';
  box.innerHTML = `<div class="modal-box"><h3>Done for today?</h3><div>${esc(title)}</div>
    ${sells ? `<p>Did you list all <b>${rec}</b> suggested for today, or fewer?</p>
      <div class="controls"><button class="btn" data-all>All ${rec}</button> <label class="chk">or <input type="number" min="0" max="${rec}" value="${Math.max(0, rec - 1)}" style="width:5em"> of ${rec}</label> <button class="btn" data-some>That many</button></div>`
      : `<p>Mark it done: it leaves the plan and Top picks until tomorrow, and the next best takes its place.</p><div class="controls"><button class="btn" data-all>Done</button></div>`}
    <div class="controls"><button class="btn" data-cancel>Cancel</button></div></div>`;
  document.body.appendChild(box);
  const close = () => box.remove();
  const send = async (done) => {
    close();
    await api('/api/done', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key, done, of: rec, title})});
    toast(done >= rec ? `Done for today: ${title}. The next best takes its place.` : `Noted ${done} of ${rec}: ${rec - done} left for today.`);
  };
  box.querySelector('[data-all]').onclick = () => send(rec);
  const some = box.querySelector('[data-some]');
  if (some) some.onclick = () => send(Math.max(0, Math.min(rec, +box.querySelector('input').value || 0)));
  box.querySelector('[data-cancel]').onclick = close;
  box.onclick = (e) => { if (e.target === box) close(); };
}
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-tick]');
  if (b) { e.preventDefault(); e.stopPropagation(); tickDialog(b.dataset.tick, b.dataset.plan ? JSON.parse(b.dataset.plan) : null); return; }
  const u = e.target.closest('[data-untick]');
  if (u) { e.preventDefault(); api('/api/done', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key: u.dataset.untick, undo: true})}).then(() => toast('Back on the list.')); }
}, true);
function donePanel() {
  const d = Object.entries(STATE.done_today || {});
  if (!d.length) return '';
  return `<details class="how"><summary>Done today (${d.length})</summary><ul>${d.map(([k, t]) => `<li>${esc(t.title || k)}${t.done < t.of ? ` (${num(t.done, 0)} of ${num(t.of, 0)})` : ''} <button class="btn" data-untick="${esc(k)}">Undo</button></li>`).join('')}</ul><div class="hint">Ticks reset each day at ${num(STATE.day_starts || 4, 0)}:00.</div></details>`;
}

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
      ${donePanel()}
      <details class="how"><summary>How to read this page</summary><div>Every list is <b>ranked</b>: 🥇🥈🥉 mark the best three, and the order weighs expected profit, how sure the numbers are, how well the item sells, what you would lose if it doesn't sell, and whether you can do it now. <b>Click any row</b> for the full numbers and "Why it's ranked here". The coloured <b>notes</b> explain warnings: hover one to read it. <b>Per day</b> assumes you sell a realistic share of what the whole region buys each day (Settings). Prices follow your realm's lowest listing, except where nobody actually pays that.</div></details>
      <div class="panel"><h2>Daily routines <small>crafts and vendor flips you can do today: each sells about once a day or more, ranked by profit a day</small></h2>${oppTable(t.now || [])}</div>
      <div class="panel"><h2>Occasional big flips <small>worth a lot per sale, but you'd sell less than one a day</small></h2>
        <div class="hint">These sell slowly: list one and expect to wait. Each shows the profit at the lowest listing and at what it actually sells for across the region, which is often less. Ranked by profit per sale and how sure the numbers are.</div>
        ${oppTable(t.slow || [], {cols: ['title', 'profit_unit'].concat(STATE.settings.sale_price_basis === 'lower' ? [] : ['profit_avg'], ['cost_unit', 'every', 'sells', 'flags']), empty: 'No slow, valuable flips right now.'})}</div>
      <div class="panel"><h2>Fishing & farming spots <small>gold per hour: open water, and with the pools you come across</small></h2>${oppTable(withPools(t.hourly || []), {cols: ['title', 'profit_unit', 'gph', 'gph_pools', 'flags'], export: false, heads: {profit_unit: 'Per catch / each'}})}
        <div class="hint">${POOL_HINT}</div>
        <div class="hint">Only spots with enough Forever data appear here (Wowhead Forever counts; your own catch logs only if you turn that on in Settings). Fishing gold/hour is open water; pool loot is a bonus shown in the details. Catches per hour use ${num(STATE.settings.casts_per_hour || 240, 0)} casts/hour (Settings). All spots, including unconfirmed Classic ones, are on the Farming tab.</div></div>
      <div class="grid2">
        <div class="panel"><h2>Unlock by levelling a profession you have</h2>${oppTable(ifAffordable(t.level_up || []), {cols: ['title', 'profit_unit', 'daily', 'sells', 'cooldown', 'flags'], heads: {daily: 'Per day (with the gold)'}, empty: noProfs ? 'No professions known yet: see the note at the top.' : 'Nothing worth it a few skill points away right now.'})}</div>
        <div class="panel"><h2>Worth switching professions for <small>at least ${num(STATE.settings.switch_bonus, 1)}× your best</small></h2>${oppTable(ifAffordable(t.switch || []), {cols: ['title', 'profession', 'daily', 'sells', 'cooldown', 'flags'], heads: {daily: 'Per day (with the gold)'}, empty: 'No other profession beats yours by enough right now.'})}</div>
      </div>`;
  },
  async craft() {
    const profs = STATE.professions_available.filter((p) => !/Racial|Riding|Test|Swim|Lockpick|Compreh|Survival|Horseman|Piloting/.test(p));
    const sel = sessionStorage.getItem('craftProf') || '';
    const doable = sessionStorage.getItem('craftDoable') === '1';
    const sellsOnly = sessionStorage.getItem('sellsOnly') !== '0';
    const rows = await api(`/api/opps?kind=craft&profession=${encodeURIComponent(sel)}&doable=${doable ? 1 : ''}&hide=${sellsOnly ? 'hard_to_sell,no_sales_data' : ''}&limit=800`);
    return `<div class="panel"><h2>Crafting profit <small>ingredients bought at the cheapest of vendor / AH; product sold at the better of AH (after cut) / vendor</small></h2>
      <div class="controls"><select id="cp"><option value="">All professions</option>${[...new Set(profs)].map((p) => `<option ${p === sel ? 'selected' : ''}>${esc(p)}</option>`).join('')}</select>
      <label class="chk"><input type="checkbox" id="cd" ${doable ? 'checked' : ''}> only what I can craft now</label>
      <label class="chk" title="Hides items that barely sell: under 1 a day in the whole region, under 1 in 10 listings selling, or over 10 days of sales already listed on your realm"><input type="checkbox" class="sells-only" ${sellsOnly ? 'checked' : ''}> hide items that barely sell</label></div>
      ${oppTable(rows, {cols: ['title', 'profession', 'profit_unit', 'cost_unit', 'units_day', 'daily', 'good_day', 'own', 'effort', 'sells', 'cooldown', 'flags']})}</div>
      <div class="hint">How to level a profession cheaply, and what each profession would earn you: the Professions tab.</div>`;
  },
  async profs() {
    const d = await api('/api/professions');
    const val = (r, which) => {
      if (r.kind === 'gathering') {
        const g = which === 'now' ? r.gather.now : (r.gather.full || r.gather.classic_full);
        if (!g) return '<span class="pill">–</span>';
        return `${money(g.gph)}<span class="pill"> an hour</span><div class="hint">${esc(g.title)}${g.classic ? ' <span class="flag" title="Some of what a node gives comes from WoW Classic loot tables: not confirmed for Forever">Classic yields</span>' : ''}</div>`;
      }
      const c = which === 'now' ? r.craft.now : r.craft.full, total = which === 'now' ? r.craft.now_daily : r.craft.full_daily;
      if (!c.length) return '<span class="pill">–</span>';
      return `${money(total)}<span class="pill"> a day</span><div class="hint">${c.map((x) => esc(x.title.replace(/^Craft /, ''))).join(', ')}</div>`;
    };
    const cost = (r) => r.kind === 'gathering' ? '<span class="pill" title="A gathering profession rises as you gather: no gold">levels as you gather</span>'
      : r.levelling ? `${money(r.levelling.total)}<div class="hint">about ${num(r.levelling.crafts, 0)} crafts${r.levelling.stuck_at ? `; stops at ${r.levelling.stuck_at}` : ''}${(r.levelling.to_find || []).length ? `; plus ${r.levelling.to_find.length} recipes to find (they only drop or come from quests)` : ''}</div>` : '<span class="pill" title="Enchantments make no item, so they are not in the recipe tables">not planned</span>';
    const good = (r) => r.kind !== 'crafting' ? '<span class="pill">–</span>' : `${money(r.craft.good_day)}<span class="pill"> a day</span>`;
    const big = (r) => r.kind === 'crafting' && r.craft.big_sales.length ? `<div class="hint" title="Worth a lot each but selling less than once a day at your share, so the average day hides them">Big sales: ${r.craft.big_sales.map((b) => `${esc(b.title.replace(/^Craft /, ''))} ${esc(moneyText(b.profit_unit))}${b.days_per_sale ? ` (1 every ${b.days_per_sale} days)` : ''}`).join(', ')}</div>` : '';
    const rows = d.rows.map((r, i) => `<tr><td>${esc(r.profession)}${r.have ? ` <span class="pill good" title="You have this profession">yours: ${r.skill}</span>` : ''}</td>
      <td class="num">${r.have ? val(r, 'now') : '<span class="pill">–</span>'}</td><td class="num">${val(r, 'full')}</td><td class="num">${good(r)}</td><td class="num">${cost(r)}</td><td>${esc(r.verdict)}${big(r)}</td></tr>`).join('');
    return `<div class="panel"><h2>Professions <small>what each primary profession earns you now and at full skill, and what getting there costs</small></h2>
      <div class="hint">${esc(d.note)} Yours: ${d.yours.length ? esc(d.yours.join(' and ')) : 'none detected'}.</div>
      <div class="tablewrap"><table><thead><tr><th title="Every profession, yours first">Profession</th><th class="num" title="With your skill today (only for professions you have)">Now</th><th class="num" title="Gathering: the best spot that only needs more skill. Crafting: the three best crafts at 300 that sell, with the gold for their ingredients">At full skill</th><th class="num" title="Optimistic: one sale today of each of its three best crafts at your realm's price, including ones that usually sell less than once a day">On a good day</th><th class="num" title="Crafting: the levelling planner's cost from your skill (or from 1) to 300; a minus means you would earn that much on the way">To get there</th><th title="A one-line verdict from the numbers on this row">In short</th></tr></thead><tbody>${rows}</tbody></table></div>
      <details class="how"><summary>How this is worked out</summary><div>Gathering professions: the best gathering spot by gold an hour, from the Gathering tab (Forever data first; a spot partly resting on WoW Classic loot tables is marked "Classic yields"). Node spots do not check your level: a high zone (Winterspring, Eastern Plaguelands, Felwood) needs a high level to farm safely. Crafting professions: the profit a day of the three best crafts that sell, from the Crafting tab, and the levelling planner below for the cost from your skill (or from skill 1 for one you don't have) to 300. One hour of farming a day is about its gold an hour a day, so the two kinds can be compared. Switching a profession means dropping one of yours and its skill: compare its "Now" with the new one's numbers and cost.</div></details></div>
      ${await levellingPanel()}`;
  },
  async flips() {
    const sellsOnly = sessionStorage.getItem('sellsOnly') !== '0', hide = sellsOnly ? '&hide=hard_to_sell,no_sales_data' : '';
    const [vf, sn] = await Promise.all([api('/api/opps?kind=vendor_flip' + hide), api('/api/sniper')]);
    return `<div class="controls"><label class="chk"><input type="checkbox" class="sells-only" ${sellsOnly ? 'checked' : ''}> hide items that barely sell</label></div><div class="panel"><h2>Buy from a vendor, sell on the AH</h2><div class="hint">Vendors are checked against Questie's Forever database and filtered to your faction. Limited-stock vendors restock over time.</div>${oppTable(vf)}</div>
      <div class="panel"><h2>Worth adding to your TSM Sniper <small>items our price snapshots often caught listed far below what they sell for</small></h2>
        <div class="hint">Snipes happen in game, within seconds: TSM's Sniper scans the auction house live, while this app's data is up to an hour old, so it doesn't suggest single cheap listings. What it can tell from ${sn.scans} snapshots is which items are worth watching for, and at what price. Add them to a TSM group with a Sniper operation at the price shown (or copy the list below and import it into a group).</div>
        ${sn.rows.length ? `<table><thead><tr><th>Item</th><th title="Resell on the AH, or sell to a vendor">Then</th><th class="num" title="Buy at this price or less. Resale: 60% of the lower of its realm listing average and its usual sale price, about 35% profit after the AH cut. Vendor: what a vendor pays.">Snipe at</th><th class="num" title="Profit on one catch at its usual price, after the AH cut (vendor: depends on the listing)">Profit each</th><th class="num" title="Share of our snapshots that had it this cheap">How often</th></tr></thead><tbody>${sn.rows.map((r) => `<tr class="row" data-item="${r.item_id}"><td>${itemLink(r.item_id, r.name)}<div class="hint">${esc(r.why)}</div></td><td>${esc(r.how)}</td><td class="num">${money(r.snipe_at)}</td><td class="num">${r.gain ? money(r.gain) : '<span class="pill">varies</span>'}</td><td class="num">${num(r.share * 100, 0)}%<div class="pill">${r.times} of ${r.snapshots}</div></td></tr>`).join('')}</tbody></table>
        <details class="how"><summary>Item list for a TSM group (copy, then import into a group in TSM)</summary><textarea readonly style="width:100%;height:60px">${esc(sn.tsm_items)}</textarea></details>` : '<div class="hint">Not enough snapshots yet: the app records prices each time TSM updates while it runs.</div>'}</div>`;
  },
  async niches() {
    const d = await api('/api/niches');
    const rows = d.rows.map((r, i) => `<tr class="row" data-item="${r.item_id}">${rankCell(i + 1)}<td>${itemLink(r.item_id, r.name)}${r.thin_supply ? ' <span class="flag good" title="Often sold out in our own price snapshots while it keeps selling: few people supply it">thin supply</span>' : ''}<div class="hint">${esc(r.why)}</div></td>
      <td>${esc(r.how.kind)}: ${esc(r.how.title)}${r.how.doable ? '' : ` <span class="pill">(${esc(r.how.needs || 'not yet')})</span>`}</td>
      <td class="num">${money(r.how.profit_unit)}</td><td class="num">${num(r.sold_per_day, 1)}</td><td class="num">${money(r.profit_day)}</td></tr>`).join('');
    return `<div class="panel"><h2>Niches <small>steady demand, low supply: items that sell every day, few are listed, and you can supply them</small></h2>
      <div class="hint">From ${d.scans} price snapshots of our own${d.scans < d.solid_scans ? ` (about a week, ${d.solid_scans}, is needed before "sold out" means much: until then it only ranks a niche higher)` : ''}. What you can do now comes first.</div>
      ${d.rows.length ? `<table><thead><tr><th>#</th><th title="The item, and the numbers that make it a niche: it sells every day, few are listed, and its price holds">Item and why it qualifies</th><th title="The app's best row that supplies it: a craft, a flip or a farming spot">How you'd supply it</th><th class="num" title="Profit on one, from the Crafting, Flips or Gathering row">Profit each</th><th class="num" title="Your share of the region's sales a day: how many you could sell without flooding it">Sells a day (you)</th><th class="num" title="The supplying row's own profit a day, the same as on its Crafting, Flips or Gathering row">Profit a day</th></tr></thead><tbody>${rows}</tbody></table>` : '<div class="hint">No niche right now.</div>'}
      <details class="how"><summary>How this is worked out</summary><div>An item counts when your share (${num(STATE.settings.market_share * 100, 0)}%) of the region's daily sales is at least one, at least half of its listings sell, your realm lists at most 10 and less than a day of the region's sales, the lowest listing is at least 90% of its usual sale price (or nothing is listed), and you can make or get it at a profit (a craft, a vendor that sells it, or something you gather). "Sold out" is how often our own snapshots saw nothing listed while it kept selling. Limits: TSM's counts come from TSM users only and are region-wide; TSM has no seller counts; a niche closes once others notice it.</div></details></div>`;
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
    // every gathering view values loot the same way: crafted worth only for what a recipe can use a day (2026-11-15)
    const CRAFT_CAP = " An item worth more crafted than sold counts at its crafted worth only for as many as its recipe can use a day (the recipe's cooldown, or what the product's market takes at your share); the rest of an hour's loot counts at its sale price. One hour of farming a day is assumed.";
    const how = (text) => `<details class="how"><summary>How this is worked out</summary><div>${text}${CRAFT_CAP}</div></details>`;
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
      <div class="tablewrap"><table><thead><tr><th class="rk">#</th><th>Item</th><th class="num" title="How many this character has">Count</th><th title="The best use for it: sell on the AH, sell to a vendor, open it, or craft with it">Best thing to do</th><th class="num" title="What one brings that way, after the AH's cut where it sells on the AH">Each</th><th class="num" title="Count x each">Total</th><th title="Warnings and facts about it: hover one">Notes</th></tr></thead><tbody>
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
      <div class="tablewrap"><table><thead><tr><th class="rk" title="Ranked by how cheap it is vs its long-term average x how well it sells x risk">#</th><th title="The item and why it might rise: from WoW Classic history and how players progress, so speculation, not Forever data">Item and idea</th><th class="num" title="What one costs now: your realm's lowest listing (its average when none are listed), and how many are listed">Buy now</th><th class="num" title="Lowest listing compared with TSM's 14-day realm market value: below it is cheaper than lately">vs 14-day avg</th><th class="num" title="Buy price now compared with TSM's long-term realm average: below it is cheaper than usual">vs long-term avg</th><th class="num" title="How the lowest listing changed over all of this app's price snapshots">Trend</th><th class="num" title="How the lowest listing changed over the last 7 days of snapshots">7 days</th><th class="num" title="How many sell a day across the region (TSM), and the share of listings that sell">Sold/day (region)</th><th class="num" title="What you'd lose if the price fell to what a vendor pays">Worst case</th><th title="How risky the idea is (from the curated list), and warnings">Risk</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="hint">Trend: our own price snapshots (lowest listing); with a day or more of history each end is a 12-hour median, so one odd listing can't swing it. 7 days appears after a week. Worst case: what you'd lose if the price fell to what a vendor pays. Click a row for the item's details and price chart; Watch alerts you on big price moves.</div>${dropped}</div>`;
  },
  async market() {
    const id = +(sessionStorage.getItem('marketItem') || 0);
    let d = null;
    if (id) { try { d = await api('/api/market?id=' + id); } catch (e) { sessionStorage.removeItem('marketItem'); } }
    return `<div class="panel"><h2>Market <small>search any item: price history, trend and market signals</small></h2>
      <div class="ac"><input id="mq" placeholder="Type an item name…" autocomplete="off" spellcheck="false" value="${d ? esc(d.name) : ''}"><div id="ac-list" class="ac-list hidden"></div></div></div>
      ${d ? marketBody(d) : '<div class="empty">Start typing an item name, then pick it from the list (arrow keys and Enter work too).</div>'}
      ${await marketsPanel()}`;
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
      ${Object.keys(chars).length ? `<table><thead><tr><th title="Your characters, from ForeverMoneyBridge and TSM">Character</th><th title="From ForeverMoneyBridge (TSM doesn't record levels)">Level</th><th class="num" title="Gold on that character">Gold</th><th title="Each profession and its skill">Professions</th><th title="Which addon these come from">From</th></tr></thead><tbody>${Object.entries(chars).map(([n, c]) => `<tr><td>${esc(n)}</td><td>${c.level ?? '<span class="pill">needs addon</span>'}</td><td class="num">${money(c.money)}</td><td>${Object.entries(c.professions || {}).map(([p, v]) => `${esc(p)} ${v.rank}`).join(', ')}</td><td class="pill">${esc(c.source)}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">No characters detected yet.</div>'}
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
      <div>Levelling: AH sales within</div><div><input type="number" step="1" min="0" id="s-levdays" value="${s.levelling_ah_days ?? 2}"> days <span class="pill">the levelling planner counts only as many AH sales of a product as your share of the region's sales in this many days; the rest go to a vendor or disenchanting. Keeps slow sellers (one sale every few days) from making a path look cheap</span></div>
      <div>Switch factor</div><div><input type="number" step="0.1" id="s-switch" value="${s.switch_bonus}"></div>
      <div>Fishing casts per hour</div><div><input type="number" id="s-casts" value="${s.casts_per_hour || 240}"></div>
      <div>Fishing skill bonus</div><div><input type="number" id="s-fbonus" placeholder="auto" value="${s.fishing_skill_bonus ?? ''}"> <span class="pill">leave empty to work it out from your bags, bank and gear (best pole + best lure + fishing hat and boots); type a number to override. Fewer fish get away when your skill plus this beats the zone's skill</span></div>
      <div>Herb nodes per hour</div><div><input type="number" id="s-hph" value="${s.herb_nodes_per_hour || 40}"> <span class="pill">until ForeverMoneyBridge has 10+ minutes of your herbalism</span></div>
      <div>Ore nodes per hour</div><div><input type="number" id="s-oph" value="${s.ore_nodes_per_hour || 40}"> <span class="pill">until ForeverMoneyBridge has 10+ minutes of your mining</span></div>
      <div>Your time is worth</div><div><input type="number" step="0.5" id="s-tv" value="${s.time_value_gold || ''}" placeholder="auto"> gold an hour <span class="pill">blank = half your best measured farming. Routines that earn less than their time is worth are marked "not worth your time"</span></div>
      <div>Kills per hour</div><div><input type="number" id="s-kph" value="${s.kills_per_hour || 60}"> <span class="pill">mobs you kill (and skin) in an hour of farming: used for skinning and mob farming gold per hour</span></div>
      <div>AH sale price</div><div><select id="s-basis"><option value="realm" ${!['lower', 'min_buyout', 'actual_sales'].includes(s.sale_price_basis) ? 'selected' : ''}>your realm's lowest listing (what you'd list at; region data only for how fast it sells)</option><option value="lower" ${s.sale_price_basis === 'lower' ? 'selected' : ''}>the lower of the lowest listing and its usual sale price (what you can count on)</option><option value="min_buyout" ${s.sale_price_basis === 'min_buyout' ? 'selected' : ''}>current lowest buyout (what you'd list at)</option><option value="actual_sales" ${s.sale_price_basis === 'actual_sales' ? 'selected' : ''}>what items actually sell for (most conservative)</option></select> <span class="pill">nothing listed: the usual sale price in every case. With the first choice, tables show "up to" the profit at the lowest listing</span></div>
      <div>Fishing drop rates</div><div><label class="chk"><input type="checkbox" id="s-ownrates" ${s.own_logs_for_rates ? 'checked' : ''}> also use my own catch logs</label> <span class="pill">off: Wowhead Forever's big samples only; your logs still give your pace and got-away rate</span></div>
      <div>Fishing pools</div><div><label class="chk"><input type="checkbox" id="s-pools" ${s.fishing_pools ? 'checked' : ''}> count pool loot in gold/hour</label> <span class="pill">off: open water only; trunks, Stranglekelp and Rumsey Rum from pools shown as a bonus, since pools have to be found first</span></div>
      <div>Updates</div><div><label class="chk"><input type="checkbox" id="s-autoupd" ${s.auto_update !== false ? 'checked' : ''}> update the app when it starts</label> <span class="pill">gets the latest version from GitHub each time you start it (only in a folder made with git clone; your settings and data are never touched)</span></div>
      <div>Shared data key</div><div><input id="s-datakey" type="password" autocomplete="off" style="width:16em" value="${esc(s.data_key || '')}" placeholder="from the app's author"> <span class="pill">unlocks the Wowhead Forever data shared with friends (drop, skinning and fishing counts). Kept on this PC only. ${esc(STATE.pack_status || '')}</span></div>
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
  labelTables();          // phone cards at once, not only on the next paint (a hidden window never paints)
}

// Narrow windows: tables become stacked cards (style.css), each value labelled with its column's name
function labelTables(root = document) {
  root.querySelectorAll('table').forEach((t) => {
    const heads = [...t.querySelectorAll(':scope > thead th')].map((th) => th.textContent.replace(/[?▲▼]/g, '').trim());
    if (!heads.length) return;
    t.classList.add('cardable');
    const first = heads.findIndex((h) => h && h !== '#');      // the item or what to do: the card's title
    t.querySelectorAll(':scope > tbody > tr').forEach((tr) => [...tr.children].forEach((td, i) => {
      if (td.dataset.label !== undefined) return;
      td.dataset.label = heads[i] === '#' || i === first ? '' : (heads[i] || '');
      if (i === first) td.classList.add('card-title');
    }));
  });
}
let labelQueued = false;
new MutationObserver(() => { if (!labelQueued) { labelQueued = true; requestAnimationFrame(() => { labelQueued = false; labelTables(); }); } })
  .observe(document.body, {childList: true, subtree: true});

function wireView() {
  document.querySelectorAll('#view tr.row[data-item]').forEach((tr) => { if (!tr.dataset.key) tr.onclick = (e) => { if (!e.target.closest('a') && tr.dataset.item) openItem(+tr.dataset.item); }; });
  if (TAB === 'profs' && $('#lp')) {
    $('#lp').onchange = (e) => { sessionStorage.setItem('levelProf', e.target.value); sessionStorage.removeItem('levelSkill'); render(); };
    $('#ls').onchange = (e) => { sessionStorage.setItem('levelSkill', e.target.value); render(); };
    $('#lt').onchange = (e) => { sessionStorage.setItem('levelTarget', e.target.value); render(); };
    $('#lde').onchange = (e) => { sessionStorage.setItem('levelDe', e.target.checked ? '1' : '0'); render(); };
  }
  if (TAB === 'craft') { $('#cp').onchange = (e) => { sessionStorage.setItem('craftProf', e.target.value); render(); }; $('#cd').onchange = (e) => { sessionStorage.setItem('craftDoable', e.target.checked ? '1' : ''); render(); }; }
  document.querySelectorAll('.sells-only').forEach((c) => c.onchange = (e) => { sessionStorage.setItem('sellsOnly', e.target.checked ? '1' : '0'); render(); });
  if (TAB === 'market') {
    wireMarket();
    const set = (k, v) => { sessionStorage.setItem(k, v); sessionStorage.removeItem('mkLimit'); render(); };
    if ($('#mk-sort')) $('#mk-sort').onchange = (e) => set('mkSort', e.target.value);
    if ($('#mk-filter')) $('#mk-filter').onchange = (e) => set('mkFilter', e.target.value);
    if ($('#mk-more')) $('#mk-more').onclick = () => { sessionStorage.setItem('mkLimit', String(+(sessionStorage.getItem('mkLimit') || 100) + 100)); render(); };
  }
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
        ah_cut: +$('#s-cut').value, market_share: +$('#s-share').value, min_sold_per_day: +$('#s-minspd').value, levelling_ah_days: $('#s-levdays').value === '' ? 2 : Math.max(0, +$('#s-levdays').value), switch_bonus: +$('#s-switch').value,
        casts_per_hour: +$('#s-casts').value, fishing_skill_bonus: $('#s-fbonus').value === '' ? null : +$('#s-fbonus').value, kills_per_hour: +$('#s-kph').value, time_value_gold: $('#s-tv').value === '' ? null : +$('#s-tv').value, herb_nodes_per_hour: +$('#s-hph').value, ore_nodes_per_hour: +$('#s-oph').value, own_logs_for_rates: $('#s-ownrates').checked, sale_price_basis: $('#s-basis').value, fishing_pools: $('#s-pools').checked,
        include_unverified_recipes: $('#s-unver').checked, data_key: $('#s-datakey').value.trim(), auto_update: $('#s-autoupd').checked,
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
    ${o.needs ? `<div>Needs</div><div class="needs">${esc(o.needs)}</div>` : ''}</div>${d.price_check ? `<div class="hint">⚠ Second opinion: ${esc(d.price_check.text)}</div>` : ''}`;
  const ef = d.effort;
  if (ef) html += `<h3>Your time</h3><div class="kv"><div>About</div><div>${num(ef.minutes, 1)} minutes a day (${num(ef.posts, 0)} auction posts incl. reposts, ingredients, crafting, a vendor trip: estimates)</div><div>For</div><div>${money(o.daily)} a day (its profit a day: more time would not sell more)</div><div>Your time is worth</div><div>${money(ef.time_value)} an hour <span class="pill">half your best measured farming; change it in Settings</span></div></div>`;
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
    const madeWith = (m) => m.made_with ? `<div class="hint">You can make this with a ${esc(m.made_with.tool)} (once every ${num(m.made_with.cooldown_hours, 0)} hours; see its own row on this tab). It is costed here at its price because selling it is what you give up by using it.</div>` : '';
    const learnText = !d.learn ? 'unknown / already known'
      : d.learn.how === 'item use' ? 'Nothing to learn: you use the item itself (game data: what using it does)'
      : d.learn.how === 'trainer' ? `Trainer, ${money(d.learn.cost)}${d.level_required ? ` (at character level ${d.level_required} or higher)` : ''}`
      : d.learn.how === 'tool' ? `Nothing to learn: you need a ${itemLink(d.learn.item_id, d.learn.name)}, which you keep (it is not used up). ${d.learn.owned ? 'You have one.' : `${d.learn.owned === false ? 'Your bags, bank and gear have none: ' : ''}it costs ${d.learn.cost !== null ? money(d.learn.cost) : '? (not on AH / vendor)'} (${esc(d.learn.source || '')}), once.`}`
      : `${esc(d.learn.name || 'recipe')}: ${d.learn.cost !== null ? money(d.learn.cost) : 'not on AH / vendor'} (${esc(d.learn.source || '')})`;
    html += `<h3>Ingredients <small>per craft</small></h3><table><tbody>${d.mats.map((m) => `<tr><td>${m.count}×</td><td>${itemLink(m.item_id, m.name)}${madeWith(m)}</td><td class="num">${money(m.unit)}</td><td>${esc(m.source)} ${flagHtml(m.flags)}</td></tr>`).join('')}</tbody></table>
      <div class="kv" style="margin-top:8px">${d.disenchant ? `<div>Disenchanted (total) <span class="pill">Classic table</span></div><div>about ${money(d.revenue)}: each one gives ${deMats(d.disenchant)}${deWho(d.disenchant)}</div>` : `<div>Sells for (total)</div><div>${money(d.revenue)} via ${esc(d.sell_channel)} (${esc(d.sell_source)})</div>`}
      <div>Skill needed</div><div>${d.skill_required}${d.skill_exact ? '' : ' (estimated)'} ${d.thresholds ? `<span class="pill">orange/yellow/green/grey: ${d.thresholds.join(' / ')}</span>` : ''}</div>
      <div>${d.tool ? 'Tool' : 'Learn it'}</div><div>${learnText}</div>
      ${(d.tools || []).length ? `<div>Tools in your bags</div><div>${d.tools.map((t) => `${t.item_id ? itemLink(t.item_id, t.name) : esc(t.name)}: ${t.have ? 'you have one' : t.have === false ? `none in your bags, bank or gear; ${t.cost !== null ? `${money(t.cost)} (${esc(t.source)})` : 'not on AH / vendor'}, once` : 'needed (your bags are not read: install Syndicator)'}`).join('<br>')}<div class="hint">The recipe needs this in your bags to be made; it is not used up.</div></div>` : ''}
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
      ${d.drops.map((x) => `<tr class="row" data-item="${x.item_id}"><td>${itemLink(x.item_id, x.name)}${x.source === 'Everloot' ? ' <span class="flag warn" title="Rate from Everloot (uploaded by players, CC BY-SA 4.0): Wowhead Forever has none for this mob yet">Everloot</span>' : ''}</td><td class="num">${num(x.per_kill, 3)}</td><td class="num">${money(x.value)}</td><td class="num">${num(x.count, 0)} of ${num(x.looted, 0)}</td></tr>`).join('')}</tbody></table>
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
    ${d.lure ? `<div>Lure</div><div>${d.lure.used ? `${esc(d.lure.name)} (+${d.lure.bonus}) used here: ${num(d.lure.per_hour, 0)} an hour at ${money(d.lure.each)} each = ${money(d.lure.cost_per_hour)} an hour, taken off the gold per hour <span class="pill">${money(d.lure.gph_with)}/h with it, ${money(d.lure.gph_without)}/h without</span>` : `${esc(d.lure.name)} not worth it here <span class="pill">${d.lure.gph_with > d.lure.gph_without ? '' : `${money(d.lure.gph_with)}/h with it (after ${money(d.lure.cost_per_hour)}/h of lures), ${money(d.lure.gph_without)}/h without`}</span>`} <span class="pill">price: ${esc(d.lure.price_source)}</span></div>` : ''}
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

// disenchanting (ForeverRecipes' WoW Classic reference table: a labelled estimate, never a Top pick)
const deMats = (de) => de.mats.map((m) => `${itemLink(m.item_id, m.name)} ${m.min === m.max ? m.min : `${m.min}-${m.max}`} (${num(m.chance * 100, 0)}%, ${money(m.each)} each)`).join(', ');
const deWho = (de) => `<div class="hint">Needs Enchanting ${de.skill} (estimated, WoW Classic rule). ${de.enchanter ? `${esc(de.enchanter)} has ${de.enchanter_skill}${de.can ? ': can do it now (mail it there).' : '.'}` : 'None of your characters has Enchanting.'} The results and chances are WoW Classic reference data (ForeverRecipes calls them provisional estimates), not Forever data.</div>`;
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
      ${it.disenchant ? `<div>Disenchant it <span class="pill" title="${esc(it.disenchant.source)}">Classic table</span></div><div>about ${money(it.disenchant.value)} each: ${deMats(it.disenchant)}${deWho(it.disenchant)}</div>` : ''}
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
    const rb = $('#refresh-now'), refreshed = rb.disabled;
    if (refreshed) { rb.disabled = false; rb.textContent = 'Refresh now'; }
    await loadState();
    if (refreshed) toast(refreshMessage());
    if (!['settings', 'search'].includes(TAB)) render();
    (data.events || []).forEach((ev) => {
      toast(ev.text);
      if (ev.important && window.Notification && Notification.permission === 'granted') new Notification('WoW Forever Money', {body: ev.text});
    });
  });
  es.addEventListener('tick', async () => { await loadState(); });
  es.onerror = () => { $('#status').textContent = 'Lost connection to the app. Is it still running?'; };
}

// After "Refresh now": prices come from the TSM app's sync; bags, gold and professions only update when the addons save,
// which happens on /reload or logout in game. Say when that last happened and recommend a /reload when it's been a while.
const RELOAD_AFTER_MIN = 10;
function refreshMessage() {
  const f = (n) => (STATE.freshness || []).find((x) => x.name === n) || {};
  const saved = Math.max(f('inventory').file_time || 0, f('profile').file_time || 0);
  const tsm = f('tsm');
  const prices = `Prices are from TSM's last download (${tsm.data_time ? ago(tsm.data_time) : 'unknown'}; the TSM desktop app updates them about hourly).`;
  if (!saved) return `Refreshed. ${prices} Your bags and gold aren't read yet: they need Syndicator or ForeverMoneyBridge, saved by a /reload in game.`;
  const mins = (Date.now() / 1000 - saved) / 60;
  return mins > RELOAD_AFTER_MIN
    ? `Refreshed. Your bags, gold and professions were last saved in game ${ago(saved)}: type /reload in game to save them now, then refresh again. ${prices}`
    : `Refreshed. Your bags, gold and professions were saved in game ${ago(saved)}. ${prices}`;
}

$('#refresh-now').onclick = async () => {
  const b = $('#refresh-now'); b.disabled = true; b.textContent = 'Refreshing...';
  try { await api('/api/refresh', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'}); } catch (e) { toast('Refresh failed: ' + e.message); }
  setTimeout(() => { b.disabled = false; b.textContent = 'Refresh now'; }, 4000);
};
document.querySelectorAll('#tabs button').forEach((b) => b.onclick = () => { TAB = b.dataset.tab; localStorage.setItem('tab', TAB); render(); });
(async () => { await loadState(); await render(); connect(); })();
