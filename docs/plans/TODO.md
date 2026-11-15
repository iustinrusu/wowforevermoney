# To-do list (in order)

**The user's checklist of all open work and decisions: `docs/plans/open-items-and-decisions.md`.** When the user
asks what's left or about the decisions, go through every item there.

When the user says "start doing the things on the todo list" (or similar), work through this list top to bottom.
Each item points to a plan file with the full brief. Follow CLAUDE.md's standing rules, check usage before each
step, commit and push each finished piece, tick it off here and note it in docs/PROJECT_LOG.md. If usage gets
tight: finish the current piece, commit, update this list, and set a reminder that runs nothing.

0. [x] **Quick check, needs the user in game** (done 2026-11-14: 1.4.1's gold = Syndicator's on both characters) (/reload once): addon 1.4.1 saves gold (compare with Syndicator in
       the app's purse), and see the project log's open items for the other in-game checks. Checked 2026-11-14:
       not yet possible, the saved file is older than the 1.4.1 install.
1. [x] **Plan for today** on the main page (the user's priority): `docs/plans/todays-plan.md` (done 2026-11-14)
2. [ ] (in progress: 2026-11-14 the data format, coverage, node yields, mob rows and 82 item pages are done;
       about 5 pages a session: the 22 left of the top 100, the 4 skinning items, pools; see the plan's Progress section)
       **TOP PRIORITY: Forever source data for every material** (fixes "some skins not counted", pool loot,
       mob drops, node yields; the user's top priority for data accuracy, 2026-11-14): `docs/plans/material-coverage.md`.
       It replaces the old Wowhead-reads item (same slow pace). Work in the order at the top of that file: other
       Forever data sources, the item-page data format, 5 top pages a session (target: top 50), pools, mob farming.
2a. [ ] **Remove the user's character names from GitHub's history** (user's yes, 2026-11-15; force push approved):
       `docs/plans/decided-2026-11-15.md`, section 2a
2b. [ ] **"Worth if crafted" only for what can be made and sold a day** (user's yes, 2026-11-15):
       `docs/plans/decided-2026-11-15.md`, section 2b
2c. [ ] **Everloot cross-check of drop rates** (user's yes, 2026-11-15; download approved: 4 requests, about 200 KB):
       `docs/plans/decided-2026-11-15.md`, section 2c
3. [-] ~~Own Forever loot tables from the addon~~: cancelled by the user (2026-11-14): loot tables come from online
       sources only, never our own logs. ForeverMoneyBridge stays at 1.4.1.
4. [ ] (first version done 2026-11-14: Gathering -> Mob farming, one row per mob, drops read so far = a floor; left:
       mobs' own pages for complete loot, coins) **Mob farming**: `docs/plans/forever-data-next.md`, section 3, with drop rates from Wowhead Forever
       ("Dropped by", material-coverage step 4) and the kills-per-hour setting, never your own logged time
4b. Moved to item 8 (the user, 2026-11-15: build it, at a lower priority).
5. [-] ~~Forever loot addons and GatherLite node locations~~: cancelled by the user (2026-11-15): no more addons
       for now, Wowhead data is enough.
6. [ ] **Review** of the 2026-11-13/14 work: `docs/plans/forever-data-next.md`, section 6
7. [ ] **Strategy features**, items 1-10 (profession advisor, levelling planner and niches first):
       `docs/plans/strategy-features.md`
8. [ ] **Dungeons view** (the user's idea; 2026-11-15: build it, at a lower priority): a "run <dungeon>" row = trash +
       bosses from their own Wowhead Forever pages, your share of a group's loot, runs per hour from Settings, the
       instance limit; dungeon mob rows already exist (flag `dungeon`). Raids later, if at all (shared raid loot).
       Dark Rune and Righteous Orb (#1 and #4 of the missing materials by traded value) drop only in Scholomance and
       Stratholme.

Done earlier: investments tab, skinning spots (7 of 19 items read), cooldowns, ranking, effort, Market tab, and
the rest in the project log's change log.
