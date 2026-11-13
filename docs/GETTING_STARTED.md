# Getting started (for a friend setting it up)

WoW Forever Money is a small app that runs on your own PC and shows the best ways to make gold in WoW: Forever:
crafts, vendor flips, fishing spots, what's in your bags and more. It uses your TSM auction prices and your
characters' data. About 15 minutes the first time.

## 1. What you need

- **Windows** with **WoW: Forever** installed.
- **TradeSkillMaster (TSM):** the TSM addon in game *and* the TSM desktop app (tradeskillmaster.com),
  logged in and running. The app gets auction prices from it, about once an hour.
- **Python 3.13 or newer.** No need to install it first: if `start.bat` doesn't find it, it offers to install
  it for you (type Y). That uses winget, Windows' own app installer, and takes a minute or two. Then close the
  window and double-click `start.bat` again. Without winget, install it from python.org and tick
  "Add python.exe to PATH". (Typing `python` in a fresh Windows opens the Microsoft Store: that's only a
  shortcut, not Python.)

## 2. Get the app

The project is on GitHub (github.com/iustinrusu/wowforevermoney) and is private, so:
- **Either** ask Iustin to add your GitHub account as a collaborator. Then, on the repo page, click
  **Code > Download ZIP**.
- **Or** ask him for a ZIP of the folder.

Unzip it somewhere simple, for example `Documents\WoWForeverMoney`.

## 3. Start it

1. Double-click **`start.bat`** in that folder.
2. The first start takes 1-2 minutes: it installs one Python package and downloads the game's item tables.
   Then your browser opens **http://127.0.0.1:8765**.
3. Keep the black window open while you use the app; close it to stop the app. Starting it again always
   replaces an old copy, even a hidden one.

## 4. Turn on the addon in WoW

The app copies its addon, **ForeverMoneyBridge**, into your WoW AddOns folder every time it starts.
To install it without starting the app, double-click **`install_addon.bat`** in the app folder. It finds
WoW: Forever by itself; if it can't, it asks you to paste your "World of Warcraft" folder (the one with
`_forever_` inside, often `C:\Program Files (x86)\World of Warcraft`). You can also drag that folder onto
`install_addon.bat`. If WoW was open, restart it once so the new addon shows up.
1. At the character screen click **AddOns** and tick **ForeverMoneyBridge**. If it says "out of date", tick
   "Load out of date AddOns".
2. Log in and type `/reload`. Wait about a minute (the addon checks some item data with the game), then
   `/reload` again.
3. In the app's **Settings** tab you should see your character with level, gold and professions.
   - Pick **your realm** if it isn't selected.
   - Optionally list the professions you prefer.

## 5. Recommended addons

The app reads these if you have them (all on CurseForge):
- **QuestieDB:** which vendors sell what, and who drops what.
- **SkillUpForever:** exact recipe skill levels.
- **Syndicator:** your bags and bank (enables the My bags tab).
- **ForeverAngler:** your fishing log.

## 6. Everyday use

- Run the TSM desktop app and `start.bat`, then play.
- WoW only saves addon data when you **`/reload`** or log out, so `/reload` whenever you want the app to catch
  up (after fishing, farming, visiting vendors or opening trunks).
- Start with **Top picks**. Click any row to see the numbers, where they come from, and any warnings
  (the coloured labels: hover them).
- **Data health** shows whether every data source is fresh. A red or yellow dot means something needs
  attention, usually the TSM app not running.

## 7. If something's wrong

- **The page says "Lost connection":** the black window was closed. Start `start.bat` again.
- **Prices are old:** make sure the TSM desktop app is running and logged in.
- **Your character isn't detected:** check ForeverMoneyBridge is ticked in AddOns, then `/reload`.
- **`start.bat` says Python isn't installed right after installing it:** close the window and start it again.
- **Optional extra:** Classic fishing tables for zones with no Forever data yet. Run this once in the app
  folder (downloads ~13 MB):

  ```bash
  python -m wfm.classicdb --update
  ```

More detail on how every number is worked out: `README.md`.
