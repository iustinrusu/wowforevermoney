# Project log

The memory of this project across chats. Newest entries at the top of each section.
Claude: read this at the start of a session; update it before ending a task (see `CLAUDE.md`).

## Goal

Make as much gold as possible in WoW: Forever. The app knows every item, uses TSM auction data, and ranks
every money-making option: crafting (any profession), vendor flips (vendor→AH, AH→vendor), recipe flips,
AH snipes, farming, fishing. It monitors continuously, updates itself when TSM syncs, and alerts on changes.

## The user's setup (as of 2026-11-13)

- Realm: **PvP-Horde**, region Forever-EU, faction Horde.
- Main: rogue, level 42. Cooking 225, Fishing 225, First Aid 225, Skinning 270, Leatherworking 161,
  Poisons 210. Two alts with little gold. Gold is low (~1-6g), so affordability matters.
- Preference: fishing > cooking > first aid. Switch to skinning/LW only if it makes a lot more gold.
- TSM 4.15 addon + TSM desktop app (syncs AppData.lua about hourly).
- WoW install: `C:\Games\World of Warcraft\_forever_` (product `wowf`, build 1.60.1.x, interface 16001).
- Addons in use that the app reads: TSM, QuestieDB, SkillUpForever, ForeverAngler, Syndicator,
  ForeverMoneyBridge (ours). The user updates most addons almost daily.

## Decisions (dated, with the reason)

- **2026-11-13 Seasons from Forever catches.** A seasonal fish counts as in season if it appears in Wowhead Forever
  counts read in the last 14 days; its opposite season is then off. No recent evidence -> Classic calendar,
  labelled. Forever rows drop out-of-season fish from their counts. Now: winter (Winter Squid caught, no Summer Bass).
- **2026-11-13 Starting the app always replaces an earlier copy** (PID file `data/app.pid`, or a python process
  listening on the port; nothing else is touched). Cause of the user's "zombie": the lock socket is bound but not
  listening, so netstat doesn't show it, and Claude's preview copy held it. tasklist can't see some processes;
  PowerShell's Get-Process can.
- **2026-11-13 Generic defaults for other users;** the user's own professions/level/realm/preferences live in their
  local `data/settings.json` (not in git). The GitHub repo is private: friends need collaborator access or a ZIP.
  Guide: `docs/GETTING_STARTED.md`.
- **2026-11-13 Usage rule (user):** when usage is tight, finish the current piece, commit, and postpone the rest.
- **2026-11-13 Investments tab.** Curated list `data/investments.json` (34 items, Classic-informed theses,
  labelled speculation); every id is checked against the item database and mismatches are dropped and shown.
  Forever data beside it: buy cost now, vs TSM 14-day realm average, our own snapshot trend (first vs latest
  under a day; 12-hour medians at each end after that; 7-day change after a week), region sold/day and sale
  rate, vendor-floor worst case, Forever recipes that use it. Server progression gauge = each cloth tier's
  share of region sold/day; the "then" comparison waits for a day of history because region sold/day only
  changes about daily. Recipe claims in the theses were checked against Forever's recipe table (Major Healing
  Potion doesn't use Mountain Silversage; Runecloth Bag uses bolts); enchants aren't in that table, so the
  Crusader claims are worded as Classic.
- **2026-11-13 Scheduled tasks are reminders only (user):** no scheduled task runs work by itself. Postponed
  work goes into a plan file in `docs/plans/`; a one-time reminder points to it and the user starts it.
- **2026-11-13 Item database = Forever server data first; your game client is the referee.** Source priority:
  in-game (addon item checks) > server data (client hotfix cache DBCache.bin, `wfm/hotfix.py`) > client tables
  (wago) > Wowhead tooltip > Questie name. Hotfix layout inferred from 1,523 overlapping items and graded per
  field; LanguageID, LockID, PageID, RequiredHoliday are untrusted (binary order differs). Result: 5,238 items
  added, 1,523 updated; all 7,304 priced items fully covered. Addon 1.4.0 checks up to 800 items per login
  (disagreements, items behind current picks, Wowhead-only items, a daily-rotating sample of 100).
- **2026-11-13 Prices self-correct:** few listings (<= 3) outside 0.5-2x the realm's recent average ->
  `price_looks_off`, valued at the recent average; stale-price banner on Top picks; Wowhead snapshots flagged
  after 30 days; Top picks ranked by profit x confidence (`engine.DOUBT` factors per flag).
- **2026-11-13 Crafts capped by ingredient market volume** (AH mats: sold/day x share / count per craft):
  vendor-sold crafts assumed 200/day (Mender's Mail Boots 6.36g/day). Future sections (levelling, switching)
  rank by `daily_if_affordable` instead of being emptied by today's gold.
- **2026-11-13 Review and strategy brainstorm:** `docs/REVIEW_2026-11-13.md` (UI/UX, strategies, next steps).
- **2026-11-13 Sale price = current lowest buyout (user's decision; supersedes the sales cap below).** The user:
  "prices should be based on minimum buyout... that the user would also list the item at". Setting
  `sale_price_basis` = `min_buyout` (default) or `actual_sales` (the conservative cap). Either way: nothing
  listed -> region average sale price (never the realm listing average alone: Hand Axe); `sells_lower` flag
  when listed 1.43x+ above real sales; contents/catch values ignore a lone outlier listing (`above_region`)
  and use its sale price. Live examples: Raw Winter Squid lowest 3.80s vs sales 2.50s (sale rate 0.47),
  Sunscale 3.98s vs 2.65s; Mageweave 26.49s lowest vs 31.35s sales (no difference: min of both).
- **2026-11-13 Full accuracy recheck.** The user said accuracy is non-negotiable. Fixes:
  - **Sale price is capped at the region's average actual sale price** (`pricing.ah_sell`). The #1 pick was a
    bogus Hand Axe vendor flip (listing avg 2.5g, real sales 6.65s); 15% of actively traded items list 1.5x+
    above real sales. This also cut the Mithril Bound Trunk from 3.74g to ~65s (rare contents were valued
    at wishful listings).
  - **Item values use only recipes you can make now** (`best_uses` doable_value); the higher-skill value is
    kept as `if_skilled` / flag `more_with_skill`. Flag `craft_limited_demand` when the product's market absorbs
    < 50 units/day at your share (e.g. Forever's Fishing Rack recipe makes trout worth 1.92s, ~11/day).
  - **Event-only vendors** (subName holiday/festival/darkmoon..., or spawns in both Elwynn and Mulgore =
    Darkmoon Faire, or no known spawn): flag `event_vendor`, out of Top picks; also on crafts using such mats.
  - Soulbound/quest items sell only to vendors (`sell_value`); valuation no longer applies the AH cut twice.
  - TSM `merged()` is order-proof; region commodity data (empty on Forever) can't overwrite realm fields.
  - Farming list drops processed goods (cooked food, potions, cured hides, cloth bolts) but keeps leathers.
- **2026-11-13 Own catch logs don't set drop rates (default).** Wowhead Forever counts only; the user's
  ForeverAngler/ForeverMoneyBridge logs give pace and got-away rate. Opt-in setting `own_logs_for_rates`.
  *Why (user):* their ForeverAngler log skews rates: small (612 casts), mixes pools and open water,
  incomplete.
- **2026-11-13 Fishing gold/hour = open water (default).** Pool-only loot (trunks, Stranglekelp, Rumsey Rum,
  Sagefish) is set aside and shown as a bonus (`value_with_pools`, `gph_with_pools`). Opt-in setting
  `fishing_pools`. *Why (user):* pools have to be found first, which takes running around. Result: Tanaris
  8.4g/h (20.5 with pools), Feralas 6.4 (14.0), Azshara 6.1 (7.6), Dustwallow 1.75 (9.2), Stranglethorn 1.6
  (27.3): Stranglethorn's value is almost all pools. Addon 1.3.0 records each fishing loot's source object
  (bobber 35591 = open water, else a pool), to measure the real pool share and search time.
- **2026-11-13 Item value = best of every channel** (`wfm/valuation.py`): AH, vendor, crafting, and *open it*
  (expected value of Forever contents at current prices, containers in containers included). Openable
  items come from the client's ItemSparse `Flags_0 & 0x4` (522 items). Openable without contents data =
  flagged `contents_unknown` (value is a floor). An "undervaluation watch" (Data health check + change
  alerts) lists anything looted/carried/caught that's openable without contents data, has no value, or is
  worth more opened than sold. *Why:* trunks were "worth 2c" (soulbound, vendor price only) while a Mithril
  Bound Trunk holds ~3.7g of Mageweave/Runecloth/leather; the user noticed it, the model didn't.
- **2026-11-13 Data must be WoW: Forever. Imperative (user).** Other versions only as labelled fallback,
  never in Top picks. Fishing: Forever data first (your catches + Wowhead Forever zone counts), one row per
  zone; Classic tables only as "Classic table: ..." rows. *Why:* checking 5 zones on Wowhead Forever showed
  Classic matches Forever in only 1 (Tanaris); Azshara is worth 137c/catch in Forever vs 314c in Classic;
  Feralas has a different fish list entirely.
- **2026-11-13 Fishing spots: layered sources** (superseded in part by the decision above). Classic
  fallback = cMaNGOS classic-db fishing tables (open, GPL-3.0). Angler's Field Guide is built on the same
  Classic data with unclear Forever provenance and an All Rights Reserved licence; Forever Fishing and
  FishFry show no percentages or sources. The 13 MB dump download was approved by the user.
- **2026-11-13 Wowhead Forever by hand:** zone Fishing tabs and item Contains tabs read in the browser pane,
  a few pages at a time, saved as dated snapshots (`data/wowhead_forever_fishing.json`,
  `data/wowhead_forever_containers.json`). Wowhead returned 403 after ~5 quick page loads; stop at once when
  that happens and go slower (8s+ between pages worked). Rows marked Classic Era are left out.
- **2026-11-13 Top picks for fishing** need confirming Forever data (10+ of your catches or 30+ Wowhead
  Forever catches) and 30+ Forever catches in total: a few lucky trunks made 7-25-catch samples look 2-3x
  better than big samples.
- **2026-11-13 Settings auto-fill** from our addon ForeverMoneyBridge (level, gold, professions), with TSM's
  saved data as a fallback. Manual settings remain the backup; addon professions replace the manual list,
  TSM professions merge onto it (TSM doesn't record gathering skills).
- **2026-11-13 Vendor prices:** a price the addon saw at a vendor wins over the game files (Black Market
  agents charge more than the base price). An item only counts as vendor-sold if a Questie vendor of the
  user's faction sells it (fixed phantom Alliance-only vendor items).
- **2026-11-13 Wowhead:** no bulk scraping (403 bot blocking; getting around it is off the table). Link every
  item; read pages by hand only for the top 10-20 picks and write short tips into `data/tips.json`.
- **2026-11-13 Format:** local Python app with a web page; stdlib server, SSE live updates, one dependency
  (cbor2). A refresh button reloads every source on demand.
- **2026-11-13 Sale price** = min(lowest listing, realm 14-day market value) minus 5% AH cut; units/day =
  region sold/day × market share (20%), capped by gold, stock and output. Conservative on purpose.
- **2026-11-13 Snipes** ("cheap relists") use recent references only: min(realm market, region market,
  region sale), sold/day ≥ 2, sale rate ≥ 0.15, listing < 60% of target. They're shown separately
  because they come from a single scan.

## Verified facts (don't re-derive)

- DBCache.bin v9: header 44 bytes ("XFTH", version, build, 32-byte hash); entries "XFTH" + push, unique, ?, table
  hash, record id, size, status (1 = valid) + data. ItemSparse hash 0x919BE54E, Item 0x50238EC2. Strings
  inline, null-terminated; no padding. 303 server-vs-Wowhead sell price disagreements on new items (awaiting
  in-game checks). wago's CSV export doesn't include hotfix rows (tried `&hotfixes=1`).
- The preview launcher may move the app to port 8766 if 8765 is busy; start.bat always uses 8765.
- 2026-11-13 recheck: raw TSM base-32 rows decoded by hand = parser output; 25/25 vendor sell prices (incl.
  Mageweave, Runecloth, leathers, potions, pearls, fish) match Wowhead Forever tooltips; top picks, container
  values, item values and fishing gold/hour for all 5 Wowhead zones match an independent recomputation (within
  1c rounding). Forever has no region commodity AH: `AUCTIONDB_COMMODITY_HISTORICAL` is empty.
- ForeverAngler counts: `c` = Fishing channel starts (every cast), `k` = fishing loot windows, `e` = "Your fish
  got away!" messages; c - k - e = missed bites / early recasts. Valid for pace, not for drop rates.
- TSM AppData.lua: item ids are decimal, every other number is base-32 (0-9, A-V). `regionSalePercent`
  and `regionSoldPerDay` are raw/1000. Checked against TSM's AuctionDBConfig.lua and an in-game tooltip
  (Raw Spotted Yellowtail: sale 45c, rate 0.631, sold/day 563.798). There's a regression test for this.
- TSM "market value" averages listings, not sales; sold/day comes from TSM users' accounting data, so it's
  a liquidity indicator.
- wago.tools serves Forever DB2 tables: `https://wago.tools/db2/<Table>/csv?build=<build>`; builds list at
  `https://wago.tools/api/builds` (key `wowf`). ItemSparse ships only ~19k of ~32k items; the rest come
  from Questie names and the Wowhead tooltip API (`https://nether.wowhead.com/forever/tooltip/item/<id>`).
- WoW addons can only write SavedVariables on /reload, logout or exit, never live.
- TSM's saved data has no character level and no gathering professions.
- ForeverAngler zone log: `c` = casts, `k` = caught, `e` = "Your fish got away!" messages; per-item counts
  in `fish`. No timing. Zone names come from the zone text (no subzone).
- cMaNGOS classic-db: the Full_DB dump was last rebuilt 2024-01-17; 407 update scripts have been added
  since. Fishing rules from the server source (mangos-classic GameObject.cpp, LootMgr.cpp): subzone loot
  table if it exists, else zone table; success if skill ≥ zone skill and roll(1-100) ≤ skill − zone skill + 5.
  Several Classic tables are incomplete (e.g. Loch Modan lists only Loch Frenzy at 25%; some coastal
  subzones list only the seasonal Winter Squid/Summer Bass).
- Forever doesn't seem to follow the Classic getaway formula: the user caught 113 and lost 17 in Tanaris
  (Classic zone skill 205) at skill 225, where Classic predicts ~25% success, not 87%.
- Wowhead Forever pages carry their data in `window.g_listviews` (`fishing` on zone pages: `note` "Waters in
  this zone have been fished N times", rows with `count`; `contains` on item pages: "opened N times", rows
  with `count` and `stack` [min, max]). Rows with `classicEra` set are Classic Era data. The "%" on an item's
  "Fished in" tab uses a different denominator (not fishing attempts): use zone pages for catch rates.
- Pools (cMaNGOS gameobject type 25) give trunks, Stranglekelp and Rumsey Rum besides their fish; pool
  spawn locations aren't usable from the dump. Trunk tier by pool tier: Tightly Sealed < Watertight <
  Iron Bound < Mithril Bound.
- ItemSparse `Flags_0 & 0x4` = openable (has its own loot); `LockID > 0` = needs Lockpicking/key.

## Postponed builds (plan `docs/plans/skinning-mobs-investments.md`; reminder 2026-11-14 00:15)

Postponed by the usage rule; the plan file has the full brief. Nothing runs by itself. In order:
1. **Skinning spots:** Wowhead Forever "Skinned from" tabs for leathers, hides and scales; QuestieDB mob
   zones; gold/hour from a kills_per_hour setting, measured when the addon has data.
2. **Mob farming:** Wowhead Forever "Dropped by" tabs for cloth, elementals and the best BoE drops; value per
   kill, plus skinning.
3. ~~Investments tab~~: done 2026-11-13 (see Decisions).

## Next session plan (plan `docs/plans/review-and-wowhead.md`; reminder 2026-11-14 10:00)

The user is firm that the data must be correct and accurate. In order:
1. **Review and test today's work adversarially:** `wfm/classicdb.py`, `wfm/fishing.py`, `wfm/valuation.py`,
   the engine's fishing/valuation/watch code, the loaders in `wfm/world.py`, `app.py` item/inventory, the
   fishing UI, and addon 1.2.0 (do `GetLootSourceInfo` and the `C_Container.UseContainerItem` hook exist on
   the Forever client?). Recompute by hand 3 fishing rows and 2 container values from the JSON snapshots
   and TSM prices, and compare with the app.
2. **Wowhead Forever, slowly:** zone Fishing tabs for every remaining fishing zone (Forever-only zones
   included), then the Contains tab for every item in the "Possibly undervalued items" check. One page
   every 8+ seconds; stop all Wowhead reading on the first 403. Read `window.g_listviews`, skip `classicEra`
   rows. Every 5th page, screenshot the tab and check a few numbers against what was extracted.
3. **Verify addon 1.3.0** once the user has /reloaded, fished and opened a trunk: `containers` in
   SavedVariables, no trunk contents in the fishing activity, and `activity[zone].fishing.sources/pools`
   (does GetLootSourceInfo give the pool's object id when fishing a pool, or the bobber's?). Then use the
   measured pool share/search time in the pool bonus instead of "every pool you pass".
4. Check the gathering list (crafted products are already excluded), then update this log, commit and push.

## Open items

- Read more Wowhead Forever zones (Arathi, Hinterlands, Western Plaguelands, Felwood, Un'Goro, Swamp of
  Sorrows, Desolace, Thousand Needles, Alterac, Hillsbrad, Wetlands, Moonglade, Winterspring, Eastern
  Plaguelands, Burning Steppes, Silithus, and Forever-only zones) and containers (Bloated fish, Sealed/Heavy
  Crate, locked chests) slowly; the undervaluation watch on Data health lists which containers matter.
- New addon ForeverMoneyBridge 1.2.0 logs container contents (and no longer counts trunk contents as
  fishing/mob loot): verify after the user opens a trunk and /reloads.
- Not valued yet: coins inside containers, disenchanting (the user has an Enchanting alt), quest rewards for
  quest items (e.g. Savage Coast Blue Sailfin), lockpicking boxes beyond their contents.
- Tips for the remaining top picks (only Frilled Lichen 249399 is done).
- Verify ForeverMoneyBridge vendor-price and loot recording after the user visits a vendor, loots and
  /reloads (only the character snapshot is verified so far).
- Known gaps: vendors with faction '' treated as accessible; AH deposits ignored; bulk-buy cost uses only
  the lowest listing.
- Cast pace is the 240 casts/hour setting until ForeverMoneyBridge has 10+ minutes of timed fishing.
- No JavaScript syntax check in the tests (no Node on this PC): an unescaped apostrophe broke the page once
  on 2026-11-13. Check the browser console after editing `web/app.js`.
- AH deposits and the cost of unsold listings aren't modelled; recipe learn cost is shown, not subtracted.
- Is Javnir Nashak (Green Firework vendor, Durotar) permanent or event-only? Questie gives no hint.
- Later: skinning spots and mob farming (Forever data first; Classic creature/skinning loot only as fallback).

## Change log

- **2026-11-13** `install_addon.bat`: installs ForeverMoneyBridge without Python or the app (finds WoW via
  TSM.cfg, the Battle.net registry entry, common folders, or asks; keeps the app-written Checks.lua).
  Tested: spaces and "(x86)" in paths (this broke cmd blocks at first; paths are now kept out of blocks),
  drag-and-drop, the prompt, TSM.cfg only, rerun. The registry fallback is untested (no entry on this PC).
  `.gitattributes` keeps .bat files CRLF, also in GitHub ZIP downloads.

- **2026-11-13** Investments tab (`wfm/investments.py`, `/api/investments`, `data/investments.json`), price
  history series now include region sold/day; page-script test for names declared twice. Tests: 81.

- **2026-11-13** Scheduled tasks turned into reminders only (user's request). Both postponed briefs saved as
  `docs/plans/skinning-mobs-investments.md` and `docs/plans/review-and-wowhead.md`; usage rule updated.

- **2026-11-13** Seasons from Forever catches; starting the app replaces an earlier copy; generic defaults
  (the user's own values in local `data/settings.json`); `docs/GETTING_STARTED.md`. Tests: 67.

- **2026-11-13** Item database from the server's hotfix cache + in-game item checks (addon 1.4.0); price safeguards
  (odd listings, stale banner, snapshot age, confidence ranking); crafts capped by ingredient volume; UI fixes;
  review doc. Tests: 66 (incl. module imports and page-script label check).

- **2026-11-13** v1 built: TSM parser, wago game data, Questie, SkillUpForever, engine (crafts, vendor
  flips, AH→vendor, snipes, gathering, measured zones), price history, alerts, audit, web UI with tabs, our
  addon ForeverMoneyBridge 1.1.0 (character snapshot, vendor prices, loot by zone with time). 28 tests.
- **2026-11-13** Added CLAUDE.md and this log; git repo with remote on GitHub.
- **2026-11-13** Fishing rebuilt: `wfm/classicdb.py` (cMaNGOS dump extractor, update scripts, pools,
  seasons, monthly GitHub check), `wfm/fishing.py` (spots, logs, got-away/pace model), Forever-first rows,
  Wowhead Forever snapshot for 5 zones, Data health check "Classic fishing tables vs Forever data".
- **2026-11-13** Accuracy recheck: sale prices capped at real sales, doable-recipe values, event vendors,
  soulbound rule, double-cut fix, TSM merge order, farming filter. 57 tests.
- **2026-11-13** Valuation engine `wfm/valuation.py` (open-it channel, contents from Wowhead Forever +
  your opens), undervaluation watch (audit + alerts), My bags shows "Open it". Addon 1.2.0 logs container
  contents. 51 tests.
