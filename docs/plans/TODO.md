# To-do list (in order)

When the user says "start doing the things on the todo list" (or similar), work through this list top to bottom.
Each item points to a plan file with the full brief. Follow CLAUDE.md's standing rules, check usage before each
step, commit and push each finished piece, tick it off here and note it in docs/PROJECT_LOG.md. If usage gets
tight: finish the current piece, commit, update this list, and set a reminder that runs nothing.

0. [x] **Quick check, needs the user in game** (done 2026-11-14: 1.4.1's gold = Syndicator's on both characters) (/reload once): addon 1.4.1 saves gold (compare with Syndicator in
       the app's purse), and see the project log's open items for the other in-game checks. Checked 2026-11-14:
       not yet possible, the saved file is older than the 1.4.1 install.
1. [x] **Plan for today** on the main page (the user's priority): `docs/plans/todays-plan.md` (done 2026-11-14)
2. [ ] (in progress: 2026-11-14 the data format, coverage, node yields, mob rows and 76 of the top 100 pages are done;
       Wowhead blocked on page 77: back off, then the 28 + 4 left, pools; see the plan's Progress section)
       **TOP PRIORITY: Forever source data for every material** (fixes "some skins not counted", pool loot,
       mob drops, node yields; the user's top priority for data accuracy, 2026-11-14): `docs/plans/material-coverage.md`.
       It replaces the old Wowhead-reads item (same slow pace). Work in the order at the top of that file: other
       Forever data sources, the item-page data format, 5 top pages a session (target: top 50), pools, mob farming.
3. [-] ~~Own Forever loot tables from the addon~~: cancelled by the user (2026-11-14): loot tables come from online
       sources only, never our own logs. ForeverMoneyBridge stays at 1.4.1.
4. [ ] (first version done 2026-11-14: Gathering -> Mob farming, one row per mob, drops read so far = a floor; left:
       mobs' own pages for complete loot, coins) **Mob farming**: `docs/plans/forever-data-next.md`, section 3, with drop rates from Wowhead Forever
       ("Dropped by", material-coverage step 4) and the kills-per-hour setting, never your own logged time
4b. [ ] **Dungeons view (user's idea, 2026-11-14; decide with the user first)**: a "run <dungeon>" row = trash +
       bosses from their own Wowhead Forever pages, your share of a group's loot, runs per hour from Settings, the
       instance limit; dungeon mob rows already exist (flag `dungeon`). Raids later, if at all (shared raid loot).
5. [ ] **Forever loot addons** (only if the user installed one through CurseForge) and **GatherLite node
       locations** (ask before downloading the UiMap tables): `docs/plans/forever-data-next.md`, sections 4-5
6. [ ] **Review** of the 2026-11-13/14 work: `docs/plans/forever-data-next.md`, section 6
7. [ ] **Strategy features**, items 1-10 (profession advisor, levelling planner and niches first):
       `docs/plans/strategy-features.md`

Done earlier: investments tab, skinning spots (7 of 19 items read), cooldowns, ranking, effort, Market tab, and
the rest in the project log's change log.
