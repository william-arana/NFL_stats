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

1. `?card=` in the URL + back/swipe pops cards + open-on-load + Copy link.
2. Breadcrumb + depth cap.
3. Game card (`g:`) + link schedule rows and game logs to it.
4. Linking audit: every name/team on every page is a card link; Lab results auto-link.
5. Shared table helper with column chooser; roll out Stats → Waivers → Trade → Lab.
6. Optional `sitemap.xml` / page index for the site.

## Open questions

- Should a card on desktop open as a side panel instead of a drop-down? (Phones: full-screen sheet.)
- Game card contents — what matters most to you there?
