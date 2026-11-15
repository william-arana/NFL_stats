"""Projection v0 (NFL_stats' own weekly projection). Same code as the private projection log.
Model: data/model/model_v0.json — per-position linear model on the backtested signals (season avg, last 3, Vegas implied,
xFP, snap % trend, share of team carries + targets, target share), K = implied + spread + dome + kicker avg, D/ST = opponent implied +
opponent sack rate + giveaways. Uses only weeks before `week`."""
import json
from pathlib import Path
import pandas as pd

MODEL = Path(__file__).resolve().parents[1] / "data" / "model" / "model_v0.json"


DOMES = {"ARI", "ATL", "DAL", "DET", "HOU", "IND", "LA", "LV", "MIN", "NO"}  # dome or retractable roof (home team)


def k_context(g):
    """Per team for this week's games: points favored by (spread, + = favorite) and 1 if indoors (dome/closed roof).
    Roof comes from the schedule; when it's blank (future games) fall back to the home team's stadium type."""
    fav, dome = {}, {}
    for r in g.itertuples():
        sp = 0.0 if pd.isna(r.spread_line) else float(r.spread_line)
        roof = getattr(r, "roof", None)
        ind = float(roof in ("dome", "closed")) if isinstance(roof, str) else float(r.home_team in DOMES)
        fav[r.home_team], fav[r.away_team] = sp, -sp
        dome[r.home_team] = dome[r.away_team] = ind
    return fav, dome


def ours(P, K, S, week, T=None):
    """Our projection v0 (projections/model_v0.json): per-position linear model on the backtested signals
    (season avg, last 3, Vegas implied, xFP, snap % trend, share of team carries + targets, target share). K: implied + spread + dome + kicker avg."""
    if not MODEL.exists():
        return pd.DataFrame(columns=["key", "ours_ppr", "ours_n_games"])
    M = json.loads(MODEL.read_text())
    g = S[S.week == week]
    imp = {**dict(zip(g.home_team, g.home_implied)), **dict(zip(g.away_team, g.away_implied))}
    prev = P[(P.week < week) & P.position.isin(["QB", "RB", "WR", "TE"])].copy()
    for c in ("carries", "targets"):
        prev[c] = prev[c].fillna(0)
    tm = prev.groupby(["team", "week"])[["carries", "targets"]].sum().sum(axis=1).rename("tm")
    prev = prev.join(tm, on=["team", "week"])
    prev["opp_share"] = (prev.carries + prev.targets) / prev.tm.replace(0, float("nan"))
    prev = prev.sort_values("week")
    out = []
    for pid, h in prev.groupby("player_id"):
        l3 = h.tail(3); pos = h.position.iloc[-1]; team = h.team.iloc[-1]
        if pos not in M["coef"] or team not in imp or pd.isna(imp[team]):
            continue
        f = {"ppr_avg": h.fantasy_points_ppr.mean(), "ppr_l3": l3.fantasy_points_ppr.mean(), "implied": imp[team],
             "xfp_l3": l3.xfp.mean(), "xfp_avg": h.xfp.mean(), "snap_avg": h.offense_pct.mean(),
             "snap_trend": l3.offense_pct.mean() - h.offense_pct.mean(), "opp_share_avg": h.opp_share.mean(),
             "opp_share_trend": l3.opp_share.mean() - h.opp_share.mean(), "target_share_l3": l3.target_share.mean()}
        f = {k: (0.0 if pd.isna(v) else float(v)) for k, v in f.items()}
        c = M["coef"][pos]
        out.append({"key": pid, "ours_ppr": round(c["Intercept"] + sum(c[k] * f[k] for k in f), 2), "ours_n_games": len(h)})
    if not K.empty and "K" in M["coef"]:
        c = M["coef"]["K"]
        fav, dome = k_context(g)
        for pid, h in K[K.week < week].sort_values("week").groupby("player_id"):
            t = h.team.iloc[-1]
            if t in imp and not pd.isna(imp[t]):
                v = c["Intercept"] + c["implied"] * imp[t] + c["k_avg"] * h.k_pts.mean()
                v += c.get("fav_by", 0) * fav.get(t, 0) + c.get("dome", 0) * dome.get(t, 0)
                out.append({"key": pid, "ours_ppr": round(v, 2), "ours_n_games": len(h)})
    if "DEF" in M["coef"] and T is not None:
        c = M["coef"]["DEF"]
        t = T[T.week < week].copy()
        fl = t[["week", "team", "fumble_recovery_opp"]].rename(columns={"team": "opponent_team", "fumble_recovery_opp": "fum_lost"})
        t = t.merge(fl, on=["week", "opponent_team"], how="left")  # an offense's fumbles lost = recoveries by the defense it played
        t["give"] = t.passing_interceptions.fillna(0) + t.fum_lost.fillna(0)
        by = t.groupby("team")
        sr = by.sacks_suffered.sum() / (by.attempts.sum() + by.sacks_suffered.sum())
        give, dst, n = by.give.mean(), by.dst_pts.mean(), by.size()
        oimp = {**dict(zip(g.home_team, g.away_implied)), **dict(zip(g.away_team, g.home_implied))}
        opp = {**dict(zip(g.home_team, g.away_team)), **dict(zip(g.away_team, g.home_team))}
        for tm in opp:
            o = opp[tm]
            if tm in dst and o in sr and not pd.isna(oimp.get(tm)):
                out.append({"key": "DEF:" + tm, "ours_ppr": round(c["Intercept"] + c["dst_avg"] * dst[tm] + c["opp_implied"] * oimp[tm]
                                                                   + c["o_sack_rate"] * sr[o] + c["o_give_pg"] * give[o], 2), "ours_n_games": int(n[tm])})
    return pd.DataFrame(out)




# ---------- v0.1: availability (docs: notes repo docs/backtests/presser-signals, 2026 wks 3-9) ----------
# v0 has no idea who's hurt. v0.1 = v0 x chance he plays. Backtest: MAE 6.35 -> 5.57, better every week, bias +1.70 -> +0.68.
# Official game status first (Out/Doubtful 0% played, Questionable 67%), then Sleeper IR/PUP, then the head coach's
# latest presser injury status before the game when the report says nothing (coach out/IR: 7% played; unclear/Q: 76%).
# A coach downgrade is ignored when the report shows he practiced Full/Limited (all 30 such cases played).
# Up/down/role/usage presser talk does NOT move points among players who play, so it isn't used.
MULT = {"out": 0.0, "coach_out": 0.15, "q": 0.73, "coach_unclear": 0.75}


def play_mult(site, week, S):
    """{gsis_id: (multiplier, reason)} for players whose chance of playing is in doubt in `week`. `site` = data/site dir."""
    site = Path(site)
    rd = lambda n: json.loads((site / n).read_text()) if (site / n).exists() else {}  # noqa: E731
    meta, status = rd("meta.json"), rd("status.json")
    out = {}
    g = S[S.week == week]
    gday = {**dict(zip(g.home_team, g.gameday)), **dict(zip(g.away_team, g.gameday))}
    # coach's latest injury status per player, from pressers before his team's game (<= 8 days)
    coach = {}
    pdir = site.parent / "pressers"
    days = sorted({d for d in gday.values() if isinstance(d, str)})
    if pdir.exists() and days:
        lo = (pd.Timestamp(days[0]) - pd.Timedelta(days=8)).strftime("%Y-%m-%d")
        for f in sorted(pdir.glob("20*.json")):
            if not (lo <= f.stem < days[-1]):
                continue
            for x in json.loads(f.read_text()):
                gd = gday.get(x.get("team"))
                if not gd or not (x["date"] < gd and (pd.Timestamp(gd) - pd.Timestamp(x["date"])).days <= 8):
                    continue
                for i in x.get("injuries") or []:
                    if i.get("player_id"):
                        prev = coach.get(i["player_id"])
                        if prev is None or x["date"] >= prev[0]:
                            coach[i["player_id"]] = (x["date"], (i.get("status") or "").lower(), x.get("coach", ""))
    practiced = {pid for pid, v in (meta.get("injuries") or {}).items()  # practiced Full/Limited, no game status: he plays (backtest 30/30)
                 if (len(v) < 3 or v[2] == week) and (v[0] or "") in ("Practice: Full", "Practice: Limited")}
    for pid, (d, st, who) in coach.items():
        if pid in practiced:
            continue
        if st in ("out", "doubtful", "ir"):
            out[pid] = (MULT["coach_out"], f"coach: {st} ({who} {d})")
        elif st in ("unclear", "questionable"):
            out[pid] = (MULT["coach_unclear"], f"coach: {st} ({who} {d})")
    for pid, v in (status.get("p") or {}).items():  # Sleeper IR / PUP
        if v.get("s") in ("IR", "PUP"):
            out[pid] = (MULT["out"], f"Sleeper {v['s']}")
    for pid, v in (meta.get("injuries") or {}).items():  # official report wins
        if len(v) > 2 and v[2] != week:
            continue
        s = (v[0] or "").lower()
        if s in ("out", "doubtful"):
            out[pid] = (MULT["out"], f"report: {v[0]}")
        elif s == "questionable":
            out[pid] = (MULT["q"], "report: Questionable")
    return out


def ours_v01(P, K, S, week, T=None, site=None):
    """v0 x play_mult. Same columns as ours() plus `avail` (multiplier) and `why`."""
    o = ours(P, K, S, week, T)
    if site is None or o.empty:
        return o.assign(avail=1.0, why="")
    m = play_mult(site, week, S)
    o["avail"] = [m.get(k, (1.0, ""))[0] for k in o.key]
    o["why"] = [m.get(k, (1.0, ""))[1] for k in o.key]
    o["ours_ppr"] = (o.ours_ppr * o.avail).round(2)
    return o
