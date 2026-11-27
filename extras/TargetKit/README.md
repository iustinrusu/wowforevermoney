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

Revised:

> Make an addon, TargetKit, kept in the repo under `extras/` and never installed by the app. It creates three macros
> (one press = one action, as WoW requires):
>
> 1. **TK Find**: targets units from a find list I keep with `/tkit add <name>` (part of a name is enough; `/tkit add`
>    alone adds my target). Closest first; pressing again within a few seconds goes to the next closest until all
>    have been visited, then starts over. Dead mobs are skipped. Dead players count, and dead NPCs count when the game
>    shows them as friendly; a dead neutral or hostile unit could be a mob, so it is skipped. Units too far for a
>    nameplate, or dead ones without one, are found by name as a fallback.
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

## Using it

- WoW needs a **full restart** (not `/reload`) to see a new addon; then tick TargetKit in the AddOns list.
- The three macros appear under Escape > Macros, General tab: drag **TK Find**, **TK Pickpocket** and **TK Sap** to
  your bars. Each is `/click TargetKitFind` (or Pick, Sap), and the addon writes the real macro just before the click.
- `/tkit add <name>`, `/tkit remove <name>`, `/tkit list`, `/tkit clear`: the find list.
- `/tkit macros` makes the three macros again if you deleted them; `/tkit forget` clears whom you robbed;
  `/tkit debug` prints, on every press, what it chose and the macro it ran.
- Nameplates matter: the addon sees units through them (enemy nameplates for mobs and players, friendly ones for
  NPCs), plus your target, mouseover, soft targets, focus and group.

## Limits (the game's, not choices)

- No exact distances: range bands only (see above).
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
