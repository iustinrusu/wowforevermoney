# Open work and decisions (the user's checklist)

Saved 2026-11-14 at the user's request: "remember this long list of todos and decisions, I will ask again and we need
to go through them all". When the user asks about it (what's left, the list, the decisions), go through **every**
item below in order: say where it stands, ask for each open decision, and tick off or update items here as they
are done or decided (with the date). Don't drop an item without the user's say.

## A. Work left on the top priority: Forever data for every material

Wowhead pace from 2026-11-15 (C3): one page every 2 minutes, at most 20 a session; at a 403 stop, then try one page after 30 minutes, 2 hours, the next day; after a second block, 5 a session (the exact reading order:
`docs/plans/material-coverage.md`, Progress section).

- [ ] A1. The rest of the top 100 coverage queue: 2 item pages left (Kingsblood 3356, Iridescent Pearl 5500; 20 read
      on 2026-11-15).
- [ ] A2. The 4 skinning items left: Black Whelp Scale (7286), Worn Dragonscale (8165), Green Dragonscale (15412),
      Chimera Leather (15423). Then "some skins not counted" goes away.
- [ ] A3. 26 fishing-pool object pages, debris and wreckage first (list in the plan, step 3). Answers whether floating
      debris is where most of the fishing gold is (the user's hunch).
- [ ] A4. Each herb and ore node's own page, so node values have no Classic parts left.
- [ ] A5. Mobs' own pages, so mob farming counts every drop (coins, gray items, gear), not only materials.
- [ ] A6. Re-read later the 22 pages where Wowhead had no Forever data yet (Data health lists them).
- [ ] A7. Javnir Nashak's Wowhead Forever page (Green Firework vendor, Durotar): always there, or only during an
      event? (moved from D3, 2026-11-15: Claude reads it in a reading session instead of asking the user)

## B. Work left that needs no Wowhead

- [x] B1. (done 2026-11-15) Review of the 2026-11-13/14 work (to-do item 6, `docs/plans/forever-data-next.md` section 6).
- [ ] B2. Strategy features (to-do item 7, `docs/plans/strategy-features.md`): profession advisor, levelling
      planner, niches first.
- [ ] B3. Not counted in profits yet: AH deposits and listings that don't sell; buying several of an ingredient
      (each costed at the lowest listing); recipe learning costs (shown, not subtracted).
- [ ] B4. Not valued yet: coins inside containers, disenchanting (the user has an Enchanting alt), quest-item
      rewards, lockboxes beyond their contents.
- [ ] B5. Pool catches: the addon records which pool a catch came from by itself (no fishing logged yet on
      2026-11-15). After the user next fishes, check the saved file has `pools` entries (moved from D3).
- [x] B6. (all three done 2026-11-15) The user's decisions of 2026-11-15, briefed in `docs/plans/decided-2026-11-15.md`: remove the character
      names from GitHub's history (C5: done 2026-11-15, history rewritten and force-pushed), crafted
      worth capped by what can be made a day (C7: done 2026-11-15), Everloot cross-check (C2: done 2026-11-15).

- [ ] B7. Comprehensive review of the whole app (UI, UX, logic, accuracy, no discrepancies between views): planned
      for a new chat after the usage reset, `docs/plans/comprehensive-review.md` (the user, 2026-11-15).

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

## D. Things only the user can do

- [-] D1. **The user won't send it (2026-11-15).** Was: send the Wowhead email (`docs/plans/wowhead-data-request.md`); a yes could replace the slow page reading.
- [-] D2. Dropped, not a to-do (the user, 2026-11-15). Was: restart their own app copy with start.bat (it replaces the one Claude started on port 8765).
- [x] D3. No to-do needed, the user /reloads often (2026-11-15). Vendor prices: checked in the saved file on
      2026-11-15, 23 vendors recorded with their prices. Pools: now B5. Javnir Nashak: now A7.
      Was: in game with ForeverMoneyBridge: visit a vendor then /reload (vendor prices recorded?); fish from a pool
      then /reload (does the game report which pool a catch came from?); is Javnir Nashak (Green Firework vendor,
      Durotar) always there or only during an event?
