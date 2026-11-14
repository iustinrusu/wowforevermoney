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

## Steps (in order)
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
2. **Skinning (fixes "some skins not counted").** Read each item's full page (every source tab, not only Skinned
   from) for the 12 items left: 4235 Heavy Hide, 8169 Thick Hide,
   8171 Rugged Hide, 15417 Devilsaur Leather, 8368 Thick Wolfhide, 8167 Turtle Scale, 8154 Scorpid Scale,
   7286 Black Whelp Scale, 8165 Worn Dragonscale, 15412 Green Dragonscale, 15419 Warbear Leather,
   15423 Chimera Leather, plus any skinnable material the audit lists. Then set `skins_partial` per spot only when
   an unread skinnable item could come from its mobs (so it disappears once all are read).
3. **Pools.** Find the Forever pool objects (Floating Debris, Floating Wreckage, Oily Blackmouth School, Firefin
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
6. **Got-away follow-ups.** Fill `fishing_skill_bonus` automatically: the equipped pole and fishing gear
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
