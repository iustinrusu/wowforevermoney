# WoW Forever Money

A local app that ranks every way to make gold in **WoW: Forever**: crafting in any profession, vendor flips, auction-house snipes, farming and fishing spots. It combines TSM prices with the game's own data and your addons' data, and it updates itself when new prices arrive.

Everything runs on your PC. The page is only reachable from your own computer, and your character data never leaves it.

## First-time setup

1. **You need:**
   - **Python 3.13.** If it's missing, install it with `winget install Python.Python.3.13`.
   - **The TSM desktop app**, running and logged in. It downloads auction prices about once an hour.
   - **WoW: Forever.** The app finds the install through TSM's settings or the usual install folders.
2. **Start the app:** double-click `start.bat`.
   - It installs the one Python package it needs and opens `http://127.0.0.1:8765/` in your browser.
   - The first start downloads the game's item and recipe tables from wago.tools, which takes about a minute.
   - Keep the black window open while you use the app. Closing it stops the app.
3. **Turn on the addon in WoW:**
   - The app copies its addon, **ForeverMoneyBridge**, into your AddOns folder every time it starts.
   - At the character screen, click **AddOns**, tick **ForeverMoneyBridge**, then log in and type `/reload` once.
   - Back in the app, the **Settings** tab should now show your character with level, gold and professions.
4. **Optional: Classic fishing tables.** These fill in zones that have no Forever data yet, and are always shown as unconfirmed. To get them, run `python -m wfm.classicdb --update` once (downloads about 13 MB from github.com/cmangos/classic-db). They're already set up on this PC.

## Everyday use

1. **Before you play:**
   - Start the TSM desktop app and this app (`start.bat`).
   - If the app is already running, starting it again just opens the page.
2. **While you play:**
   - Play normally. The addon records your gold, skills, what you loot and where, how long you spend, vendor prices, and what trunks and clams contain.
   - WoW only writes addon data to disk when you `/reload` or log out.
   - So **type `/reload` whenever you want the app to catch up**, for example after a fishing session or after opening a few trunks.
3. **The app updates by itself:**
   - It re-reads TSM prices whenever the TSM app syncs, and re-reads your addons whenever they change (including after addon updates).
   - It shows a desktop notification when something new and profitable appears.
4. **Refresh now** (top right) re-reads everything right away: useful just after a `/reload`.
5. **Start with Top picks**, then click any row for the details, sources and caveats.

## The tabs

| Tab | What it's for |
|---|---|
| **Top picks** | What to do now, ranked by profit per day. Also: the best fishing and farming spots per hour, snipes (single cheap listings to check in game), things a higher profession skill unlocks, and other professions worth switching to. Only Forever-confirmed data appears here. |
| **Crafting** | Every recipe in every profession, with ingredient costs (cheapest of vendor or AH) and sale value. Filter by profession, or tick "only what I can craft now". |
| **Flips** | Buy from a vendor and sell on the AH; buy on the AH and sell to a vendor; cheap listings to relist. |
| **Farming** | Every fishing spot, Forever data first. "Fish in …" rows are Forever data (your catches plus Wowhead Forever). "Classic table: …" rows are WoW Classic data, often wrong for Forever. Below that: what every farmed material is worth. |
| **My bags** | Everything your characters carry (from Syndicator) and the best thing to do with each: sell on the AH, sell to a vendor, craft with it, or **open it**. |
| **Item search** | Look up any of the ~32,000 items: prices, price history, who sells or drops it, recipes, where to fish it. |
| **Changes** | A history of new top picks, snipes, watched price moves and newly spotted undervalued items. |
| **Data health** | How old each data source is, and accuracy checks. Includes Classic fishing vs Forever, and "possibly undervalued items". The dot on the tab turns yellow or red when something needs attention. |
| **Settings** | Your detected characters, the manual fallback values (gold, level, professions), and the assumptions: AH cut, your share of daily sales, casts per hour, alerts, and when data counts as stale. |

**In an item's details** (click any item):
- **Open on Wowhead** for comments and tips.
- **Watch price** sends an alert when its price moves 20% or more.
- **I gather … per hour** gives gold per hour for farming it.
- **Copy item list for TSM** (under most tables) can be pasted into TSM under Groups → Import.

**Flags** (the small labels on rows) explain anything uncertain; hover over one for the full explanation. The ones that matter most:
- **Classic, unconfirmed** (red): data from WoW Classic, not Forever. It never reaches Top picks.
- **contents unknown**: it can be opened, but its Forever contents aren't known yet, so its value is a floor. Open one with the addon on, then `/reload`.
- **open it**: worth more opened than sold.
- **small sample**: not many catches or loots logged yet.
- **assumed casts/hour**: fishing pace from your setting. It becomes **measured** after about 10 minutes of fishing with the addon on.
- **vendor price from game files** / **black market vendor**: open that vendor once with the addon on to record the real price.
- **pool loot extra**: this gold/hour is open water only. The details show what pools would add.
- **slow seller**, **can't afford**, **snapshot**: check before acting.

## The addon: ForeverMoneyBridge

- **What it saves:**
  - your level, gold, faction and professions (fills in Settings automatically);
  - what you loot, in which zone, from what (fishing, skinning, herbs, mining, mobs) and how long you spent;
  - real vendor prices when you open a vendor;
  - what each trunk, clam or crate gave you.
- **When:** only on `/reload` or logout, because WoW doesn't let addons write files any other time.
- **`/fmb`** takes a snapshot right away (then `/reload` to write it).
- **Updates:** the app copies the latest version into your AddOns folder each time it starts. Do a `/reload` in game to load it.
- **Privacy:** nothing leaves your PC. It only writes WoW's normal saved-variables file, which this app reads.

## Command line

```bash
python run.py --port 8765 --no-browser
```

Starts the app on another port, or without opening the browser.

```bash
python -m wfm.classicdb --update
```

Checks GitHub for a newer Classic fishing dump, and downloads and extracts it if there is one.

## Troubleshooting

- **"Lost connection to the app"** at the top of the page: the black window was closed. Start `start.bat` again.
- **Prices are old** (Data health shows yellow or red for TSM): is the TSM desktop app running and logged in? It writes new prices about hourly.
- **Your character isn't detected:**
  - Make sure ForeverMoneyBridge is ticked in the AddOns list. If it shows as out of date, tick "Load out of date AddOns".
  - Then `/reload`.
- **A number looks wrong:**
  - Open the row's details: every value shows where it came from.
  - Check the assumptions in Settings.
  - Check the accuracy checks on Data health.

## Where the data comes from

| Source | What it gives | How it stays fresh |
|---|---|---|
| TSM `AppData.lua` (TSM desktop app) | realm and region prices, sale rates, sold/day | re-read when the TSM app writes it (about hourly) |
| wago.tools game tables (DB2) | items, vendor prices, recipes, zones | downloaded for your exact client build; re-downloaded when WoW patches |
| QuestieDB addon | which NPCs sell, drop and contain each item, faction, location | re-read whenever the addon updates |
| SkillUpForever addon | exact recipe skill levels, trainer fees, limited-stock vendors | re-read whenever the addon updates |
| ForeverMoneyBridge (our addon, auto-installed) | your level, gold, professions, real vendor prices, loot by zone with time spent | on logout or `/reload` |
| ForeverAngler, Syndicator | your fishing catch log; your bags | on logout or `/reload` |
| Wowhead Forever (read by hand) | real Forever fishing counts for 5 zones; what 5 trunks/clams contain | a dated snapshot in `data/wowhead_forever_*.json`; re-read the pages to refresh |
| cMaNGOS classic-db (Classic 1.12, **not Forever**) | fishing tables for zones with no Forever data yet | downloaded once (`python -m wfm.classicdb --update`); checked monthly for a newer dump |
| Wowhead tooltip API | names and vendor prices for ~3k items the client's tables don't ship | fetched slowly once, cached in `data/tooltips.json` |

The **Data health** tab shows every source's age and version, plus the accuracy checks.

## How the numbers work

- **Buy cost** is the cheapest of a vendor you can use (your faction) and the lowest AH listing.
- **Sale price** is the lower of the current lowest listing and the realm's 14-day market value, minus the AH cut. It's conservative: you'll have to undercut.
- **Per day**: profit × the units you can realistically sell per day. That's TSM's region sold/day × your market share setting (default 20%), capped by your gold, vendor stock and recipe output.
- **Gold/hour** is only shown when it's measured (ForeverMoneyBridge time logs), assumed from your settings (ForeverAngler has no timing), or from a rate you entered.
- **What an item is worth** is the best of four ways to turn it into gold: sell on the AH, sell to a vendor, craft with it, or **open it** (trunks, clams, crates). Opening is valued at the expected value of its Forever contents at current prices, so a Mithril Bound Trunk is worth its Mageweave and Runecloth, not its 2c vendor price. The client's own item flags say which items can be opened; any openable item with unknown contents is flagged "contents unknown" (its value is a floor) and listed in the undervaluation watch on Data health.
- **Fishing** is Forever data first: your catches plus Wowhead Forever zone counts, one row per zone ("Fish in ..."). Classic tables appear only as "Classic table: ..." rows, are often wrong for Forever (Data health shows how far), and never reach Top picks. Gold/hour for fishing = worth per catch x catches per hour (casts/hour setting x your landed rate x fish kept).
- **Fishing drop rates** come from Wowhead Forever's large samples. Your own catch logs are small, mix pools with open water and can be incomplete, so by default they only give your pace and got-away rate (Settings: "also use my own catch logs").
- **Pools** (Floating Wreckage/Debris, schools) have to be found first, so fishing gold/hour is open water only. What pool loot (trunks, Stranglekelp, Rumsey Rum) adds is shown in each row's details (Settings: "count pool loot"). The addon records which catches came from pools, so your real pool share can be measured.

## Known limits (read these)

- TSM "market value" averages *listings*, not sales. "Region sold/day" and "region sale price" come from TSM users' sales records, so treat sold/day as a liquidity indicator, not an exact count.
- Only the lowest listing is known. Buying many units costs more than the lowest price shown.
- Game-file vendor prices are base prices; some vendors charge more (Black Market agents, for example). Those rows are flagged until ForeverMoneyBridge records the real price.
- About a third of recipe skill requirements are estimated (yellow − 40). They're marked `~`.
- "Cheap relist" and "AH → vendor" rows come from one scan snapshot. Check them in game, or use TSM's Sniper.
- AH deposits for listings that don't sell are not included.
- Wowhead Forever zone counts mix open water and pools. Pool-only loot is set aside, but school fish that are also caught in open water (Oily Blackmouth, Firefin Snapper, Stonescale Eel) stay in, so open-water shares of those fish are slightly high.
- Coins inside containers aren't counted (Wowhead doesn't list them). Disenchanting and quest rewards aren't valued yet.

## Tests and audits

```bash
python -m unittest discover -s tests -t .
```

```bash
python -m wfm.audit
```

The tests check every calculation against hand-worked numbers, plus regressions for bugs found while building. The audit cross-checks the live data sources against each other.
