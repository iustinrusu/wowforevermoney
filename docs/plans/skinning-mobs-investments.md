# Plan: skinning spots, mob farming, Investments tab

Postponed on 2026-11-13 by the usage rule. Nothing runs by itself: a reminder points here. To start, open a
Claude Code session in this folder and say "Do the plan in docs/plans/skinning-mobs-investments.md".

You are continuing work on the WoW Forever Money app in the WoWForeverMoney project folder (git repo; remote https://github.com/iustinrusu/wowforevermoney.git, branch main).

First read CLAUDE.md, docs/PROJECT_LOG.md and docs/REVIEW_2026-11-13.md (section 4, strategies). They hold every decision and verified fact so far. Follow the standing rules strictly:
- **All data must be WoW: Forever.** This is imperative. Classic data is labelled fallback only and never reaches Top picks.
- **Accuracy first.** Second-guess every decision, verify numbers against a second source, and add tests.
- **Think broad.**
- **Wowhead:** only slow reads in the built-in browser pane (mcp__Claude_Browser tools). One page every 8+ seconds; stop all Wowhead reading at the first HTTP 403. Read data from `window.g_listviews`, never parse screenshots, and skip rows with `classicEra` set.
- **Ask before downloading files.**
- **Never send the user's personal data to outside services.**
- **Usage rule from the user:** check usage with mcp__ccd_session_mgmt__get_usage before each step. If the 5-hour limit gets tight, don't cut a step off midway: finish the current piece, commit it, then write the remaining steps into a plan file in docs/plans and set a one-time reminder after the reset that only points to it (reminders never run anything). Write those steps in the project log too.

Python: %LOCALAPPDATA%\Programs\Python\Python313\python.exe. Tests: `python -m unittest discover -s tests -t .`. Start the app with the browser pane's preview_start (launch config "wfm"); a new start replaces any earlier copy by itself.

Build these three, in order. Commit and push after each one; push only if all tests pass. End commit messages with:
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

1. **PARTLY DONE 2026-11-14** (7 of 19 items read before a Wowhead 403; see the project log's open items for the
   rest). **Skinning spots**, ranked by gold/hour like fishing (wfm/fishing.py and Engine.fishing_spots are the model to follow).
   - **Data:** on Wowhead Forever item pages (https://www.wowhead.com/forever/item=<id>), read the "Skinned from" listview. Check `Object.keys(window.g_listviews)` for its id; its rows are NPCs with count and outof. Pages to read:
     - leathers: Light 2318, Medium 2319, Heavy 4234, Thick 4304, Rugged 8170
     - hides: Light 783, Medium 4232, Heavy 4235, Thick 8169, Rugged 8171
     - Devilsaur Leather 15417, Thick Wolfhide 8368
     - scales: Turtle Scale 8167, Scorpid Scale 8154, Black Whelp Scale 7286, Worn Dragonscale 8165
     - also: Warbear Leather 15412, Frostsaber Leather 15419, Chimera Leather 15423
     First confirm each id's name in the app's item database. Save the result to data/wowhead_forever_skinning.json: dated, with URLs, and tracked in git like the fishing snapshot.
   - **Joining:** use QuestieDB (world.questie.npcs) for each NPC's zone, level and spawn count.
   - **Values:** expected value per skin uses the app's valuer (Engine.valuer).
   - **Pace:** add a new setting kills_per_hour (default 60, "assumed"). Replace it with measured pace from the ForeverMoneyBridge 'skinning' and 'mobs' activity logs (loots and seconds) when there are 10+ minutes of data.
   - **Skill:** the required skinning skill per mob level uses the classic rule (level x 5 for mobs above level 20, else (level - 10) x 10). Label that rule "Classic rule" and flag mobs the user can't skin yet (the user has Skinning 270).
   - **Display:** rows "Skin in <zone>: <mob names>" on the Farming tab. They enter Top picks hourly only with enough Forever data.

2. **Mob farming** for profitable drops: per mob, value per kill = sum of drop rate x item value, plus skinning when it's a beast.
   - Pick the items with the highest value x liquidity that drop from mobs, using TSM sold/day and QuestieDB npcDrops:
     - cloth: Linen 2589, Wool 2592, Silk 4306, Mageweave 4338, Runecloth 14047, Felcloth 14256
     - elementals: Elemental Earth 7067, Fire 7068, Air 7069, Water 7070; Heart of Fire 7077; Globe of Water 7079; Breath of Wind 7081; Core of Earth 7075; Living Essence 12803; Essence of Undeath 12808; Ichor of Undeath 7972
     - Righteous Orb 12811
     - the most valuable BoE drops found in the data
   - Read their "Dropped by" listviews on Wowhead Forever. Save the result to data/wowhead_forever_drops.json, same snapshot format.
   - Classic drop rates from QuestieDB's classicItemDrops.lua may fill gaps only as labelled, unconfirmed Classic data.
   - Rows "Kill <mob> in <zone>" with value per kill, gold/hour (kills_per_hour) and level range, flagged when the user (level 42) is under-levelled.
   - Mention that rogue pickpocketing and coin drops aren't counted yet.

3. **DONE on 2026-11-13, skip this step.** **Investments tab**: items that may rise in value as WoW: Forever matures (it launched about a week before 2026-11-13).
   - **Curated list** data/investments.json (tracked in git). For each item: id, name, category, thesis (why it may rise, from how it went in WoW Classic and from player progression: raiding consumables, Fire Resistance, endgame enchanting, flasks), horizon, risk.
   - **Candidates** (check each id's name in the item database and drop any mismatch):
     - Black Lotus 13468; Elemental Fire/Earth/Water/Air 7068/7067/7070/7069
     - Essence of Fire/Earth/Water/Air 7078/7076/7080/7082; Essence of Undeath 12808
     - Arcane Crystal 12363, Thorium Bar 12359, Arcanite Bar 12360
     - Large Brilliant Shard 14344, Greater Eternal Essence 16203, Illusion Dust 16204
     - Runecloth 14047, Felcloth 14256, Mooncloth 14342
     - Devilsaur Leather 15417, Rugged Leather 8170
     - herbs: Dreamfoil 13463, Mountain Silversage 13465, Plaguebloom 13466, Icecap 13467, Gromsblood 8846, Golden Sansam 13464
     - potions and elixirs: Major Healing Potion 13446, Major Mana Potion 13444, Greater Fire Protection Potion 13457, Elixir of the Mongoose 13452
     - Righteous Orb 12811, Raw Nightfin Snapper 13759, Raw Winter Squid 13755
   - **Per item, show:**
     - current lowest buyout, realm market value, region average sale price, sold/day and sale rate
     - the trend from the app's own price history (wfm/history.py: first vs latest snapshot, and 7-day change once there is enough history)
     - the downside to the vendor price floor
     - a Watch button (reuse the existing watchlist)
   - **Server progression gauge:** share of region sold/day across cloth tiers (Linen, Wool, Silk, Mageweave, Runecloth). A rising Runecloth share means more players near level 60, when endgame demand starts.
   - **Labelling:** label the whole tab clearly as speculation based on Classic patterns, not Forever data, with no promised returns.
   - Add an engine/API endpoint, a web tab, tests, and a README section.

At the end:
- Run all tests and check every tab in the browser pane: all must load, and the console must show no errors. Also run the page-script check in tests/test_web.py.
- Update README.md, docs/PROJECT_LOG.md (decisions, verified facts, change log, open items) and the next steps in docs/REVIEW_2026-11-13.md.
- Commit and push.
- Finish with a plain-language summary for the user: what was built, the top skinning and mob spots with gold/hour, the investment candidates, and what still needs them (for example, play with the addon on, then /reload).