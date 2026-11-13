# Plan: more Forever data, mob farming, review

Saved on 2026-11-14 (usage rule: postponed, not cut off). Nothing runs by itself: a reminder points here. To start,
open a Claude Code session in this folder and say "Do the plan in docs/plans/forever-data-next.md".

First read CLAUDE.md and docs/PROJECT_LOG.md (Decisions, Verified facts, Open items). Standing rules apply: all data
must be WoW: Forever (Classic only as a labelled fallback, never in Top picks), accuracy first with tests, ask before
downloading anything, public addons are installed by the user through the CurseForge app, never send personal data
out, check usage before each step and postpone (plan file + reminder only) when it gets tight. End commit messages
with: Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>. Commit and push each finished piece.

## 1. Our own Forever loot tables (best long-term source)
Extend addon/ForeverMoneyBridge so every loot is also counted per source: GetLootSourceInfo(slot) gives the GUID
of the mob or node. Save `activity[zone][act].sources[npcOrObjectId] = {loots, items = {[itemId] = count}}` for
mobs, skinning, herbalism and mining (fishing already records sources/pools). Then:
- `nodes.py`: use measured items per node (by object id) instead of Classic loot where a node has 20+ gathers;
  drop the `classic_yields` flag for those spots.
- skinning: measured skins per mob complement the Wowhead counts.
- mob farming: per-mob value per kill (coins + every drop) from your own kills.
Bump the addon version; keep Checks.lua untouched; test the Lua with a careful read (no game here) and tell the
user to /reload twice.

## 2. Wowhead Forever, slowly (about 7 pages per session; it returned 403 after 7 on 2026-11-14)
Use the compact extract from the project log (top 40 rows, outof >= 50, skip `classicEra`), collect in the tab's
localStorage and read it out once; make the stop check THROW on a non-Forever page so a batch halts at once.
Order: skinning items left (4235 Heavy Hide, 8169 Thick Hide, 8171 Rugged Hide, 15417 Devilsaur Leather,
8368 Thick Wolfhide, 8167, 8154, 7286, 8165, 15412, 15419, 15423), then "Dropped by" for cloth (2589, 2592, 4306,
4338, 14047, 14256) and elementals (7067-7070, 7075, 7077, 7079, 7081, 12803, 12808, 7972, 12811), then herb and
ore node object pages ("Contains" tab) for Forever yields. Save to data/wowhead_forever_*.json (tracked).

## 3. Mob farming tab (after 1 or 2)
Rows "Kill <mob> in <zone>": value per kill (drops x your value, + skinning for beasts if you skin), kills per hour
(the kills_per_hour setting or measured), level range vs yours. Forever data only in Top picks.

## 4. Forever loot addons (ask the user first; they install through the CurseForge app)
Candidates found on CurseForge (not verified): HexLoot (syncs drop data with party/guild), Blackthornes Farmer
(per-mob loot and gold), Glimpse (nodes and creature loot, has an API), LootInsight Forever, vanThos DataBase,
Wishwell Forever. If the user installs one, read its SavedVariables like the other addons, check its format and
whether it holds only the user's own data or shared data, and label it by source.

## 5. GatherLite node locations
GatherLite ships Forever node positions from Wowhead (`plugins/database/data/forever.lua`,
`addon.predefined[objectID][uiMapID] = {x, y, ...}`). Using it needs UiMap ids -> zones (wago tables UiMap and
UiMapAssignment: ask before downloading). Compare its node counts with QuestieDB's per zone.

## 6. Review
Adversarial review of everything built on 2026-11-13/14 (pricing WALL and liquidity, ranking, history compaction,
market signals, skinning, nodes, source grading, cooldowns). Small things noticed: container details list only the
top 12 contents (say so in the UI); shared transmute cooldown could pick the best mix per day (now: best one only).
