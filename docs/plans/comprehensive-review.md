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

## Known items to look at (from 2026-11-15)
- Levelling planner values products with no recorded sales at vendor price where Crafting shows the listing
  ("no sales data"): deliberate; check it's explained in both places.
- Engine.realm_dips / ah_to_vendor are no longer used in runs: remove or keep for the Sniper list.
- Node spots don't check the player's level (Winterspring mining shows 37g an hour for a level 42).
- Herb/ore spots could use the larger of QuestieDB and GatherLite node counts per zone.
- Sniper list: only ~32 snapshots so far; recheck once a week of history exists.
- Niches' sold-out signal needs a week of snapshots (84+).
