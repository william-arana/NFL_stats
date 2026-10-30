"""Weekly data refresh for the NFL_stats site and master workbook.

Pulls the current season from nflverse and writes:
  data/latest/csv/*.csv      one file per dataset (Power Query / Google Sheets friendly)
  data/latest/master.xlsx    every dataset as its own tab
  data/site/*.json           compact column-oriented files the website reads

Run:  python scripts/update_data.py            (current season)
      python scripts/update_data.py 2025       (any season)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import nflreadpy as nfl
import polars as pl

ROOT = Path(__file__).resolve().parent.parent
CSV_DIR = ROOT / "data" / "latest" / "csv"
SITE_DIR = ROOT / "data" / "site"
XLSX = ROOT / "data" / "latest" / "master.xlsx"
OFFENSE = ["QB", "RB", "WR", "TE"]


def log(msg: str) -> None:
    print(f"[update] {msg}", flush=True)


def safe(name: str, fn):
    """Load a dataset; a single failed source shouldn't kill the whole refresh."""
    try:
        df = fn()
        log(f"{name}: {df.height:,} rows x {df.width} cols")
        return df
    except Exception as e:  # noqa: BLE001
        log(f"{name}: FAILED ({e})")
        return None


def round_floats(df: pl.DataFrame, n: int = 3) -> pl.DataFrame:
    return df.with_columns([pl.col(c).round(n) for c, t in df.schema.items() if t in (pl.Float32, pl.Float64)])


def to_columns_json(df: pl.DataFrame) -> dict:
    """Column-oriented JSON: {"cols": [...], "data": {col: [values]}} — small and fast to parse."""
    df = round_floats(df, 3)
    return {"cols": df.columns, "rows": df.height, "data": {c: df[c].to_list() for c in df.columns}}

DEFENSE = ["DE", "DT", "NT", "DL", "LB", "OLB", "ILB", "MLB", "CB", "DB", "SAF", "S", "FS", "SS"]
OLINE = ["T", "G", "C", "OT", "OG", "OL"]
OL_SLOTS = ["LT", "LG", "C", "RG", "RT"]


def build_extra(raw: dict, players, bridge, t: pl.DataFrame, injuries: dict, ps: pl.DataFrame) -> None:
    """Kickers (weekly + Sleeper default kicker points), defensive players (weekly box score + PFR pressure /
    coverage), offensive linemen (snaps, depth chart slot, team pressure / sack / run-blocking with vs without him).
    Free data has no per-lineman pressures allowed (that's PFF / tracking data), so O-line uses game-level with/without."""
    reg = ps.filter(pl.col("season_type") == "REG")

    # Kickers: Sleeper default scoring — FG 0-39 3, 40-49 4, 50+ 5, PAT 1, missed FG -1, missed PAT -1
    k = reg.filter(pl.col("position") == "K")
    if k.height:
        z = lambda c: pl.col(c).fill_null(0)  # noqa: E731
        k = k.with_columns(
            (z("fg_made_0_19") + z("fg_made_20_29") + z("fg_made_30_39")).alias("fg_0_39"),
            z("fg_made_40_49").alias("fg_40_49"), (z("fg_made_50_59") + z("fg_made_60_")).alias("fg_50"),
        ).with_columns(
            (3 * pl.col("fg_0_39") + 4 * pl.col("fg_40_49") + 5 * pl.col("fg_50") + z("pat_made")
             - z("fg_missed") - z("pat_missed")).cast(pl.Float64).alias("k_pts"))
        kk = k.select("player_id", "player_display_name", "team", "opponent_team", pl.col("week").cast(pl.Int32),
                      "fg_made", "fg_att", "fg_long", "fg_0_39", "fg_40_49", "fg_50", "fg_missed", "pat_made", "pat_att",
                      "pat_missed", "k_pts", "headshot_url")
        (SITE_DIR / "kickers.json").write_text(json.dumps(to_columns_json(kk), separators=(",", ":")))
        log(f"kickers: {kk.height} kicker-weeks")

    # Defensive players: weekly box score + snaps + PFR pressure / coverage
    dw = reg.filter(pl.col("position").is_in(DEFENSE))
    if dw.height:
        z = lambda c: pl.col(c).fill_null(0) if c in dw.columns else pl.lit(0)  # noqa: E731
        dw = dw.select("player_id", "player_display_name", "position", "team", "opponent_team", pl.col("week").cast(pl.Int32),
                       (z("def_tackles_solo") + z("def_tackle_assists")).alias("tkl"), z("def_tackles_solo").alias("solo"),
                       z("def_tackles_for_loss").alias("tfl"), z("def_sacks").alias("sk"), z("def_qb_hits").alias("qbh"),
                       z("def_interceptions").alias("int"), z("def_pass_defended").alias("pd"),
                       z("def_fumbles_forced").alias("ff"), z("def_tds").alias("td"))
        sc, pdf = raw.get("snap_counts"), raw.get("pfr_def")
        if sc is not None and bridge is not None:
            snaps = (sc.filter(pl.col("game_type") == "REG").join(bridge, on="pfr_player_id", how="inner")
                     .select("player_id", pl.col("week").cast(pl.Int32), pl.col("defense_snaps").alias("snaps"),
                             pl.col("defense_pct").alias("snap_pct")).unique(["player_id", "week"]))
            dw = dw.join(snaps, on=["player_id", "week"], how="left")
        if pdf is not None and bridge is not None:
            pf = (pdf.filter(pl.col("game_type") == "REG").join(bridge, on="pfr_player_id", how="inner")
                  .select("player_id", pl.col("week").cast(pl.Int32), pl.col("def_pressures").alias("prs"),
                          pl.col("def_times_hurried").alias("hurries"), pl.col("def_times_blitzed").alias("blitz"),
                          pl.col("def_targets").alias("tgt"), pl.col("def_completions_allowed").alias("cmp"),
                          pl.col("def_yards_allowed").alias("yds_alw"), pl.col("def_receiving_td_allowed").alias("td_alw"),
                          pl.col("def_missed_tackles").alias("mtkl")).unique(["player_id", "week"]))
            dw = dw.join(pf, on=["player_id", "week"], how="left")
        (SITE_DIR / "def_week.json").write_text(json.dumps(to_columns_json(round_floats(dw, 2)), separators=(",", ":")))
        log(f"defensive players: {dw.height} player-weeks")

    # Offensive linemen: snaps + depth chart slot + team results with / without him
    sc = raw.get("snap_counts")
    if sc is not None and bridge is not None:
        ol = (sc.filter((pl.col("game_type") == "REG") & pl.col("position").is_in(OLINE))
              .join(bridge, on="pfr_player_id", how="inner")
              .select("player_id", pl.col("player").alias("name"), "position", "team", pl.col("week").cast(pl.Int32),
                      "offense_snaps", "offense_pct").unique(["player_id", "week"]))
        tt = t.select("team", "week", pl.col("pressures_allowed").fill_null(0).alias("prs"),
                      (pl.col("attempts").fill_null(0) + pl.col("sacks_suffered").fill_null(0)).alias("db"),
                      pl.col("sacks_suffered").fill_null(0).alias("sk"), pl.col("ybc").fill_null(0).alias("ybc"),
                      pl.col("pfr_carries").fill_null(0).alias("car"))
        slot = {}
        dc = raw.get("depth_charts")
        if dc is not None and "pos_abb" in dc.columns:
            for r in dc.filter(pl.col("pos_abb").is_in(OL_SLOTS)).iter_rows(named=True):
                if r["gsis_id"]:
                    lab = r["pos_abb"] + ("" if (r["pos_rank"] or 1) == 1 else str(r["pos_rank"]))
                    if r["gsis_id"] not in slot or (r["pos_rank"] or 9) < slot[r["gsis_id"]][1]:
                        slot[r["gsis_id"]] = (lab, r["pos_rank"] or 9)
        rows = []
        for (pid,), g in ol.group_by(["player_id"]):
            g = g.sort("week")
            team = g["team"][-1]
            on_w = set(g.filter(pl.col("offense_pct") >= 0.5)["week"].to_list())
            tw_ = tt.filter(pl.col("team") == team)
            on, off = tw_.filter(pl.col("week").is_in(list(on_w))), tw_.filter(~pl.col("week").is_in(list(on_w)))
            rate = lambda d: (d["prs"].sum() / d["db"].sum()) if d.height and d["db"].sum() else None  # noqa: E731
            sk_g = lambda d: (d["sk"].sum() / d.height) if d.height else None  # noqa: E731
            ybc = lambda d: (d["ybc"].sum() / d["car"].sum()) if d.height and d["car"].sum() else None  # noqa: E731
            inj = injuries.get(pid)
            pos = g["position"][-1]
            sl = slot.get(pid, ("", 9))[0][:2]
            if pos in ("OL", "OT", "OG"):  # generic labels: use the depth chart slot when there is one
                pos = {"LT": "T", "RT": "T", "LG": "G", "RG": "G"}.get(sl, "C" if sl.startswith("C") else ("T" if pos == "OT" else "G" if pos == "OG" else "OL"))
            rows.append({"player_id": pid, "name": g["name"][-1], "pos": pos, "team": team,
                         "slot": slot.get(pid, ("", 9))[0], "g": int((g["offense_snaps"] > 0).sum()), "starts": len(on_w),
                         "snaps": int(g["offense_snaps"].sum()), "snap_pct": float(g["offense_pct"].mean()),
                         "prs_on": rate(on), "prs_off": rate(off), "g_off": off.height,
                         "sk_on": sk_g(on), "sk_off": sk_g(off), "ybc_on": ybc(on), "ybc_off": ybc(off),
                         "inj": f"{inj[0]} · {inj[1]}".strip(" ·") if inj else ""})
        if rows:
            df = round_floats(pl.DataFrame(rows), 3)
            (SITE_DIR / "oline.json").write_text(json.dumps(to_columns_json(df), separators=(",", ":")))
            log(f"offensive linemen: {df.height}")


def main() -> None:
    season = int(sys.argv[1]) if len(sys.argv) > 1 else nfl.get_current_season()
    S = [season]
    log(f"season {season}")

    raw: dict[str, pl.DataFrame | None] = {
        "player_week": safe("player_stats", lambda: nfl.load_player_stats(seasons=S)),
        "team_week": safe("team_stats", lambda: nfl.load_team_stats(seasons=S)),
        "schedule": safe("schedules", lambda: nfl.load_schedules(seasons=S)),
        "snap_counts": safe("snap_counts", lambda: nfl.load_snap_counts(seasons=S)),
        "ff_opportunity": safe("ff_opportunity", lambda: nfl.load_ff_opportunity(seasons=S)),
        "pfr_pass": safe("pfr_pass", lambda: nfl.load_pfr_advstats(seasons=S, stat_type="pass", summary_level="week")),
        "pfr_rush": safe("pfr_rush", lambda: nfl.load_pfr_advstats(seasons=S, stat_type="rush", summary_level="week")),
        "pfr_rec": safe("pfr_rec", lambda: nfl.load_pfr_advstats(seasons=S, stat_type="rec", summary_level="week")),
        "pfr_def": safe("pfr_def", lambda: nfl.load_pfr_advstats(seasons=S, stat_type="def", summary_level="week")),
        "ngs_passing": safe("ngs_passing", lambda: nfl.load_nextgen_stats(seasons=S, stat_type="passing")),
        "ngs_rushing": safe("ngs_rushing", lambda: nfl.load_nextgen_stats(seasons=S, stat_type="rushing")),
        "ngs_receiving": safe("ngs_receiving", lambda: nfl.load_nextgen_stats(seasons=S, stat_type="receiving")),
        "injuries": safe("injuries", lambda: nfl.load_injuries(seasons=S)),
        "depth_charts": safe("depth_charts", lambda: nfl.load_depth_charts(seasons=S)),
    }
    dc = raw["depth_charts"]
    if dc is not None and "dt" in dc.columns:
        # 2025+ depth charts are daily snapshots; keep only the most recent one per team
        latest = dc.group_by("team").agg(pl.col("dt").max().alias("_max"))
        raw["depth_charts"] = dc.join(latest, on="team").filter(pl.col("dt") == pl.col("_max")).drop("_max")
        log(f"depth_charts: trimmed to latest snapshot ({raw['depth_charts'].height:,} rows)")
    players = safe("players", nfl.load_players)

    # ---------- raw outputs: CSV + master.xlsx ----------
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, df in raw.items():
        if df is None:
            continue
        # nested/list columns don't fit in CSV/Excel
        flat = df.select([c for c, t in df.schema.items() if not isinstance(t, (pl.List, pl.Struct, pl.Array))])
        flat.write_csv(CSV_DIR / f"{name}.csv")
        written[name] = flat
    import xlsxwriter  # noqa: F401  (polars uses it)

    with xlsxwriter.Workbook(XLSX) as wb:
        about = wb.add_worksheet("About")
        about.write(0, 0, f"NFL_stats master workbook — {season} season")
        about.write(1, 0, f"Refreshed {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from nflverse")
        about.write(3, 0, "Tab")
        about.write(3, 1, "Rows")
        for i, (name, df) in enumerate(written.items(), start=4):
            about.write(i, 0, name)
            about.write(i, 1, df.height)
            df.write_excel(wb, worksheet=name[:31], autofit=False, table_style="Table Style Light 9", float_precision=3)
    log(f"wrote {XLSX.relative_to(ROOT)} and {len(written)} CSVs")

    # ---------- site files ----------
    ps, sched = raw["player_week"], raw["schedule"]
    games = sched.filter(pl.col("game_type") == "REG") if sched is not None else None
    last_week = int(games.filter(pl.col("home_score").is_not_null())["week"].max() or 0) if games is not None else 0

    # pfr_player_id -> gsis_id bridge for snap counts
    bridge = None
    if players is not None:
        bridge = players.select(pl.col("pfr_id").alias("pfr_player_id"), pl.col("gsis_id").alias("player_id")).drop_nulls().unique("pfr_player_id")

    # Players (weekly, offense)
    keep = ["player_id", "player_display_name", "position", "team", "opponent_team", "week",
            "completions", "attempts", "passing_yards", "passing_tds", "passing_interceptions", "sacks_suffered",
            "passing_air_yards", "passing_epa", "passing_cpoe",
            "carries", "rushing_yards", "rushing_tds", "rushing_first_downs", "rushing_epa",
            "targets", "receptions", "receiving_yards", "receiving_tds", "receiving_air_yards",
            "receiving_yards_after_catch", "receiving_first_downs", "receiving_epa",
            "target_share", "air_yards_share", "wopr", "racr",
            "rushing_fumbles_lost", "receiving_fumbles_lost", "sack_fumbles_lost",
            "fantasy_points", "fantasy_points_ppr", "headshot_url"]
    pw = ps.filter(pl.col("position").is_in(OFFENSE) & (pl.col("season_type") == "REG")).select([c for c in keep if c in ps.columns])
    pw = pw.with_columns((pl.col("fantasy_points") + (pl.col("fantasy_points_ppr") - pl.col("fantasy_points")) / 2).alias("fantasy_points_half"))

    sc = raw["snap_counts"]
    if sc is not None and bridge is not None:
        snaps = (sc.filter(pl.col("game_type") == "REG").join(bridge, on="pfr_player_id", how="inner")
                 .select("player_id", pl.col("week").cast(pl.Int32), "offense_snaps", "offense_pct"))
        pw = pw.join(snaps.unique(["player_id", "week"]), on=["player_id", "week"], how="left")
    ff = raw["ff_opportunity"]
    if ff is not None:
        ffk = ff.select(pl.col("player_id"), pl.col("week").cast(pl.Int32),
                        pl.col("total_fantasy_points_exp").alias("xfp"),
                        pl.col("total_fantasy_points_diff").alias("xfp_diff"))
        pw = pw.join(ffk.unique(["player_id", "week"]), on=["player_id", "week"], how="left")
    pp = raw["pfr_pass"]
    if pp is not None and bridge is not None:
        prs = (pp.filter(pl.col("game_type") == "REG").join(bridge, on="pfr_player_id", how="inner")
               .select("player_id", pl.col("week").cast(pl.Int32), pl.col("times_pressured").alias("qb_pressured"),
                       pl.col("times_blitzed").alias("qb_blitzed")))
        pw = pw.join(prs.unique(["player_id", "week"]), on=["player_id", "week"], how="left")
    pr = raw["pfr_rush"]
    if pr is not None and bridge is not None:
        ybc = (pr.filter(pl.col("game_type") == "REG").join(bridge, on="pfr_player_id", how="inner")
               .select("player_id", pl.col("week").cast(pl.Int32),
                       pl.col("rushing_yards_before_contact").alias("ybc"), pl.col("rushing_yards_after_contact").alias("yac_rush"),
                       pl.col("rushing_broken_tackles").alias("broken_tackles")))
        pw = pw.join(ybc.unique(["player_id", "week"]), on=["player_id", "week"], how="left")
    inj = raw["injuries"]
    if inj is not None:
        wk = inj["week"].max()
        short = {"Did Not Participate In Practice": "DNP", "Limited Participation in Practice": "Limited",
                 "Full Participation in Practice": "Full"}
        cur = inj.filter(pl.col("week") == wk)
        injuries = {}
        for r in cur.unique("gsis_id", keep="last").iter_rows(named=True):
            status = r["report_status"] or (f"Practice: {short.get(r['practice_status'], r['practice_status'])}" if r["practice_status"] else None)
            if r["gsis_id"] and status:
                injuries[r["gsis_id"]] = [status, r["report_primary_injury"] or r["practice_primary_injury"] or "", int(wk)]
    else:
        injuries = {}

    # Teams (weekly): offense + what the defense allowed (= opponent's offense that game)
    tw = raw["team_week"].filter(pl.col("season_type") == "REG")
    tcols = ["team", "opponent_team", "week", "attempts", "completions", "passing_yards", "passing_tds",
             "passing_interceptions", "sacks_suffered", "passing_epa", "carries", "rushing_yards", "rushing_tds",
             "rushing_epa", "def_sacks", "def_qb_hits", "def_interceptions", "fumble_recovery_opp", "def_tds",
             "def_safeties", "special_teams_tds", "def_fg_blocks", "def_punt_blocks", "def_pat_blocks", "def_fumbles_forced"]
    t = tw.select([c for c in tcols if c in tw.columns])
    if games is not None:
        g = games.filter(pl.col("home_score").is_not_null())
        sc_long = pl.concat([
            g.select(pl.col("home_team").alias("team"), pl.col("week").cast(pl.Int32), pl.col("home_score").alias("points_for"), pl.col("away_score").alias("points_against")),
            g.select(pl.col("away_team").alias("team"), pl.col("week").cast(pl.Int32), pl.col("away_score").alias("points_for"), pl.col("home_score").alias("points_against")),
        ])
        t = t.join(sc_long, on=["team", "week"], how="left")
    if pp is not None:
        t = t.join(pp.filter(pl.col("game_type") == "REG").group_by("team", pl.col("week").cast(pl.Int32))
                   .agg(pl.col("times_pressured").sum().alias("pressures_allowed")), on=["team", "week"], how="left")
    pdf = raw["pfr_def"]
    if pdf is not None:
        t = t.join(pdf.filter(pl.col("game_type") == "REG").group_by("team", pl.col("week").cast(pl.Int32))
                   .agg(pl.col("def_pressures").sum().alias("def_pressures"), pl.col("def_times_blitzed").sum().alias("def_blitzes")),
                   on=["team", "week"], how="left")
    if pr is not None:
        # team-level line play: yards before contact is mostly the O-line's doing
        t = t.join(pr.filter(pl.col("game_type") == "REG").group_by("team", pl.col("week").cast(pl.Int32))
                   .agg(pl.col("carries").sum().alias("pfr_carries"),
                        pl.col("rushing_yards_before_contact").sum().alias("ybc"),
                        pl.col("rushing_yards_after_contact").sum().alias("yac_rush"),
                        pl.col("rushing_broken_tackles").sum().alias("broken_tackles")),
                   on=["team", "week"], how="left")
    t = t.with_columns((pl.col("passing_yards") + pl.col("rushing_yards")).alias("total_yards"))
    opp = t.select(pl.col("team").alias("opponent_team"), "week",
                   pl.col("total_yards").alias("yards_allowed"), pl.col("passing_yards").alias("pass_yards_allowed"),
                   pl.col("rushing_yards").alias("rush_yards_allowed"),
                   (pl.col("passing_epa") + pl.col("rushing_epa")).alias("epa_allowed"))
    t = t.join(opp, on=["opponent_team", "week"], how="left")
    pa = pl.col("points_against")
    pa_pts = (pl.when(pa == 0).then(10).when(pa <= 6).then(7).when(pa <= 13).then(4).when(pa <= 20).then(1)
              .when(pa <= 27).then(0).when(pa <= 34).then(-1).otherwise(-4))
    # Sleeper D/ST scoring used in both leagues: sack 1, INT 2, fumble rec 2, forced fumble 1, TD 6,
    # safety 2, blocked kick 2, points-allowed tiers. Return yards / yards allowed aren't scored.
    t = t.with_columns((pl.col("def_sacks") + 2 * pl.col("def_interceptions") + 2 * pl.col("fumble_recovery_opp")
                        + pl.col("def_fumbles_forced").fill_null(0)
                        + 6 * (pl.col("def_tds") + pl.col("special_teams_tds")) + 2 * pl.col("def_safeties")
                        + 2 * (pl.col("def_fg_blocks") + pl.col("def_punt_blocks") + pl.col("def_pat_blocks")) + pa_pts
                        ).alias("dst_pts"))

    # Schedule (all games, with implied team totals)
    sch = games.select("game_id", pl.col("week").cast(pl.Int32), "gameday", "gametime", "weekday", "away_team", "home_team",
                       "away_score", "home_score", "spread_line", "total_line", "roof", "temp", "wind", "away_rest", "home_rest",
                       "div_game", "away_qb_name", "home_qb_name", "stadium")
    # nflverse spread_line is from the home team's view: positive = home favored
    sch = sch.with_columns(((pl.col("total_line") + pl.col("spread_line")) / 2).alias("home_implied"),
                           ((pl.col("total_line") - pl.col("spread_line")) / 2).alias("away_implied"))

    # Defenders (season to date): coverage weak spots + top pass rushers, per team
    defenders = None
    if pdf is not None:
        d = pdf.filter(pl.col("game_type") == "REG")
        if players is not None:
            d = d.join(players.select(pl.col("pfr_id").alias("pfr_player_id"), pl.col("position").alias("pos")).drop_nulls().unique("pfr_player_id"),
                       on="pfr_player_id", how="left")
        else:
            d = d.with_columns(pl.lit(None).alias("pos"))
        defenders = (d.group_by("pfr_player_id").agg(
                pl.col("pfr_player_name").last().alias("name"), pl.col("pos").last(),
                pl.col("team").sort_by("week").last().alias("team"), pl.len().alias("g"),
                pl.col("def_targets").sum().alias("tgt"), pl.col("def_completions_allowed").sum().alias("cmp"),
                pl.col("def_yards_allowed").sum().alias("yds"), pl.col("def_receiving_td_allowed").sum().alias("td"),
                pl.col("def_ints").sum().alias("int"), pl.col("def_pressures").sum().alias("prs"),
                pl.col("def_sacks").sum().alias("sk"), pl.col("def_times_hitqb").sum().alias("hits"),
                pl.col("def_missed_tackles").sum().alias("mtkl"), pl.col("def_tackles_combined").sum().alias("tkl"))
            .with_columns(
                # NFL passer rating formula with targets as attempts
                pl.when(pl.col("tgt") > 0).then(
                    (pl.min_horizontal(pl.max_horizontal(((pl.col("cmp") / pl.col("tgt")) - 0.3) * 5, 0), 2.375)
                     + pl.min_horizontal(pl.max_horizontal(((pl.col("yds") / pl.col("tgt")) - 3) * 0.25, 0), 2.375)
                     + pl.min_horizontal(pl.max_horizontal((pl.col("td") / pl.col("tgt")) * 20, 0), 2.375)
                     + pl.min_horizontal(pl.max_horizontal(2.375 - (pl.col("int") / pl.col("tgt")) * 25, 0), 2.375)) / 6 * 100
                ).alias("rating"))
            .filter((pl.col("tgt") > 0) | (pl.col("prs") > 0))
            .drop("pfr_player_id"))
        (SITE_DIR / "defenders.json").write_text(json.dumps(to_columns_json(defenders), separators=(",", ":")))
        log(f"defenders: {defenders.height}")

    # ---------- kickers, defensive players, offensive linemen (Stats tabs + cards) ----------
    try:
        build_extra(raw, players, bridge, t, injuries, ps)
    except Exception as e:  # noqa: BLE001  (never let these break the main refresh)
        log(f"extra (kickers/defenders/oline): FAILED ({e})")

    meta = {"season": season, "last_completed_week": last_week, "next_week": last_week + 1,
            "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "player_rows": pw.height, "team_rows": t.height, "injuries": injuries}
    (SITE_DIR / "players.json").write_text(json.dumps(to_columns_json(pw), separators=(",", ":")))
    (SITE_DIR / "teams.json").write_text(json.dumps(to_columns_json(t), separators=(",", ":")))
    (SITE_DIR / "schedule.json").write_text(json.dumps(to_columns_json(sch), separators=(",", ":")))
    (SITE_DIR / "meta.json").write_text(json.dumps(meta, separators=(",", ":")))
    try:
        tm = nfl.load_teams()
        current = set(sch["home_team"].to_list()) | set(sch["away_team"].to_list())
        meta_t = {}
        for r in tm.iter_rows(named=True):
            if r["team_abbr"] in current:
                logo = r["team_logo_espn"] or ""
                slug = logo.rsplit("/", 1)[-1].split(".")[0] if logo else r["team_abbr"].lower()
                meta_t[r["team_abbr"]] = {"name": r["team_name"], "nick": r["team_nick"], "conf": r["team_conf"], "div": r["team_division"],
                                          "color": r["team_color"], "color2": r["team_color2"], "espn": slug,
                                          "logo": f"https://a.espncdn.com/combiner/i?img=/i/teamlogos/nfl/500/{slug}.png&h=96&w=96"}
        (SITE_DIR / "teams_meta.json").write_text(json.dumps(meta_t, separators=(",", ":")))
    except Exception as e:  # noqa: BLE001
        log(f"teams_meta: FAILED ({e})")
    if players is not None:
        ids = players.select("gsis_id", "espn_id").drop_nulls()
        keep_ids = set(pw["player_id"].to_list())
        (SITE_DIR / "ids.json").write_text(json.dumps({g: str(e).split(".")[0] for g, e in ids.iter_rows() if g in keep_ids}, separators=(",", ":")))
    log(f"site data: {pw.height} player-weeks, {t.height} team-weeks, {sch.height} games, through week {last_week}")


if __name__ == "__main__":
    main()
