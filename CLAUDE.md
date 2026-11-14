# Gold Ever After (WoW Forever Money): notes for Claude

A local Python app (web page at http://127.0.0.1:8765) that ranks every way to make gold in **WoW: Forever**
for the user's characters, using TSM auction data plus game data and addon data. User-facing docs: `README.md`.

**To-do list: `docs/plans/TODO.md`.** When the user says "start doing the things on the todo list", work through it
in order (each item points to a plan file with the full brief).

**Read `docs/PROJECT_LOG.md` at the start of every session.** It holds the decisions made so far and why,
facts we verified, open items, and a dated change log. Add to it before ending any task that changed
behaviour, made a decision, or verified a fact. Earlier chats were long and got compressed, so the log is the
memory of the project, not the chat.

## Standing rules from the user

- **All data must be for WoW: Forever. This is imperative.** Prefer Forever sources (TSM Forever-EU,
  wago.tools `wowf` build, QuestieDB Forever, SkillUpForever, Wowhead `/forever/`, the user's own addon
  logs). Data from another version (Classic, cMaNGOS, Era, retail) is only a fallback. It's labelled with
  its version on every row, never presented as Forever fact, and can't reach Top picks until Forever data
  (the user's catches/logs or a Wowhead Forever check) confirms it.
- **Think broad.** Cover all items and every way to make money (crafting in any profession, vendor flips,
  AH flips, farming, fishing, snipes...). The user's examples are samples, not the scope. Never gate by level
  or skill. Show what's doable now first, but never hide the rest.
- **Accuracy first.** Data must never be silently stale. Every number shows its source. Add tests for each
  calculation. In reviews, second-guess every decision, double-check accuracy against a second source,
  and look for better alternatives.
- **Addons update almost daily.** Anything read from an addon is re-read automatically when its files change.
- **Wowhead:** never bulk-scrape or get around their bot blocking (pages return 403 to scripts). Allowed:
  linking to Wowhead, the public tooltip API (slow, cached), and reading a short list of pages in the
  browser pane when asked. The user's decision (2026-11-14): if no bulk Forever source exists, read the top 100 of
  the coverage queue at one page a minute, stopping at the first block (`docs/plans/material-coverage.md`).
- **Downloads:** ask first (file name, source, size).
- **Usage limits:** when usage is getting tight, don't interrupt a task midway: finish the current piece,
  commit it, write the remaining steps into a plan file in `docs/plans/` (and note them in the project log),
  and set a one-time reminder for after the limit resets. The user said this should always be done.
- **Scheduled tasks are reminders only.** A scheduled task never does the work: it only reminds the user and
  points to the plan file. The user starts the work themselves (user's rule, 2026-11-13).
- **Explain everything plainly.** Every number, column and note in the app has a clear explanation in plain
  language (hover help, "how this is worked out", full-sentence notes); no cryptic few-word labels. UI:
  readability and usability first, then the WoW theme.
- **Addons:** public addons are installed by the user through the CurseForge app; our ForeverMoneyBridge comes
  with the app. Recommend, never download addons yourself.
- **Privacy:** never send the user's name, email, or character names to outside services (GitHub included: no
  real character names in tests, docs or commits; use made-up names). HTTP requests use
  the generic User-Agent `WoWForeverMoney/0.1 (personal gold tool)`.
- **Git:** remote is https://github.com/iustinrusu/wowforevermoney.git (branch `main`). Always commit and
  push each finished piece of work without asking (the user's standing permission for this project,
  2026-11-14). Never commit `data/` (caches, price history, logs, settings) except the
  hand-curated `data/tips.json`, `data/investments.json` and `data/wowhead_forever_*.json`, and never commit the WoW account folder
  number or other account identifiers.

## Run, test, audit

Python 3.13: `%LOCALAPPDATA%\Programs\Python\Python313\python.exe` (only dependency: cbor2).

```bash
python run.py --no-browser --port 8765
python -m unittest discover -s tests -t .
python -m wfm.audit
python -m wfm.classicdb --update
```

Only one copy of the app runs at a time (it holds a mutex on port 47651). The browser pane's `preview_stop`
doesn't kill the python process on this machine, so stop it by PID.

## Code map

| File | What it does |
|---|---|
| `wfm/paths.py` | finds the WoW install, addon folders, SavedVariables, client build |
| `wfm/tsm.py` | parses TSM `AppData.lua` (base-32 numbers; sale % and sold/day are raw/1000) |
| `wfm/gamedata.py` | wago.tools DB2 CSVs pinned to the client build: items, recipes, zones |
| `wfm/questie.py` | QuestieDB baked TOC (base64 CBOR): vendors, NPC drops, objects; drop rates |
| `wfm/skillup.py` | SkillUpForever: exact recipe skill levels, trainer fees, limited stock |
| `wfm/classicdb.py` | cMaNGOS classic-db fishing/pool tables (Classic 1.12: fallback only, never Forever fact) |
| `wfm/fishing.py` | fishing spots, your catch logs + Wowhead Forever counts, got-away and pace model |
| `wfm/hotfix.py` | decodes the client's hotfix cache (DBCache.bin): exact Forever item data; layout inferred and graded |
| `wfm/skinning.py` | skinning spots from Wowhead Forever "Skinned from" counts |
| `wfm/wowhead_items.py` | Wowhead Forever item/object/npc pages read by hand: format, importer, mob drops, node yields |
| `wfm/valuation.py` | an item's worth through every channel (AH, vendor, craft, open it) |
| `wfm/lua.py` | Lua table parser for SavedVariables and addon data files |
| `wfm/profile.py` | characters from ForeverMoneyBridge + TSM; auto-fills settings |
| `wfm/world.py` | loads every source, tracks freshness, reloads on file change |
| `wfm/pricing.py` | buy/sell quotes and flags; money formatting |
| `wfm/engine.py` | all opportunity calculations and top-pick sections |
| `wfm/plan.py` | "Your plan for today": cash-in, cooldowns, routines, snipe, farming, big flip, goal as ranked steps |
| `wfm/history.py` | SQLite price history: every realm scan for 14 days, then daily candles for a year |
| `wfm/market.py` | Market tab: one item's history, trends and market signals (sentiment) |
| `wfm/investments.py` | Investments tab: curated list (`data/investments.json`), trends, vendor floor, progression gauge |
| `wfm/alerts.py` | change events and Windows toasts |
| `wfm/tooltips.py` | slow cached Wowhead tooltip fetch for items missing from the game tables |
| `wfm/audit.py` | cross-source accuracy checks (shown on the Data health tab) |
| `wfm/coverage.py` | which traded materials/items lack Forever source data; Wowhead reading queue |
| `wfm/app.py` | HTTP server, JSON API, SSE live updates, watcher loop |
| `web/` | the page (index.html, app.js, style.css) |
| `addon/ForeverMoneyBridge/` | our WoW addon; copied into AddOns when the app starts |
| `data/` | caches and user state (not versioned, except the hand-curated `data/tips.json`, `data/investments.json` and `data/wowhead_forever_*.json`) |
