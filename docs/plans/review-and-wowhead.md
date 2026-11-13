# Plan: review, tests, Wowhead Forever data

**Superseded by docs/plans/forever-data-next.md (2026-11-14).**

Postponed on 2026-11-13. Nothing runs by itself: a reminder points here. To start, open a Claude Code session
in this folder and say "Do the plan in docs/plans/review-and-wowhead.md".

You are continuing work on the WoW Forever Money app in the WoWForeverMoney project folder (a git repo; remote https://github.com/iustinrusu/wowforevermoney.git, branch main).

Start by reading CLAUDE.md and docs/PROJECT_LOG.md in that folder, especially "Standing rules", "Verified facts" and "Next session plan". They hold every decision so far. Follow the standing rules strictly:
- All data must be WoW: Forever. This is imperative. Other versions (Classic, cMaNGOS) are labelled fallback only and never reach Top picks.
- Accuracy first: second-guess every decision, double-check numbers against a second source, and look for better alternatives.
- Think broad: every way to make gold, not only the user's examples.
- Wowhead: no bulk scraping and no getting around their blocking. Read pages slowly in the built-in browser pane only.
- Ask before downloading files.
- Never send the user's personal details to outside services.
- Usage rule from the user: check usage with mcp__ccd_session_mgmt__get_usage before each step. If the 5-hour limit gets tight, finish the current piece, commit it, write the remaining steps into a plan file in docs/plans, and set a one-time reminder after the reset that only points to it (reminders never run anything).

The user is firm that the data must be correct and accurate. Do these steps in order. Use the task list and keep the user informed.

1. Review and test (most important). PARTLY DONE 2026-11-14: audit run (found and fixed the new-item sell price
   problem), addon containers verified, Mithril Bound Trunk recomputed. Still to do: the adversarial code review.
- Run `python -m unittest discover -s tests -t .` and `python -m wfm.audit`. Python is at %LOCALAPPDATA%\Programs\Python\Python313\python.exe.
- Do an adversarial review of the code written on 2026-11-13: wfm/classicdb.py, wfm/fishing.py, wfm/valuation.py, the fishing, valuation and undervaluation-watch code in wfm/engine.py, the loaders in wfm/world.py, item() and inventory() in wfm/app.py, the fishing UI in web/app.js, and addon/ForeverMoneyBridge/ForeverMoneyBridge.lua (now version 1.4.0).
- For the addon, check whether GetLootSourceInfo and a hooksecurefunc on C_Container.UseContainerItem work on the Forever client (interface 16001). Use the addon's own code and Forever addons in C:\Games\World of Warcraft\_forever_\Interface\AddOns as references.
- Recompute by hand 3 fishing rows and 2 container values (Mithril Bound Trunk, Big-mouth Clam). Use data/wowhead_forever_fishing.json, data/wowhead_forever_containers.json and the TSM prices (read via wfm.tsm from the TSM AppHelper AppData.lua). Compare with what the app shows.
- Fix real bugs with tests. Report anything doubtful rather than guessing.

2. Wowhead Forever data, slowly, in the built-in browser pane (mcp__Claude_Browser tools)
- Zone pages: https://www.wowhead.com/forever/zone=<id>. Read the Fishing data with JavaScript: `window.g_listviews['fishing']` has `note` ("Waters in this zone have been fished N times") and `data` rows with `id` and `count`. Skip rows where `classicEra` is set.
- Read every fishing zone not yet in data/wowhead_forever_fishing.json, Forever-only zones included (find their ids in data/gamedata/<build>/AreaTable.csv). Start with the user's level range (Arathi 45, Hinterlands 47, Western Plaguelands 28, Felwood 361, Un'Goro 490, Swamp of Sorrows 8, Desolace 405, Thousand Needles 400, Alterac 36, Hillsbrad 267, Wetlands 11, Moonglade 493, Winterspring 618, Eastern Plaguelands 139, Burning Steppes 46, Silithus 1377), then the rest.
- Item pages: https://www.wowhead.com/forever/item=<id>. Read `window.g_listviews['contains']`: `note` ("opened N times"), and rows with `id`, `count` and `stack` [min, max]. Skip `classicEra` rows. Do this for every item in the Data health check "Possibly undervalued items" with "contents unknown" (e.g. 13881, 21243, 8366, 13874, 13875, 6355, 6357).
- Pace: one page at a time, at least 8 seconds between page loads. On the first HTTP 403, stop all Wowhead reading for this run and record where you stopped in the project log.
- Verify extraction: on every 5th page, click the relevant tab, take a screenshot, and check that a few visible numbers match what you extracted.
- Append results to the two JSON snapshot files in their existing format, with today's date in "checked" and the page URL.

3. Addon verification
If the user has /reloaded since 2026-11-13 and opened a trunk, check C:\Games\World of Warcraft\_forever_\WTF\Account\*\SavedVariables\ForeverMoneyBridge.lua:
- `containers` is recorded;
- no trunk contents appear in `activity[zone].fishing`.
Never write the account folder number into the repo.

4. Then
- Check that the gathering list no longer includes crafted products (fixed on 2026-11-13: crafted consumables, "Cured " hides and "Bolt of " cloth are excluded in Engine.gathering).
- Restart the app and check it in the browser pane. Start it with the launch config "wfm" via preview_start. preview_stop doesn't kill python on this machine, so stop the old process by PID first.
- Update docs/PROJECT_LOG.md: decisions, verified facts, open items, change log, and remove the done steps from "Next session plan".
- Commit, and push to origin main only if all tests pass. End commit messages with: Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Finish with a short plain-language summary for the user:
- what was verified;
- what was wrong and fixed;
- what Wowhead data was added;
- what still needs them, such as an in-game /reload.