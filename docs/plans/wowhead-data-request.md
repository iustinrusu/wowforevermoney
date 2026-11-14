# Draft: asking Wowhead for WoW: Forever data access

Written 2026-11-14 (material-coverage plan, step 1b). The user sends it themselves, through Wowhead's contact page
(linked at the bottom of every wowhead.com page) or their feedback address; Claude never sends it. Fill in the
bracketed parts before sending. Keep the tool's name generic if you prefer not to link the GitHub repo (it is private).

---

**Subject:** Data access question for a personal WoW: Forever gold tool

Hello Wowhead team,

I play WoW: Forever and am building a small personal tool, for my own use only, that helps me decide how to make
gold (crafting, gathering, fishing, farming). It runs on my own PC, reads my own TSM auction data, and links every
item back to its Wowhead page.

To value farming spots properly I need the source data your Forever item pages show: "Dropped by", "Skinned from",
"Mined from" / "Gathered from", "Fished in" and "Contains" (counts and "out of" totals), for about 300 trade goods
(cloth, leather, ore, herbs, elementals, fish).

Your pages refuse automated requests, which I respect, so I have been opening a few pages by hand. Is there a way to
get this data that you are comfortable with?

- an export or data file for Forever sources (even an old one is fine),
- an API, or
- a reading pace you consider acceptable (for example one page a minute for a few hundred pages, once).

I would credit Wowhead wherever the numbers appear, keep a link to the item page beside every figure, and not
redistribute the data.

Thank you for the site, it is the best reference for Forever.

[Your first name]

---

Why now: no bulk Forever source covers the valuable materials yet. Everloot (everloot.app, CC BY-SA 4.0, checked
2026-11-14) has 1,753 public drop rates from player uploads, but they cover 15% of the uncovered traded material value
(none of Dark Rune, Runecloth, Arcane Crystal, Righteous Orb, Mageweave) with a median of 21 loot windows per rate.
