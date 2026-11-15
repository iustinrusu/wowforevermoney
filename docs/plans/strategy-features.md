# Plan: strategy features (thinking ahead, not just today's prices)

Ideas from the 2026-11-14 talk about professions and Forever's economy evolving in phases. Not scheduled yet:
do them after docs/plans/todays-plan.md and docs/plans/forever-data-next.md. To start one, open a Claude Code
session here and say "Do item N of docs/plans/strategy-features.md". Standing rules apply (CLAUDE.md): Forever
data first, anything from Classic history labelled as speculation, plain-language explanations, tests.

1. **Profession advisor** (a Professions view). For your two primary professions and each alternative pair:
   gold per hour now (gathering) and per day (crafting), what the next skill milestones unlock (e.g. Leatherworking
   265: Devilsaur Gauntlets), the switching cost (skill you'd lose, time and gold to level the new one), and a
   short "now vs later" verdict: gathering pays most early, crafting captures the margin and the phase demand.
2. **Done 2026-11-15** (Crafting tab, "Levelling a profession"; project log). **Levelling planner** for a crafting profession: the cheapest path from your skill to a target (SkillUpForever
   thresholds for orange/yellow/green, current AH prices, selling what you craft to offset the cost), with total
   gold, time, and what it unlocks. Your own gathered materials count at what they'd sell for.
3. **Vertical integration**: when you gather an ingredient yourself (skin, mine, pick), show the craft both ways:
   ingredients bought on the AH, and your own ingredients at what you'd get for selling them, plus the gathering
   time. Shows when skin -> craft beats selling the leather.
4. **Server phase tracker**: from the progression gauge (cloth tiers, Runecloth share) and price history, estimate
   where the server is (levelling, many at 60, raiding) and show a "prepare for the next phase" list: items that rose
   in Classic before each phase (fire resistance before Molten Core and Onyxia, flasks and raid consumables when
   raiding starts, pre-raid best-in-slot crafts that peak at first 60s and fade), clearly labelled as Classic history.
   Alerts when the gauge or an item's sales cross a threshold.
5. **Peak-and-fade items**: pre-raid BiS crafts and their mats (Devilsaur set, Devilsaur Leather) rise when players
   reach 60 and fall when raid gear replaces them: track them with trends and say "sell into the peak" while sales
   are rising, "stop stocking" when they turn.
6. **Recipe finder**: where each pattern comes from (vendor with limited stock and restock, drop, world drop, quest,
   reputation), what it costs on the AH vs the vendor, and which ones are worth buying before a phase.
7. **Alt planner**: given your characters, which professions an alt should take to complement yours (e.g. an
   Herbalism + Alchemy alt for weekly raid consumables, or Mining to feed Thorium/Arcane Crystal), with expected
   weekly income.
8. **Raid-week rhythm**: from price history by weekday, when consumables and mats sell best (before raid nights)
   and the best day to list each of your items.
9. **Demand trends**: weeks-long sold/day trends (needs more history) to spot rising demand early; feeds the
   Investments tab, the phase tracker and alerts.
10. **Niches: steady demand, low supply** (user idea, 2026-11-14). A list of items that sell every day (TSM region
    sold/day) with most listings selling (sale rate), few listed on your realm (under a day of sales), often sold
    out in our own snapshots (nothing listed in many scans while sales continue: the best sign few people supply
    it), a price that holds (lowest listing near or above the average sale price, steady history), and a way for
    you to supply it (a recipe you know or can buy, a vendor item, something you gather). Each row says why it
    qualifies, how you'd make or get it, and how many a day you could sell without flooding it. Limits to show:
    region-wide counts from TSM users only, no seller counts in TSM data, niches close once noticed (so the
    sold-out history matters). Needs a week or more of history for the sold-out signal.
