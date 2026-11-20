# Plan: Forever source data for every material (top priority)

Saved on 2026-11-14 (usage at 77%: postponed, not cut off). Nothing runs by itself: a reminder points here.
To start, open a Claude Code session in this folder and say "Do the plan in docs/plans/material-coverage.md".

First read CLAUDE.md and docs/PROJECT_LOG.md. Standing rules apply: Forever data only (Classic only as a labelled
fallback, never in Top picks), accuracy first with tests, plain-language explanations, ask before any download,
Wowhead read slowly by hand (below), check usage before each step and postpone with a plan file + a reminder that
runs nothing. End commit messages with: Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>.

## What the user asked (2026-11-14)
- "'some skins not counted' should be fixed. This problem stems from not having a full db of items. Try to cover
  all materials and items, it's important, this is top priority for our app data accuracy."
- "Own per mob and per node loot tables should come from online data sources, we should not build our own loot
  tables." (Item 2 of the old to-do list is cancelled; ForeverMoneyBridge stays at 1.4.1.)
- "Most of the gold in fishing comes from floating debris which yield materials, but correct me if I'm wrong."
  Checked: likely right. Our "with pools" figure only counts pool loot that shows up in Wowhead's per-zone
  fishing counts (trunks, Stranglekelp, Rumsey Rum at the share Wowhead users happened to fish pools: Tanaris 3.6%,
  Stranglethorn 12.9%). What a pool itself yields is on the pool object's own Wowhead page, never read; zone counts
  show only traces (Bolt of Runecloth 0.01% in Stranglethorn). So pool value is undercounted.
- Got-away rate = the game's rule with effective skill (skill + pole, gear, lure) vs the zone's or pool's skill.
  Done 2026-11-14 (setting `fishing_skill_bonus`); follow-ups in step 6.

## Progress (session 2, 2026-11-14)
- Step 1 done: Everloot (everloot.app, CC BY-SA, player uploads) is the only bulk Forever source found; it covers 15%
  of the uncovered traded material value with tiny samples, so it does not replace page reading (project log).
  1b done: docs/plans/wowhead-data-request.md (the user sends it).
- Step 2 done: `wfm/wowhead_items.py`, `data/wowhead_forever_items.json`, importer `python -m wfm.wowhead_items import`,
  coverage, node yields, skinning merge, mob farming rows (to-do item 4, first version).
- Step 3: 76 of the top 100 read at one a minute (plus 6 earlier pages); **Wowhead returned 403 at 15:28 on page 77
  (12804 Powerful Mojo)**. Back-off check at 15:59 (30 minutes later): one page (12804) loaded normally, so the
  block had lifted. 16:01-16:08: 4 more at 2 minutes apart, no block (12803 248815 3712 8836), then 4236 Cured Heavy
  Hide at 16:21 (it had been skipped on an assumption; the user: never skip, check everything in order. Its page has
  no loot source, only "Created by": crafted-only, now confirmed). Left, in order: 1206 15419 12800 3820 13546 249428 2842
  8154 12203 6471 3864 249391 249427 12184 4232 6037 13464 1529 4387 3182 3356 5500, then the skinning items
  7286 8165 15412 15423. Next sessions (pace decided 2026-11-15): one page every 2 minutes, at most 20 a session; at a 403 stop, then try one page after 30 minutes, 2 hours, the next day; after a second block, 5 a session.
- Session 3 (2026-11-15): 20 pages at 2 minutes apart, no block: 1206 15419 12800 3820 13546 249428 2842 8154 12203
  6471 3864 249391 249427 12184 4232 6037 13464 1529 4387 3182 (102 item pages in all). Left of the top 100: 3356
  Kingsblood, 5500 Iridescent Pearl; then the skinning items 7286 8165 15412 15423, the pools (step 3 list), Javnir
  Nashak (checklist A7). A saved batch is checked against a SHA-256 of the tab's store before importing.
- **Reading order from 2026-11-20:** the Data health check "Wowhead reading queue" (`coverage.reading_queue`): items
  and mobs together, by the gold a day the app can't see yet x a level weight (level 60 in full, 30 half, at least a
  fifth). A mob: an hour of it by the WoW Classic loot table (`wfm/classicmobs.py`, a guide only) at today's prices,
  the market limit and its kill speed, minus what Forever data shows; rare and named mobs (under 5 spawn points in
  QuestieDB) left out. An item without Forever source data: your share of the region's trade in it a day; items only
  dungeon mobs drop are left for the Dungeons view (C4). Read it from the top, skip pages read in the last month.
- Session 6 (2026-11-20, late evening, the first from the reading queue; the user: "Do it now"): 20 pages, 2 minutes
  apart, no block, the queue's top 20: items 13486 16713 287020 4500 16723 12692 12809 16710 12820 13047 18362 16673
  273127 13443 287033 13466 18333 13444, npcs 11745 8546. The coins ("Worth") now come from the coin icons (Dark
  Adept 5s 82c). Saved with every special character as a \u escape, so the copy was exact the first time (SHA-256,
  15,467 characters); kept in the tab as `wfm_pages_saved_006`. No Forever drops recorded yet: Cyclone Warrior.
  Pages: 140 items, 21 npcs.
- Session 5 (2026-11-20, evening, the mob farming review): 20 pages, 2 minutes apart, no block. Items 7081 16252
  14505 13499 12808 16246 15753 7069 7079 13496, npcs 8667 4494 8526 8550 14455 8525 7372 6138 7132 9397 (order: the
  user asked for high-level, high-interest pages first). The reader now keeps an npc page's Quick Facts (`facts`:
  health, level, the coins a kill gives as "Worth", read from the coin icons from the next session on; this batch's
  Worth was taken from the text, two numbers = silver and copper). Batch checked with SHA-256 (13,200 characters;
  a non-breaking space in "React: A H" had to be restored), saved in the tab as `wfm_pages_saved_005`. No Forever
  drops recorded yet (re-read later): Shadowmage, Whirling Invader, Living Storm, Recipe: Greater Shadow Protection
  Potion, Recipe: Greater Nature Protection Potion. Next: a reading queue ranked by gold at stake and mob level.
- Session 4 (2026-11-20, just after midnight): 20 pages at 2 minutes apart, no block: spell 1289305 (B10), items
  274964 13545 18335 8396 (B9), vendors 3364 15419 4453 260565 16015 248200 2664 265346 2832 (checklist A0), 3356
  5500 (the top 100 is done), 7286 8165 15412 15423 (the skinning items are done). The tab's storage had lost the
  reader: set up again (`wfm_fn` now also keeps a vendor's Sells tab: [item, stock (-1 = unlimited), price, standing,
  1 if it costs a currency or items]; `wfm_go3` waits until 2 minutes since the last page and throws if more than 40 s
  are left). Batch checked with SHA-256 (16,481 bytes), saved in the tab as `wfm_pages_saved_004`. Next: the
  Philosopher's Stone page (B10), more vendors (A0), Fizzlefuse again, Javnir Nashak (A7), then the pools (step 3).
- How to read (works): in the Wowhead tab, `localStorage` keys `wfm_fn` (reader: throws on a blocked or non-Forever
  page, stores the page under `wfm_pages`) and `wfm_go2` (waits until 60 s since the last page, at most 40 s);
  per page a batch of [wait 10, wait 10, run wfm_go2, navigate, run wfm_fn]; 3 pages per batch (the tool stops a call
  after about 4 minutes; 25 actions max). Every 10-15 pages read `wfm_pages` out, save it to a file and run the
  importer, then clear it. Saved copies stay in the tab as `wfm_pages_saved_00N`.

## Order to work in (decided with the user, 2026-11-14)
The user's goal: all the Forever data, the only way to accurate numbers. Reading the top of the queue covers most of
the value: the top 10 / 30 / 50 / 100 material pages cover 37% / 59% / 72% / 88% of the uncovered traded material
value (331 materials uncovered). Claude advised a slow pace (bulk reading goes against Wowhead's blocking and, as
far as known, its terms, and could block the user's own connection); the user decided (2026-11-14): **if steps 1
and 1b find no bulk source, read the top 100 at one page a minute** (step 3).
1. **Other Forever data sources first** (step 7 below): one web search for WoW: Forever loot databases, exports or
   addons with Forever loot data; ask before downloading anything. A bulk source would replace most page reading.
   1b. Draft a short email for the user to send to Wowhead asking for Forever data access (personal gold tool).
2. **Item-page data format and its use** (no Wowhead needed): a tracked `data/wowhead_forever_items.json` with each
   read page's source tabs (dropped-by, skinned-from, mined/gathered-from, fished-in, contained-in), its ids passed to
   `coverage.audit` as `pages`, and the engine using it: value per kill for mob drops, node yields replacing Classic
   ones. Test data: the 5 pages already saved in the Wowhead tab's localStorage (`wfm_pages`).
3. **Read the top 100 of the coverage queue at one page a minute** (user's decision; only if no bulk source), then
   the 7 skinning items left (step 2 below). In the built-in browser as now; stop at the first 403 or challenge page
   and never get around a block (no other browser, proxy or sign-in); keep each page in the tab's localStorage
   (`wfm_pages`), read out and save to data/ every 10 pages, and check usage every 10 pages. If it gets blocked,
   back off (30 min, 2 h, next day) and fall back to about 5 pages a session.
4. **Pools** (step 3 below): first find the Forever pool objects' Wowhead pages (e.g. from a zone's fishing tab or
   an item's "Fished in"/"Contained in" tab, which names the pool), then read them.
5. **Mob farming** (to-do item 4), then the rest of the to-do list.

## Steps (reference)
1. **Done 2026-11-14: coverage audit** (`wfm/coverage.py`, Data health "Forever source data for every material",
   tests/test_coverage.py). First result: 17 of 351 traded materials and 20 of 2,437 traded looted items fully
   covered; dropped by mobs 0 of 1,333, objects 0 of 1,536, herbs 0 of 39, veins 0 of 23, skinned 5 of 48, fished
   37 of 65. Queue top: Dark Rune, Runecloth, Arcane Crystal, Righteous Orb, Mageweave, Silk. To make a read count,
   save full item pages to a tracked `data/wowhead_forever_items.json` and pass their ids as `pages`. Original
   brief: **Coverage audit (code, no Wowhead).** New `wfm/coverage.py` + a Data health check "Forever source coverage":
   every material (trade goods: cloth, leather, hides, scales, herbs, ore, bars, stone, gems, elemental, meat,
   fish; raw fish/meat of class 0/5 that recipes use; openable containers) with a TSM price, and for each which
   Forever source data we have: skinned from (`data/wowhead_forever_skinning.json`), dropped by (none yet),
   gathered from nodes (none: Classic yields), fishing (zone counts), container contents, pool contents. Output a
   ranked reading queue (AH value x region sold/day) of Wowhead Forever pages, each with what it fixes.
   Tests: a fake item set -> the right gaps and order.
2. **Skinning (fixes "some skins not counted").** Progress 2026-11-14: 5 more read 40 s apart with no block
   (4235 Heavy Hide, 8169 Thick Hide, 8171 Rugged Hide, 15417 Devilsaur Leather, 8368 Thick Wolfhide): 12 of 19.
   Their other tabs (dropped-by, contained-in) are kept in the Wowhead tab's localStorage key `wfm_pages`
   (built-in browser profile) for step 4: read them out from there instead of reloading the pages. Left: 8167,
   8154, 7286, 8165, 15412, 15419, 15423. Original brief: Read each item's full page (every source tab, not only Skinned
   from) for the 12 items left: 4235 Heavy Hide, 8169 Thick Hide,
   8171 Rugged Hide, 15417 Devilsaur Leather, 8368 Thick Wolfhide, 8167 Turtle Scale, 8154 Scorpid Scale,
   7286 Black Whelp Scale, 8165 Worn Dragonscale, 15412 Green Dragonscale, 15419 Warbear Leather,
   15423 Chimera Leather, plus any skinnable material the audit lists. Then set `skins_partial` per spot only when
   an unread skinnable item could come from its mobs (so it disappears once all are read).
3. **Pools.** Reading list ready 2026-11-14 (QuestieDB Forever objects checked against the Classic fishing holes; pool
   variants of one name have different loot tables per tier, so every id gets its own page,
   `https://www.wowhead.com/forever/object=<id>`), in this order: Floating Debris 180655; Floating Wreckage 180662,
   180685, 180751, 180901; possibly Forever-only: Strange Debris 693670 (Durotar), Shipwreck Debris 186283 (Dustwallow
   Marsh), School of Fish 180184 (Elwynn); Oily Blackmouth School 180582, 180664, 180682, 180750, 180900; Firefin
   Snapper School 180657, 180683, 180752, 180902; Stonescale Eel Swarm 180712; Greater Sagefish School 180684; Sagefish
   School 180656, 180663; Oil Spill 180661; Patch of Elemental Water 180753; School of Deviate Fish 180658; School of
   Tastyfish 180248; Muddy Churning Waters 180369 (Zul'Gurub). 26 pages. QuestieDB has spawn points for only 9 of
   them (pools move), so zones come from the pages. The reader stores object pages as `object=<id>`; their "Contains"
   tab feeds `wowhead_items.object_yields` (complete). Original brief: Find the Forever pool objects (Floating Debris, Floating Wreckage, Oily Blackmouth School, Firefin
   Snapper School, Stonescale Eel Swarm, Greater Sagefish School, Oil Spill, any Forever-only pool) and read each
   object page's "Contains" tab (opened N times, rows with count and stack). Save as
   `data/wowhead_forever_pools.json` (tracked). Model: gold/hour with pools = open water + pools fished per hour
   (new setting, explained) x catches per pool (from Wowhead's counts) x value per pool catch, with each pool's
   required skill in the got-away roll; pool loot leaves the open-water share. Recheck the user's claim with the
   numbers and tell them. Tests with hand-worked numbers.
4. **Mob drops ("Dropped by").** Cloth 2589, 2592, 4306, 4338, 14047, 14256; elementals 7067-7070, 7075, 7077,
   7079, 7081, 12803, 12808, 7972, 12811; then the audit's next most valuable drops. Feeds mob farming (to-do item 4):
   value per kill from drop rates x the kills-per-hour setting (never your own logged time).
5. **Herb and ore nodes, fishing zones, containers.** Node object pages ("Contains") replace Classic yields (drop
   `classic_yields` where read); fishing zones not read yet (Arathi 45, Hinterlands 47, Western Plaguelands 28,
   Felwood 361, Un'Goro 490, Swamp of Sorrows 8, Desolace 405, Thousand Needles 400, Alterac 36, Hillsbrad 267,
   Wetlands 11, Moonglade 493, Winterspring 618, Eastern Plaguelands 139, Burning Steppes 46, Silithus 1377,
   Forever-only zones); containers Data health lists as "contents unknown" (13881, 21243, 8366, 13874, 13875, 6355,
   6357).
6. **Got-away follow-ups.** Gear checked 2026-11-14 from Forever tooltips (Wowhead's tooltip service): 14 of 15
   bonuses match (all lures, poles, hat, boots); Darkwood Fishing Pole has no Forever tooltip (Classic +15, labelled);
   Aquadynamic Fish Attractor lasts 5 min, the other lures 10 (`fishing.LURE_MINUTES`). Lure cost per hour done
   2026-11-14 (`Engine.fishing_lure`, `fishing.lure_pays`): a spot uses your best lure only where it pays.
   Earlier: partly done 2026-11-14: `Engine.fishing_bonus` = best pole + best lure + fishing hat and
   boots found in bags, bank and equipped (`fishing.FISHING_GEAR`, Classic values, an id counts only if Forever's
   name matches); a number in Settings overrides. Left: confirm each value from its Forever tooltip (the tooltip
   API, `wfm/tooltips.py`), lure cost per hour, more gear. Original brief: Fill `fishing_skill_bonus` automatically: the equipped pole and fishing gear
   (Syndicator's equipped items) and the best lure in your bags, with bonus values from Forever's game data
   (SpellEffect on wago.tools: ask before downloading) or labelled Classic values; subtract the lure's cost per hour
   (one lure per 10 minutes). Check whether Wowhead Forever zone pages state a fishing skill (Forever zone skills
   instead of Classic ones).
7. **Other online sources.** One web search for other WoW: Forever loot databases or exports; ask before
   downloading anything.

## Wowhead pace (unchanged rules)
About 5 pages per session, 30-60 s apart; spread the list over days; only re-read pages whose data is getting old.
On a 403 stop at once and back off one single page per check: 30 minutes, then 2 hours, then the next day. Never
get around the blocking. Compact extract: top 40 rows, outof >= 50, skip rows with `classicEra`; collect in the tab's
localStorage and read it out once; the stop check THROWS on a non-Forever or blocked page so a batch halts.
Save to the tracked `data/wowhead_forever_*.json` files in the same formats as now.
