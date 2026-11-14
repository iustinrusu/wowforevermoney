# Plan: "Do these now" becomes a smart plan for today (the main page's champion)

Saved on 2026-11-14 (usage was at 82%; postponed, not cut off). Nothing runs by itself: a reminder points here.
To start, open a Claude Code session in this folder and say "Do the plan in docs/plans/todays-plan.md".
Do this before docs/plans/forever-data-next.md: the user called it the main attraction.

First read CLAUDE.md and docs/PROJECT_LOG.md. Standing rules apply (Forever data only in Top picks, accuracy
first with tests, explain everything in plain language with no cryptic labels, usage rule: postpone with a plan
file + a reminder that runs nothing). End commit messages with: Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

## What the user asked (2026-11-14)
"Do these now should be our main attraction... tune the algorithm to actually show smart things in this section,
suggestions, actual smart things to do. Think like a pro WoW player." Effort must count and be hinted clearly
(done: `Engine.effort`, time value = half the best measured farming gold/hour, "not worth your time"). Every
hint must be explicit, never a few cryptic words.

## How a pro plans a gold session (the algorithm)
A pro doesn't pick one list sorted by profit/day. They run a short checklist, best value for their time first:
1. **Cash in what you already have** (zero cost, minutes): from your bags/bank/mail (Syndicator, `World.inventory`,
   `World.syndicator`, active character only):
   - items whose best channel is the AH and that sell (not `hard_to_sell`): one action "List these on the AH"
     with the top items, total value, posts needed (effort), and the price to list at;
   - openable items worth more opened (trunks, clams): "Open your N trunks";
   - grey/vendor-only items: "Sell your junk to a vendor";
   - expired auctions in mail: "Collect and relist N expired auctions".
2. **Daily cooldowns** if you have the profession (transmute, Mooncloth): one action for the best of each shared
   cooldown group (`Engine._one_per_cooldown`).
3. **Daily routines**: the current "Do these now" rows (>= 1 sale a day, after time cost), top 3-4, each with a
   concrete instruction: "Buy 13 Junglevine Wine from <vendor> in <zone> for 3s, list at 18s 90c (sells ~65 a day
   in the region)". Vendor names/zones are in `detail['vendors']`; ingredient sources in `detail['mats']`.
4. **One farming session**: the best Forever-confirmed hourly activity you can do now (measured rows first):
   "Spend an hour: Skin in Redridge (~9.7g/h)". Never Classic-yield rows.
5. **One occasional big flip** if its profit at the average sale price is large: "List one Pattern: Devilsaur
   Gauntlets: ~32g at the usual price, about one sale every 4 days".
6. **One long-term goal** (shown last, not ranked against the rest): the best unlock ("Level Leatherworking to
   265 for Devilsaur Gauntlets, ~19g a day") or the top investment.

Rank items 1-5 by **value of the action today** = expected gain (one-off gain, a day of a routine, an hour of
farming) minus its minutes x your time value; drop anything not worth its time; at most 2 per type so the list
stays varied; 6-8 actions. Each action carries: what to do (an instruction), why (one plain sentence with the key
numbers), expected gain, minutes, gold per hour of your time, gold needed, confidence, and the row key so a click
opens the existing details. Put the builder in a new `wfm/plan.py` (pure functions, unit-tested) and expose it as
`result['plan']` / in `/api/state`.

## The page
- A "Your plan for today" panel at the top of Top picks: numbered cards (medals 1-3) with the instruction in bold,
  the why-sentence under it, and chips for gain, time, gold/hour and gold needed. Click opens the details.
- Keep the detailed tables below ("Daily routines", "Occasional big flips", "Gathering", "Snipes", "Unlock...").
- Explain the plan's logic in a "How this plan is made" details block, in plain words.

## Tests
- plan.py: cash-in actions from a fake inventory (AH vs vendor vs open), time cost drops tiny actions, diversity
  cap, Classic-yield rows never appear, cooldown action only with the profession, ordering by value of the action.
- Engine/app: `/api/state` includes the plan; the page renders it (tests/test_web checks still pass).
- Check in the browser pane; then README (Top picks) and the project log.
