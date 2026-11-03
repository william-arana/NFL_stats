"""Projection v0 (NFL_stats' own weekly projection). Same code as the private projection log.
Model: data/model/model_v0.json — per-position linear model on the backtested signals (season avg, last 3, Vegas implied,
xFP, snap % trend, share of team carries + targets, target share), K = implied + kicker avg, D/ST = opponent implied +
opponent sack rate + giveaways. Uses only weeks before `week`."""
import json
from pathlib import Path
import pandas as pd

MODEL = Path(__file__).resolve().parents[1] / "data" / "model" / "model_v0.json"


def ours(P, K, S, week, T=None):
    """Our projection v0 (projections/model_v0.json): per-position linear model on the backtested signals
    (season avg, last 3, Vegas implied, xFP, snap % trend, share of team carries + targets, target share). K: implied + kicker avg."""
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
        for pid, h in K[K.week < week].sort_values("week").groupby("player_id"):
            t = h.team.iloc[-1]
            if t in imp and not pd.isna(imp[t]):
                out.append({"key": pid, "ours_ppr": round(c["Intercept"] + c["implied"] * imp[t] + c["k_avg"] * h.k_pts.mean(), 2), "ours_n_games": len(h)})
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


