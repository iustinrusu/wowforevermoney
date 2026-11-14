# Open work and decisions (the user's checklist)

Saved 2026-11-14 at the user's request: "remember this long list of todos and decisions, I will ask again and we need
to go through them all". When the user asks about it (what's left, the list, the decisions), go through **every**
item below in order: say where it stands, ask for each open decision, and tick off or update items here as they
are done or decided (with the date). Don't drop an item without the user's say.

## A. Work left on the top priority: Forever data for every material

Wowhead pace since the 403 of 2026-11-14: about 5 pages a session, 2 minutes apart (details and the exact reading
order: `docs/plans/material-coverage.md`, Progress section).

- [ ] A1. The rest of the top 100 coverage queue: 22 item pages, Moss Agate (1206) first.
- [ ] A2. The 4 skinning items left: Black Whelp Scale (7286), Worn Dragonscale (8165), Green Dragonscale (15412),
      Chimera Leather (15423). Then "some skins not counted" goes away.
- [ ] A3. 26 fishing-pool object pages, debris and wreckage first (list in the plan, step 3). Answers whether floating
      debris is where most of the fishing gold is (the user's hunch).
- [ ] A4. Each herb and ore node's own page, so node values have no Classic parts left.
- [ ] A5. Mobs' own pages, so mob farming counts every drop (coins, gray items, gear), not only materials.
- [ ] A6. Re-read later the 22 pages where Wowhead had no Forever data yet (Data health lists them).

## B. Work left that needs no Wowhead

- [ ] B1. Review of the 2026-11-13/14 work (to-do item 6, `docs/plans/forever-data-next.md` section 6).
- [ ] B2. Strategy features (to-do item 7, `docs/plans/strategy-features.md`): profession advisor, levelling
      planner, niches first.
- [ ] B3. Not counted in profits yet: AH deposits and listings that don't sell; buying several of an ingredient
      (each costed at the lowest listing); recipe learning costs (shown, not subtracted).
- [ ] B4. Not valued yet: coins inside containers, disenchanting (the user has an Enchanting alt), quest-item
      rewards, lockboxes beyond their contents.

## C. Decisions for the user

- [ ] C1. Dungeons view (the user's idea): **"not yet" (2026-11-14)**, ask again. Claude's view: yes for dungeons
      (Dark Rune and Righteous Orb, #1 and #4 of the missing materials by traded value, drop only in Scholomance and
      Stratholme), no for raids (loot shared by 20-40); needs bosses' own Wowhead pages.
- [ ] C2. Everloot as a second source: download its drop rates (4 small requests, about 200 KB, CC BY-SA data, kept
      in data/ uncommitted) to cross-check our rates?
- [ ] C3. Wowhead reading pace: stay at about 5 pages a session, or go back to one a minute until the next block
      (the first block lifted within 30 minutes)?
- [ ] C4. Forever loot addons and GatherLite node locations (to-do item 5): install any through CurseForge?
      GatherLite's node locations also need map tables downloaded (Claude asks with file name and size first).
- [ ] C5. The user's character name in the first commit (0b17b50): remove it from GitHub's history (needs a force
      push, which rewrites history) or leave it?
- [ ] C7. "Worth if crafted": count it only for as many as the product's market (your share) and cooldown take a day,
      the rest at the sale price? (asked 2026-11-14, not answered yet; the price checks list the 8 ingredients
      affected, e.g. Thorium Bar 21g 65s via Transmute: Arcanite for 1 every 2 days, sells for 17s.)
- [ ] C6. Settings assumptions: kills per hour (60), herb and ore nodes per hour (40 each), casts per hour, market
      share (20%): set to match the user's own play?

## D. Things only the user can do

- [ ] D1. Send the Wowhead email (`docs/plans/wowhead-data-request.md`); a yes could replace the slow page reading.
- [ ] D2. Restart their own app copy with start.bat (it replaces the one Claude started on port 8765).
- [ ] D3. In game with ForeverMoneyBridge: visit a vendor then /reload (vendor prices recorded?); fish from a pool
      then /reload (does the game report which pool a catch came from?); is Javnir Nashak (Green Firework vendor,
      Durotar) always there or only during an event?
