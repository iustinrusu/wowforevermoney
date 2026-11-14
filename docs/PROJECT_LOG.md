# Project log

The memory of this project across chats. Newest entries at the top of each section.
Claude: read this at the start of a session; update it before ending a task (see `CLAUDE.md`).

## Goal

Make as much gold as possible in WoW: Forever. The app knows every item, uses TSM auction data, and ranks
every money-making option: crafting (any profession), vendor flips (vendor→AH, AH→vendor), recipe flips,
AH snipes, farming, fishing. It monitors continuously, updates itself when TSM syncs, and alerts on changes.

## The user's setup (as of 2026-11-14)

- Realm: **PvP-Horde** (the addon may record the server's internal name "CAMWOW EU5 Realm 4 PvP"), region
  Forever-EU, faction Horde.
- Main: rogue, level 42. Skinning 275, Leatherworking 161, Fishing 232, Cooking 225, First Aid 225, Poisons.
  Two alts with little gold. Gold ~26.8g across the faction (read from Syndicator).
- Profession thinking (2026-11-14 talk): keep Skinning + Leatherworking for the long run (push LW toward 265 for
  Devilsaur Gauntlets before most players reach 60); maybe add a gathering/alchemy alt later.
- TSM addon + TSM desktop app (syncs AppData.lua about hourly).
- WoW install: `C:\Games\World of Warcraft\_forever_` (product `wowf`, build 1.60.1.x, interface 16001).
- Addons the app reads: TSM + AppHelper, QuestieDB, SkillUpForever, ForeverAngler, Syndicator, ForeverMoneyBridge
  (ours). Installed but not read yet: GatherLite (Forever node locations). Public addons come from the CurseForge app.

## Decisions (dated, with the reason)

- **2026-11-14 Your own time is never a rate (user: "I am low level and time spent in zones is not spent entirely on
  farming... only reported, computed or theoretical rates").** Removed everywhere: the "measured" gold/hour of
  `activity_zones` rows (now a loot log, flag `your_log`, no gph: "Kill mobs in Dustwallow Marsh 10.26g/h" was
  questing time), measured skinning/node/fishing pace (always the Settings numbers: skins, nodes, casts per hour),
  fishing's "measured here" pace, and your landed share (bites you didn't click depend on attention, like time;
  shown, not used). Time value = half the best farming spot that may reach Top picks (`Engine._hourly_ok`: Forever
  counts at Settings paces), else 2g/h. Also fixed: skinning rows said "your pace: catches per hour from
  your timed fishing" (a fishing label reused).
- **2026-11-14 Loot tables only from online sources (user: "we should not build our own loot tables").** The
  per-mob/node logging drafted as addon 1.5.0 was taken out before it was committed (ForeverMoneyBridge stays
  1.4.1); to-do item "own Forever loot tables" cancelled. If coins per loot are wanted later, the drafted method
  was: the gold change (PLAYER_MONEY) while a loot window is open + 1 s, no language-dependent text parsing.
- **2026-11-14 Got-away rate = the game's rule with your effective skill (user).** Effective skill = Fishing skill +
  setting `fishing_skill_bonus` (pole, gear, lure; default 0) against the zone's skill (WoW Classic zone skills,
  labelled); your own got-away log is never used. With no bonus set, the user's 232 in Tanaris (205) keeps 32%
  (232 - 205 + 5), so Tanaris dropped from 6g 91s/h; Bright Baubles (+75) brings it to 100%. Auto-filling the
  bonus from pole, gear and lures (and lure cost per hour) is in docs/plans/material-coverage.md step 6.
- **2026-11-14 Pools are undercounted (user's hunch, checked).** "With pools" only counts pool loot that appears in
  Wowhead's per-zone fishing counts (Tanaris 3.6% of catches, Stranglethorn 12.9%); pool objects' own contents
  (Floating Debris materials) were never read. Fix: docs/plans/material-coverage.md step 3.
- **2026-11-14 Every material needs Forever source data: top priority (user).** docs/plans/material-coverage.md.
  Coverage audit (`wfm/coverage.py`, Data health): a traded (region sold/day >= 1) looted item = Questie (Forever)
  drop/object sources, or a trade good of a gathered kind, or anything in a fishing table (Classic tables only hint
  what to look for: raw fish is meat 7/8 or food 0/5 in the data); crafted (recipe product) or vendor-bought ones
  are left out. Reading unit = one Wowhead Forever item page (all its source tabs). Start: 17 of 351 materials.
- **2026-11-14 Your plan for today (user: "Do these now should be our main attraction... think like a pro").**
  `wfm/plan.py` (pure functions, tests/test_plan.py) builds `result['plan']` (in `/api/state`), shown as numbered
  cards at the top of Top picks. Sources: cash-in from what the character you play holds (`Engine.my_holdings`:
  Syndicator bags, bank, mail, and auctions past their end time, which sold or came back), cooldown crafts
  (>= 20 h, doable, one per shared cooldown), Daily routines (top 'now'), snipes (count half: the listing may be
  gone), the best Forever-backed farming hour, one big flip (>= 1g at the lower of lowest-listing and usual-sale
  profit). Value today = gain x confidence - minutes x time value; <= 0 dropped; caps: 3 routines, 1 farm, 1 big
  flip, 2 of anything else; best 8 by value. **Shown in order of gold per hour of your time, not by value**
  (deviation from the brief: by value the 1-hour farm, worth the most in total, was always #1, while a 2-minute
  snipe or a 5-minute routine earns 3-10x more per hour and should be done first). List quantity per item =
  what sells in about 2 days at your share. Things you probably use yourself are named but never counted: class 0
  consumables (except raw fish/meat that recipes use: Raw Winter Squid is "food" in the data), spell reagents
  (15/1: Flash Powder, Thieves' Tools), profession tools (weapon subclass 14/20: Skinning Knife, fishing poles);
  found on the user's bags (29 Instant Poison III, Skinning Knife and Flash Powder were first listed for sale).
  Gear stays out of the vendor junk pile. "Do these now" was renamed "Daily routines".
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
- **2026-11-14 Effort and time value (user).** `Engine.effort`: estimated minutes a day for crafts and vendor
  flips (10 s per post, reposts = 1/sale rate up to 5, stackables posted 5 at a time, 15 s per AH ingredient,
  3 s per craft, 2 min vendor trip). Time value = half the best measured farming gold/hour (4.7g/h for the
  user) or `time_value_gold`. Ranking subtracts the time's worth; daily profit <= it -> `not_worth_time`
  (problem flag, out of Top picks): 434 rows on 2026-11-14. Notes are explained in full sentences under every
  table and in each row's details; cryptic labels rewritten.
- **2026-11-14 Daily routines vs occasional flips (user: "is Devilsaur really the top pick?").** Pattern: Devilsaur
  Gauntlets was #1 in Do these now: 69g profit at the 75g lowest listing x 0.26 sales a day (region 1.28/day x 20%)
  = 17.7g/day, even at confidence 0.36; it actually sells for 36g. Now Do these now needs >= 1 expected sale a day
  (`DAILY_ROUTINE`); slower ones go to "Occasional big flips" (ranked by profit per sale x confidence x risk)
  with profit at the region average sale price shown too. Column names: "Sales a day (you)" (shown as "1 every N
  days" under 1) and "Profit a day", with hover explanations. Not modelled yet: effort (e.g. 49 vendor-sold
  crafts a day ranks on profit alone).
- **2026-11-14 Gold was read wrong: the app thought the user had 3s 20c, really 26g 78s.** ForeverMoneyBridge
  1.4.0 saved 0 gold for the active character (its snapshot on PLAYER_LOGOUT/reload can read 0), while Syndicator,
  saved at the same moment, had 267,812c. Every affordability cap and "can't afford" flag used the wrong gold.
  Fixes: the app takes each character's gold from Syndicator when present (`World._merge_money`; the addon's
  value is kept as `money_addon`); realm names are matched loosely (the addon stored the server's internal name
  "CAMWOW EU5 Realm 4 PvP" where Syndicator/TSM say "PvP"); addon 1.4.1 no longer overwrites gold on logout
  and re-snapshots 5 s after login. Purse widget in the header (gold + bags/bank/mail/auction value).
- **2026-11-14 Name and look: "Gold Ever After"** ("happily ever after" + WoW: Forever). Theme: serif headings
  (Palatino/Book Antiqua, already on Windows), gold trim, tab icons, Wowhead item icons (iconizeLinks via the
  tooltip script the page already loaded), zebra tables, "How to read this page" on Top picks, "How this is
  worked out" per Gathering view. No new third-party scripts or fonts. Repo/folder name unchanged.
- **2026-11-14 Herbalism and mining spots + Gathering tab** (`wfm/nodes.py`, `Engine.node_spots`). Node locations:
  QuestieDB Forever spawns per zone. Items per node: Classic loot from the cMaNGOS dump already on disk (times the
  average number of gathers a node allows, data4/data5), flag `classic_yields`, never in Top picks. Black Lotus
  listed but not averaged (rare spawn); zones with < 5 nodes skipped; instances flagged. Classic skill table per
  node, labelled. The Farming tab became Gathering with a profession picker (primary/secondary explained).
- **2026-11-14 Dungeon detection fixed:** "continent not 0/1" called Forever's new open-world zones (Zephras Isle
  on continent 2991, Storm Cliffs 2791) dungeons. Now `gamedata.is_instance` uses the Classic instance map ids.
- **2026-11-14 Recipe cooldowns** (user OK'd the download: SpellCooldowns.csv, 120 KB, wago.tools, build
  1.60.1.70938; now in `gamedata.TABLES`). Cooldown = max(CategoryRecoveryTime, RecoveryTime) at DifficultyID 0;
  10+ minutes caps crafts a day at 24 h / cooldown (crafts and the material best-use volume). Forever values:
  Transmute: Arcanite and Legionite 47 h, elemental transmutes 23 h, Mooncloth 95 h, Refined Scale of Onyxia 2 h,
  Iron to Gold and Mithril to Truesilver 1 h, Transmute: Elemental Fire 10 min. Arcanite potential 38.8g/day ->
  20.3g/day (#1 -> #5 on Crafting).
- **2026-11-14 Transmutes share one cooldown in Forever** (user asked to check; SpellCategories 345 KB +
  SpellCategory 9 KB from wago.tools): category 310 "Transmute - Alchemy" holds Arcanite, Legionite, the eight
  elemental transmutes, Elemental Fire and Refined Scale of Onyxia; each starts the shared cooldown for its own
  duration. Iron to Gold, Mithril to Truesilver and Mooncloth have their own cooldowns. Rows get a "shared
  cooldown" flag and a Cooldown column; Top picks keep only the best recipe per shared cooldown.
- **2026-11-14 Sources graded by in-game checks.** The audit showed the hotfix cache's sell price for items only
  it has (new Forever items) was wrong for 310 of 342 checked (91%; all other fields matched; no consistent
  ratio, not explained by PriceVariance/PriceRandomValue, one version per record), while hotfix updates to
  shipped items were right (14/14). Now: source 'server-new' vs 'server'; `gamedata.grade_sources` grades every
  (source, field) against in-game checks, and a field wrong > 20% with 30+ checks is not trusted for that
  source's unchecked items (`Item.untrusted`): their vendor price counts as unknown (no AH-to-vendor flips, no
  vendor value or salvage), and they go first in the in-game check queue. 4,908 items affected on 2026-11-14.
- **2026-11-14 Skinning spots** (`wfm/skinning.py`, `Engine.skinning_spots`, `data/wowhead_forever_skinning.json`):
  Wowhead Forever "Skinned from" counts per mob (count/outof, levels, zones; Classic Era rows skipped, flag is
  `classicEra: true` on this tab), mobs skinned 50+ times, top 40 per item. Zone value per skin = average over mobs
  you can skin (Classic skill rule, labelled) and kill (<= level + 3), weighted by times skinned. Pace measured
  from ForeverMoneyBridge skinning logs (10+ min; 136/h for the user), else `kills_per_hour` (60). Read 7 of 19
  items before Wowhead returned 403 (all five leathers + Light/Medium Hide): values are a floor (flag
  `skins_partial`). Hourly Top picks now hold at most 5 rows per activity type.
- **2026-11-14 Wowhead 403 after 7 pages at 11 s spacing** (Heavy Hide). My batch made one more request after
  the 403 because the stop check returned a value instead of throwing: next time throw so the batch halts.
- **2026-11-14 Ranking (user: numbered rows, medals, smart order).** `Engine.rank`: profit basis (daily + 10% of
  what more gold adds; gph for activities; profit for snipes) x confidence x risk 1/(1 + 0.05 x downside/profit),
  downside = cost - vendor salvage x doable (skill gap 0.5, other profession 0.25) x problems 0.2 x preferred 1.1.
  Checked on real data: with 3s of gold, Green Firework (16/day affordable) now beats Junglevine Wine (1/day).
  Weights started at 25%/0.5 and were lowered after that check.
- **2026-11-14 Price history kept locally (TSM has none).** TSM's AppData holds only averages (marketValue 14-day,
  marketValueRecent, historical, regionHistorical, regionMarketValue, regionSale), no series. Each scan is
  ~6,800 rows (~0.3 MB), so hourly for 45 days would be ~300 MB: now every scan for 14 days, then one daily
  candle per item (OHLC of the lowest listing + averages) for 365 days. Snapshots exist only while the app runs.
- **2026-11-14 A wall of overpriced listings is not a price.** Root cause of a 9g "Short Staff" flip: `ah_sell`
  trusted the lowest listing whenever more than 3 were listed (10 listings at 10g; sells for 1s 90c). Now, if
  the lowest listing is over 3x the region average sale price, the value is that sale price (flag
  `listed_far_above_sales`). Fixed in the one price function, so crafts, flips, farming, container and fish
  values all follow. 745 of 6,203 listed items were over 2x; 3x (not 2x) keeps real realm premiums such as
  Arcanite Bar (lowest 50g, realm avg 42g, sells 24g), which stays flagged "sells for less".
- **2026-11-14 Only suggest items that actually sell (user).** `pricing.liquidity`: hard to sell = region
  sold/day < max(1, setting) or sale rate < 10% or realm listings > 10 days of region sales (realm sales <= region
  sales, so days of supply is a floor); never in Top picks, hidden by default on Crafting/Flips. Slow (rate < 25%)
  and crowded (> 3 days) rank lower (x0.7 each). Realm share of region sales is unknown (TSM data has only
  PvP-Horde), so no finer realm estimate. On 2026-11-14 it hid 333 of 684 crafts.
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

- 2026-11-14: ForeverMoneyBridge 1.4.0 records containers on the Forever client (Big-mouth Clam x7, Mithril
  Bound Trunk x4, Iron Bound Trunk x4 with contents); no trunk-only items (Bolts) appear in mob or skinning logs.
  Fishing exclusion not verifiable yet (no fishing logged since 1.4.0).
- 2026-11-14: Mithril Bound Trunk recomputed by hand: the 12 listed contents match to the copper (54s 47c of
  68s 50c; the rest is rarer contents).
- 2026-11-14: Questie has no mob lists for cloth (Linen to Runecloth); its elemental drop rates are Classic.
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

## What to do next

The ordered to-do list is **`docs/plans/TODO.md`**; each item links to a plan file with the full brief.
Older plan files (`skinning-mobs-investments.md`, `review-and-wowhead.md`) are superseded; their open parts
moved into `forever-data-next.md`.

## Open items

- The to-do list (`docs/plans/TODO.md`) holds the planned work; below are smaller known gaps.
- Not valued yet: coins inside containers, disenchanting (the user has an Enchanting alt), quest rewards for
  quest items (e.g. Savage Coast Blue Sailfin), lockpicking boxes beyond their contents.
- Plan for today: whether a cooldown is ready is unknown (the step says "if it is ready"); snipes come from the last
  scan; items on the AH list can include gear you would rather keep (the step says so).
- Not modelled: AH deposits and the cost of unsold listings; recipe learn cost is shown, not subtracted; bulk-buy
  cost uses only the lowest listing; vendors with faction '' are treated as accessible; effort uses estimates.
- Tips for the remaining top picks (only Frilled Lichen 249399 is done).
- Verify in game after the user /reloads: addon 1.4.1 saves gold correctly (1.4.0 saved 0 on logout; still unchecked on
  2026-11-14: the saved file predates the 1.4.1 install); vendor-price
  recording at a vendor; fishing `sources`/`pools` (does GetLootSourceInfo give the pool's object id?).
- No JavaScript syntax check in the tests (no Node on this PC): check the browser console after editing
  `web/app.js`; tests/test_web.py catches broken flag labels and names declared twice.
- Is Javnir Nashak (Green Firework vendor, Durotar) permanent or event-only? Questie gives no hint.
- The user's character name was in tests until 2026-11-14 and is still in the first commit (0b17b50); removing it
  from history needs a force push (the user's decision).

## Change log

- **2026-11-14** Own logged time/pace no longer used for any rate; time value from Forever farming spots; pace labels
  fixed; got-away from effective skill (setting `fishing_skill_bonus`); material-coverage plan (top priority);
  coverage audit on Data health. Tests: 145.

- **2026-11-14** Plan for today on Top picks (`wfm/plan.py`, `Engine.my_holdings`, plan cards with medals, chips and
  "How this plan is made"); "Do these now" renamed "Daily routines"; narrow screens no longer scroll sideways
  (`.grid2 > * { min-width: 0 }`). On the user's data: 8 steps, ~25g expected for ~1.4 hours. Tests: 137.

- **2026-11-14** Docs cleanup for new sessions: stale plan sections replaced by a pointer to docs/plans/TODO.md,
  open items pruned, setup updated, missing Wowhead fishing/container reads added to the plan, new standing rules
  (plain explanations, CurseForge addons, no real character names on GitHub); character name removed from tests.

- **2026-11-14** Effort model and time value; "Time a day" column; plain-language notes everywhere.

- **2026-11-14** Occasional big flips section; clearer per-day columns with hover help. Tests: 121.

- **2026-11-14** Purse in the header; gold from Syndicator (fixes 0 gold from the addon); addon 1.4.1. Tests: 120.

- **2026-11-14** UI refresh and new name (Gold Ever After); README section "Addons this tool uses" (CurseForge app).

- **2026-11-14** Gathering tab (Fishing, Skinning, Herbalism, Mining, Mob farming, Materials), herb/ore spots,
  instance detection by map id, settings for nodes per hour.

- **2026-11-14** Cooldown column (shown where a row has one); shared transmute cooldown from SpellCategories.
  Tests: 118.

- **2026-11-14** Recipe cooldowns from SpellCooldowns cap crafts per day ("cooldown" flag, shown in details).
  Tests: 117.

- **2026-11-14** Item sources graded by in-game checks; new hotfix items' vendor prices untrusted until checked;
  audit says which (source, field) is untrusted. Tests: 116.

- **2026-11-14** Skinning spots on the Farming tab and in hourly Top picks; skins-per-hour setting; Wowhead
  Forever skinning snapshot (7 items). Tests: 113.

- **2026-11-14** Ranking: `Engine.rank` score on every row, # column with gold/silver/bronze medals, "Why it's
  ranked here" in details, investments ranked (cheap vs long-term x sells x risk), numbered bags and search.
  Tests: 107.

- **2026-11-14** History: 14 days of scans + daily candles for a year (`History.compact`); Market tab shows TSM
  long-term and recent averages and a long-term reference line. Tests: 99.

- **2026-11-14** Overpriced listing walls valued at actual sales (`pricing.WALL = 3`). Short Staff flip: 9g 49s
  -> 78c. Tests: 98.

- **2026-11-14** Market tab (`wfm/market.py`, `/api/market`): autocomplete search, SVG price chart (line or daily
  candles, listings as volume, hover crosshair, 24h/7d/30d/all), and five signals summed into a sentiment label
  (+-2 thresholds; no data = no vote). Hand-drawn SVG, no chart library (no new third-party script). Tests: 96.

- **2026-11-14** Selling check (`pricing.liquidity`): "barely sells" / "slow to sell" / "crowded" flags, Sells
  column, "How well it sells" in details, filter on Crafting and Flips. Tests: 90.

- **2026-11-13** Items sold only by Black Market agents get no vendor price until ForeverMoneyBridge sees the
  real one (user's choice): no vendor flips or ingredient costs from the game-file price. Affected now:
  Frilled Lichen 249399, Torbernite 248820, Pristine Leather 249427.

- **2026-11-13** Frilled Lichen (249399) costs **4g 50s** at Mister Graphed (Black Market), seen in game by the
  user; the tip and the black-market flag text said 4s 50c (coin icons misread on Wowhead). Corrected. Lesson:
  hand-written prices must say which coin they mean and be checked in game.

- **2026-11-13** Friend's Crafting tab was empty: without SkillUpForever every recipe was dropped as unverified.
  Now, when SkillUpForever is missing, crafts are shown flagged "unverified recipe" (still never Top picks);
  Data health says what is lost. Top picks warns when the character/professions aren't detected. Tests: 82.

- **2026-11-13** `start.bat` finds Python 3.13+ (per-user and all-users installs, the `py` launcher, PATH;
  skips the Microsoft Store "python" shortcut) and, if missing, offers `winget install --id Python.Python.3.13`.
  Tested: found here; missing + No; missing + Yes (winget stubbed). The `py` launcher branch is untested (no
  launcher on this PC), and the real winget install wasn't run.

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
