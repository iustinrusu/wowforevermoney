# Gold Ever After

*A WoW: Forever money guide* (project folder: WoWForeverMoney)

A local app that ranks every way to make gold in **WoW: Forever**: crafting in any profession, vendor flips, auction-house snipes, farming and fishing spots. It combines TSM prices with the game's own data and your addons' data, and it updates itself when new prices arrive.

**New here? Follow [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** (about 15 minutes).

Everything runs on your PC. The page is only reachable from your own computer, and your character data never leaves it.

## First-time setup

1. **You need:**
   - **Python 3.13 or newer.** If it's missing, `start.bat` offers to install it with winget (type Y).
   - **The TSM desktop app**, running and logged in. It downloads auction prices about once an hour.
   - **WoW: Forever.** The app finds the install through TSM's settings or the usual install folders.
2. **Start the app:** double-click `start.bat`.
   - It installs the one Python package it needs and opens `http://127.0.0.1:8765/` in your browser.
   - The first start downloads the game's item and recipe tables from wago.tools, which takes about a minute.
   - Keep the black window open while you use the app. Closing it stops the app. Starting it again always replaces an earlier copy, even a hidden one.
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

**Your purse** (top right): your gold now, plus what your bags, bank, mail and current auctions are worth at today's
prices (hover for the breakdown, click for My bags). From Syndicator; auctions are an estimate, since your listing
prices aren't recorded.

| Tab | What it's for |
|---|---|
| **Top picks** | Starts with **Your plan for today**: a short checklist of the best things to do now, like a seasoned gold-maker plans a session. It cashes in what you already own (what sells on the AH, containers worth opening, vendor junk; never things you probably use yourself, such as potions, poisons or your Skinning Knife), then cooldown crafts, your best daily routines, a snipe, one farming hour backed by Forever data and one big flip, each as a concrete instruction ("Buy 11 ... from ... at 3s each; list at 18s each") with a plain reason, the expected gold, the minutes it takes, gold per hour of your time, gold needed and how sure we are. Steps not worth your time are left out; the rest are shown quick wins first. A long-term goal comes last. Below the plan, the full lists, ranked by profit per day. Also: the best fishing and farming spots per hour, snipes (single cheap listings to check in game), things a higher profession skill unlocks, and other professions worth switching to. Only Forever-confirmed data appears here. "Daily routines" holds crafts and vendor flips that sell about once a day or more; slower but valuable ones are under **Occasional big flips**, with the profit at the lowest listing and at what the item actually sells for. "Sales a day (you)" = what the whole region buys a day x your share (Settings), capped by your gold, stock and ingredients; "Profit a day" = profit each x that. |
| **Crafting** | Every recipe in every profession, with ingredient costs (cheapest of vendor or AH) and sale value. Filter by profession, or tick "only what I can craft now". |
| **Professions** | Each profession: what it earns you now, at full skill, and what it costs to get there. Below, the **levelling planner**: the cheapest path from any skill to any other (300 by default), using every recipe in the game. Each stretch shows the recipe, how many crafts, what the materials cost (a material your gathering gives counts at what it would sell for, marked "yours" only where Forever data says so), what the products bring back (the AH only for about 2 days of your share of its sales, then a vendor or disenchanting) and where to learn the recipe. Training the next rank (Journeyman to go past 75, Expert past 150, Artisan past 225) is a row of its own with its fee, the skill and level it asks for and who teaches it; a pattern no one sells on your realm now says "may have to wait". |
| **Flips** | Buy from a vendor and sell on the AH; buy on the AH and sell to a vendor; cheap listings to relist. |
| **Gathering** | Pick an activity: **Fishing**, **Skinning**, **Herbalism**, **Mining**, **Mob farming** or **Materials**. Each ranks zones by gold per hour and explains how. Gold per hour is always worked out from reported counts (Wowhead Forever) at the paces in Settings; your own logged time is never used, because time in a zone includes questing, travel and breaks. Your own loot per zone is shown as a log, without a gold per hour. Fishing and skinning use Forever counts from Wowhead; herb and ore yields are WoW Classic numbers (labelled, kept out of Top picks) until your addon measures your own gathering. |
| **My bags** | Everything your characters carry (from Syndicator) and the best thing to do with each: sell on the AH, sell to a vendor, craft with it, or **open it**. |
| **Investments** | Items that may rise in value as the server matures, with a **server progression gauge** (how much of each cloth tier sells: more Runecloth = more players near 60). The ideas are speculation from WoW Classic patterns; the prices, trends and recipes beside them are Forever data. |
| **Market** | Search any item (suggestions as you type) for a stock-market style view: price history chart (lowest listing, realm 14-day average, region average sale, listings as volume; daily candles once there are 2+ days), 24 h / 7 d / overall change, and **market signals** (momentum, price vs 14-day average, supply change, demand, your realm vs the region) summed into Bullish / Neutral / Bearish. Signals describe the market now; they are not a forecast. History builds up while the app runs: TSM's data file only has averages, so the app saves every realm scan (about hourly) for 14 days, then one daily candle per item for a year. TSM's own long-term and recent averages are shown too. |
| **Item search** | Look up any of the ~32,000 items: prices, price history, who sells or drops it, recipes, where to fish it. |
| **Changes** | A history of new top picks, snipes, watched price moves and newly spotted undervalued items. |
| **Data health** | How old each data source is, and accuracy checks. Includes Classic fishing vs Forever, vendor prices three ways (TSM, your own client's checks, the game files), and "possibly undervalued items". The dot on the tab turns yellow or red when something needs attention. |
| **Settings** | **Motion**: the page's animations (the night sky moving as you scroll, panels and rows rising in, the sliding tab line, gold counting up, a sparkle when you tick a step). "Follow Windows" (the default) turns them off when Windows asks apps for less motion (Settings > Accessibility > Visual effects > Animation effects); On or Off decide outright, saved at once. Off changes nothing but the movement. Then your detected characters, the manual fallback values (gold, level, professions), and the assumptions: AH cut, your share of daily sales, how many days of AH sales the levelling planner counts (2: a product that sells once every few days can't make a path look cheap), casts per hour, alerts, and when data counts as stale. |

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
- **vendor price from game files**: open that vendor once with the addon on to record the real price.
- **Black Market agents** charge far more than the game files say (Frilled Lichen: 4g 50s, not 1s 20c), so items
  only they sell get no vendor price, no flip and no ingredient cost until you open their shop with the addon on.
- **pool loot extra**: "Gold / hour" is open water only. The "Gold / hour with pools" column adds the pools you come across (not counting the time spent finding them, so it's a ceiling).
- **slow seller**, **can't afford**, **snapshot**: check before acting.

## Addons this tool uses

Install the public addons with the **CurseForge app** (curseforge.com/download/app): pick World of Warcraft, the
**Forever** version, search each name below and click Install. CurseForge keeps them updated, and the app re-reads
them automatically after every update. Only ForeverMoneyBridge comes from this tool instead.

| Addon | Needed? | What the app gets from it | Where |
|---|---|---|---|
| **TSM desktop app** + **TradeSkillMaster** + **TradeSkillMaster_AppHelper** | **Required** | Auction prices: the desktop app writes them into AppHelper's folder about hourly | Addons: CurseForge app. Desktop app: tradeskillmaster.com |
| **ForeverMoneyBridge** (this tool's addon) | **Required** | Your level, gold, professions, real vendor prices, loot and time per zone, trunk contents, in-game item checks | Installed by `start.bat` or `install_addon.bat` |
| **ForeverRecipes** | Strongly recommended | The main recipe source: which recipes can really be learned in Forever, the skill and character level each needs, trainer fees, where to learn each recipe (trainers, vendors, drops, quests), rogue poisons. Without it (and without SkillUpForever), crafts are marked "unverified recipe" and never reach Top picks | CurseForge app |
| **SkillUpForever** | Optional | Fills gaps in ForeverRecipes: rank training fees in the levelling path, stock limits at vendors (herb sellers and others), a few required skills. While it is installed the app saves a copy of these tables (`data/skillup_saved.json`), so you can delete the addon afterwards and nothing changes | CurseForge app |
| **Questie** (with **QuestieDB**) | Strongly recommended | Vendors, who drops what, herb and ore node locations (Forever data) | CurseForge app |
| **Syndicator** | Recommended | Your bags and bank: enables the My bags tab | CurseForge app |
| **ForeverAngler** | Optional | Fishing log (pace and got-away rate) | CurseForge app |
| **GatherLite** | Optional | Forever herb, ore and fishing-pool positions, and which nodes are herbs or ore (with QuestieDB, which materials your Herbalism or Mining gives) | CurseForge app |

Not used yet, but worth knowing: several Forever addons record loot per mob and per node and might one day feed
the app more Forever data (HexLoot, Blackthornes Farmer, Glimpse, LootInsight Forever, vanThos DataBase).
See docs/PROJECT_LOG.md, open items.

## The addon: ForeverMoneyBridge

- **Item checks:** the app writes a list of items to verify (`Checks.lua` in the addon folder). In game, the addon asks your client about each one and saves the answers, which override every other source. Data health shows how often each source was right.
- **What it saves:**
  - your level, gold, faction and professions (fills in Settings automatically);
  - what you loot, in which zone, from what (fishing, skinning, herbs, mining, mobs) and how long you spent;
  - real vendor prices when you open a vendor;
  - what each trunk, clam or crate gave you.
- **When:** only on `/reload` or logout, because WoW doesn't let addons write files any other time.
- **TSM's vendor prices:** about 30 seconds after you log in, the addon reads TSM's own vendor prices (what a vendor
  pays, what a vendor charges) for every item the app prices; `/reload` after that to save them. The app uses them
  before the game files.
- **`/gea`** (or `/fmb`) takes a snapshot right away (then `/reload` to write it).
- **`/gea start`** / **`/gea stop`**: the farm meter: what you loot and its worth, gold an hour, and XP gained (total,
  an hour, and how long to the next level at that pace). Prices: the app's own values (as its My bags shows them)
  while they are under 12 hours old, else TSM in game, so it also works without the app (your realm's lowest
  listing, else its average, minus the 5% AH cut; the vendor price when that is higher). `/gea prices app` or
  `/gea prices tsm` fixes one source, `/gea prices auto` goes back; `/gea prices` explains them.
- **Fold the meter:** the "–" button at the top right (or `/gea min`) folds the window to one line: the total, gold an
  hour and the time; "+" opens it again. It stays folded for the next session until you open it. `/gea hide` hides it
  completely and `/gea show` brings it back. Folded or hidden, it keeps counting (only Pause and Stop change that).
- **`/reload` or log out mid-session:** the session carries on when you're back within 30 minutes (paused stays
  paused, and the time away doesn't count). After longer, it's saved as it stood when you logged out.
- **Boxes you open** (lockboxes, junkboxes, clams, trunks): a box you loot counts nothing until you open it, then what's
  inside counts under "Opened". Since the 25 Nov 2026 patch most boxes open straight into your bags with no loot
  window, so the addon watches your bags: when a box leaves them, the items that arrive within 2 seconds (not from a
  loot window, and not while a vendor, bank, mailbox, trade window or the auction house is open) are what it held.
  `/gea debug` prints in chat what the meter makes of each loot window and each box.
- **Gold looted** counts your own coin lines ("You loot 3 Silver, 15 Copper", "Your share of the loot is ..."), so two
  loots in quick succession both count. Other players' coins, sales, mail and quest rewards don't.
- **Minimap button:** a gold coin on the edge of the minimap. Click it for every command in a list (start, pause,
  stop, hide or show, fold, the price source, debug, the full command list); hover a line to see what it does. Drag the
  coin around the minimap to move it: its place is saved and kept through relogs, `/reload` and game restarts (the same
  spot on every character). The coin is grey while no session runs or it is paused. "Hide this minimap button" in
  the list hides it; `/gea minimap` brings it back. `/gea help` prints every command with what it does.
- **The log:** the addon writes down what it does and why, all the time: every item and coin the meter counts or skips
  (and why), each box it sees leave your bags, the loot log, and every error, with where it happened (errors are also
  announced once in chat). `/gea log` shows the last 15 lines (`/gea log 40` for more, `/gea log clear` empties it).
  It keeps the last 600 lines in the addon's saved file; WoW writes that on `/reload` or logout. When something looks
  wrong, `/reload` and say so: the log tells what happened.
- **Which version is running:** `/gea debug` and `/gea` say it (for example "Gold Ever After 1.6.6"). The app copies
  a new addon into WoW when it starts, so after an update start the app, then `/reload` in game.
- **Install without the app:** double-click `install_addon.bat`. It finds WoW: Forever (TSM desktop app
  settings, the Battle.net install entry, then the usual folders on drives C to H), or asks for the folder.
  It never overwrites the item-check list (`Checks.lua`) the app wrote.
- **Updates:** the app copies the latest version into your AddOns folder each time it starts. Do a `/reload` in game to load it.
- **Privacy:** nothing leaves your PC. It only writes WoW's normal saved-variables file, which this app reads.

## Extras (not part of the app)

`extras/` holds our own addons that the app never installs, kept here for later changes:

- **TargetKit** (`extras/TargetKit`): three one-key macros: TK Find (a find list, closest first, press again for the
  next), TK Pickpocket (the closest humanoid not robbed yet: Sap, then Pick Pocket) and TK Sap (mouseover, else the
  closest enemy player, including stealthed ones the game reveals). A minimap button opens its window: keys for the
  three macros (Shift, Ctrl and Alt combinations, mouse buttons) and the find list (type a name, or add your target).
  Its README has the details and how to install it.

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
| Your client's hotfix cache (`_forever_/Cache/ADB/enUS/DBCache.bin`) | exact Forever data for ~5,200 items the client tables don't ship, and ~1,500 server updates to items they do | re-read whenever the game updates the file |
| Your game client (ForeverMoneyBridge item checks) | the final word on sell price, quality, levels, stack size and binding for the items the app asks about | after you log in (or `/reload`), wait a minute, then `/reload` again |
| QuestieDB addon | which NPCs sell, drop and contain each item, faction, location | re-read whenever the addon updates |
| ForeverRecipes addon | the main recipe source: which recipes you can learn, skill and level each needs, trainer fees, where to learn them, rogue poisons | re-read whenever the addon updates |
| SkillUpForever addon (optional) | rank training fees, vendor stock limits, a few required skills ForeverRecipes lacks (WoW Classic database tables) | re-read whenever the addon updates; after you delete it, the copy the app saved |
| ForeverMoneyBridge (our addon, auto-installed) | your level, gold, professions, real vendor prices, loot by zone with time spent | on logout or `/reload` |
| ForeverAngler, Syndicator | your fishing catch log; your bags | on logout or `/reload` |
| Wowhead Forever (read by hand) | real Forever fishing counts for 5 zones; what 5 trunks/clams contain | a dated snapshot in `data/wowhead_forever_*.json`; re-read the pages to refresh |
| cMaNGOS classic-db (Classic 1.12, **not Forever**) | fishing tables for zones with no Forever data yet | downloaded once (`python -m wfm.classicdb --update`); checked monthly for a newer dump |
| Wowhead tooltip API | names and vendor prices for ~3k items the client's tables don't ship | fetched slowly once, cached in `data/tooltips.json` |

The **Data health** tab shows every source's age and version, plus the accuracy checks.

## How the numbers work

- **Buy cost** is the cheapest of a vendor you can use (your faction) and the lowest AH listing.
- **Sale price** is the **current lowest buyout** on your realm (what you'd list at), minus the AH cut. With nothing listed there's no buyout to match, so the region's **average actual sale price** is used (a Hand Axe whose listings average 2.5g really sells for about 6.6s). If even the lowest listing is over 3x what the item actually sells for across the region (a wall of wishful prices: Short Staff had 10 listings at 10g and sells for 1s 90c), nobody pays it, so the item is valued at its region average sale price and flagged "listings far above sales". Items listed well above what they actually sell for get a "sells for less" flag: at that price they may sit unsold. Settings can switch to "what items actually sell for", which never values anything above its real sale price. Soulbound and quest items only count at their vendor price. A lone listing far above the region's usual price is never used for trunk contents or catches.
- **Names link to Wowhead:** every item name opens its Wowhead WoW: Forever page (with Wowhead's tooltip on hover), and so do NPC and mob names where the app knows them (vendors, trainers, quest givers, mobs that drop or are skinned, mob farming rows), shown with a dotted underline.
- **Crafting values** (what a material is worth when you craft it) use only recipes you can make now. A better recipe that needs more skill is shown as "more with skill". If the crafted product's market only absorbs a few a day, it's flagged "limited demand". Farming loot (mobs, skins, nodes, fish) counts on the AH only for as many as your share of the region's daily sales, assuming an hour of farming a day; the rest at the next best price, usually a vendor's (an hour of Tanaris air elementals gives about 48 Breaths of Wind, the market takes about 10 a day). A lowest listing three or more times what an item actually sells for counts at the sale price. Mob farming paces each mob by its health: "Kills per hour" in Settings is for a typical mob of your level, a mob with more health is killed more slowly and one with less faster (its health from its Wowhead Forever page where read, else the typical health at its level, a WoW Classic rule). A material listed on your realm's AH is never counted above what buying one costs ("at buy price"): one you hold or loot only saves you buying one, and the craft's own profit is on its Crafting row. A craft that only pays at today's unusual prices (its row fails the second opinion at typical prices) gives its materials no crafted worth at all.
- **Value guards** (on Data health): "Values never above the buy price" checks every value the app works out (My bags, the farm meter, farming rows); if any part of the app ever comes out above what buying one costs, the value is held at the buy price, flagged "held at buy price", and the check turns red. "Values that swing" compares every value with the one at the previous price update: one that moved by half or more beyond its own price's move rests on other items' prices (a thin margin between big prices) and is listed for 24 hours.
- **Event vendors** (Darkmoon Faire, holiday vendors) and vendors with no known location are flagged "event vendor" and kept out of Top picks.
- **Ranking (the # column, medals for 1-3):** every row gets a score = expected profit (per day; per hour for
  activities; per purchase for snipes) x how sure we are (data quality and how well it sells) x risk (what you'd
  lose if it doesn't sell, vs the profit: risking 20x the profit halves it) x can you do it now (x0.5 for a skill
  gap, x0.25 for a profession you don't have) x problems (x0.2 for "barely sells", event or Black Market vendors,
  unverified recipes, Classic-only data) x 1.1 for preferred professions. What more gold would add counts 10%, so
  what you can afford now comes first. The number stays with the row when you sort by another column; each row's
  details show the breakdown. Investments rank by how cheap the item is vs its TSM long-term average x how well
  it sells x risk.
- **Your time counts.** Each daily routine gets an estimated play time a day (posting auctions and reposting the
  ones that expire, buying ingredients, crafting, one vendor trip). That time is charged at what an hour of your
  time is worth: half your best measured farming gold per hour (or your own value in Settings). Routines that
  earn less than their time is worth are marked "not worth your time" and left out of Top picks. The "Time a
  day" column shows the minutes and what they earn per hour.
- **Does it actually sell?** Before suggesting anything you'd sell on the AH, the app checks three TSM numbers:
  how many sell per day in the whole Forever EU region, what share of listings sell, and how many are already
  listed on your realm (as days of the region's sales). **Barely sells** (never suggested; hidden by default on
  Crafting and Flips): under 1 sold a day (or your Settings minimum, if higher), under 1 in 10 listings selling,
  or over 10 days of sales already listed. **Slow to sell** (under 1 in 4 listings sells) and **crowded** (over 3
  days listed) are shown but ranked lower. The "Sells" column and each row's details show the numbers.
- **Recipe cooldowns** (from the game's SpellCooldowns table) cap how many a day you can make: Transmute:
  Arcanite 47 hours, so about 0.5 a day; Mooncloth 95 hours. Rows say "cooldown" (and a Cooldown column
  shows it). All transmutes share one cooldown in Forever, so Top picks suggest only the best one. Where the
  cooldown sets the pace, "Profit a day" shows what one craft makes and how often ("a craft, every 3 days"),
  since it earns on the day you craft it; the average a day is under it in small print and is what ranks it.
- **Per day**: profit × the units you can realistically sell per day. That's TSM's region sold/day × your market share setting (default 20%), capped by your gold, vendor stock and recipe output.
- **Vendors with only a few at a time**: when the cheapest seller of an ingredient has only a few a restock (Vi'el's 2 Felcloth, an herb vendor's 3 Golden Sansam), a craft counts those first and buys the rest on the AH at its price (your share of its sales), as long as the dearer copies still pay; the cost per craft is the average ("vendor first, then AH"). "Ingredient in limited stock" now means the vendor's stock really holds the crafts down. The levelling planner, which buys dozens, prices such an ingredient at the AH when the AH lists it.
- **Gold/hour** is only shown when it's measured (ForeverMoneyBridge time logs), assumed from your settings (ForeverAngler has no timing), or from a rate you entered.
- **What an item is worth** is the best of four ways to turn it into gold: sell on the AH, sell to a vendor, craft with it, or **open it** (trunks, clams, crates). Opening is valued at the expected value of its Forever contents at current prices, so a Mithril Bound Trunk is worth its Mageweave and Runecloth, not its 2c vendor price. The client's own item flags say which items can be opened; any openable item with unknown contents is flagged "contents unknown" (its value is a floor) and listed in the undervaluation watch on Data health.
- **Fishing** is Forever data first: your catches plus Wowhead Forever zone counts, one row per zone ("Fish in ..."). Classic tables appear only as "Classic table: ..." rows, are often wrong for Forever (Data health shows how far), and never reach Top picks. Gold/hour for fishing = worth per catch x catches per hour (casts/hour setting x fish kept). Fish kept follows the game's rule: your effective skill (Fishing + the pole, gear and lure bonus you set in Settings, e.g. Bright Baubles +75) against the zone's skill (WoW Classic zone skills). Your own fishing logs never set a rate.
- **Fishing drop rates** come from Wowhead Forever's large samples. Your own catch logs are small, mix pools with open water and can be incomplete, so by default they only give your pace and got-away rate (Settings: "also use my own catch logs").
- **Pools** (Floating Wreckage/Debris, schools) have to be found first, so fishing gold/hour is open water only. What pool loot (trunks, Stranglekelp, Rumsey Rum) adds is shown in each row's details (Settings: "count pool loot"). The addon records which catches came from pools, so your real pool share can be measured.

- **Investments:** the candidate list and its reasons are hand-written in `data/investments.json` from how these items went in WoW Classic, so treat them as ideas, not Forever facts. Each id is checked against the item database; a mismatch is left out and listed. Shown per item: what buying one costs now, how that compares with TSM's 14-day realm average, the trend in this app's own price snapshots (first vs latest scan until there's a day of history; after that each end is a 12-hour median, so one odd listing can't swing it; a 7-day change after a week), region sold/day and sale rate, the worst case if the price fell to what a vendor pays, and how many Forever recipes use it. Reselling must beat the AH cut: with 5% the price has to rise 5.3% just to break even (deposits not counted).

## Known limits (read these)

- TSM "market value" averages *listings*, not sales. "Region sold/day" and "region sale price" come from TSM users' sales records, so treat sold/day as a liquidity indicator, not an exact count.
- Only the lowest listing is known. Buying many units costs more than the lowest price shown.
- Game-file vendor prices are base prices; some vendors charge more (Black Market agents, for example). Those rows are flagged until ForeverMoneyBridge records the real price; items sold only by Black Market agents are left out until then.
- About a third of recipe skill requirements are estimated (yellow − 40). They're marked `~`.
- "Cheap relist" and "AH → vendor" rows come from one scan snapshot. Check them in game, or use TSM's Sniper.
- AH deposits for listings that don't sell are not included.
- Wowhead Forever zone counts mix open water and pools. Pool-only loot is set aside, but school fish that are also caught in open water (Oily Blackmouth, Firefin Snapper, Stonescale Eel) stay in, so open-water shares of those fish are slightly high.
- Coins inside containers aren't counted (Wowhead doesn't list them). Quest rewards aren't valued yet. Disenchanting is an estimate from a WoW Classic table (in the ForeverRecipes addon), labelled "Classic table" and never used for Top picks or the plan.

## Tests and audits

```bash
python -m unittest discover -s tests -t .
```

```bash
python -m wfm.audit
```

The tests check every calculation against hand-worked numbers, plus regressions for bugs found while building. The audit cross-checks the live data sources against each other. The farm meter's tests (`tests/test_meter_lua.py`) run the addon under Lua 5.1, WoW's Lua, and need `pip install lupa`; without it they are skipped.
