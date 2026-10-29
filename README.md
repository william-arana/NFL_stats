# NFL_stats

My fantasy football stats lab: NFL data from [nflverse](https://github.com/nflverse), refreshed automatically, for finding waiver-wire pickups on my own numbers instead of app news feeds.

**Site:** https://william-arana.github.io/NFL_stats/

| Page | What it does |
|---|---|
| [Guide](https://william-arana.github.io/NFL_stats/) | Every nflverse dataset and all ~1,500 columns, by dataset or stat category. Pick stats and copy the list. |
| [Stats](https://william-arana.github.io/NFL_stats/stats.html) | Players (fantasy / receiving / rushing / passing, per game or totals, any week range, game logs), Teams (offense, defense & D/ST, pass rush matchup), Defense vs position, Schedule & Vegas lines. |
| [Lab](https://william-arana.github.io/NFL_stats/lab.html) | Build your own tables in the browser: point-and-click pivots, a SQL editor (DuckDB), 8 waiver recipes, charts, CSV export, saved queries. |
| [Waivers](https://william-arana.github.io/NFL_stats/waivers.html) | Free agents in the selected Sleeper league ranked by a waiver score (recent xFP, PPR, snap/touch trends, matchup), my roster with likeliest drops, and D/ST streamers. |

## Leagues & theme

- Leagues live in `data/leagues.json` (Sleeper league id, team count, my roster id). The **League** picker in the nav switches every page; free agents get a green name and an **FA** tag on the Stats board.
- Rosters: the browser asks Sleeper live; if that fails it uses the snapshot `.github/workflows/update-sleeper.yml` saves three times a day (`data/site/leagues.json`).
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
| `index.html`, `stats.html`, `lab.html` | Site pages |
| `lab/recipes.sql` | Lab recipes. Add your own: a `-- @recipe id` line, `-- @title`, `-- @blurb`, then the SQL. |
| `lab/init.sql` | Views created when the Lab loads (`games_long`) |
| `assets/site.css` | Shared colors, fonts, nav |
| `data/site/` | Compact JSON the site reads: players, teams, schedule, defenders, meta + injuries, Sleeper rosters + id map |
| `assets/site.js` | Theme toggle, league picker, Sleeper roster lookups |
| `scripts/update_sleeper.py` | Sleeper rosters → `data/site/leagues.json`, `sleeper_map.json` |
| `data/catalog.json` | Catalog behind the Guide |
| `scripts/update_data.py` | Weekly data pull → CSVs, master.xlsx, site JSON |
| `scripts/build_catalog.py`, `fetch_live_columns.py`, `page_template.html` | Rebuild the Guide catalog |

Run locally: `pip install -r requirements.txt && python scripts/update_data.py`, then `python -m http.server` and open http://localhost:8000.

## Roadmap

1. ~~Map everything nflverse offers~~ (Guide)
2. ~~Weekly data pipeline + Stats board + Excel hookup~~
3. ~~Lab: in-browser pivots and stats (DuckDB)~~
4. ~~Sleeper league join → Waivers board~~
5. Models: D/ST pressure matchups, usage risers, expected vs. actual points; backtest weekly
6. Team news and press conference signals; Claude built into the site

Data: [nflverse](https://github.com/nflverse) (CC-BY 4.0 for most datasets; FTN charting CC-BY-SA 4.0). D/ST points follow the leagues' Sleeper D/ST scoring (sack 1, INT 2, fumble recovery 2, forced fumble 1, TD 6, safety 2, blocked kick 2, points-allowed tiers).
