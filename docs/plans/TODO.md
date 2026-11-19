# To-do list (in order)

**The user's checklist of all open work and decisions: `docs/plans/open-items-and-decisions.md`.** When the user
asks what's left or about the decisions, go through every item there.

When the user says "start doing the things on the todo list" (or similar), work through this list top to bottom.
Each item points to a plan file with the full brief. Follow CLAUDE.md's standing rules, check usage before each
step, commit and push each finished piece, tick it off here and note it in docs/PROJECT_LOG.md. If usage gets
tight: finish the current piece, commit, update this list, and set a reminder that runs nothing.

**Where it stands (2026-11-19, end of a long day session; 5-hour window at about 85%, weekly 20%):** done that day,
all pushed (details: PROJECT_LOG decisions and change log of 2026-11-19): Salt Shaker and every item interaction
(item uses, essences, Darkmoon cards, recipe tools, Poisons, Data health "Item interactions"), ForeverRecipes as a
second recipe source, disenchanting from a labelled Classic table, Biggest markets (complete, ranked, glowing border),
levelling planner overhaul (whole-path optimisation, every way back, shopping list), farm meter 1.6.x (XP; the app's
prices while fresh, else TSM in game), vendor prices from TSM first (addon 1.6.2). The comprehensive review (1a) was
NOT started: the user asked for these instead. Next, in order:

0b. [ ] **The user, in game (no Claude needed, 2 minutes):** log in, wait a minute, /reload. That saves TSM's vendor
       prices (addon 1.6.2; Data health "Vendor prices from TSM" then fills in) and lets Claude check the farm meter
       (checklist B8: start /gea start, kill a few mobs, a screenshot with the XP line).
1a. [ ] **Comprehensive review** (UI, UX, logic, accuracy, how all systems work together; the user's request,
       2026-11-15): `docs/plans/comprehensive-review.md`. Include what 2026-11-19 added: the levelling planner's
       new algorithm on every profession, item-use crafts, Biggest markets, disenchant labels.
1d. [ ] **Levelling paths stop where patterns only drop** (2026-11-19: Leatherworking stops at 270). ForeverRecipes'
       Sources.lua has who sells each pattern (`Sellers`, `RecipeVendorCosts`, limited stock in `SourceMeta`) and the
       top drop chances (`Drops`): use its vendor-sold patterns as learnable (with their price and limited stock), show
       drop-only ones as "you'd have to find this", so a path can reach 300. Also count rank training (Journeyman,
       Expert, Artisan) fees and levels.
1e. [ ] **Wowhead reading session** (pace in CLAUDE.md, at most 20 pages): checklist A0 (vendor stock for flips),
       B10 (one Power Crystal transmutation spell page: who casts them?), B9 (Mote of Unstable Magic, Shellfish,
       Pristine Black Diamond, Vulture Gizzard: the biggest markets the app has no way into), then A1, A2.
1f. [ ] **In-game checks for every priced item** (2026-11-19 idea, "TSM is the king"): the addon checks up to 800
       items a login; after TSM's vendor prices arrive, compare them with the game files on Data health and decide
       whether the game files are still needed for vendor sell prices at all.
1c. [x] (built 2026-11-15, addon 1.5.0; untested in game until the user tries it) **Farm meter in ForeverMoneyBridge** (the user, 2026-11-15; prices must match the app's):
       `docs/plans/farm-meter.md`. After the comprehensive review, or alongside it.
1b. [x] (done 2026-11-15, the user said "do it now") **Realm prices, own materials, three profit views** (the user's decisions, 2026-11-15):
       `docs/plans/realm-prices-and-profit-views.md`. Then continue with (a)-(d) above.

0. [x] **Quick check, needs the user in game** (done 2026-11-14: 1.4.1's gold = Syndicator's on both characters) (/reload once): addon 1.4.1 saves gold (compare with Syndicator in
       the app's purse), and see the project log's open items for the other in-game checks. Checked 2026-11-14:
       not yet possible, the saved file is older than the 1.4.1 install.
1. [x] **Plan for today** on the main page (the user's priority): `docs/plans/todays-plan.md` (done 2026-11-14)
2. [ ] (in progress: 102 item pages read by 2026-11-15; 2 minutes apart, at most 20 a session: 3356 and 5500 left
       of the top 100, then the 4 skinning items, pools, Javnir Nashak; see the plan's Progress section)
       **TOP PRIORITY: Forever source data for every material** (fixes "some skins not counted", pool loot,
       mob drops, node yields; the user's top priority for data accuracy, 2026-11-14): `docs/plans/material-coverage.md`.
       It replaces the old Wowhead-reads item (same slow pace). Work in the order at the top of that file: other
       Forever data sources, the item-page data format, 5 top pages a session (target: top 50), pools, mob farming.
2a. [x] (done 2026-11-15: Claude ran data/rewrite_history.sh at the user's word; force-pushed)
       **Remove the user's character names from GitHub's history** (user's yes, 2026-11-15; force push approved):
       `docs/plans/decided-2026-11-15.md`, section 2a
2b. [x] (done 2026-11-15: valuation.capped_total, every quantity and hourly row; see the project log)
       **"Worth if crafted" only for what can be made and sold a day** (user's yes, 2026-11-15):
       `docs/plans/decided-2026-11-15.md`, section 2b
2c. [x] (done 2026-11-15: Data health "Drop rates: Wowhead Forever vs Everloot"; 10 of 10 comparable pairs agree;
       the open question for the user, fill gaps from Everloot?, is in the checklist, C8)
       **Everloot cross-check of drop rates** (user's yes, 2026-11-15; download approved: 4 requests, about 200 KB):
       `docs/plans/decided-2026-11-15.md`, section 2c
3. [-] ~~Own Forever loot tables from the addon~~: cancelled by the user (2026-11-14): loot tables come from online
       sources only, never our own logs. ForeverMoneyBridge stays at 1.4.1.
4. [ ] (first version done 2026-11-14: Gathering -> Mob farming, one row per mob, drops read so far = a floor; left:
       mobs' own pages for complete loot, coins) **Mob farming**: `docs/plans/forever-data-next.md`, section 3, with drop rates from Wowhead Forever
       ("Dropped by", material-coverage step 4) and the kills-per-hour setting, never your own logged time
4b. Moved to item 8 (the user, 2026-11-15: build it, at a lower priority).
5. [x] (done 2026-11-15: wfm/gatherlite.py, Data health entry; map tables downloaded after the user's yes. Left as
       follow-ups: node spots could count the larger of QuestieDB and GatherLite per zone; pool zones for the pool model)
       **GatherLite node locations** (installed; the user, 2026-11-15: "could be useful"; ask before downloading
       the UiMap tables, with file name and size): `docs/plans/forever-data-next.md`, section 5. And keep an open
       mind to new addons: recommend any good Forever addon found (loot addons: section 4); the user installs them
       through CurseForge.
6. [x] (done 2026-11-15: recomputation and invariants pass, one coverage bug fixed; project log)
       **Review** of the 2026-11-13/14 work: `docs/plans/forever-data-next.md`, section 6
7. [ ] (2026-11-15: items 2 (levelling planner), 1 (profession advisor, Professions tab) and 10 (Niches tab)
       done; next 3 (vertical integration), then 4-9)
       **Strategy features**, items 1-10 (profession advisor, levelling planner and niches first):
       `docs/plans/strategy-features.md`
8. [ ] **Dungeons view** (the user's idea; 2026-11-15: build it, at a lower priority): a "run <dungeon>" row = trash +
       bosses from their own Wowhead Forever pages, your share of a group's loot, runs per hour from Settings, the
       instance limit; dungeon mob rows already exist (flag `dungeon`). Raids later, if at all (shared raid loot).
       Dark Rune and Righteous Orb (#1 and #4 of the missing materials by traded value) drop only in Scholomance and
       Stratholme.

Done earlier: investments tab, skinning spots (7 of 19 items read), cooldowns, ranking, effort, Market tab, and
the rest in the project log's change log.
