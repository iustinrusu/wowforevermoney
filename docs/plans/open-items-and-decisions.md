# Open work and decisions (the user's checklist)

Saved 2026-11-14 at the user's request: "remember this long list of todos and decisions, I will ask again and we need
to go through them all". When the user asks about it (what's left, the list, the decisions), go through **every**
item below in order: say where it stands, ask for each open decision, and tick off or update items here as they
are done or decided (with the date). Don't drop an item without the user's say.

## A. Work left on the top priority: Forever data for every material

Wowhead pace from 2026-11-15 (C3): one page every 2 minutes, at most 20 a session; at a 403 stop, then try one page after 30 minutes, 2 hours, the next day; after a second block, 5 a session (the exact reading order:
`docs/plans/material-coverage.md`, Progress section).

- [ ] A0. (2026-11-27: 3 more read, the vendors behind the biggest "stock unknown" flips: Mazk Snipeshot sells
      Bronze Tube 2 a restock (14 vendors sell it; the other 13 still unread), Jolee Brightmeadows and Jyn Stonehoof
      sell everything without a limit. Fizzlefuse re-read: all 29 items cost Merchant's Favor (currency 3402), 45-1,000
      each. The reader now reads the stock right (`avail`) and how many one purchase gives (Light Shot: 200).
      All stock-unknown flips together are worth about 14g a day, so further vendor pages are low priority. Next if
      wanted: Blacksmith Rand / Bronk Steelrage / Rarc (Rusted Chain gear), Nerrist or Keena (Recipe: Curiously Tasty
      Omelet).)
      (2026-11-20: 9 vendors read: Borya, Kania, Wizzle Brassbolts, Kor'gar, Vi'el, Fizzlefuse, Kelsey Yance,
      Aurian Highgrove, Nixxrax Fillamug. Borya doesn't sell Pattern: Invoker's Cord in Forever (QuestieDB's 46g-a-day
      flip was a phantom); Wizzle doesn't sell Copper Modulator, Kor'gar does, 2 a restock; Fizzlefuse's schematics
      cost a currency, not gold. The app now trusts a read vendor page over QuestieDB. Next, by profit at stake: the Hand
      Axe weapon vendors (Jyn Stonehoof, Urtharo, ...), Yaelika Farclaw, Timothy Weldon; re-read Fizzlefuse with the
      fixed reader to see the currency.) **First in the next Wowhead session (the user, 2026-11-15: "Wowhead always has more accurate data"):** vendor
      stock from Wowhead Forever NPC pages ("Sells" tab, Stock column: a number = limited, ∞ = unlimited) for the vendors
      behind vendor flips flagged "stock unknown", most profitable first (Wizzle Brassbolts and Kor'gar for Copper
      Modulator first). Store per npc and item like the addon's records; the engine already caps by stock.
- [x] A1. (done 2026-11-20) The rest of the top 100 coverage queue: 2 item pages left (Kingsblood 3356, Iridescent
      Pearl 5500; 20 read on 2026-11-15).
- [x] A2. (done 2026-11-20: "some skins not counted" is gone from all 40 skinning spots) The 4 skinning items left:
      Black Whelp Scale (7286), Worn Dragonscale (8165), Green Dragonscale (15412), Chimera Leather (15423).
- [ ] A3. (2026-11-27: paused. Wowhead has recorded no Forever loot for pools yet: Floating Debris 180655, Oily
      Blackmouth School 180582 and the Forever-only Fresh Wreckage 630533 have no Contains tab; Strange Debris 693670
      holds only a quest item. Re-check one pool page in a later session; the rest of the list waits until one has
      data. Meanwhile the addon records pool catches itself: B5.)
      26 fishing-pool object pages, debris and wreckage first (list in the plan, step 3). Answers whether floating
      debris is where most of the fishing gold is (the user's hunch).
- [ ] A4. Each herb and ore node's own page, so node values have no Classic parts left.
- [ ] A5. Mobs' own pages, so mob farming counts every drop (coins, gray items, gear), not only materials.
      (2026-11-20 review, `docs/plans/mob-farming-review.md`: Toxic Horror is 17th of 554 open-world mobs by Classic
      value a kill; a 20-page reading list for the candidates: Tanaris air elementals for Breath of Wind, Silithus
      Essence of Air, Eastern Plaguelands Essence of Undeath, recipe drops such as Crusader. Read the same evening:
      20 pages, 10 mobs' own pages with their coins and health; results in the review's Progress.)
- [x] A8. (done 2026-11-20: market limit and kill speed by health, `docs/plans/mob-farming-review.md`) Market limit on farmed loot: count at the AH price only your share of
      the realm's daily sales for an hour's loot, the rest at the vendor price (Breath of Wind: about 50 an hour, your
      share 9.9 a day). And kill speed from each mob's health and level instead of one pace for all.
- [ ] A6. Re-read later the 22 pages where Wowhead had no Forever data yet (Data health lists them).
- [x] A7. (done 2026-11-27: only during the Harvest Festival. His Forever page's one quest, Honoring a Hero, is in
      Wowhead's Harvest Festival category, and its comment says he appears then; his fireworks now count as an event
      vendor's.) Javnir Nashak's Wowhead Forever page (Green Firework vendor, Durotar): always there, or only during an
      event? (moved from D3, 2026-11-15: Claude reads it in a reading session instead of asking the user)

## B. Work left that needs no Wowhead

- [x] B1. (done 2026-11-15) Review of the 2026-11-13/14 work (to-do item 6, `docs/plans/forever-data-next.md` section 6).
- [ ] B2. (2026-11-20: 1, 2, 3 and 10 done on 2026-11-15; left 4-9: phase tracker, peak-and-fade items, recipe
      finder (partly there: every recipe's sources), alt planner, raid-week rhythm, demand trends; to-do C3)
      Strategy features (to-do item 7, `docs/plans/strategy-features.md`): profession advisor, levelling
      planner, niches first.
- [ ] B3. Not counted in profits yet: AH deposits and listings that don't sell; buying several of an ingredient
      (each costed at the lowest listing); recipe learning costs (shown, not subtracted).
- [ ] B4. Not valued yet: coins inside containers, quest-item
      rewards, lockboxes beyond their contents.
- [ ] B5. (2026-11-20: checked the saved file again: still no fishing logged, so nothing to check yet.) Pool
      catches: the addon records which pool a catch came from by itself (no fishing logged yet on
      2026-11-15). After the user next fishes, check the saved file has `pools` entries (moved from D3).
- [x] B6. (all three done 2026-11-15) The user's decisions of 2026-11-15, briefed in `docs/plans/decided-2026-11-15.md`: remove the character
      names from GitHub's history (C5: done 2026-11-15, history rewritten and force-pushed), crafted
      worth capped by what can be made a day (C7: done 2026-11-15), Everloot cross-check (C2: done 2026-11-15).

- [x] B7. (done 2026-11-20, to-do B1: report in docs/plans/comprehensive-review.md) Comprehensive review of the whole app (UI, UX, logic, accuracy, no discrepancies between views): planned
      for a new chat after the usage reset, `docs/plans/comprehensive-review.md` (the user, 2026-11-15).

- [x] B8. (Done 2026-11-27, addon 1.6.10: three Heavy Junkboxes counted, items and coins, the user: "looks ok now";
      the minimap button, the fold and a container as "not opened yet" without the app work too, the user: "the
      checklist items that you mentioned are unchecked are actually working". Addon 1.6.9:
      everything is logged now; after any test, `/reload` and Claude reads
      ForeverMoneyBridgeDB.log. Addon 1.6.8: after `/reload` a gold coin sits on the minimap's edge (left, a little low). Click
      it: the command list opens toward the middle of the screen; drag the coin and `/reload`: it stays where you put
      it. Addon 1.6.7: `/reload`, `/gea debug` says "Gold Ever After 1.6.7 debug on". Open a box: chat
      says "box opened into your bags: item N gave ..." and the window's Items and "Opened" go up. Two coin loots
      in quick succession: both count under Gold looted. If a box gives coins, check Gold looted goes up too (coins
      count from their "You loot" line; a box that gives coins with no line would be missed).
      Earlier: the user's first try ("still not working after opening heavy junkbox") ran on 1.6.3, since the app
      hadn't run since 26 Nov; on 1.6.6 the box's reminder went but its contents didn't count, which showed boxes
      open straight into the bags.
      Addon 1.6.4: open a lockbox, junkbox or clam with `/gea debug` on during a session; chat says
      "loot window: containers from item N (found by source / used / locked)", or "(which box: not found)". A screenshot
      of that line tells which way works on Forever since the 25 Nov patch; then /gea stop, /reload, and the loot log's
      containers should list it. Addon 1.6.5: with a session running, /reload; chat says "carried on with your session
      (N min so far)" and the window shows the same total and time.)
      (2026-11-20: the saved file shows XP and loot counted: a meter session in Maraudon that ended 2026-11-19
      23:45 saved 47,609 XP, 1g 48s 69c in coins and its loot (8g 10s 12c in all). Left: the fold, never used yet (no
      folded state saved), a screenshot folded and open; a container as "not opened yet" without the app.)
      (2026-11-19) Farm meter 1.6.x in game: XP line, prices (the app's while under 12 h old, else TSM), a
      container from a mob or fishing shown as "not opened yet" without the app. Claude can't run WoW: a screenshot.
      Same login: addon 1.6.2 saves TSM's vendor prices about 30 s after login (then /reload); Data health shows them.
      Done 2026-11-19: TSM's vendor prices saved (22,265 sell, 87 buy); the XP line and "Prices: the app's, from 2.0 h
      ago" show (the user's screenshot, nothing looted yet). Left: XP and loot counted after a few kills; a container
      as "not opened yet" without the app; addon 1.6.3's fold ("–" at the top right or /gea min: a screenshot folded
      and open, and that the window doesn't jump when folding).
- [ ] B14. (2026-11-27 evening, TargetKit 1.5.6, our extra addon.) Done: TK Find (friendly players; same-named mobs:
      the closest, the user's choice), TK Sap in battlegrounds (the user: "sap working correctly"; stealthed players
      first, 1.5.3). Left: TK Pickpocket in the open world and a dungeon (the closest robbable humanoid, a camp of one
      name, walking past a group); whether dungeons hide mob names like Alterac Valley (the log says "the game hides");
      TK Find on a name typed in Alterac Valley ("Irondeep Trogg": does the game take it?); TK Sap on mobs outside
      battlegrounds (1.5.5). After each, `/reload` and Claude reads TargetKitDB.log.
      Earlier notes: (2026-11-27, TargetKit 1.4.x) Done for TK Find (2026-11-27: a friendly player targeted
      every press, the log shows it). Left: TK Find on enemy mobs that share a name (put one on the list, stand near
      three or more, press TK Find a few times within 8 s: each press should take the next one; 1.4.1 failed here,
      1.4.2 found the game refuses nameplate lines; 1.4.3/1.4.4 went round with the game's Tab, which landed on
      other mobs; 1.4.5, the user's call: no cycling of same-named mobs, the closest by name, the next list name
      in sight on each press); TK Sap (1.4.6: with a farther enemy player targeted, a rogue appearing next to you
      should be taken; check in a battleground or duel area; 1.4.8: in battlegrounds every press is the game's
      nearest enemy player from scratch, the game hides enemies from addons there) and TK Pickpocket (1.4.7: walking past a group
      stealthed, each press should take the one next to you, never the one behind; a camp of one name too) and TK
      Pickpocket once out of combat. Then `/reload` and Claude reads TargetKitDB.log (chat stays quiet since 1.4.1;
      `/tkit chat` shows TargetKit's notes in chat). Same-named friendly NPCs only ever get the closest (no friendly
      nameplates): the user's choice, enemies matter more.
- [x] B11. (done 2026-11-19: every recipe with where to learn it, then rank training in to-do A3) Levelling paths
      stop where the next patterns only drop (Leatherworking at 270): use ForeverRecipes' pattern sellers and drop
      chances, and rank training fees (TODO 1d).
- [x] B12. (done 2026-11-19, to-do A4) Compare TSM's vendor prices with the game files once they arrive; check every
      priced item in game, not only 800 a login (TODO 1f). Decided: not every item. TSM gives a vendor price for every
      item but 15 and matches your client on 2,966 of 2,969, so the 800 checks a login go where TSM and the game files
      disagree (1,471 on 2026-11-19: two logins), and to checks TSM now disagrees with that are 3+ days old.
- [ ] B13. (2026-11-19) Rank training fees in the levelling path (Journeyman, Expert, Artisan) come from SkillUpForever's
      tables, which take them from the WoW Classic database (CMaNGOS classic-db, before reputation discounts), as do
      the recipe trainer fees it lists: labelled "Classic database", not Forever fact. Next time you train a rank or a
      recipe, tell Claude what the trainer asked for (or send a screenshot of the trainer window). If it differs,
      Claude can make the addon read the trainer window, so the fees become Forever data.
- [ ] B9. (2026-11-20: all 4 pages read. Mote of Unstable Magic: 60 Forever mobs, 68 new mob farming rows, mostly
      dungeon bosses; best open-world: Blackmaw Devotee in Blackmaw Hold. Shellfish: only from Shellfish Traps in
      Desolace, 84% of openings (1-2 each); the app has no row for opening objects like that yet. Pristine Black
      Diamond: a rare world drop in Forever (1 in 200-1,200 kills). Vulture Gizzard: one Forever mob, 27% of kills.
      Left: a farming row for objects such as the Shellfish Trap.) (2026-11-19) Big markets the app has no way into (Market tab, "only items the app has no way into"): Mote of
      Unstable Magic (215 kinds of mob drop it, 390g traded a day), Shellfish, Pristine Black Diamond, Vulture
      Gizzard; dungeon gear and patterns belong to the Dungeons view (to-do 8). Each needs its Wowhead Forever page
      (Wowhead budget) to become a farming row.
- [ ] B10. (2026-11-27: the Philosopher's Stone page read. It is the tool for 16 spells: the alchemy transmutes, Flask
      of Petrification, Refined Scale of Onyxia, the Forever-only Transmute: Legionite (Alchemy 275, from a drop) and
      Transmute: Red Power Crystal to Blue Power Crystal, the one with no profession, skill or source at all. The stone
      binds when picked up and alchemists make it at 225, so it is probably an alchemist's spell, but nothing says how
      it is learned. Data health "Item interactions" now says this on the Power Crystal rows. Still open: only someone
      in game can tell (an alchemist with a Philosopher's Stone: is it in the spellbook or the Alchemy window?).)
      (2026-11-20: spell 1289305 read. "Transmute: Red Power Crystal to Blue Power Crystal": 2-second cast,
      tool Philosopher's Stone, 1 Red Power Crystal makes 1 Blue. Wowhead lists no profession skill and nothing that
      teaches it, so who can cast it is still open; the Philosopher's Stone's own page is the next one to read.)
      (2026-11-19) Power Crystal transmutations (Forever-only spells 1289305, 1308151-1308225: 5 crystals of one
      colour into 5 of another; Red sells for 14s, Green 2s): the game data has no player source. Read one spell's
      Wowhead Forever page to find who or what casts them (an object in Un'Goro?); if players can, they are a flip.
      Data health "Item interactions" lists them.

## C. Decisions for the user

- [x] C1. **Decided 2026-11-15: build it, at a lower priority** (to-do 8, after the strategy features).
      Was "not yet" (2026-11-14). Claude's view: yes for dungeons
      (Dark Rune and Righteous Orb, #1 and #4 of the missing materials by traded value, drop only in Scholomance and
      Stratholme), no for raids (loot shared by 20-40); needs bosses' own Wowhead pages.
- [x] C2. **Decided 2026-11-15: yes** (to-do 2c; the download approved as described). Everloot as a second source: download its drop rates (4 small requests, about 200 KB, CC BY-SA data, kept
      in data/ uncommitted) to cross-check our rates?
- [x] C3. **Decided 2026-11-15 by Claude (the user: "it's up to you", based on how Wowhead went):** one page every 2 minutes, at most 20 a session; at a 403 stop, then try one page after 30 minutes, 2 hours, the next day; after a second block, 5 a session.
      Why: the one block came after 76 pages in a row at one a minute; 5 pages 2 minutes apart after it went
      fine. Half that rate, and a quarter of that run per session, should stay clear of it. The ~53 pages left
      (22 items, 4 skins, 26 pools, Javnir Nashak) take about 3 sessions.
- [x] C4. **Decided 2026-11-15:** GatherLite's data could be useful (to-do 5: its node locations), and keep an open
      mind to new addons: recommend any good Forever addon found (the user installs it through CurseForge). At
      first that day: "if we can get by with just Wowhead data, let's not add more addons". Was: Forever loot addons and GatherLite node locations (to-do item 5): install any through CurseForge?
      GatherLite's node locations also need map tables downloaded (Claude asks with file name and size first).
- [x] C5. **Decided 2026-11-15: yes, remove it** ("let's make it more secure"; force push approved): to-do 2a.
      Was: the user's character name in the first commit (0b17b50, now 73e3f39 after the rewrite): remove it from GitHub's history (needs a force
      push, which rewrites history) or leave it?
- [x] C7. **Decided 2026-11-15: yes, Claude's recommendation** (to-do 2b). "Worth if crafted": count it only for as many as the product's market (your share) and cooldown take a day,
      the rest at the sale price? (asked 2026-11-14, not answered yet; the price checks list the 8 ingredients
      affected, e.g. Thorium Bar 21g 65s via Transmute: Arcanite for 1 every 2 days, sells for 17s.)
- [x] C6. **Decided 2026-11-15: keep Claude's educated guesses**, the current defaults: 60 kills an hour, 40 herb
      and 40 ore nodes an hour, 240 fishing casts an hour, 20% of a realm's daily sales. The user can still change
      them in Settings. Was: set to match the user's own play?

- [x] C8. **Decided 2026-11-15: Claude's recommendation** (built: flag `everloot`). Was: may Everloot fill gaps where Wowhead Forever has no data? The cross-check (Data
      health) found the 10 pairs with 30+ loots on both sides all agree within chance (median ratio 1.04), but Everloot's
      small samples lean high (19 of 24 higher, median 1.63x: a rate only exists once the item dropped). Claude's
      recommendation: yes, only from rates with 30+ loot windows, labelled "Everloot", kept out of Top picks until a
      Wowhead Forever page confirms them; never from smaller samples.

- [x] C9. **Decided 2026-11-15: yes** (the user: "I approve downloads too", for downloads in general). Was: download two map tables for GatherLite's node positions? UiMap.csv and
      UiMapAssignment.csv from wago.tools (build 1.60.1.70938; no size given by the server, estimate well under 1 MB
      together). They turn GatherLite's map ids into zones. GatherLite has positions QuestieDB lacks (fishing pools:
      Oily Blackmouth, Firefin Snapper, Sagefish; 10x more chests; 2-4x more of some herbs). Claude's recommendation:
      yes, but it is a small gain (node weights per zone, where pools are), after the pool pages are read.

- [x] C10. **Decided 2026-11-19: yes, labelled** (built the same day: item details, My bags, "craft and disenchant it"
      rows; flag `classic_disenchant`, out of Top picks and the plan). Was: **Disenchanting values.** The app doesn't value disenchanting (your Enchanting alt; the
      Biggest markets list has Large Brilliant Shard at 389g traded a day). ForeverRecipes ships disenchant tables
      (by item level, quality and armor/weapon), but they are Classic reference data that its own author calls
      provisional estimates. Claude's recommendation: use them as a labelled fallback ("Classic disenchant table"),
      for My bags ("disenchant it" next to vendor and AH) and craft-to-disenchant rows, kept out of Top picks until
      Forever data confirms them (as with the Classic fishing tables). Or wait for a Forever source.

## D. Things only the user can do

- [-] D1. **The user won't send it (2026-11-15).** Was: send the Wowhead email (`docs/plans/wowhead-data-request.md`); a yes could replace the slow page reading.
- [-] D2. Dropped, not a to-do (the user, 2026-11-15). Was: restart their own app copy with start.bat (it replaces the one Claude started on port 8765).
- [x] D3. No to-do needed, the user /reloads often (2026-11-15). Vendor prices: checked in the saved file on
      2026-11-15, 23 vendors recorded with their prices. Pools: now B5. Javnir Nashak: now A7.
      Was: in game with ForeverMoneyBridge: visit a vendor then /reload (vendor prices recorded?); fish from a pool
      then /reload (does the game report which pool a catch came from?); is Javnir Nashak (Green Firework vendor,
      Durotar) always there or only during an event?
