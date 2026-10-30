# NFL_stats

My fantasy football stats lab: NFL data from [nflverse](https://github.com/nflverse), refreshed automatically, for finding waiver-wire pickups on my own numbers instead of app news feeds.

**Site:** https://william-arana.github.io/NFL_stats/

| Page | What it does |
|---|---|
| [Home](https://william-arana.github.io/NFL_stats/) | Next kickoff, top waiver add, best D/ST stream, highest implied total, links to every page, live headlines + fantasy news + Sleeper trending adds. |
| [Guide](https://william-arana.github.io/NFL_stats/guide.html) | Every nflverse dataset and all ~1,500 columns, by dataset or stat category. Pick stats and copy the list. |
| [Stats](https://william-arana.github.io/NFL_stats/stats.html) | Players (fantasy / receiving / rushing / passing, per game or totals, any week range, game logs), Teams (offense, defense & D/ST with rushing vs passing yards allowed, pass rush matchup), Defense vs position (points allowed by position + rush/pass yards, carries and yards per play allowed), Schedule & Vegas lines. |
| [Lab](https://william-arana.github.io/NFL_stats/lab.html) | Build your own tables in the browser: point-and-click pivots, a SQL editor (DuckDB), 10 waiver recipes (incl. RB and WR pickup checks with PFR, Next Gen, depth chart and injury data), charts, CSV export, saved queries. |
| [Waivers](https://william-arana.github.io/NFL_stats/waivers.html) | Free agents in the selected Sleeper league ranked by a waiver score (recent xFP, PPR, snap/touch trends, matchup), player search (name, team or position; includes rostered players), my roster with likeliest drops, and D/ST streamers. |
| [Trade](https://william-arana.github.io/NFL_stats/trade.html) | Two-sided trade comparison: pick players/defenses from any league roster or search, then compare FP/g, last 3, xFP, usage, weekly scores, rest-of-season schedule and news. Shareable link; "Copy for Claude" summary. |

**Stat descriptions:** dotted-underlined column names on Stats, Lab, Waivers and Trade open a short description (from the Guide's data dictionary, `data/catalog.json`, plus notes for stats the site calculates) with a link to that stat in the Guide (`guide.html#q=<field>`). Tap the rest of a header to sort. Lives in `assets/glossary.js`.

**Player & defense cards:** click any player or D/ST name (Waivers, Trade, Home trending, Stats opponents/teams) for weekly fantasy points, season stats, game log and news (`assets/cards.js`). News = the site's archive (`data/site/news/`, built by `scripts/update_player_news.py` 3× a day with the Sleeper job; grows all season) + the live per-player feeds from Sleeper (`api.sleeper.app/players/nfl/<id>/news`: RotoWire, FantasyPros, RotoBaller, newest 10) and ESPN (fantasy player news, newest ~8), both read straight from the browser.

## Leagues & theme

- Leagues live in `data/leagues.json` (Sleeper league id, team count, my roster id, and `viewers`: the teams offered in the **Team** picker, e.g. 67FFL · Just Win Baby). The picker switches every page; free agents get a green name and an **FA** tag on the Stats board.
- Rosters: the browser asks Sleeper live; if that fails it uses the snapshot `.github/workflows/update-sleeper.yml` saves three times a day (`data/site/leagues.json`).
- The small arrow icon after a player's name opens Sleeper (copies the name for search; Sleeper has no per-player web page), the ESPN player page (`data/site/ids.json`), or a news search.
- Light mode is the default; the nav button switches to dark (remembered per browser).

## Data refresh

`.github/workflows/update-data.yml` runs `scripts/update_data.py`:

- **Tuesday** 8:17 AM PT: full refresh after Monday Night Football
- **Thursday** afternoon and **Sunday** morning: picks up new injury reports
- **Any time:** Actions tab → *Update data* → *Run workflow*

Each run commits the small site files in `data/site/` (the site redeploys itself) and uploads the big files to the **[data-latest release](https://github.com/william-arana/NFL_stats/releases/tag/data-latest)**:

- `master.xlsx`: every dataset as its own tab
- one CSV per dataset: `player_week`, `team_week`, `schedule`, `snap_counts`, `ff_opportunity`, `pfr_pass/rush/rec/def`, `ngs_passing/rushing/receiving`, `injuries`, `depth_charts`

### Excel hookup (Power Query)

Data → Get Data → From Web, then paste a file URL:

```
https://github.com/william-arana/NFL_stats/releases/download/data-latest/player_week.csv
```

Load it to a sheet. Each Tuesday, hit **Data → Refresh All**. Google Sheets: `=IMPORTDATA("<same url>")`.

## Lab tables

| Table | One row per | Notes |
|---|---|---|
| `players` | offensive player per game | box score + snap % + expected points (`xfp`, `xfp_diff`) + PFR pressure/contact stats |
| `teams` | team per game | offense, defense, D/ST points, pressures made/allowed, yards & EPA allowed |
| `schedule` | game | Vegas spread/total, implied totals, weather, rest |
| `games_long` | team per game | schedule flipped so every team has its own row: `team`, `opp`, `implied`, `opp_implied` |
| `meta` | — | `season`, `last_completed_week`, `next_week` |

## Repo layout

| Path | What it is |
|---|---|
| `index.html` | Home: hero with this week's quick hits, page cards, quick links, news rail |
| `guide.html`, `stats.html`, `lab.html`, `waivers.html` | Site pages |
| `scripts/update_news.py` | Hourly headlines (NFL.com, ESPN, PFT, CBS), RotoWire player news, Sleeper trending adds → `data/site/news.json` |
| `lab/recipes.sql` | Lab recipes. Add your own: a `-- @recipe id` line, `-- @title`, `-- @blurb`, then the SQL. |
| `lab/init.sql` | Views created when the Lab loads (`games_long`) |
| `assets/site.css` | Shared colors, fonts, nav |
| `data/site/` | Compact JSON the site reads: players, teams, schedule, defenders, meta + injuries, Sleeper rosters + id map |
| `assets/site.js` | Theme toggle, league picker, Sleeper roster lookups |
| `assets/cards.js` | Clickable player + defense cards (stats, game log, news) on every page |
| `assets/glossary.js` | Stat descriptions behind the underlined column names |
| `assets/tables.js` | Columns button (hide / reorder) for any `table[data-cols]`, pages and cards |
| `scripts/update_player_news.py` | Per-player / per-defense news archive → `data/site/news/*.json` |
| `trade.html` | Trade analyzer |
| `scripts/update_sleeper.py` | Sleeper rosters → `data/site/leagues.json`, `sleeper_map.json` |
| `data/catalog.json` | Catalog behind the Guide |
| `scripts/update_data.py` | Weekly data pull → CSVs, master.xlsx, site JSON (incl. `kickers.json`, `def_week.json`, `oline.json` for the Defenders / O-line / Kickers tabs) |
| `scripts/build_catalog.py`, `fetch_live_columns.py`, `page_template.html` | Rebuild the Guide catalog |

Run locally: `pip install -r requirements.txt && python scripts/update_data.py`, then `python -m http.server` and open http://localhost:8000.

## Roadmap

Full plan, ideas and decisions: [ROADMAP.md](ROADMAP.md). Navigation plan: [docs/SITEMAP.md](docs/SITEMAP.md).

1. ~~Map everything nflverse offers~~ (Guide)
2. ~~Weekly data pipeline + Stats board + Excel hookup~~
3. ~~Lab: in-browser pivots and stats (DuckDB)~~
4. ~~Sleeper league join → Waivers board~~
5. Models: D/ST pressure matchups, usage risers, expected vs. actual points; backtest weekly
6. Team news and press conference signals; Claude built into the site

Data: [nflverse](https://github.com/nflverse) (CC-BY 4.0 for most datasets; FTN charting CC-BY-SA 4.0). D/ST points follow the leagues' Sleeper D/ST scoring (sack 1, INT 2, fumble recovery 2, forced fumble 1, TD 6, safety 2, blocked kick 2, points-allowed tiers).
