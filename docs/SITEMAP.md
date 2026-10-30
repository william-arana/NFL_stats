# Sitemap & navigation plan

Active project (see ROADMAP → Now). Goal: everything inter-navigable — every name and team clickable, cards that link to cards, phone back/swipe that works, a breadcrumb, defined stats, customizable and sortable tables.

## What exists today (2026-10-29)

| Page | URL state it already supports |
|---|---|
| Home `./` | none |
| Guide `guide.html` | `#q=<field>` (stat search; glossary links land here) |
| Stats `stats.html` | `#players` `#teams` `#dvp` `#schedule` (tabs) |
| Lab `lab.html` | `#ds=<dataset>`, `#picks=<json>` (from Guide "Open in Lab"), `&ask` |
| Waivers `waivers.html` | none (league comes from the nav picker / localStorage) |
| Trade `trade.html` | `#a=…&b=…` (shareable trade) |

Already in place:
- **Cards** (`assets/cards.js`): click any `data-card="p:<gsis_id>"` / `d:<TEAM>` → card drops down. Cards hold a **stack**: clicking a name inside a card pushes a new card, ← goes back. But the stack isn't in the URL, so the phone back button/swipe leaves the page instead of going back a card, and you can't share or bookmark a card.
- **Glossary** (`assets/glossary.js`): dotted-underlined headers on Stats, Lab, Waivers, Trade → description + link to `guide.html#q=`.
- **Sort**: header click on Stats, Waivers, Lab results, Trade.
- **Column sets**: Stats has preset chips (fantasy/receiving/rushing/passing); no free column chooser anywhere.

## Target URL scheme

Pages keep their `#hash` state (no breaking changes). Cards use a **query param** so they never fight with page hashes:

| What | URL |
|---|---|
| Player card on any page | `stats.html?card=p:00-0036355#players` |
| Defense/team card | `waivers.html?card=d:KC` |
| Game card (new) | `?card=g:2026_08_KC_LV` (nflverse `game_id`) |
| Stat definition | `guide.html#q=target_share` (exists) |

Behavior:
- Opening a card = `history.pushState` with `?card=…`. Opening a card from inside a card pushes again. **Browser back / phone swipe pops one card**; back from the first card closes it and returns to the page.
- Loading a URL with `?card=` opens that card on page load → every card is shareable/bookmarkable.
- **Breadcrumb** at the top of the card: `Waivers › J. Jefferson › MIN D/ST › KC @ MIN` — each crumb clickable. The stack is capped (proposed 12 deep, breadcrumb shows the last 4 with "…") — that's the "clear limit".
- Card header gets a "Copy link" button.

Later (only if cards get too big): full pages `player.html?id=`, `team.html?t=`, `game.html?id=` reusing the card renderers.

## Every entity links everywhere

- Player → team (D/ST card and team offense), next opponent, each game in the game log, news.
- Team/D/ST → roster players (top by usage), schedule rows → game cards.
- Game (new card) → both teams, top fantasy performers, Vegas line, weather.
- Everywhere: names via `NFLSCards.pbtn/dbtn`, never plain text. Audit pages for unlinked names (Home headlines, Lab results tables with `player_id`/`team` columns, Guide examples).

## Tables (shared helper)

One table helper reused by Stats, Waivers, Lab results, Trade:
- sort on any column (exists — unify the code)
- **column chooser**: show/hide/reorder, saved per table in localStorage (`nfls-cols-<table>`); later per account
- every header through the glossary
- Lab results: auto-link `player_id`, `team`, `game_id` columns as cards

## Build order (one PR each)

1. ✅ `?card=` in the URL + back/swipe pops cards + open-on-load + Copy link. (2026-10-29)
2. ✅ Breadcrumb + depth cap (12). (2026-10-29)
2b. ✅ Pop-out windows: ⧉ on a card or any card section floats it in a draggable, resizable, minimizable window that stays while you browse; names inside open cards; windows follow you across pages in the same tab (sessionStorage, max 6). (2026-10-29)
3. ✅ Game card (`g:<game_id>`): score or implied totals, QBs, rest, spread/O-U (covered/over after the game), weather, top fantasy scorers (final) or players to watch with matchup rank (upcoming), team form side by side. Linked from Stats → Schedule ("Game card" + team names), week numbers in player and D/ST game logs, and the next-game week on cards. (2026-10-29)
4. ✅ Linking audit (2026-10-29): Home hero tiles (next game, top add, D/ST stream, highest implied → cards), Home NFL matchups → game cards, RotoWire news names → player cards; Stats players: name opens the card, ▸ still expands week rows (logs' week → game card), team column → team card; Stats Teams/DvP next opponent → game card; Waivers team column → team card; card subtitles (team) and D/ST game log opponents → cards; Lab results auto-link player names, `player_id`/`gsis_id`, team columns and `game_id` (not click-tested: DuckDB CDN blocked in the test sandbox). Not linked on purpose: individual defenders (no defender cards yet).
5. Shared table helper with column chooser; roll out Stats → Waivers → Trade → Lab.
6. Optional `sitemap.xml` / page index for the site.

## Decided

- 2026-10-29 · Cards stay as a drop-down on desktop (phones: bottom sheet), plus pop-out windows for anything you want to keep on screen — like the Stats board's expandable rows, where several stay open at once.
- 2026-10-29 · Game card shows: both teams, Vegas line, weather, top fantasy scorers.
- Known tradeoffs: drop-downs scroll with the page and can open partly off-screen near the bottom (it scrolls into view); on phones a pop-out window covers the top of the card sheet until you drag or minimize it; pop-outs are snapshots that refresh when scoring changes or the page reloads, not live mid-game.
