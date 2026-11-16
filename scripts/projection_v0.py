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


def moved_teams(site):
    """{gsis_id: current team} for players traded / signed elsewhere since their last game (status.json "moved", from Sleeper)."""
    f = Path(site) / "status.json" if site is not None else None
    if not f or not f.exists():
        return {}
    return {k: v[1] for k, v in (json.loads(f.read_text()).get("moved") or {}).items()}


def ours(P, K, S, week, T=None, moved=None):
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
        l3 = h.tail(3); pos = h.position.iloc[-1]; team = (moved or {}).get(pid, h.team.iloc[-1])  # traded: new team's game
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
            t = (moved or {}).get(pid, h.team.iloc[-1])
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
    for pid, v in (status.get("p") or {}).items():  # Sleeper IR / PUP, or no NFL team (released)
        if v.get("s") in ("IR", "PUP"):
            out[pid] = (MULT["out"], f"Sleeper {v['s']}")
        elif v.get("s") == "FA":
            out[pid] = (0.0, "released (no NFL team on Sleeper)")
    try:  # backup QBs don't start: 0 (notes repo docs/backtests/qb-starter)
        j = json.loads((site / "players.json").read_text())
        Pq = pd.DataFrame({c: j["data"][c] for c in ("player_id", "position", "team", "week", "attempts", "offense_pct")})
        lab = site.parent / "lab" / "injuries.csv.gz"
        Iq = pd.read_csv(lab, usecols=["season", "week", "gsis_id", "report_status", "practice_status"]) if lab.exists() else None
        if Iq is not None and "season" in meta:
            Iq = Iq[Iq.season == meta["season"]]
        for pid, why in qb_backups(Pq, Iq, week, moved_teams(site)).items():
            out[pid] = (0.0, why)
        res = status.get("p") or {}  # IR/PUP aren't on the weekly report: those are hurt, handled below
        for pid in lost_role(Pq, S, Iq, week):
            if pid not in res:
                out[pid] = (0.0, "no offensive snaps in his team's last 2 games")
    except Exception as e:  # never break the projection over this
        print(f"qb_backups skipped: {e}")
    for pid, v in (meta.get("injuries") or {}).items():  # official report wins
        if len(v) > 2 and v[2] != week:
            continue
        s = (v[0] or "").lower()
        if s in ("out", "doubtful"):
            out[pid] = (MULT["out"], f"report: {v[0]}")
        elif s == "questionable":
            out[pid] = (MULT["q"], "report: Questionable")
    return out


def qb_backups(P, I, week, moved=None):
    """{gsis_id: reason} for QBs who won't start in `week` (projected 0). Box scores + injury report only, so it backtests.
    Starter of a team's last game keeps the job, except: the season's regular starter (most starts) who lost it to injury
    (on an injury report after his last start) gets it back once this week's report has him practicing Full/Limited and not Out/Doubtful. Benched starters stay benched."""
    q = P[(P.week < week) & (P.position == "QB")].copy()
    if q.empty:
        return {}
    q["attempts"] = q.attempts.fillna(0)
    st = q.sort_values("attempts", ascending=False).drop_duplicates(["team", "week"])  # starter = most attempts that game
    st = st[st.attempts >= 5]
    inj = I[I.week <= week] if I is not None and len(I) else pd.DataFrame(columns=["week", "gsis_id", "report_status"])
    wk = inj[inj.week == week]
    out_now = set(wk[wk.report_status.isin(["Out", "Doubtful"])].gsis_id)
    # back from injury = on this week's report, practicing Full/Limited, not ruled out (IR players aren't on the report)
    back = set(wk[wk.practice_status.str.startswith(("Full", "Limited"), na=False) & ~wk.report_status.isin(["Out", "Doubtful"])].gsis_id) \
        if "practice_status" in wk else set()
    starters = {}
    for team, g in st.sort_values("week").groupby("team"):
        last = g.player_id.iloc[-1]
        reg = g.player_id.value_counts().idxmax()
        qb1 = last
        if reg != last and reg in back:
            lw = g[g.player_id == reg].week.max()
            if ((inj.gsis_id == reg) & (inj.week > lw)).any():  # he was hurt after his last start, now not ruled out
                qb1 = reg
        if qb1 in out_now and last not in out_now:
            qb1 = last
        starters[team] = qb1
    cur = q.sort_values("week").groupby("player_id").team.last()  # each QB's latest team
    for pid, t in (moved or {}).items():  # traded QB: backup on his new team unless he started its last game
        if pid in cur.index:
            cur[pid] = t
    return {pid: f"backup QB ({starters[t]} starts)" for pid, t in cur.items() if t in starters and pid != starters[t]}


def lost_role(P, S, I, week, k=2):
    """Players with no offensive snaps in each of their team's last k games before `week` who weren't on any injury report
    in weeks week-3..week (so not hurt, just out of the rotation, e.g. Emanuel Wilson once Charbonnet + Price returned).
    Backtest 2026 wks 3-9: 50 player-weeks averaged 0.25 PPR (1 scored 5+); setting them to 0 cut the miss 5.45 -> 5.21."""
    tg = pd.concat([S[["week", "home_team"]].rename(columns={"home_team": "team"}), S[["week", "away_team"]].rename(columns={"away_team": "team"})])
    last = tg[tg.week < week].sort_values("week").groupby("team").tail(k)
    prev = P[(P.week < week) & P.position.isin(["QB", "RB", "WR", "TE"])].sort_values("week")
    if prev.empty:
        return set()
    team = prev.groupby("player_id").team.last()
    played = prev[prev.offense_pct.fillna(0) > 0].groupby("player_id").week.agg(set)
    tw = last.groupby("team").week.agg(set)
    hurt = set(I[(I.week >= week - 3) & (I.week <= week)].gsis_id) if I is not None and len(I) else set()
    return {pid for pid, t in team.items() if t in tw and len(tw[t]) == k and not (played.get(pid, set()) & tw[t]) and pid not in hurt}


def ours_v01(P, K, S, week, T=None, site=None):
    """v0 x play_mult. Same columns as ours() plus `avail` (multiplier) and `why`."""
    o = ours(P, K, S, week, T, moved_teams(site))
    if site is None or o.empty:
        return o.assign(avail=1.0, why="")
    m = play_mult(site, week, S)
    o["avail"] = [m.get(k, (1.0, ""))[0] for k in o.key]
    o["why"] = [m.get(k, (1.0, ""))[1] for k in o.key]
    o["ours_ppr"] = (o.ours_ppr * o.avail).round(2)
    return o


# ---------- ROS v0 (notes repo docs/backtests/ros) ----------
# Rest-of-season PPR through week 18 = this week's v0.1 + v0's per-game number for every later team game x the share of
# team games a fantasy-relevant player actually plays (2022-24). An estimated implied total per future game added nothing
# (hurt QBs), so later games use this week's number. Backtest: beats season avg x games left for RB/WR/TE in 2025 and 2026
# (rank corr +0.05 to +0.13), ties for QBs. Sleeper IR/PUP or a hurt regular QB1: skips 3 more weeks; out for the season,
# backup QB, released, or no offensive snaps in his team's last 2 games (not hurt): 0.
ROS_LAST_WEEK = 18
GAMES_PLAYED = {"QB": 0.764, "RB": 0.783, "WR": 0.799, "TE": 0.794}


def ros(P, K, S, week, T=None, site=None):
    """{gsis_id: rest-of-season PPR, weeks week..18} for QB/RB/WR/TE."""
    mv = moved_teams(site)
    v0 = ours(P, K, S, week, T, mv)
    if v0.empty:
        return {}
    v1 = ours_v01(P, K, S, week, T, site).set_index("key").ours_ppr
    st = {}
    if site is not None and (Path(site) / "status.json").exists():
        st = json.loads((Path(site) / "status.json").read_text()).get("p") or {}
    m = play_mult(site, week, S) if site is not None else {}
    pos = P[P.week < week].sort_values("week").groupby("player_id")[["position", "team"]].last()
    fut = S[(S.week > week) & (S.week <= ROS_LAST_WEEK)]
    left = pd.concat([fut.home_team, fut.away_team]).value_counts()
    # each team's regular starting QB (most starts this season): hurt, not benched, so he comes back later
    q = P[(P.week < week) & (P.position == "QB")].fillna({"attempts": 0}).sort_values("attempts", ascending=False).drop_duplicates(["team", "week"])
    q = q[q.attempts >= 5]
    reg = set(q.groupby("team").player_id.agg(lambda x: x.value_counts().idxmax())) if len(q) else set()
    out = {}
    for r in v0.itertuples():
        if r.key not in pos.index or pos.position[r.key] not in GAMES_PLAYED:
            continue
        p, team = pos.position[r.key], mv.get(r.key, pos.team[r.key])
        why = m.get(r.key, (1.0, ""))[1]
        s = st.get(r.key) or {}
        hurt_qb1 = why.startswith("backup QB") and r.key in reg and r.key not in mv  # a traded QB isn't his new team's QB1
        gone = why.startswith(("released", "no offensive snaps")) or (why.startswith("backup QB") and not hurt_qb1)
        if s.get("season") or gone:
            out[r.key] = 0.0
            continue
        n = int(left.get(team, 0))
        if s.get("s") in ("IR", "PUP") or hurt_qb1:  # injured regular QB1: back after ~3 more weeks
            n = max(0, n - 3)
        out[r.key] = round(float(v1.get(r.key, r.ours_ppr)) + GAMES_PLAYED[p] * r.ours_ppr * n, 1)
    return out
