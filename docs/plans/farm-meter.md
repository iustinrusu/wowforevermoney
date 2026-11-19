# Plan: farm meter in ForeverMoneyBridge (the user's request, 2026-11-15)

"Build into our addon if possible, but as long as all items are priced correctly." Postponed at 93% of the weekly
usage; do it in a new chat after the reset (after or alongside docs/plans/comprehensive-review.md). Claude can't run
WoW: the user tests in game; ask them for screenshots or the saved file after a session.

## The key point: prices must match the app exactly
**Superseded 2026-11-19 (the user: the addon should work standalone):** addon 1.6.0 prices with TSM in game by
default and the app's table only after `/gea prices app`; XP gained, an hour and the time to the next level were added.
See the project log, Decisions, 2026-11-19.

TSM's in-game price API alone would value items differently from the app (realm lowest listing vs walls and freak
sales, soulbound items, things that don't sell, crafted worth with its daily cap, containers' contents). So:
- The app writes a price table into the addon folder, the way it already writes Checks.lua
  (`profile.write_item_checks`): `addon/ForeverMoneyBridge/Prices.lua` in the WoW AddOns folder, generated after each
  recompute: item id -> copper per unit as the app values it (`Valuer.value`, the same as My bags), plus how it's
  valued (AH, vendor, open it, crafted) and the time it was written. Only items that can be looted (trade goods,
  fish, gear, containers, coins aside), to keep it small; check the size.
- WoW reads addon files only at login or /reload, so the table is as fresh as the last /reload: show its age in the
  meter, and fall back for items missing from it: TSM_API custom price "first(DBMinBuyout, DBMarket)" when TSM is
  loaded, else the vendor price (GetItemInfo's sellPrice), each labelled in the meter (so it's clear which prices
  are the app's).
- Raw gold looted counts as is.

## The meter
- Slash commands (the user, 2026-11-15): `/fmb start` starts a session and shows the window; `/fmb stop` ends the
  session (saved) and hides the window; `/fmb pause` / `/fmb resume`; `/fmb` alone prints the commands. The window
  only appears while a session runs.
- A small movable window (remembers its position; also Pause and Stop buttons): session time
  (only while running), gold looted, items looted and their value, total, and gold per hour; the top 5 items by value;
  a line saying which prices were used (app table age, TSM fallback count, vendor fallback count).
- Counts loot from LOOT_READY / CHAT_MSG_LOOT (the addon already logs loot; reuse it) and money from PLAYER_MONEY
  changes while a loot window is open (+1 s), as drafted on 2026-11-14 (no language-dependent text parsing).
- Kills, skins and fishing catches counted too, so a session can be compared with the app's estimate for that spot.
- Saves finished sessions in ForeverMoneyBridgeDB (zone, minutes, value, gold/hour) for the user to look back on.
- Fold (1.6.3, the user 2026-11-19: "collapse feature / minimize feature"): the "–" button at the far right of the
  title bar (or `/gea min`) folds the window to its 34-pixel title bar showing "total · gold an hour · time" (no copper
  once there is gold; ", paused" when paused); Pause and Stop hide with the rest, "+" opens it again. Saved as
  `ForeverMoneyBridgeDB.meter.collapsed`. The position is now saved as the top left corner (`{"TOPLEFT", x, y,
  "BOTTOMLEFT"}`): WoW had anchored the moved window at its bottom right corner, so folding would have moved the title
  bar. `/gea hide` / `/gea show` hide it completely; the session keeps counting either way. The open title is just
  "Gold Ever After" (the old "· farm meter" ran under the Pause button at the 260-pixel width); paused shows on the
  Time line.
- The app still never uses these sessions as farming rates (user's rule, 2026-11-14); it may show them on the
  Gathering tab as "your sessions" if the user wants.

## Tests
- Python: the price-table writer (format, item selection, values equal to Valuer.value, size).
- Lua: a small pure function for the session maths (value, gold/hour, fallbacks) that can be checked with a Lua
  interpreter if one is available; otherwise by hand with the user's first session.
- Bump the addon version (1.5.0) and note it in the project log; the app copies the addon into AddOns on start.

## Addon install and updates (checked 2026-11-15)
Already works: on every start the app copies each ForeverMoneyBridge file that differs into WoW's AddOns folder
(`profile.install_addon`, compares content, not only the version), and update-on-start pulls new addon code first, so
a new meter version reaches the game on the next app start plus a /reload. To add: remove files from the AddOns copy
that were deleted from the addon (none so far), and support subfolders if the meter adds any (copy2 on a folder
fails today).
