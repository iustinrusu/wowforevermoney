# To-do list (in order)

**The user's checklist of all open work and decisions: `docs/plans/open-items-and-decisions.md`.** When the user
asks what's left or about the decisions, go through every item there.

When the user says "start doing the things on the todo list" (or similar), work through this list top to bottom.
Each item points to a plan file with the full brief. Follow CLAUDE.md's standing rules, check usage before each
step, commit and push each finished piece, tick it off here and note it in docs/PROJECT_LOG.md. If usage gets
tight: finish the current piece, commit, update this list, and set a reminder that runs nothing.

**Where it stands (2026-11-15, end of a night session; stopped at 80% of the weekly usage with 4 days left):**
done that night: 2b, 2c, 6, 7 items 1, 2 and 10, and 20 Wowhead pages (the session's limit). Next, in order:
(a) item 2: 20 more Wowhead pages (Kingsblood 3356, Iridescent Pearl 5500, the 4 skinning items, then the pools
list), pace as in CLAUDE.md; (b) item 7: strategy item 3 (vertical integration), then 4-9; (c) item 8, Dungeons;
(d) item 4: mobs' own pages (part of the Wowhead budget). 2a, C8 (Everloot fills mob-drop gaps), C9 and item 5 were done the
same night; nothing waits on the user.

1a. [ ] **FIRST, IN A NEW CHAT AFTER THE USAGE RESET (19 Nov): comprehensive review** (UI, UX, logic, accuracy,
       how all systems work together; the user's request, 2026-11-15): `docs/plans/comprehensive-review.md`.
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
