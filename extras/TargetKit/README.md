# TargetKit

Three one-key target helpers for WoW: Forever, each as a macro the addon makes for you. It's our own addon, kept in
this repo for later changes. It is **not part of the WoW Forever Money app**: the app only installs
`addon/ForeverMoneyBridge`, so TargetKit never reaches the app or anyone else's install.

## The request, revised (2026-11-27)

The user's words: "create a new addon that should not be included in the gea app, but should live in our repo for
further adjustments later maybe: the addon should have these three macros, one for targeting desired targets (to find
specific targets, npcs, players etc). should start with closest and cycle through available if possible. dead mobs
should be skipped, but dead players or npcs should count too (if mobs and npcs cant be differentiated, skip dead npcs
too). pickpocket macro should always target the closest pickpocketable target available and sap + pickpocket. pvp sap
macro should always target closest target available as closest as physically possible and sap (should work on both
npcs and enemy players, but enemy players should have priority), and if you can add mouseover interaction for simple
sap that would be awesome, but it's ok if you can't. revise the prompt". Then: "the pvp sap is especially needed for
sapping invisible targets, useful in battlegrounds against rogues for example" and "sap does not break stealth".
Later the same day: "maybe a minimap button would be nice too, for rebinding the macros (key combinations, key + key,
should be accepted), also an option to input the mob that should be targeted for the target macro would be nice, or
an option to set to current selected target would be nice too" and "being able to create a macro to /use_addon_target,
/use_addon_pickpocket, /use_addon_sap (command names are placeholders) would be nice, so I can have them on my action
bars".

Revised:

> Make an addon, TargetKit, kept in the repo under `extras/` and never installed by the app. It creates three macros
> (one press = one action, as WoW requires):
>
> 1. **TK Find**: targets units from a find list I keep with `/tkit add <name>` (part of a name is enough; `/tkit add`
>    alone adds my target). Closest first; pressing again within a few seconds goes to the next closest until all
>    have been visited, then starts over. Dead mobs are skipped. Dead players count, and dead NPCs count when the game
>    shows them as friendly; a dead neutral or hostile unit could be a mob, so it is skipped. Units too far for a
>    nameplate, or dead ones without one, are found by name as a fallback.
>    (1.4.3, what Forever allows: an addon can't target a unit by its nameplate, only by name, which gives the
>    closest of that name in any direction, or with the game's Tab, which only goes through what's in front of you
>    and fairly near, every enemy. 1.4.5, the user's call after trying Tab: "if it's too messy let's just drop
>    cycling". So TK Find only targets by name, so only what's on the list: the closest match; with one of them
>    targeted, the next name from the list that's in sight. Mobs that share a name: always the closest.)
> 2. **TK Pickpocket**: targets the closest humanoid I can rob (attackable, not a player, alive, not in combat, not
>    pickpocketed yet), then Sap and Pick Pocket in one press (Sap doesn't break stealth on Forever). If one of the
>    two was still on cooldown, the next press on that unit does the missing one; after that it moves on to the next
>    closest. Units already robbed are remembered for 2 hours.
> 3. **TK Sap** (for PvP, above all stealthed players in battlegrounds): my mouseover enemy first. Else the closest
>    enemy player in Sap range that isn't in combat; else the game's own nearest enemy player, which is the only way
>    to catch a stealthed player the game has just revealed (they have no nameplate, so no addon can see them); else
>    the closest NPC in Sap range; else the game's nearest enemy.
>
> Within WoW's rules: an addon can't choose a target by itself, and can't change a macro in combat. Sap and Pick Pocket
> are used out of combat anyway; in combat the macros fall back to the game's own targeting. "Closest" can only mean
> the nearest range band the game reports (Pick Pocket's range, Sap's, 10, 11, 28 yards, further); within a band, the
> unit whose nameplate is lower on the screen.
>
> 4. **A minimap button** opens a TargetKit window: a key for each macro (Set, then press it: one key with Shift, Ctrl
>    or Alt if I like, or mouse button 3 to 5, or the wheel; WoW can't bind two ordinary keys pressed together), and
>    the find list (type a name and press Enter, or **Add my target**; each name with Remove). Keys are kept through
>    relogs and don't overwrite my own bindings: clearing one gives the key back.
> 5. **On my bars:** the three macros. (Asked for: a line of my own for my own macros. Not possible since 1.4.0: an
>    addon's own slash command can't target or cast, and on Forever the game doesn't run a `/click` from a macro into
>    an addon's secure button, so the choice has to be in the TK macros themselves.)

## Using it

- WoW needs a **full restart** (not `/reload`) to see a new addon; then tick TargetKit in the AddOns list.
- **The window:** click the Sap icon on the minimap's edge (or type `/tkit`). Keys: click **Set** next to a macro and
  press the key (Shift-F, Ctrl-Alt-3, mouse button 4, Ctrl + wheel down...); **Clear** gives the key back. The key
  works while TargetKit is loaded and your own binding for it comes back when you clear it. Find list: type a name
  (part of one is enough) and press Enter, or **Add my target**; **Remove** takes one off; the wheel scrolls a long
  list. Drag the minimap button to move it; `/tkit minimap` hides it or brings it back.
- **How a press works (1.4.0):** out of combat TargetKit looks around five times a second and writes its choice
  into the three macros themselves ("/targetexact Name" and the spell), at most every 0.4 s
  while nothing is pressed, at once after a press so the next one gets the next unit, and not while the game's Macros
  window is open. A press runs what's written, with no addon code in between. Just before combat each macro gets its
  fixed text (the game's own targeting), since macros can't change in combat. Units seen only as your mouseover or a
  soft target (a friendly player with friendly nameplates off, say) are targeted by their exact name, because the
  mouse is somewhere else by the time you press. When TargetKit sees nobody from your list, TK Find targets by name
  ("/cleartarget", then "/target name" for each name, your first entry last so it wins); the game then takes the
  closest unit of that name, which can be a corpse. Each macro's last line clicks a marker button so
  the log sees the press (TK Sap's mouseover Sap ends its macro early, so that press shows only by its cast).
  Before 1.4.0 the macros held `/click TKFind` on a secure button that held the choice; the 1.3.0 log showed the game
  ran the macro's first line on every press but never that button's macro.
- **What Forever doesn't allow (1.4.2, from the log):** an addon can't ask a nameplate where it is on screen, so
  within one range band TargetKit goes round in a steady order instead of lowest-on-screen first (before 1.4.2 that
  refusal made every look fail: TK Find went "closest, none, closest", and failed whenever CorpseGlow lit a corpse,
  since that gives the corpse a nameplate). And within one press, a macro's [conditions] see the target you had
  before it, so the macros never put "/cleartarget" before a "[noexists]" line. TK Sap's lines, when it doesn't have
  an enemy player in Sap range in sight: no attackable target, the game's nearest enemy (or the NPC in Sap range
  TargetKit sees); then, unless you already target a living enemy player, the game's nearest enemy player, which wins
  if there is one; then Sap.
- **TK Sap and the closest enemy player (1.4.6):** an enemy player TargetKit sees in Sap range (by nameplate, or as
  your soft enemy target) is targeted by name and sapped, whoever you have targeted; players' names are unique, so
  it's exact. An enemy player you target who is further off than Sap's range isn't kept: the macro clears it (or
  takes the NPC in Sap range) and then the game's nearest enemy player. The macro is rewritten at once when the
  enemy player to Sap changes, and TargetKit looks again as soon as a nameplate appears or your soft enemy target
  changes, instead of waiting up to 0.4 s. What no addon can do: Sap a stealthed player the game shows you no
  nameplate or soft target for; your mouse over him still works (the mouseover Sap line comes first).
- **On your bars:** the three macros are under Escape > Macros, General tab: drag **TK Find**, **TK Pickpocket** and
  **TK Sap** to your bars and leave their text as it is (TargetKit rewrites it). A key set in the window runs the same
  macro, so it works without the macro being on a bar.
- `/tkit add <name>`, `/tkit remove <name>`, `/tkit list`, `/tkit clear`: the find list from chat.
- **The log**, always on: every press (which macro, every unit it saw and why it took or passed over each, the macro it
  ran), what came of it in the next 2 seconds (the game's error line such as "Out of range.", the cast, the new
  target), the game settings that matter at login (act on key down, nameplates, soft targeting), the macros and keys
  it made (each key checked to really run the macro), anything the game blocked, and every error with where. Since 1.2.1 each press also records what the game itself ran for it (its targeting and casting
  functions, watched without getting in the way) and where your target went. Since 1.4.0: when a macro chose a unit
  and your target isn't that unit 0.3 s later, the log says so ("chose a target, but the game didn't target it");
  the first write of each macro in a session is logged, and a warning if the game keeps a
  different text than was written, and TK Find notes when nobody on your list is near enough.
- **Chat stays quiet (1.4.1):** what TargetKit notices by itself (nobody near, warnings, errors, the macros made) goes
  to the log only. `/tkit chat` shows it in chat too (kept through relogs; `/tkit chat` again turns it off). Answers
  to what you type (`/tkit list`, `/tkit add`, `/tkit log`, `/tkit help`) still show in chat, and what you do in the
  window shows on its bottom line.
  `/tkit log` shows the last 15 lines (`/tkit log 40`, `/tkit log clear`); the last 400 are kept
  in the saved file, written on `/reload` or logout. When something doesn't work, `/reload` and say so.
- `/tkit macros` makes the three macros again if you deleted them; `/tkit forget`
  clears whom you robbed; `/tkit debug` prints, on every press, what it chose and the macro it ran (off after every
  `/reload`); `/tkit chat` (above); `/tkit help`.
- Nameplates matter: the addon sees units through them (enemy nameplates for mobs and players, friendly ones for
  NPCs), plus your target, mouseover, soft targets, focus and group. It can't target through them: Forever refuses
  "/target nameplateN" in a macro (1.4.3), so every choice is written by name, and the game takes the closest unit
  of that name, in any direction, nameplate showing or not. So TK Find can't go round mobs that share a name: it
  takes the closest one. With several names on your list, each press goes to the next name in sight. (1.4.3 and
  1.4.4 went round same-named mobs with the game's Tab, but Tab goes through every enemy in front of you whose
  nameplate shows, so it landed on other mobs and missed ones behind you; 1.4.5 dropped it.)

## Limits (the game's, not choices)

- No exact distances: range bands only (see above).
- Keys: one key with Shift, Ctrl, Alt, or a mouse button or the wheel; two ordinary keys together can't be bound.
  Keys can't change in combat.
- An addon's own slash command can't target or cast, and a macro can't change in combat: in combat the macros hold
  the game's own targeting. A macro is at most 255 characters, so a long find list is cut to the names that fit.
- A macro of your own can't run TK Find's choice (no `/click` into an addon's secure button runs on Forever, and the
  game doesn't run a macro from inside another): use the TK macros, or keys.
- A stealthed player is invisible to addons until the game reveals them, and even then has no nameplate. TK Sap
  hands that case to the game's own nearest-enemy-player targeting, which does see them.
- Sap and Pick Pocket on Forever: Sap doesn't break stealth (the user, 2026-11-27). Whether Pick Pocket shares the
  global cooldown isn't checked; the "next press does the missing one" rule covers both cases.

## Tests

`python -m unittest tests.test_targetkit_lua` (Lua 5.1 through lupa; `tests/targetkit_harness.lua` stands in for WoW).

## Install or update

Copy this folder into WoW's AddOns folder (the app doesn't):

```powershell
Copy-Item -Recurse -Force extras\TargetKit "C:\Games\World of Warcraft\_forever_\Interface\AddOns\"
```
