# WoW Forever Money

A local app that ranks every way to make gold in **WoW: Forever**: crafting in any profession, vendor flips, auction-house snipes, farming and fishing spots. It combines TSM prices with the game's own data and your addons' data, and it updates itself when new prices arrive.

## Start it

Double-click `start.bat`, or run:

```bash
python run.py
```

It opens `http://127.0.0.1:8765/`. Keep the window open while you use it. Only one copy runs at a time.

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

## Known limits (read these)

- TSM "market value" averages *listings*, not sales. "Region sold/day" and "region sale price" come from TSM users' sales records, so treat sold/day as a liquidity indicator, not an exact count.
- Only the lowest listing is known. Buying many units costs more than the lowest price shown.
- Game-file vendor prices are base prices; some vendors charge more (Black Market agents, for example). Those rows are flagged until ForeverMoneyBridge records the real price.
- About a third of recipe skill requirements are estimated (yellow − 40). They're marked `~`.
- "Cheap relist" and "AH → vendor" rows come from one scan snapshot. Check them in game, or use TSM's Sniper.
- AH deposits for listings that don't sell are not included.
- Wowhead Forever zone counts mix open water and pools. If you only fish open water, you'll catch fewer trunks than those numbers suggest.
- Coins inside containers aren't counted (Wowhead doesn't list them). Disenchanting and quest rewards aren't valued yet.

## Tests and audits

```bash
python -m unittest discover -s tests -t .
```

```bash
python -m wfm.audit
```

The tests check every calculation against hand-worked numbers, plus regressions for bugs found while building. The audit cross-checks the live data sources against each other.
