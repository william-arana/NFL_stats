"""Browser-ready copies of every nflverse dataset in the Guide, for the Lab and the Guide previews.

Writes (all same-origin on GitHub Pages, so the site can read them with no download step):
  data/lab/<id>.csv.gz           current-season data (or the whole table for lookup tables), read by DuckDB in the Lab
  data/lab/preview/<id>.json     first 25 rows (newest week first), shown inline in the Guide
  data/lab/index.json            what's there: rows, columns, size, season, refreshed time

Runs inside the "Update data" workflow. Run by hand:  python scripts/build_lab_data.py [season]
"""
from __future__ import annotations

import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import nflreadpy as nfl
import polars as pl

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "lab"
PREV = OUT / "preview"
PREVIEW_ROWS = 25
# Files bigger than this stay out of the repo (play-by-play gets trimmed to fit instead)
MAX_BYTES = 6_000_000


def log(msg: str) -> None:
    print(f"[lab] {msg}", flush=True)


def flat(df: pl.DataFrame) -> pl.DataFrame:
    """Drop list/struct columns (DuckDB can read them, but previews and CSV exports can't)."""
    return df.select([c for c, t in df.schema.items() if not isinstance(t, (pl.List, pl.Struct, pl.Array, pl.Object))])


def latest_depth(df: pl.DataFrame) -> pl.DataFrame:
    if "dt" in df.columns:
        latest = df.group_by("team").agg(pl.col("dt").max().alias("_max"))
        return df.join(latest, on="team").filter(pl.col("dt") == pl.col("_max")).drop("_max")
    return df


def nextgen(S):
    parts = []
    for st in ("passing", "rushing", "receiving"):
        d = nfl.load_nextgen_stats(seasons=S, stat_type=st)
        parts.append(d.with_columns(pl.lit(st).alias("stat_type")))
    return pl.concat(parts, how="diagonal_relaxed")


def pbp(S):
    d = nfl.load_pbp(seasons=S)
    # Keep it small enough for the browser: real plays only
    if "play_type" in d.columns:
        d = d.filter(pl.col("play_type").is_in(["pass", "run", "punt", "field_goal", "kickoff", "extra_point", "qb_kneel", "qb_spike"]))
    return d


def recent(fn, back: int):
    """Lookup tables with history: keep the last few seasons so they stay light."""
    def go(S):
        return fn(seasons=list(range(S[0] - back, S[0] + 1)))
    return go


def last_season(fn):
    def go(S):
        return fn(seasons=[S[0] - 1])
    return go


# Guide dataset id -> (loader taking [season], what the Lab table is called, scope note)
SOURCES = {
    "player_stats":   (lambda S: nfl.load_player_stats(seasons=S), "player_stats", "this season, weekly"),
    "team_stats":     (lambda S: nfl.load_team_stats(seasons=S), "team_stats", "this season, weekly"),
    "schedules":      (lambda S: nfl.load_schedules(seasons=S), "schedules", "this season"),
    "pbp":            (pbp, "pbp", "this season, every play"),
    "ff_opportunity": (lambda S: nfl.load_ff_opportunity(seasons=S), "ff_opportunity", "this season, weekly"),
    "snap_counts":    (lambda S: nfl.load_snap_counts(seasons=S), "snap_counts", "this season, weekly"),
    "participation":  (last_season(nfl.load_participation), "participation", "last season (no longer published)"),
    "ftn_charting":   (lambda S: nfl.load_ftn_charting(seasons=S), "ftn_charting", "this season, every play"),
    "pfr_pass":       (lambda S: nfl.load_pfr_advstats(seasons=S, stat_type="pass", summary_level="week"), "pfr_pass", "this season, weekly"),
    "pfr_rush":       (lambda S: nfl.load_pfr_advstats(seasons=S, stat_type="rush", summary_level="week"), "pfr_rush", "this season, weekly"),
    "pfr_rec":        (lambda S: nfl.load_pfr_advstats(seasons=S, stat_type="rec", summary_level="week"), "pfr_rec", "this season, weekly"),
    "pfr_def":        (lambda S: nfl.load_pfr_advstats(seasons=S, stat_type="def", summary_level="week"), "pfr_def", "this season, weekly"),
    "nextgen":        (nextgen, "nextgen", "this season, weekly"),
    "injuries":       (lambda S: nfl.load_injuries(seasons=S), "injuries", "this season, weekly"),
    "depth_charts":   (lambda S: latest_depth(nfl.load_depth_charts(seasons=S)), "depth_charts", "latest depth chart"),
    "rosters":        (lambda S: nfl.load_rosters(seasons=S), "rosters", "this season"),
    "players":        (lambda S: nfl.load_players(), "player_info", "all players"),
    "ff_playerids":   (lambda S: nfl.load_ff_playerids(), "ff_playerids", "all players"),
    "ff_rankings":    (lambda S: nfl.load_ff_rankings(type="week"), "ff_rankings", "latest weekly ranks"),
    "combine":        (recent(nfl.load_combine, 4), "combine", "last 5 draft classes"),
    "draft_picks":    (recent(nfl.load_draft_picks, 9), "draft_picks", "last 10 drafts"),
    "contracts":      (lambda S: nfl.load_contracts(), "contracts", "all contracts"),
    "trades":         (lambda S: nfl.load_trades(), "trades", "all trades"),
    "officials":      (lambda S: nfl.load_officials(seasons=S), "officials", "this season"),
    "teams":          (lambda S: nfl.load_teams(), "team_info", "all teams"),
}
NOT_AVAILABLE = {"espn_qbr": "ESPN QBR isn't in nflreadpy, so it can't be loaded here yet."}


def write_gz(df: pl.DataFrame, path: Path) -> int:
    """Gzipped CSV: DuckDB's built-in CSV reader takes it with no extension download.
    mtime=0 keeps the bytes identical when the data hasn't changed, so git sees no diff."""
    data = gzip.compress(df.write_csv().encode(), compresslevel=9, mtime=0)
    path.write_bytes(data)
    return len(data)


def newest_first(df: pl.DataFrame) -> pl.DataFrame:
    keys = [c for c in ("season", "week", "gameday", "game_date", "draft_year", "year_signed") if c in df.columns]
    return df.sort(keys, descending=True, nulls_last=True) if keys else df


def main() -> None:
    season = int(sys.argv[1]) if len(sys.argv) > 1 else nfl.get_current_season()
    S = [season]
    OUT.mkdir(parents=True, exist_ok=True)
    PREV.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    old = {}
    try:
        old = json.loads((OUT / "index.json").read_text()).get("datasets", {})
    except Exception:  # noqa: BLE001
        pass
    try:
        cat = {d["id"]: d for d in json.loads((ROOT / "data" / "catalog.json").read_text())["datasets"]}
    except Exception:  # noqa: BLE001
        cat = {}
    index = {}
    for ds_id, (fn, table, scope) in SOURCES.items():
        try:
            df = flat(fn(S))
        except Exception as e:  # noqa: BLE001
            log(f"{ds_id}: FAILED ({str(e)[:160]})")
            if ds_id in old:  # keep serving the last good copy
                index[ds_id] = {**old[ds_id], "stale": True}
            continue
        df = newest_first(df)
        path = OUT / f"{ds_id}.csv.gz"
        size = write_gz(df, path)
        if size > MAX_BYTES and "week" in df.columns:
            # too big for the repo: keep the most recent weeks that fit
            wks = sorted(df["week"].drop_nulls().unique().to_list(), reverse=True)
            keep = len(wks)
            while size > MAX_BYTES and keep > 1:
                keep -= 1
                df = df.filter(pl.col("week").is_in(wks[:keep]))
                size = write_gz(df, path)
            scope += f" (last {keep} weeks)"
        if size > MAX_BYTES:
            path.unlink()
            log(f"{ds_id}: {size/1e6:.1f} MB is too big for the site, skipped")
            continue
        prev = df.head(PREVIEW_ROWS)
        prev = prev.with_columns([pl.col(c).round(3) for c, t in prev.schema.items() if t in (pl.Float32, pl.Float64)])
        prev = prev.with_columns([pl.col(c).cast(pl.Utf8) for c, t in prev.schema.items() if t.is_temporal()])
        (PREV / f"{ds_id}.json").write_text(json.dumps({"cols": prev.columns, "rows": prev.rows()}, separators=(",", ":"), default=str))
        weeks = None
        if "week" in df.columns and df.height:
            w = df["week"].drop_nulls()
            weeks = [int(w.min()), int(w.max())] if w.len() else None
        index[ds_id] = {"table": table, "name": cat.get(ds_id, {}).get("name", ds_id), "fn": cat.get(ds_id, {}).get("fn", ""), "rows": df.height, "cols": df.width, "bytes": size, "scope": scope,
                        "weeks": weeks, "updated": now}
        log(f"{ds_id}: {df.height:,} rows x {df.width} cols, {size/1e6:.2f} MB -> {table}")
    (OUT / "index.json").write_text(json.dumps({"season": season, "updated": now, "datasets": index,
                                                "unavailable": NOT_AVAILABLE}, separators=(",", ":")))
    log(f"{len(index)} datasets, {sum(v['bytes'] for v in index.values())/1e6:.1f} MB total")


if __name__ == "__main__":
    main()
