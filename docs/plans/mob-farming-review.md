# Mob farming review (2026-11-20, the user: "double check that the current mob farming ranking is accurate and profits are precise, then look for any missing data, because I have a feeling farming toxic horrors in felwood is not the best mob farm in the game")

## What was checked
- **The math is right as designed.** A mob row = for each drop, Wowhead Forever's count / times looted x the stack
  size x what one is worth (the app's value, never above the buy price since 2026-11-20), plus the skin if you can
  skin it; gold an hour = that x the kills-per-hour setting (60). Recomputed by hand for the top rows: Toxic Horror,
  Essence of Water 17 of 129 loots (13.2%) x 3g 79s 98c = 50s 08c a kill, x 60 = 30g 05s an hour. Same for Entropic
  Beast, Entropic Horror, Diseased Black Bear (skin 19s 20c), Angerclaw Grizzly.
- **The ranking is sound.** Hourly Top picks only take mobs you can do now (level), backed by Forever data, with a
  solid sample, not elite or dungeon; each is scored by gold an hour x how sure the data is. 880 mob rows (177 dungeon,
  320 elite, 660 doable now).

## What is missing (why Toxic Horror probably isn't the best)
1. **Every mob row is a floor.** All 880 count only the drops whose *item* pages were read ("Dropped by" tabs of the
   traded materials in the coverage queue). No mob's own page has been read, so grey items, coins, gear, recipes and
   materials outside the queue are missing. Mobs that drop none of the read items have no row at all.
2. **Coins and grey items.** From the WoW Classic database (cMaNGOS 1.12, labelled, not Forever data): a level 50-60
   humanoid drops a median of 1s 30c in coins, and greys add about 4s a kill. Beasts and most elementals drop no coins
   (Toxic Horror: none). So coins and greys add about 3g an hour for humanoids: they don't decide the ranking.
3. **Kill speed is the same for every mob** (the 60 kills an hour setting). A level 45 elemental with 2,100 health
   dies much faster for a level 51 than a level 54 Toxic Horror with 3,240.
4. **No market limit on farmed loot.** An hour of farming assumes everything sells at today's lowest listing. Fine
   for Toxic Horror (7.9 Essences of Water an hour; your share of the realm's sales is 13.4 a day), wrong for Breath of
   Wind (about 50 an hour from Tanaris elementals; your share is 9.9 a day).

## Candidates the Classic tables point to (value per kill at today's prices; Classic rates, not Forever)
Toxic Horror is 17th of 554 open-world, non-elite mobs level 45+ by Classic value a kill (43s; Forever data says 50s),
21st per 1,000 health. Above it, among others:

| Mob | Zone, level | Classic value a kill | Mostly from | Forever data now |
|---|---|---|---|---|
| Scarlet Spellbinder | Western Plaguelands 57-58 | 2g 43s | Formula: Enchant Weapon - Crusader (0.7%, 293g; sells 0.3 a day in the region) | 3s 78c (Runecloth only) |
| Dark Caster | Eastern Plaguelands 56-57 | 1g 36s | Pattern: Wizardweave Turban (2%, 41g) | no row |
| Shadowmage, Dark Adept | Eastern Plaguelands 58-60 | 1g 15s-1g 18s | Recipe: Greater Shadow Protection Potion (1.9%, 47g) | no row |
| Deadwind Warlock | Deadwind Pass 57-58 | 92s | Formula: Enchant Bracer - Superior Strength (77g) | no row |
| Arkkoran Oracle | Azshara 54-55 | 89s | Pattern: Stormshroud Armor (35g) | no row |
| Gusting Vortex | Tanaris 43-45 | 86s | Breath of Wind (84% a kill, 95s) | no row |
| Whirling Invader, Cyclone Warrior | Silithus 57-59 | 76s-78s | Essence of Air (12%, 4g 61s) | no row |
| Living Storm | Tanaris 47-49 | 74s | Breath of Wind (67%) | no row |
| Scourge Warder | Eastern Plaguelands 55-56 | 57s | Essence of Undeath (85%, 44s) | no row |

The recipe drops are lotteries (a rare drop worth a lot, selling less than once a day). For a level 51, Tanaris air
elementals (Gusting Vortex, Living Storm) look strongest, but the realm only takes about 10 Breaths of Wind a day at
your share, so an hour of them would flood it (point 4).

## Progress
- **2026-11-20 Reading session done (step 1, 20 pages, no block).** The user: "Reading session first", then "maybe
  start with reading high interest, high level items and mobs first" (the order was changed to that). What Forever
  says, with each mob's own page now counting every drop and its coins:

  | Mob | Gold an hour (60 kills) | From | Sample |
  |---|---|---|---|
  | Arkkoran Oracle, Azshara 54-55 | 221g | Pattern: Stormshroud Armor 3 of 29 loots (34g) | tiny |
  | Dark Caster, Eastern Plaguelands 56-57 | 140g | Pattern: Wizardweave Turban 2 of 37 (42g) | tiny |
  | Scarlet Spellbinder, Western Plaguelands 57-58 | 101g | Crusader formula 5 of 955 (0.52%, 293g); Runecloth | solid |
  | Deadwind Warlock, Deadwind Pass 57-58 | 83g | Superior Strength formula 2 of 160 (77g), EZ-Thro Shell schematic | fair |
  | Gusting Vortex, Tanaris 43-45 | 53g | Breath of Wind 33 of 41 (80%), Elemental Air | small |
  | Toxic Horror, Felwood 53-54 | 36g | Essence of Water 85 of 617 (13.8%) and the rest of its loot | solid |

  The recipe drops sell less than once a day in the whole region (Crusader 0.3, Stormshroud 0.4): without a market
  limit (step 2) these rows promise gold nobody would pay. Coins from the pages' Quick Facts ("Worth"): about 5s a
  kill for the level 55-60 humanoids (Classic table: about 1s 30c), none for elementals. Scourge Warder drops no
  Essence of Undeath in Forever (Classic: 85% a kill); in Forever it comes mostly from Stratholme and Scholomance.
  Elemental Air's lowest listing jumped to 1g 20s (16:23) and 70s (17:23) while it sells for about 22s, which lifts
  the Desolace and Thousand Needles air elementals for now: step 2 should value an hour's loot at what it sells for.

- **2026-11-20 Market limit built (step 2; the user: "let's not forget about the other two gaps").** An hour's loot
  goes to the best way first, each only as far as it takes them in a day (`valuation.Valuer.lanes`, `unit_worth`):
  crafting as many as the recipe uses, the AH your share of the region's daily sales, the rest at a vendor's price.
  And a lowest listing 3x or more above what the item sells for counts at the sale price (`ah_price_doubtful` now
  includes `listed_far_above_sales`): Breath of Wind was listed at 98s 99c but sells for 9s 50c (realm average
  14s 48c). Result: 202 of 1,437 farming rows changed. Arkkoran Oracle 221g -> 11g an hour, Scarlet Spellbinder 101g
  -> 25g, Deadwind Warlock 83g -> 13g, the Desolace and Thousand Needles air elementals about 27g -> 6g, Gusting
  Vortex 12g -> 6g. Toxic Horror stays at about 35g an hour and is the best open-world mob farm the app has Forever
  data for; the hourly Top picks are Toxic Horror, Entropic Horror, Entropic Beast, Diseased Black Bear, Angerclaw
  Grizzly. Bags and the farm meter are unchanged (they value what you hold, not an hour a day).

- **2026-11-20 Kill speed built (step 3).** The kills-per-hour setting is for a typical normal mob of your level;
  each mob's pace = setting x typical health at your level / its health, between 0.5x and 1.5x (`Engine.kill_pace`).
  Its health: its Wowhead Forever page (Quick Facts) where read, else the typical health at its level (`MOB_HEALTH`,
  the median normal mob of the WoW Classic database, labelled a Classic rule; it matches Forever where a page shows
  health). A mob above your reach is paced at the level it needs (its "needs level" note). Final ranking, open world:
  Toxic Horror 32g an hour (54 kills: 3,293 health), Scarlet Spellbinder about 28g once you are 55+, Rock Stalker and
  Desert Rumbler (Silithus, small samples) 22-23g, Entropic Horror 15g. **Answer to the user's question: with Forever
  data, realistic prices and the market limit, Toxic Horror is the best open-world mob farm the app knows of.** Still
  open: mobs whose own page isn't read (most rows are a floor), and a reading queue ranked by gold at stake and level.

## Proposed next steps (the user decides)
1. **Wowhead reading session, 20 pages** (pace in CLAUDE.md): item pages Breath of Wind (7081), Essence of Undeath
   (12808), Elemental Air (7069), Globe of Water (7079), Formula: Enchant Weapon - Crusader (16252), Pattern:
   Wizardweave Turban (14505), Recipe: Greater Shadow Protection Potion (13499), Pattern: Stormshroud Armor (15753),
   Formula: Enchant Bracer - Superior Strength (16246), Recipe: Greater Nature Protection Potion (13496); mob pages
   (complete drops, greys too, and health) for Gusting Vortex, Living Storm, Toxic Horror, Scarlet Spellbinder,
   Scourge Warder, Whirling Invader, Dark Caster, Arkkoran Oracle, Deadwind Warlock, Shadowmage. Mob page ids: look up
   on the item pages' "Dropped by" tabs (QuestieDB has them too).
2. **Market limit on farmed loot**: an hour of farming a day counts at the AH price only as many as your share of the
   realm's daily sales; the rest at the next best price (vendor). Same idea as crafted worth (2026-11-15). Affects all
   farming rows (mobs, skinning, nodes, fishing, Farm rows).
3. **Kill speed from mob health and level** (from the mob pages as they are read; Forever data), instead of one pace
   for every mob.
4. Dungeon farms stay apart: to-do C4 (Dungeons view).

The analysis script (Classic dump, one-off): scratch only; rebuild from `wfm/classicdb.py` (`parse_tuples`,
`expected_items`) and the dump's `creature_template` (MinLootGold, MaxLootGold, LootId, health) and
`creature_loot_template` if needed again.
