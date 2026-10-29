# NFL_stats

My fantasy football stats lab: NFL data from [nflverse](https://github.com/nflverse), refreshed automatically, for finding waiver-wire pickups on my own numbers instead of app news feeds.

**Site:** https://william-arana.github.io/NFL_stats/

| Page | What it does |
|---|---|
| [Guide](https://william-arana.github.io/NFL_stats/) | Every nflverse dataset and all ~1,500 columns, by dataset or stat category. Pick stats and copy the list. |
| [Stats](https://william-arana.github.io/NFL_stats/stats.html) | Players (fantasy / receiving / rushing / passing, per game or totals, any week range, game logs), Teams (offense, defense & D/ST, pass rush matchup), Defense vs position, Schedule & Vegas lines. |
| Lab | *Coming:* build your own tables and pivots in the browser (DuckDB). |
| Waivers | *Coming:* models ranked against players available in my Sleeper leagues. |

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

## Repo layout

| Path | What it is |
|---|---|
| `index.html`, `stats.html` | Site pages |
| `assets/site.css` | Shared colors, fonts, nav |
| `data/site/` | Compact JSON the Stats page reads (players, teams, schedule, meta + injuries) |
| `data/catalog.json` | Catalog behind the Guide |
| `scripts/update_data.py` | Weekly data pull → CSVs, master.xlsx, site JSON |
| `scripts/build_catalog.py`, `fetch_live_columns.py`, `page_template.html` | Rebuild the Guide catalog |

Run locally: `pip install -r requirements.txt && python scripts/update_data.py`, then `python -m http.server` and open http://localhost:8000.

## Roadmap

1. ~~Map everything nflverse offers~~ (Guide)
2. ~~Weekly data pipeline + Stats board + Excel hookup~~
3. Lab: in-browser pivots and stats (DuckDB)
4. Sleeper league join → Waivers board
5. Models: D/ST pressure matchups, usage risers, expected vs. actual points; backtest weekly
6. Team news and press conference signals; Claude built into the site

Data: [nflverse](https://github.com/nflverse) (CC-BY 4.0 for most datasets; FTN charting CC-BY-SA 4.0). D/ST points use Sleeper default scoring and are approximate.
