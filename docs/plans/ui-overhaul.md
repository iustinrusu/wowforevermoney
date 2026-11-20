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
  If the user wants the balance moved further toward flash, ask; don't assume.
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
