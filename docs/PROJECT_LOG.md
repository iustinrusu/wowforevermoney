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
- Gathering list wrongly includes crafted products (cooked fish, cured hides): exclude recipe products.
- Known gaps: vendors with faction '' treated as accessible; AH deposits ignored; bulk-buy cost uses only
  the lowest listing.
- Cast pace is the 240 casts/hour setting until ForeverMoneyBridge has 10+ minutes of timed fishing.
- Later: skinning spots and mob farming (Forever data first; Classic creature/skinning loot only as fallback).

## Change log

- **2026-11-13** v1 built: TSM parser, wago game data, Questie, SkillUpForever, engine (crafts, vendor
  flips, AH→vendor, snipes, gathering, measured zones), price history, alerts, audit, web UI with tabs, our
  addon ForeverMoneyBridge 1.1.0 (character snapshot, vendor prices, loot by zone with time). 28 tests.
- **2026-11-13** Added CLAUDE.md and this log; git repo with remote on GitHub.
- **2026-11-13** Fishing rebuilt: `wfm/classicdb.py` (cMaNGOS dump extractor, update scripts, pools,
  seasons, monthly GitHub check), `wfm/fishing.py` (spots, logs, got-away/pace model), Forever-first rows,
  Wowhead Forever snapshot for 5 zones, Data health check "Classic fishing tables vs Forever data".
- **2026-11-13** Valuation engine `wfm/valuation.py` (open-it channel, contents from Wowhead Forever +
  your opens), undervaluation watch (audit + alerts), My bags shows "Open it". Addon 1.2.0 logs container
  contents. 51 tests.
