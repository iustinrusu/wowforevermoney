# Plan: realm prices, own materials, three profit views (decided 2026-11-15)

First item of the next session (to-do item 1b). Follow CLAUDE.md's standing rules (tests for every calculation,
plain-language explanations, commit and push each piece, project log).

## What the user decided (2026-11-15)
- "Prices should be based on my realm, because I play on a realm, not on the region." This replaces the 2026-11-14
  decision (profit at the lower of the lowest listing and the region's usual sale price).
- Skip tracking the user's own sales (TSM's accounting): not wanted.
- Show profit three ways: an average day, a good day, and with materials you gather yourself.
- Prompted by: Tailoring "only ~10g a day" (Mooncloth: 95 h cooldown, listed 28g on the realm, the region's usual
  sale 15g 77s, 22% of listings sell) and Devilsaur Leggings (sells ~65g, 20g profit each, but the region sells 1 every
  3 days, 3% of listings sell, 34 listed on the realm).

## 1. Realm prices
- New default `sale_price_basis` = `realm`: the realm's lowest listing (what you would list at). Keep the existing
  protections that use realm data: odd few listings (`price_looks_off`, realm market value), nothing listed (realm
  market value, then region values, labelled). Walls (`listed_far_above_sales`) and freak sales: keep them as flags and
  a warning in the row ("listed far above what sells in the region: may sit unsold"), no longer as the price.
- Region data stays for speed only: sold a day, sale rate, days of supply, hard to sell / slow / crowded (TSM has no
  realm sales data: say so in Settings and in the "how this is worked out" texts).
- The old bases stay in Settings (`lower`, `min_buyout`, `actual_sales`) so the user can switch back.
- Recheck what depends on the basis: anomalies' second opinion (it already compares with typical prices: keep as the
  safety net, and its findings must still keep money-losing rows out of Top picks), "up to" lines (now the region's
  usual sale is the "may sell for less" line instead), plan for today, valuation, investments. Update tests that assume
  `lower`. Show on real data how many rows change and the biggest movers (Mooncloth, Devilsaur Leggings).

## 2. Own materials (strategy item 3, vertical integration)
- For each craft with ingredients you gather (your gathering professions: Skinning -> leather/hides, Herbalism ->
  herbs, Mining -> ore/stone/bars via smelting; fishing for cooking; cloth/meat from mobs): profit if you buy the mats
  (today), and "with your own materials": product sale - the mats' sale value = what crafting adds over selling raw.
- The farming time behind them: per ingredient, the best Forever-backed spot that gives it (skinning/mob/node rows,
  their rates and the Settings paces) -> hours to gather one craft's worth -> gold per hour for farm + craft + sell.
  Ingredients with no Forever rate: say so, no time estimate.
- Never count own materials as free (you could sell them): the user's point is answered by showing both.

## 3. Three profit views
- Average day (today's numbers): profit x what your share of the market takes a day, cooldowns included.
- Good day (labelled optimistic): one sale of each high-value item today at the realm's lowest listing, including the
  slow ones (e.g. the leggings' profit + Mooncloth's), plus the steady ones' daily profit.
- Own materials: both of the above with gathered ingredients counted as in part 2.
- Where: Crafting tab columns (Profit a day / On a good day / With your own materials), the Professions tab (three
  figures per profession, plus an "occasional big sales" line so items like Devilsaur Leggings stay visible), and the
  plan for today if it fits. Hover help and "how this is worked out" for each.

## Tests (hand-worked)
- Realm basis: lowest listing used even above the region's usual sale; odd-listing and nothing-listed paths; the
  warning flag on walls.
- Own materials: a craft with one gathered and one bought ingredient; the time from a spot's rate.
- Good day: two slow items and one steady item summed as defined.
