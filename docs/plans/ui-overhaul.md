# Plan: UI overhaul, a more modern and flashy WoW look (the user's request, 2026-11-20)

The next high-priority to-do (`docs/plans/TODO.md`, B2), to be done in a new chat. To start: open Claude Code in this
folder and say "Do the plan in docs/plans/ui-overhaul.md". Read CLAUDE.md and docs/PROJECT_LOG.md first. Standing
rules apply: commit and push each finished piece, note decisions and changes in the project log, check usage before
each step (if it gets tight: finish the piece, commit, write what's left here, set a reminder that runs nothing).

## What the user asked
"I would also like a UI overhaul regarding design: more wow themes, more animations and effects, parallax, whatever is
needed for a more modern and flashy app."

## Where things are
- The page is plain HTML, CSS and JavaScript with no build step: `web/index.html`, `web/style.css`, `web/app.js`. No
  Node on this PC: check the browser console after every `web/app.js` edit (the browser pane, `.claude/launch.json`
  "wfm", port 8765; stop the server by PID afterwards, `preview_stop` doesn't kill it).
- Theme today: CSS variables in `:root` (dark panels, gold `--gold`, silver, copper, item quality colours `--q0`..`--q5`),
  a gold-trimmed header (`.top`), tabs (`nav button`), panels, tables, pills and flags, plan cards (`.plan-card`),
  the drawer (`.drawer`), toasts (`#toasts`). Motion today: button transitions and the glowing gold border on rows
  you can do now (`tr.yours`, `@keyframes yours-glow`), switched off under `prefers-reduced-motion`.
- Phones (review part 4, 2026-11-20): under 700 px every table becomes cards (`labelTables` in `web/app.js`,
  `table.cardable` in `web/style.css`), card cells wrap, the header scrolls away and the tabs are one swipeable row;
  nothing may scroll sideways at 375 px.
- `tests/test_web.py` checks the page's JavaScript for broken flag labels and names declared twice.

## Rules for the overhaul
- Readability first (CLAUDE.md: "UI: readability and usability first, then the WoW theme"): numbers, gold amounts,
  warnings and hover help must stay as easy to read as now or easier. Effects frame the data, never cover or blur it.
  Confirmed by the user, 2026-11-20: "readability first sounds good, you can start".
- WoW-inspired, made here: own CSS (gradients, borders, shadows, textures drawn in CSS or SVG made for this app). Never
  copy Blizzard's art, fonts (Friz Quadrata, Morpheus are licensed), UI textures or logos; item icons stay as they are.
- `prefers-reduced-motion`: every animation and parallax off (or a fade at most). A "less motion" switch in Settings
  as well, saved like the other settings.
- Performance: tables of 400+ rows and live updates (SSE) must stay smooth. Animate only `transform` and `opacity`,
  nothing per row that runs all the time; parallax with CSS (or one `requestAnimationFrame` handler), not per element.
- Phones: everything above keeps working at 375 px (no sideways scroll, cards, header). Check wide and narrow.
- Every new visual state that carries meaning (a glow, a colour) gets hover help in plain words, like the rest.

## Ideas to choose from (show the user, let them pick)
- A header with depth: layered background (night sky, mountains, a faint rune circle) that moves at different speeds as
  you scroll (parallax), the gold trim lit by a slow shimmer.
- Panels as framed cards: dark stone or leather texture in CSS, a thin gold frame with corner pieces, a soft glow on
  hover; section titles with a gold rule.
- Gold amounts: coin colours with a light sheen; totals that count up when they change (the purse, plan totals).
- Top picks and the plan: rank medals (1st, 2nd, 3rd) with a shine, an entrance where cards rise in one after another,
  a celebratory sparkle when you tick a step done.
- Tabs: a sliding gold underline, a soft fade between views, icons that light up on hover.
- Tables: row hover lift, item quality colours with a faint glow for epics and rares, sticky headers styled as banners.
- Drawer and toasts: slide and fade, a parchment-like toast with a seal for alerts.
- Loading: skeleton shimmer instead of blank space; an empty state with a small illustration.
- Optional ambient touches the user can switch off: drifting embers or dust in the header, a subtle vignette.

## Order of work
1. "Before" screenshots of every tab, wide and 375 px (send them to the user with the first proposal).
2. Propose a direction: two or three small mock-ups of the header, a panel and a table row (in the browser pane), the
   user picks. Write the choice in the project log.
3. Build in pieces, committing each: theme tokens and textures, header and parallax, panels and cards, tables and
   pills, gold and numbers, motion (entrances, ticks, drawer, toasts), loading and empty states, the "less motion"
   setting.
4. Check every tab wide and at 375 px, the console, `prefers-reduced-motion`, and a long table's scrolling; run the
   tests. "After" screenshots to the user.
5. Note it in README (Settings: "less motion"), the project log and this file's Progress.

## Done when
The user signs off on the after screenshots; no tab scrolls sideways at 375 px; the console is clean; reduced motion
and the Settings switch turn the motion off; tests pass.

## Progress
- **2026-11-20 Steps 1 and 2 done; waiting for the user to pick a look.**
  - "Before" pictures: every tab at 1440 px and at 375 px (26, in `data/screenshots/before/`, not committed: they show
    characters and gold), taken with the new `tools/screenshots.py` (Edge without a window, through its DevTools port,
    standard library only; a throw-away profile). It also checks each view: no tab scrolls sideways at 375 px, no
    console errors from the app (Wowhead's tooltip site sometimes fails in the throw-away profile: counted apart).
    Run it again for the "after" pictures: `python tools/screenshots.py after` (the app must be running).
  - Mock-ups: `web/mockups/directions.html` (open http://127.0.0.1:8765/static/mockups/directions.html while the app
    runs): three looks, each a small scrollable copy of the app with made-up numbers (header with parallax, the plan
    panel, a table, an alert), wide or 375 px. A "Night watch" (night sky, mountains, turning rune circle, embers, gold
    trim with a running light, stone panels with gold corner pieces), B "Leather and ledger" (tooled leather band,
    stitching, rivets, map and compass, ledger tables, parchment alerts with a wax seal), C "Arcane glass" (aurora,
    three star layers, glass-like cards, rows as strips, a light running round the number-one pick, coin icons
    instead of g/s/c). Common to all: tab underline that slides, rows and cards rise in, medal shine, sparkle when
    a step is ticked, the purse counts up. Pictures in `data/screenshots/mockups/`. Delete the mock-up page once
    the look is built.
  - Found: Windows "Animation effects" is off on the user's PC, so every browser there reports
    `prefers-reduced-motion: reduce`. Followed strictly, the user would see none of the motion they asked for.
    Proposed: Settings "Motion" with three choices (follow Windows, on, off), the page keyed on one attribute the
    script sets, not on the media query directly. Waiting for the user's choice.
  - Other proposal shown in the mock-ups: rare blue and epic purple item names a touch lighter (today #0070dd and
    #a335ee are about 3.6:1 on the dark panels, below the 4.5:1 usual for small text); headings in Cinzel, a free
    font (SIL Open Font License) the app would ship (the mock-up loads it from Google Fonts).
- **2026-11-20 The user picked A, Night watch ("Build A, Night watch"). Built in one piece:**
  - Theme: Cinzel headings (bundled: `web/fonts/cinzel-latin.woff2`, SIL Open Font License in `web/fonts/OFL.txt`; served
    as font/woff2), rare blue `#3b9cff` and epic purple `#b870ff` (about 6:1, the game's colours are about 3.6:1), a still
    glow on rare, epic and legendary names, tabular figures for numbers.
  - Header: night sky, two mountain ranges, a rune circle, embers, a gold trim with a running light, a drawn coin;
    parallax from one scroll handler (at most once a frame) setting `--sy` on the sky only; the sliding gold tab line
    (`placeInk`, transform only).
  - Panels: stone texture (SVG noise), thin gold frame, four corner pieces in one pseudo-element (none on nested
    panels or in the drawer), gold rule under titles; banner table headings, warm row highlight; plan cards lift.
  - Motion: panels, plan cards and the first 12 rows of each table rise in on a tab switch only (never on live
    updates), medal shine, purse and plan total count to a new value, a sparkle where you tick a step done, toasts,
    drawer and the done dialog slide and fade in. Loading shimmer (first load, and a view that takes over 150 ms);
    empty states get a small purse drawn in gold.
  - Settings "Motion": follow Windows (default), on, off; saved at once without recalculating (`PAGE_ONLY_SETTINGS`
    in `wfm/app.py`), kept in the browser too so the first paint is right. CSS: everything stops under
    `html[data-motion="off"]`; the media query only decides before the page script runs.
  - Checked: every tab wide and 375 px (`tools/screenshots.py after`: no sideways scroll, no console errors), the
    three motion modes, parallax, the tab line and the count-up in headless Edge (rAF does not run in the browser pane
    while it is off screen, so those were checked there). Tests: `tests/test_motion.py` (setting saved, checked, no
    recalculation; the off rule; new keyframes move only transform and opacity). The mock-up page is removed.
  - Left as it was: the Biggest markets glow (`yours-glow`, the user's request of 2026-11-19) animates outline and
    shadow, not transform/opacity; it stops with Motion off.
- **2026-11-20 Signed off by the user ("Signed off") on the after pictures (`data/screenshots/after/`). Done.**
  Every "done when" point met: sign-off; no tab scrolls sideways at 375 px; console clean; Motion off and the system's
  reduce-motion (with "follow Windows") stop every animation; tests pass.
