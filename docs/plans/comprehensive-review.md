# Plan: comprehensive review (the user's request, 2026-11-15)

Do this first in a new chat after the weekly usage limit resets (19 Nov). To start: open Claude Code in this folder
and say "Do the plan in docs/plans/comprehensive-review.md". Read CLAUDE.md and docs/PROJECT_LOG.md first. Standing
rules apply: accuracy first, every fix gets a test, plain-language explanations, commit and push each finished piece,
note findings and fixes in the project log. Check usage before each part; if it gets tight, finish the part, commit,
write what's left here and set a reminder that runs nothing.

## What the user asked
"A comprehensive review: UI, UX, logic, accuracy, etc, and how all systems work together with no discrepancies."
Prompted by real finds on 2026-11-15: the plan showed Barbaric Bracers at 23g an hour while Crafting showed 99s a
day (two definitions of "per hour", both misleading for something the market takes once a day); Niches showed a
different profit a day than Crafting; a stray apostrophe blanked the whole page; Mooncloth and Devilsaur Leggings
looked low until realm prices and the good-day view were added.

## How to work
Second-guess every number. For each part: read the code, run it on the user's real data, compare with an independent
recomputation or a second source, and look at the page in the browser (wide and at 375 px). List findings first,
fix the clear bugs, ask the user only about real decisions. Never skip a check on an assumption.

## Parts, in order
1. **Every number has one meaning.** Run `python tools/consistency_check.py` (0 problems on 2026-11-15) and extend
   it to every pair of places that show the same figure: Top picks vs tabs, plan steps vs rows, Professions vs
   Crafting/Gathering, Niches vs rows, Sniper vs Market, purse vs My bags vs plan cash-in, item drawer vs tables,
   Market tab vs TSM fields, Investments vs pricing, levelling planner vs Crafting, Data health counts vs tabs.
   Also: units and labels (per unit / per day / per hour / per sale, "you" vs "region"), rounding, the AH cut
   applied exactly once, the same sale basis (realm) everywhere.
2. **Pricing and profit logic.** Realm basis end to end (pricing.ah_sell, add_upside "at usual", walls, freak
   sales, odd listings, nothing listed); crafted-worth cap; good day; own materials; effort and time value;
   ranking/score; confidence factors; liquidity flags; Top picks exclusions; plan selection and caps. Independent
   recomputation of the top rows of every kind (crafts, flips, farming spots, mob rows, fishing, nodes) from raw
   TSM rows and source files.
3. **Data sources and freshness.** Every source in World: what happens when it's missing, stale or updated while the
   app runs (addons update almost daily); Forever-vs-Classic labelling on every row; Everloot gap-filling; GatherLite;
   the encrypted Wowhead pack (unlock with key, wrong key, new data after an update); starter price history.
4. **UI and UX.** Every tab, wide and narrow: readability, plain-language hover help on every column and number,
   empty states, loading, errors, the character dropdown, Refresh now, Settings (every option explained and saved),
   drawers, tables-as-cards on phones, links and icons. Load every view in the browser and check the console after
   any web/app.js edit (no Node on this PC). Look for cryptic labels, duplicated or contradicting explanations.
5. **How the systems work together.** One end-to-end pass as a new user would (fresh clone with a friend's
   settings: no Syndicator, no data key, ZIP install) and as the user (all addons): start.bat, update.bat, first
   start, Data health, every tab. Then one as the user switching characters.
6. **Tests and code health.** Gaps in tests for calculations, dead code (e.g. the snipe rows' methods), duplicated
   logic that could drift apart (one function per rule), slow spots.
7. **Report.** A short summary for the user: what was found, what was fixed, what needs their decision.

## Progress (started 2026-11-20, to-do B1)
- Part 1 done 2026-11-20: `tools/consistency_check.py` now builds the app as it runs (nothing written to AddOns) and
  compares what each tab's own function returns, 16 pairs, each with how many were compared: plan vs rows, Top picks
  vs tabs, Niches, Professions vs Crafting, Professions vs Gathering and the levelling panel, item drawer vs tables,
  the AH cut taken once, profit a day = profit each x a day, Market tab vs TSM and drawer, Investments vs TSM and
  drawer, Biggest markets vs TSM and rows, Sniper vs TSM, levelling vs Crafting, purse vs My bags, plan cash-in vs My
  bags, Data health counts vs tabs. 0 problems on real data. Found: the plan cash-in check had compared nothing since
  it was written (it looked for a field `each`; the item lines say `unit`). Units and labels: in part 4 (UI).
- Part 2 done 2026-11-20: rebuilt from raw TSM rows and source files (scratch script, not the engine's pricing code):
  top 60 crafts and top 60 vendor flips match to the copper; top 30 skinning, herb and ore spots (value x pace),
  top 30 fishing spots (value x casts x share kept - lures where they pay) and top 40 mob rows (rounding only) match.
  Invariants: no Classic data in Top picks or the plan (only the skinning spots' `skill_classic_rule`, which changes
  nothing at Skinning 300), no negative gold an hour, every pick in the right section, cooldown caps hold (the Salt
  Shaker's 0.34 is 0.338 rounded). Fixed: 27 "Farm" rows for things only a recipe makes (Farm Arcanite Bar 341g a day
  as Mining, Arcanite Rod 84g, Mooncloth 53g, oils counted as fish); node spots now use GatherLite's node counts where
  higher and are not "doable now" in a zone whose mobs are mostly 4+ levels above you (`Engine.zone_level`, flag
  `zone_above_you`). Both known items done. Crafted-worth cap, good day, own materials, effort, ranking: unchanged
  since the 2026-11-15 review, which checked them.
- Part 3 done 2026-11-20: the data layer started with each source missing (TSM, QuestieDB, SkillUpForever,
  ForeverRecipes, both, no SavedVariables at all, a friend without the data key, GatherLite and Everloot): it loads,
  runs and says what's missing every time. Addon folders are watched file by file (`_mtime` reads the newest .lua), so
  updates reload. Fixed notes: TSM missing now says there are no prices and how to get them; QuestieDB missing says
  what is lost and how to install it; the Wowhead pages' status said "No zones read yet" whenever no fishing zone was
  read, and for a friend without the data key it now says the pages are locked and the key unlocks them. The pack:
  key, wrong key and newer local pages are tested (`tests/test_datapack.py`). Classic labels: every row kind that uses
  Classic data carries its flag (fishing tables, node yields, gathers per node, disenchanting, Everloot, skill rule).
- Part 4 done 2026-11-20 (in the browser pane, every tab, full width and a 375 px phone; console clean): every column
  header now has hover help (30 had none: Cost each, Gold / hour, Sells (region), Cooldown, all of Investments, My
  bags, Niches, the levelling tables, Settings' characters, Biggest markets). Phone fixes: the Professions comparison
  table now scrolls inside its box; card cells wrap (rows of warning labels made Top picks, Crafting, Flips and
  Gathering 360-690 px too wide); Settings fits (it was 507 px); long "How this is worked out" summaries wrap; the
  header scrolls away and the tabs are one swipeable row (they covered half the screen). Tables turn into cards when a
  view renders, not only on the next paint. Not changed: wording of the notes (read through, no contradictions found
  in the tabs checked); the Settings save and the item drawer were exercised by earlier sessions' browser checks.

## Known items to look at (from 2026-11-15)
- Levelling planner values products with no recorded sales at vendor price where Crafting shows the listing
  ("no sales data"): deliberate; check it's explained in both places.
- Engine.realm_dips / ah_to_vendor are no longer used in runs: remove or keep for the Sniper list.
- Node spots don't check the player's level (Winterspring mining shows 37g an hour for a level 42).
- Herb/ore spots could use the larger of QuestieDB and GatherLite node counts per zone.
- Sniper list: only ~32 snapshots so far; recheck once a week of history exists.
- Niches' sold-out signal needs a week of snapshots (84+).
