# To-do list (in order)

**The user's checklist of all open work and decisions: `docs/plans/open-items-and-decisions.md`.** When the user
asks what's left or about the decisions, go through every item there.

When the user says "start doing the things on the todo list" (or similar), work through this list top to bottom.
Each item points to a plan file or carries the full brief. Follow CLAUDE.md's standing rules, check usage before each
step, commit and push each finished piece, tick it off here and note it in docs/PROJECT_LOG.md. If usage gets
tight: finish the current piece, commit, update this list, and set a reminder that runs nothing.

**Order (the user, 2026-11-19, end of day): first the topics of the 2026-11-19 session (part A), then the
comprehensive app review (part B), then the rest (part C).** What that session did, all pushed: Salt Shaker and
every item interaction, ForeverRecipes as a second recipe source, disenchanting from a labelled Classic table, Biggest
markets (complete, ranked, glowing border), the levelling planner overhaul and then every recipe in the game with
where to learn it, farm meter 1.6.x (XP; the app's prices while fresh, else TSM in game), vendor prices from TSM first
(addon 1.6.2). Details: PROJECT_LOG decisions and change log of 2026-11-19.

## A. The 2026-11-19 session's topics (highest priority)

A0. [ ] **The user, in game (no Claude needed, 2 minutes, any time):** log in, wait a minute, /reload. That saves
       TSM's vendor prices (addon 1.6.2; Data health "Vendor prices from TSM" then fills in) and lets Claude check the
       farm meter (checklist B8: /gea start, kill a few mobs, a screenshot with the XP line).
A1. [ ] **Slow sellers must not drive the levelling route** (the user: "slow sells should not rank that high in the
       algorithm deciding best route"; agreed 2026-11-19, to be built after the usage reset). Today `levelling.WEEK`
       lets the AH take a week of your share of a product's sales, at the lowest listing (`ah_sell` in
       `Engine.levelling`). Living Shoulders 255-257 earns 61g only from 2 slow sales at 37g (one every 3-4 days at a
       20% share; at the vendor price those 2 points cost about 7g); Devilsaur Leggings -113g the same. Change:
       (1) the AH takes only about 2 days of your share (a constant, or a setting "count AH sales within N days",
       default 2); (2) price each sale at the lower of the lowest listing and the region's actual sale average
       (`pricing.usual_sale`, as Big flips do); (3) the Back column says when a sale is slow ("about 1 sale every 4
       days"). Update tests (`test_the_ah_takes_only_so_many_then_the_vendor_price`), re-run every profession 1->300 on
       real data and compare totals before and after; update the "How this is worked out" text.
A2. [ ] **The rest of the levelling work** (every recipe in the game and where to learn it: done 2026-11-19):
       - rank training (Journeyman, Expert, Artisan): fee, the skill and character level each needs, at 75/150/225 the
         path must stop for it (ForeverRecipes `Trainers` may hold the rank spells; check, never assume Classic fees);
       - a recipe whose pattern is only on the AH at "market value (none listed now)" or "region market value": say
         you may have to wait for one (the price is shown; nothing flags it yet);
       - materials marked "yours" that aren't gathered (Ironfeather, Cured Rugged Hide showed "yours" on the
         Leatherworking path: GATHER_PROFESSION by trade-goods subclass is too wide; check it);
       - check a "find it" row in the browser: none came up on real data (every path uses buyable recipes).
A3. [ ] **Compare TSM's vendor prices with the game files** (after A0; "TSM is the king"): the addon checks up to 800
       items a login; once TSM's vendor prices arrive, compare them on Data health and decide whether the game files
       are still needed for vendor sell prices at all.
A4. [ ] **Wowhead reading session** (pace in CLAUDE.md, at most 20 pages): checklist B10 (one Power Crystal
       transmutation spell page: who casts them?), B9 (Mote of Unstable Magic, Shellfish, Pristine Black Diamond,
       Vulture Gizzard: the biggest markets the app has no way into), A0 (vendor stock for flips), then A1, A2.

## B. Then: the comprehensive app review

B1. [ ] **Comprehensive review** (UI, UX, logic, accuracy, how all systems work together; the user's request,
       2026-11-15): `docs/plans/comprehensive-review.md`. Include what 2026-11-19 added: the levelling planner (new
       algorithm, every recipe, where to learn, slow sellers) on every profession, item-use crafts, Biggest markets,
       disenchant labels, TSM vendor prices.

## C. Then the rest

C1. [ ] (in progress: 102 item pages read by 2026-11-15; 2 minutes apart, at most 20 a session: 3356 and 5500 left
       of the top 100, then the 4 skinning items, pools, Javnir Nashak; see the plan's Progress section)
       **Forever source data for every material** (fixes "some skins not counted", pool loot, mob drops, node
       yields; the user's top priority for data accuracy, 2026-11-14): `docs/plans/material-coverage.md`. Work in the
       order at the top of that file: other Forever data sources, the item-page data format, 5 top pages a session
       (target: top 50), pools, mob farming.
C2. [ ] (first version done 2026-11-14: Gathering -> Mob farming, one row per mob, drops read so far = a floor; left:
       mobs' own pages for complete loot, coins) **Mob farming**: `docs/plans/forever-data-next.md`, section 3, with
       drop rates from Wowhead Forever ("Dropped by", material-coverage step 4) and the kills-per-hour setting, never
       your own logged time.
C3. [ ] (2026-11-15: items 2 (levelling planner), 1 (profession advisor, Professions tab) and 10 (Niches tab) done;
       next 3 (vertical integration), then 4-9) **Strategy features**, items 1-10: `docs/plans/strategy-features.md`
C4. [ ] **Dungeons view** (the user's idea; 2026-11-15: build it, at a lower priority): a "run <dungeon>" row = trash +
       bosses from their own Wowhead Forever pages, your share of a group's loot, runs per hour from Settings, the
       instance limit; dungeon mob rows already exist (flag `dungeon`). Raids later, if at all (shared raid loot).
       Dark Rune and Righteous Orb (#1 and #4 of the missing materials by traded value) drop only in Scholomance and
       Stratholme. Dungeon gear also tops Biggest markets.

## Done (details in the project log's change log)

- 2026-11-19: every recipe in the game in the levelling path with where to learn it; levelling overhaul; Biggest
  markets; vendor prices from TSM (addon 1.6.2); farm meter XP and TSM prices (1.6.x); disenchanting (Classic table,
  labelled); ForeverRecipes; every item interaction (Salt Shaker, poisons, essences, decks, tools).
- 2026-11-15: farm meter in ForeverMoneyBridge (addon 1.5.0); realm prices, own materials, three profit views;
  character names removed from GitHub's history; "worth if crafted" capped at what sells; Everloot cross-check;
  GatherLite node locations; review of the 2026-11-13/14 work.
- 2026-11-14: plan for today on the main page; addon 1.4.1 gold check. Cancelled: own loot tables from the addon
  (loot tables come from online sources only, never our own logs).
- Earlier: investments tab, skinning spots, cooldowns, ranking, effort, Market tab, and the rest in the change log.
