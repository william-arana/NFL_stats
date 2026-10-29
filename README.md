# nfl_stats

My fantasy football stats lab. The goal: a master spreadsheet of NFL data (from [nflverse](https://github.com/nflverse)) for finding waiver-wire pickups on my own numbers instead of app news feeds.

## What's here

| Path | What it is |
|---|---|
| `index.html` | **nflverse Field Guide**: every nflverse dataset and all ~1,500 columns, browsable by dataset or stat category. Pick the stats you care about and copy the list. Live at the GitHub Pages link in the sidebar. |
| `data/catalog.json` | The catalog behind the page: datasets, columns, descriptions, categories, "essential" flags. |
| `scripts/fetch_live_columns.py` | Pulls current-season data with `nflreadpy` to capture column names that aren't in the official dictionaries. |
| `scripts/build_catalog.py` | Builds `catalog.json` from the nflreadr data dictionaries + live columns. |
| `scripts/page_template.html` | Page template; the catalog gets injected into it. |

## Roadmap

1. ~~Map everything nflverse offers~~ (Field Guide)
2. Pick the stats that matter, then build the master workbook (one tab per dataset, long format, weekly refresh)
3. Join Sleeper league data so the sheet only shows players I can actually pick up
4. Models: D/ST pressure matchups, usage risers, expected-vs-actual fantasy points
5. Backtest the models week over week
6. Add team news and press conference signals

## Rebuilding the catalog

```bash
pip install nflreadpy
git clone --depth 1 https://github.com/nflverse/nflreadr.git   # official data dictionaries
python scripts/fetch_live_columns.py   # writes cols.json
python scripts/build_catalog.py        # writes catalog.json
```

Data: [nflverse](https://github.com/nflverse) (CC-BY 4.0 for most datasets; FTN charting is CC-BY-SA 4.0).
