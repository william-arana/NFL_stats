"""Weekly rundown articles for the Home page (67FFL).

  recap   (Tuesday, after the data refresh): your week, lineup hindsight ("could you have known?"), top performers,
          on-field injuries, around the league, grading of last week's preview.
  preview (Thursday): your best lineup by our projection, close calls with reasons, waiver adds, K/DEF streamers,
          buy low / sell high, trade fits around the league.

Facts are computed here from the site's data + Sleeper (league scoring, starters, points). Claude writes the prose from
the facts only (ANTHROPIC_API_KEY); without a key the article is rendered from templates. Sleeper/ESPN projections are
never used or shown (benchmarks stay private); "ours" = projection v0 (scripts/projection_v0.py).

Output: data/site/articles/<season>-w<WW>-<kind>.json (+ index.json).
Usage: python scripts/build_articles.py --kind recap|preview [--week N] [--no-llm] [--dry-run] [--fixture matchups.json]"""
import argparse, json, os, re, sys, datetime as dt
from pathlib import Path
import pandas as pd, requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from projection_v0 import ours  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SITE, OUT = ROOT / "data" / "site", ROOT / "data" / "site" / "articles"
API = "https://api.sleeper.app/v1"
UA = {"User-Agent": "NFL_stats weekly articles (personal, non-commercial)"}
SLOT_OK = {"QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "K": {"K"}, "DEF": {"DEF"},
           "FLEX": {"RB", "WR", "TE"}, "SUPER_FLEX": {"QB", "RB", "WR", "TE"}, "REC_FLEX": {"WR", "TE"}, "WRRB_FLEX": {"WR", "RB"}}
INJ_RE = re.compile(r"(left (sunday's|monday's|thursday's|saturday's|the) (game|contest|win|loss)|exited|was carted|carted off|won't return|will not return|did not return|didn't return|ruled out for the (rest|remainder)|questionable to return|doubtful to return|was evaluated for a concussion|entered the concussion protocol|went down with|was helped off|suffered an? [a-z ]{0,40}(injury|sprain|strain|tear|fracture|contusion) (in|during) (sunday's|monday's|thursday's|saturday's|the) (game|contest|win|loss|first|second|third|fourth))", re.I)
NOT_INJ = re.compile(r"(off the (week \d+ )?injury report|not worried|expected to be (ok|fine)|no injury)", re.I)
MODEL_ID = os.environ.get("ARTICLE_MODEL", "claude-sonnet-5-5")


# ---------------------------------------------------------------- data
def rows(j):
    return pd.DataFrame({c: j["data"][c] for c in j["cols"]})


def J(n):
    return json.loads((SITE / n).read_text())


def load():
    meta = J("meta.json")
    P, T, S = rows(J("players.json")), rows(J("teams.json")), rows(J("schedule.json"))
    K = rows(J("kickers.json")) if (SITE / "kickers.json").exists() else pd.DataFrame()
    smap = J("sleeper_map.json")
    L = J("leagues.json")
    lg = next(x for x in L["leagues"] if str(x.get("id")) == "1396022326247591936")
    status = J("status.json") if (SITE / "status.json").exists() else {}
    return meta, P, T, S, K, smap, lg, status


def sleeper(path):
    r = requests.get(API + path, headers=UA, timeout=60)
    r.raise_for_status()
    return r.json()


def names_index(P, K, smap):
    """key → (name, pos, team). Keys: gsis ids, DEF:<TEAM>."""
    idx = {}
    for r in P.sort_values("week").itertuples():
        idx[r.player_id] = (r.player_display_name, r.position, r.team)
    if not K.empty:
        for r in K.sort_values("week").itertuples():
            idx[r.player_id] = (r.player_display_name, "K", r.team)
    for t in set(smap.get("team_fix", {}).values()) | set(P.team.dropna()):
        idx["DEF:" + t] = (t + " D/ST", "DEF", t)
    return idx


def to_key(sid, smap):
    sid = str(sid)
    if sid.isalpha() and len(sid) <= 3:
        return "DEF:" + smap.get("team_fix", {}).get(sid, sid)
    return smap["map"].get(sid)


# ---------------------------------------------------------------- lineup helpers
def best_lineup(cands, slots):
    """cands: list of dicts with key, pos, v. Fill fixed slots first (best v), then flex slots. Returns [(slot, cand)]."""
    left = sorted([c for c in cands if c.get("v") is not None], key=lambda c: -c["v"])
    used, out = set(), []
    order = sorted(slots, key=lambda s: len(SLOT_OK.get(s, {s})))  # narrowest slots first
    for s in order:
        ok = SLOT_OK.get(s, {s})
        pick = next((c for c in left if c["key"] not in used and c["pos"] in ok), None)
        if pick:
            used.add(pick["key"])
        out.append((s, pick))
    return out


def signals(key, P, T, S, week, proj):
    """Pre-game numbers for one player (only games before `week`)."""
    o = proj.get(key)
    if key.startswith("DEF:"):
        tm = key[4:]
        h = T[(T.team == tm) & (T.week < week)]
        g = S[S.week == week]
        opp = dict(zip(g.home_team, g.away_team)) | dict(zip(g.away_team, g.home_team))
        oimp = dict(zip(g.home_team, g.away_implied)) | dict(zip(g.away_team, g.home_implied))
        return {"ours": o, "season_avg": rnd(h.dst_pts.mean()), "opp": opp.get(tm), "opp_implied": rnd(oimp.get(tm))}
    h = P[(P.player_id == key) & (P.week < week)].sort_values("week")
    if h.empty:
        return {"ours": o}
    l3 = h.tail(3)
    tm = h.team.iloc[-1]
    g = S[S.week == week]
    imp = dict(zip(g.home_team, g.home_implied)) | dict(zip(g.away_team, g.away_implied))
    opp = dict(zip(g.home_team, g.away_team)) | dict(zip(g.away_team, g.home_team))
    return {"ours": o, "season_avg": rnd(h.fantasy_points_ppr.mean()), "last3": rnd(l3.fantasy_points_ppr.mean()),
            "snap_pct_season": pct(h.offense_pct.mean()), "snap_pct_last3": pct(l3.offense_pct.mean()),
            "xfp_last3": rnd(l3.xfp.mean()), "target_share_last3": pct(l3.target_share.mean()),
            "team_implied": rnd(imp.get(tm)), "opp": opp.get(tm), "games": int(len(h))}


def rnd(v, n=1):
    try:
        return None if v is None or pd.isna(v) else round(float(v), n)
    except (TypeError, ValueError):
        return None


def pct(v):
    return None if v is None or pd.isna(v) else int(round(float(v) * 100))


# ---------------------------------------------------------------- facts
def injuries_on_field(P, week, S, idx, owner_of):
    """News items about players who played this week that say they got hurt / left the game, dated game week."""
    g = S[S.week == week]
    if g.empty:
        return []
    start = pd.to_datetime(g.gameday.min()) - pd.Timedelta(days=1)
    end = pd.to_datetime(g.gameday.max()) + pd.Timedelta(days=2)
    played = P[P.week == week]
    rel = set(played.player_id) & ({k for k in owner_of} | set(P.groupby("player_id").fantasy_points_ppr.mean().loc[lambda s: s >= 6].index))
    out = []
    for pid in rel:
        f = SITE / "news" / f"{pid}.json"
        if not f.exists():
            continue
        try:
            items = json.loads(f.read_text()).get("items", [])
        except Exception:  # noqa: BLE001
            continue
        hits = []
        for it in items:
            d = pd.to_datetime(it.get("d", ""), errors="coerce", utc=True)
            if pd.isna(d) or not (start.tz_localize("UTC") <= d <= end.tz_localize("UTC")):
                continue
            txt = f"{it.get('h', '')}. {it.get('s', '')}"
            m = INJ_RE.search(txt)
            if m and not NOT_INJ.search(it.get("h", "")):
                sent = next((x for x in re.split(r"(?<=[.!?])\s+", txt) if m.group(0) in x), m.group(0))
                hits.append({"date": d.strftime("%Y-%m-%d"), "headline": it.get("h", ""), "what_happened": sent[:300], "summary": (it.get("s") or "")[:400]})
        if hits:
            name, pos, team = idx.get(pid, (pid, "", ""))
            row = played[played.player_id == pid].iloc[0]
            # who absorbs the work: teammate at the same position with the most snaps this week
            mates = played[(played.team == team) & (played.position == pos) & (played.player_id != pid)].sort_values("offense_pct", ascending=False)
            nxt = mates.iloc[0] if len(mates) else None
            out.append({"player": name, "key": pid, "pos": pos, "team": team, "fantasy_team": owner_of.get(pid),
                        "snap_pct_this_week": pct(row.offense_pct), "ppr_this_week": rnd(row.fantasy_points_ppr),
                        "news": sorted(hits, key=lambda x: x["date"])[-2:],
                        "next_up": None if nxt is None else {"player": nxt.player_display_name, "key": nxt.player_id, "snap_pct_this_week": pct(nxt.offense_pct),
                                                            "fantasy_team": owner_of.get(nxt.player_id)}})
    return sorted(out, key=lambda x: (x["fantasy_team"] is None, -(x["ppr_this_week"] or 0)))


def top_performers(P, T, K, week, idx, owner_of):
    w = P[P.week == week]
    out = {}
    for pos in ("QB", "RB", "WR", "TE"):
        t = w[w.position == pos].nlargest(5, "fantasy_points_ppr")
        out[pos] = [{"player": r.player_display_name, "key": r.player_id, "team": r.team, "opp": r.opponent_team, "ppr": rnd(r.fantasy_points_ppr),
                     "xfp": rnd(r.xfp), "fantasy_team": owner_of.get(r.player_id)} for r in t.itertuples()]
    if not K.empty:
        kk = K[K.week == week].nlargest(3, "k_pts")
        out["K"] = [{"player": r.player_display_name, "key": r.player_id, "team": r.team, "pts": rnd(r.k_pts), "fantasy_team": owner_of.get(r.player_id)} for r in kk.itertuples()]
    dd = T[T.week == week].nlargest(3, "dst_pts")
    out["DEF"] = [{"player": r.team + " D/ST", "key": "DEF:" + r.team, "opp": r.opponent_team, "pts": rnd(r.dst_pts), "fantasy_team": owner_of.get("DEF:" + r.team)} for r in dd.itertuples()]
    w2 = w.dropna(subset=["xfp"]).assign(diff=lambda x: x.fantasy_points_ppr - x.xfp)
    out["beat_expected"] = [{"player": r.player_display_name, "key": r.player_id, "pos": r.position, "ppr": rnd(r.fantasy_points_ppr), "xfp": rnd(r.xfp),
                             "fantasy_team": owner_of.get(r.player_id)} for r in w2.nlargest(5, "diff").itertuples()]
    out["usage_without_points"] = [{"player": r.player_display_name, "key": r.player_id, "pos": r.position, "ppr": rnd(r.fantasy_points_ppr), "xfp": rnd(r.xfp),
                                    "fantasy_team": owner_of.get(r.player_id)} for r in w2[w2.xfp >= 10].nsmallest(5, "diff").itertuples()]
    return out


def team_week(m, slots, idx, smap, proj):
    """One fantasy team's week from a Sleeper matchup row: started vs best possible lineup (league scoring)."""
    pts = m.get("players_points") or {}
    starters = [s for s in (m.get("starters") or []) if s and s != "0"]
    cands = []
    for sid in m.get("players") or []:
        k = to_key(sid, smap)
        name, pos, team = idx.get(k, (str(sid), None, None)) if k else (str(sid), None, None)
        cands.append({"sid": str(sid), "key": k or "sl:" + str(sid), "player": name, "pos": pos, "team": team, "v": rnd(pts.get(str(sid), 0.0), 2),
                      "ours": proj.get(k), "started": str(sid) in starters})
    start_slots = [s for s in slots if s not in ("BN", "IR", "TAXI")]
    best = best_lineup(cands, start_slots)
    best_pts = round(sum(c["v"] for _, c in best if c), 2)
    actual = rnd(m.get("points"), 2)
    started = [c for c in cands if c["started"]]
    best_keys = {c["key"] for _, c in best if c}
    benched_should = sorted([c for c in cands if c["key"] in best_keys and not c["started"]], key=lambda c: -c["v"])
    started_shouldnt = sorted([c for c in started if c["key"] not in best_keys], key=lambda c: c["v"])
    swaps = []
    for a, b in zip(benched_should, started_shouldnt):  # pair the biggest misses
        swaps.append({"benched": a, "started": b, "points_lost": round(a["v"] - b["v"], 2)})
    return {"roster_id": m["roster_id"], "matchup_id": m.get("matchup_id"), "points": actual, "best_possible": best_pts,
            "left_on_bench": round(best_pts - (actual or 0), 2), "efficiency_pct": int(round(100 * (actual or 0) / best_pts)) if best_pts else None,
            "starters": sorted(started, key=lambda c: -c["v"]), "bench": sorted([c for c in cands if not c["started"]], key=lambda c: -c["v"]), "swaps": swaps}


def recap_facts(week, args):
    meta, P, T, S, K, smap, lg, status = load()
    idx = names_index(P, K, smap)
    rosters = {r["roster_id"]: r for r in lg["rosters"]}
    owner_of = {k: rosters[rid]["team_name"] for rid in rosters for k in rosters[rid]["players"]}
    me = lg["my_roster_id"]
    league = sleeper(f"/league/{lg['id']}") if not args.fixture else {"roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "K", "DEF", "BN", "BN", "BN", "BN", "BN"]}
    slots = league["roster_positions"]
    mus = json.loads(Path(args.fixture).read_text()) if args.fixture else sleeper(f"/league/{lg['id']}/matchups/{week}")
    # who owned whom THAT week (rosters change after the games): from the matchup rows, not today's snapshot
    owner_of = {}
    for m in mus:
        tn = rosters.get(m["roster_id"], {}).get("team_name", f"Team {m['roster_id']}")
        for sid in m.get("players") or []:
            k = to_key(sid, smap)
            if k:
                owner_of[k] = tn
    o = ours(P, K, S, week, T)
    proj = dict(zip(o.key, o.ours_ppr)) if len(o) else {}
    tw = {m["roster_id"]: team_week(m, slots, idx, smap, proj) for m in mus}
    for rid, t in tw.items():
        t["team"] = rosters.get(rid, {}).get("team_name", f"Team {rid}")
        t["record_now"] = f"{rosters.get(rid, {}).get('wins', 0)}-{rosters.get(rid, {}).get('losses', 0)}"
        opp = next((x for x in tw.values() if x["matchup_id"] == t["matchup_id"] and x["roster_id"] != rid), None)
        t["opponent"] = rosters.get(opp["roster_id"], {}).get("team_name") if opp else None
        t["opp_points"] = opp["points"] if opp else None
        t["result"] = None if not opp or t["points"] is None else ("W" if t["points"] > opp["points"] else "L" if t["points"] < opp["points"] else "T")
        t["mvp"] = t["starters"][0] if t["starters"] else None
        t["dud"] = t["starters"][-1] if t["starters"] else None
        t["would_have_won_with_best"] = bool(opp and t["result"] == "L" and t["best_possible"] > (opp["points"] or 0))
    mine = tw.get(me)
    # "could you have known": for each swap, compare pre-game signals
    hindsight = []
    for s in (mine or {}).get("swaps", []):
        a, b = s["benched"], s["started"]
        sa, sb = signals(a["key"], P, T, S, week, proj), signals(b["key"], P, T, S, week, proj)
        call = None
        if sa.get("ours") is not None and sb.get("ours") is not None:
            call = "our projection pointed the right way" if sa["ours"] > sb["ours"] + 0.5 else ("too close to call" if abs(sa["ours"] - sb["ours"]) <= 0.5 else "our projection also preferred the player you started (variance)")
        hindsight.append({"should_have_started": {**a, "pregame": sa}, "instead_of": {**b, "pregame": sb}, "points_lost": s["points_lost"], "verdict": call})
    prev_preview = OUT / f"{meta['season']}-w{week:02d}-preview.json"
    grading = None
    if prev_preview.exists():
        pv = json.loads(prev_preview.read_text()).get("facts", {})
        rec = {c["key"] for c in pv.get("my_best_lineup", []) if c}
        if mine and rec:
            allp = {c["key"]: c["v"] for c in mine["starters"] + mine["bench"]}
            grading = {"suggested_lineup_points": round(sum(allp.get(k, 0) for k in rec), 2), "your_points": mine["points"], "best_possible": mine["best_possible"],
                       "calls": [{"call": cc.get("call"), "start": cc.get("start", {}).get("player"), "start_pts": allp.get(cc.get("start", {}).get("key")),
                                  "sit": cc.get("sit", {}).get("player"), "sit_pts": allp.get(cc.get("sit", {}).get("key"))} for cc in pv.get("close_calls", [])]}
    league_rows = sorted(tw.values(), key=lambda t: -(t["points"] or 0))
    return {"kind": "recap", "season": meta["season"], "week": week, "league": lg["name"], "my_team": rosters[me]["team_name"],
            "trade_deadline_week": 11, "my_week": mine, "hindsight": hindsight, "top_performers": top_performers(P, T, K, week, idx, owner_of),
            "injuries": injuries_on_field(P, week, S, idx, owner_of)[:12], "league_teams": [slim_team(t) for t in league_rows],
            "high_score": league_rows[0]["team"] if league_rows else None, "grading_last_preview": grading,
            "projections_note": "ours = NFL_stats projection v0 computed only from games before this week (backfilled for weeks before 9)."}


def slim_team(t):
    sl = lambda c: None if not c else {"player": c["player"], "key": c["key"], "pos": c["pos"], "pts": c["v"]}  # noqa: E731
    return {"team": t["team"], "result": t["result"], "points": t["points"], "opponent": t["opponent"], "opp_points": t["opp_points"],
            "record_now": t["record_now"], "mvp": sl(t["mvp"]), "dud": sl(t["dud"]), "left_on_bench": t["left_on_bench"],
            "efficiency_pct": t["efficiency_pct"], "would_have_won_with_best": t["would_have_won_with_best"],
            "biggest_bench_miss": None if not t["swaps"] else {"benched": sl(t["swaps"][0]["benched"]), "started": sl(t["swaps"][0]["started"])}}


def preview_facts(week, args):
    meta, P, T, S, K, smap, lg, status = load()
    idx = names_index(P, K, smap)
    rosters = {r["roster_id"]: r for r in lg["rosters"]}
    owner_of = {k: rosters[rid]["team_name"] for rid in rosters for k in rosters[rid]["players"]}
    me = lg["my_roster_id"]
    slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "K", "DEF"]
    o = ours(P, K, S, week, T)
    proj = dict(zip(o.key, o.ours_ppr)) if len(o) else {}
    inj = (meta.get("injuries") or {})
    sts = status.get("p", {}) if isinstance(status, dict) else {}
    g = S[S.week == week]
    playing = set(g.home_team) | set(g.away_team)

    def cand(k):
        name, pos, team = idx.get(k, (k, None, None))
        out_flag = (inj.get(k, [""])[0] in ("Out", "Doubtful", "IR")) or (sts.get(k, {}).get("s") in ("IR", "PUP", "NFI"))
        on_bye = team is not None and team not in playing
        v = None if on_bye or out_flag else proj.get(k)
        return {"key": k, "player": name, "pos": pos, "team": team, "v": v, "ours": proj.get(k), "bye": on_bye,
                "injury": (inj.get(k) or [None, None])[:2] if k in inj else None, "status": sts.get(k, {}).get("s")}

    def team_view(rid):
        c = [cand(k) for k in rosters[rid]["players"]]
        best = best_lineup(c, slots)
        return c, best

    my_c, my_best = team_view(me)
    in_best = {cc["key"] for _, cc in my_best if cc}
    bench = sorted([c for c in my_c if c["key"] not in in_best and c["v"] is not None], key=lambda c: -c["v"])
    close = []
    used = set()
    flexy = [(s, c) for s, c in my_best if c and s not in ("K", "DEF", "QB")]
    for s, c in sorted(flexy, key=lambda x: x[1]["v"]):  # weakest starters first
        ok = SLOT_OK.get(s, {s})
        alt = next((b for b in bench if b["pos"] in ok and b["key"] not in used), None)
        if alt and c["v"] - alt["v"] <= 1.5:
            used.add(alt["key"])
            close.append({"slot": s, "call": f"{c['player']} over {alt['player']}", "margin": round(c["v"] - alt["v"], 2),
                          "start": {**c, "pregame": signals(c["key"], P, T, S, week, proj)}, "sit": {**alt, "pregame": signals(alt["key"], P, T, S, week, proj)}})
    rostered = set(owner_of)
    fa = []
    for k, v in proj.items():
        if k in rostered or v is None:
            continue
        name, pos, team = idx.get(k, (k, None, None))
        if team not in playing or sts.get(k, {}).get("s") or (inj.get(k, [""])[0] in ("Out", "Doubtful", "IR")):
            continue
        h = P[(P.player_id == k) & (P.week < week)]
        if len(h) and h.week.max() < week - 2 and not k.startswith("DEF:"):
            continue  # hasn't played in 2+ weeks (likely hurt / benched)
        fa.append({"key": k, "player": name, "pos": pos, "team": team, "ours": v, "pregame": signals(k, P, T, S, week, proj)})
    waivers = {p: sorted([x for x in fa if x["pos"] == p], key=lambda x: -x["ours"])[:4] for p in ("QB", "RB", "WR", "TE", "K", "DEF")}
    # buy low / sell high on my roster: points vs expected (season)
    bs = []
    for c in my_c:
        h = P[(P.player_id == c["key"]) & (P.week < week)]
        if len(h) >= 3 and h.xfp.notna().any():
            bs.append({"player": c["player"], "key": c["key"], "pos": c["pos"], "ppr_per_g": rnd(h.fantasy_points_ppr.mean()), "xfp_per_g": rnd(h.xfp.mean()),
                       "gap": rnd(h.fantasy_points_ppr.mean() - h.xfp.mean())})
    bs = sorted(bs, key=lambda x: x["gap"])
    # around the league: projected starting strength by position + trade fits with me
    strength, views = {}, {}
    for rid in rosters:
        c, best = team_view(rid)
        views[rid] = (c, best)
        by = {}
        for s, cc in best:
            if cc and s not in ("K", "DEF"):
                by.setdefault(cc["pos"], []).append(cc["v"])
        strength[rid] = {p: round(sum(v), 1) for p, v in by.items()}
    med = {p: float(pd.Series([strength[r].get(p, 0) for r in strength]).median()) for p in ("QB", "RB", "WR", "TE")}
    def depth(rid):
        c, best = views[rid]
        inb = {cc["key"] for _, cc in best if cc}
        return sorted([x for x in c if x["key"] not in inb and x["ours"] is not None and x["pos"] in ("QB", "RB", "WR", "TE")], key=lambda x: -x["ours"])
    my_bench = depth(me)
    my_weak = {p: min([cc["v"] for s, cc in my_best if cc and cc["pos"] == p and s not in ("FLEX",)] or [0]) for p in ("RB", "WR", "TE", "QB")}
    teams = []
    for rid, r in rosters.items():
        c, best = views[rid]
        needs = [p for p in ("QB", "RB", "WR", "TE") if strength[rid].get(p, 0) < med[p] * 0.85]
        surplus = [x for x in depth(rid) if x["ours"] >= 8]
        fits = []
        if rid != me:
            for x in surplus:
                if x["ours"] > my_weak.get(x["pos"], 99) + 1:
                    give = next((y for y in my_bench if y["pos"] in needs and abs((y["ours"] or 0) - x["ours"]) <= 3), None)
                    if give:
                        fits.append({"you_get": slim_c(x), "you_give": slim_c(give)})
        hurt = [slim_c(x) | {"injury": x["injury"], "status": x["status"]} for x in c if (x["injury"] and x["injury"][0] in ("Out", "Doubtful", "IR", "Questionable")) or x["status"]]
        teams.append({"team": r["team_name"], "record_now": f"{r.get('wins', 0)}-{r.get('losses', 0)}", "projected_starting_pts": round(sum(cc["v"] for _, cc in best if cc and cc["v"]), 1),
                      "strength_by_pos": strength[rid], "needs": needs, "surplus": [slim_c(x) for x in surplus[:3]], "injured_or_out": hurt[:5], "trade_fits_with_you": fits[:2]})
    teams.sort(key=lambda t: -t["projected_starting_pts"])
    return {"kind": "preview", "season": meta["season"], "week": week, "league": lg["name"], "my_team": rosters[me]["team_name"], "trade_deadline_week": 11,
            "my_best_lineup": [None if not cc else {"slot": s, **slim_c(cc), "bye": cc["bye"], "injury": cc["injury"]} for s, cc in my_best],
            "my_projected_total": round(sum(cc["v"] for _, cc in my_best if cc and cc["v"]), 1),
            "my_unavailable": [slim_c(c) | {"bye": c["bye"], "injury": c["injury"], "status": c["status"]} for c in my_c if c["v"] is None and (c["bye"] or c["injury"] or c["status"])],
            "close_calls": close, "waiver_adds": waivers, "buy_low_on_your_roster": bs[:2], "sell_high_on_your_roster": bs[::-1][:2],
            "league_median_strength": {p: round(v, 1) for p, v in med.items()}, "around_the_league": teams,
            "projections_note": "ours = NFL_stats projection v0 (backtested signals: season avg, last 3, Vegas implied, xFP, snap % and touch-share trends, target share; D/ST by opponent Vegas implied)."}


def slim_c(c):
    return {"player": c["player"], "key": c["key"], "pos": c["pos"], "team": c.get("team"), "ours": c.get("ours") if c.get("ours") is not None else c.get("v")}


# ---------------------------------------------------------------- writing
SECTIONS = {
    "recap": [("my_week", "Your week"), ("hindsight", "Could you have known?"), ("top_performers", "Top performers"),
              ("injuries", "Injuries on the field"), ("around_league", "Around the league"), ("grading", "Grading last week's preview")],
    "preview": [("my_lineup", "Your best lineup"), ("close_calls", "Close calls"), ("waivers", "Waiver adds and streamers"),
                ("buy_sell", "Buy low, sell high"), ("around_league", "Around the league: needs and trade fits")],
}
SYSTEM = """You write the weekly fantasy football rundown for William's private stats site (his 12-team PPR Sleeper league, 67FFL; his team is given in the facts).
Rules:
- Use ONLY the facts JSON. fantasy_team tags in a recap are the rosters as of that week; trust them.
- Use ONLY the facts JSON. Never invent stats, injuries, quotes, game details or reasons that are not in the facts.
- Write player names exactly as they appear in the facts (the site turns them into links). Team names as given.
- "ours" is the site's own projection, built only from data available before the games. Say "our projection".
- In "Could you have known?", be honest: say whether a pre-game signal (our projection, snap % trend, xFP, target share, Vegas implied) pointed the right way, or whether it was variance nobody could see.
- Injuries: only report what the news facts say. A news sentence filed under one player can be about a teammate (e.g. 'Jaylen Wright exited… which could mean more work for Gordon'): report the player the sentence says got hurt, and frame the filed player as the one who gains. Say who is next up when given. Skip items that only say a player returned or was fine unless they left the game first.
- Trade fits: frame as ideas worth a look, mention the trade deadline week.
- Style: sharp, conversational, data-first, like a smart friend who did the homework. Short paragraphs and bullets. Bold key numbers sparingly. No hype words, no emojis, no tables.
- Skip a section (empty md) if its facts are empty.
Output format (plain text, no JSON, no code fences):
HEADLINE: <max 12 words>
DEK: <one sentence>
=== <section id> ===
<markdown for that section>
…one "=== id ===" block per requested section id, in order (leave a block empty to skip it)."""


def claude_write(facts, kind):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    want = [{"id": i, "title": t} for i, t in SECTIONS[kind]]
    msg = f"Write this week's {kind} for week {facts['week']}.\nSections (in order): {json.dumps(want)}\n\nFacts:\n{json.dumps(facts, default=str)}"
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=180,
                      headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                      json={"model": MODEL_ID, "max_tokens": 8000, "system": SYSTEM, "messages": [{"role": "user", "content": msg}]})
    if r.status_code != 200:
        print(f"Claude API {r.status_code}: {r.text[:300]}", file=sys.stderr)
        return None
    data = r.json()
    txt = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
    if data.get("stop_reason") == "max_tokens":
        print("Claude hit max_tokens; using what came back", file=sys.stderr)
    hl = re.search(r"^HEADLINE:\s*(.+)$", txt, re.M); dk = re.search(r"^DEK:\s*(.+)$", txt, re.M)
    parts = re.split(r"^===\s*([a-z_]+)\s*===\s*$", txt, flags=re.M)
    got = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    if not hl or not got:
        print("Couldn't parse Claude's reply; falling back to templates", file=sys.stderr)
        return None
    titles = dict(SECTIONS[kind])
    u = data.get("usage", {})
    return {"headline": hl.group(1).strip(), "dek": dk.group(1).strip() if dk else "",
            "sections": [{"id": i, "title": titles[i], "md": got.get(i, "")} for i, _ in SECTIONS[kind]],
            "usage": {"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"), "model": MODEL_ID}}


def fmt_p(c):
    return f"{c['player']} ({c.get('pos') or ''}{', ' + str(c['v']) if c.get('v') is not None else ''})"


def template_write(f, kind):
    S = []
    if kind == "recap":
        m = f["my_week"] or {}
        S.append(("my_week", "Your week", "\n".join([
            f"{f['my_team']} scored **{m.get('points')}** vs {m.get('opponent')} ({m.get('opp_points')}): **{m.get('result')}**." if m else "",
            f"Best possible lineup: {m.get('best_possible')} ({m.get('left_on_bench')} left on the bench, {m.get('efficiency_pct')}% efficient)." if m else "",
            "", *[f"- {c['player']}: {c['v']}" for c in (m.get('starters') or [])[:3]]])))
        S.append(("hindsight", "Could you have known?", "\n".join(
            f"- Start **{h['should_have_started']['player']}** ({h['should_have_started']['v']}) over {h['instead_of']['player']} ({h['instead_of']['v']}): {h['points_lost']} pts. Our projection had {h['should_have_started']['pregame'].get('ours')} vs {h['instead_of']['pregame'].get('ours')}; {h['verdict'] or 'no projection'}."
            for h in f["hindsight"]) or "Your lineup was the best possible lineup."))
        tp = f["top_performers"]
        S.append(("top_performers", "Top performers", "\n".join(f"- **{p}:** " + ", ".join(f"{x['player']} {x.get('ppr', x.get('pts'))}" for x in tp.get(p, [])) for p in ("QB", "RB", "WR", "TE", "K", "DEF"))))
        S.append(("injuries", "Injuries on the field", "\n".join(f"- **{i['player']}** ({i['pos']}, {i['team']}): {i['news'][-1]['what_happened']}" + (f". Next up: {i['next_up']['player']}." if i.get('next_up') else "") for i in f["injuries"]) or ""))
        S.append(("around_league", "Around the league", "\n".join(f"- **{t['team']}** {t['result'] or ''} {t['points']}–{t['opp_points']} vs {t['opponent']}. MVP {t['mvp']['player'] if t['mvp'] else '–'}; {t['left_on_bench']} left on the bench." for t in f["league_teams"])))
        g = f.get("grading_last_preview")
        S.append(("grading", "Grading last week's preview", "" if not g else f"Our suggested lineup would have scored {g['suggested_lineup_points']} (you scored {g['your_points']}, best possible {g['best_possible']})."))
    else:
        S.append(("my_lineup", "Your best lineup", f"Projected total **{f['my_projected_total']}**.\n\n" + "\n".join(f"- {c['slot']}: {c['player']} ({c['ours']})" for c in f["my_best_lineup"] if c)))
        S.append(("close_calls", "Close calls", "\n".join(f"- {c['call']} by {c['margin']}" for c in f["close_calls"])))
        S.append(("waivers", "Waiver adds and streamers", "\n".join(f"- **{p}:** " + ", ".join(f"{x['player']} ({x['ours']})" for x in xs) for p, xs in f["waiver_adds"].items() if xs)))
        S.append(("buy_sell", "Buy low, sell high", "\n".join([*(f"- Buy low: {x['player']} ({x['ppr_per_g']} PPR vs {x['xfp_per_g']} expected)" for x in f["buy_low_on_your_roster"]),
                                                               *(f"- Sell high: {x['player']} ({x['ppr_per_g']} PPR vs {x['xfp_per_g']} expected)" for x in f["sell_high_on_your_roster"])])))
        S.append(("around_league", "Around the league: needs and trade fits", "\n".join(f"- **{t['team']}** ({t['record_now']}): needs {', '.join(t['needs']) or 'nothing major'}" + "".join(f"; idea: get {x['you_get']['player']} for {x['you_give']['player']}" for x in t["trade_fits_with_you"]) for t in f["around_the_league"])))
    title = f"Week {f['week']} {'recap' if kind == 'recap' else 'preview'}"
    return {"headline": title, "dek": f"{f['league']} · {f['my_team']}", "sections": [{"id": i, "title": t, "md": md} for i, t, md in S]}


def links_for(f):
    """name → card key for every player/team mentioned in the facts (the page links them)."""
    out = {}
    def walk(x):
        if isinstance(x, dict):
            if "player" in x and "key" in x and isinstance(x["player"], str) and isinstance(x["key"], str) and not x["key"].startswith("sl:"):
                out[x["player"]] = ("d:" + x["key"][4:]) if x["key"].startswith("DEF:") else "p:" + x["key"]
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(f)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["recap", "preview"], required=True)
    ap.add_argument("--week", type=int)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fixture")
    a = ap.parse_args()
    meta = J("meta.json")
    week = a.week or (meta["last_completed_week"] if a.kind == "recap" else meta["next_week"])
    facts = recap_facts(week, a) if a.kind == "recap" else preview_facts(week, a)
    try:
        art = None if a.no_llm else claude_write(facts, a.kind)
    except Exception as e:  # noqa: BLE001  never fail the run over the prose
        print(f"Claude step failed ({e}); using templates", file=sys.stderr)
        art = None
    writer = "claude" if art else "template"
    if not art:
        art = template_write(facts, a.kind)
    doc = {"season": facts["season"], "week": week, "kind": a.kind, "league": facts["league"], "my_team": facts["my_team"],
           "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "writer": writer,
           "headline": art.get("headline"), "dek": art.get("dek"), "sections": art.get("sections", []), "links": links_for(facts),
           "usage": art.get("usage"), "facts": facts}
    if a.dry_run:
        print(json.dumps({k: v for k, v in doc.items() if k != "facts"}, indent=1, default=str)[:6000])
        return
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"{facts['season']}-w{week:02d}-{a.kind}.json"
    (OUT / name).write_text(json.dumps(doc, default=str, separators=(",", ":")))
    idx_f = OUT / "index.json"
    idx = json.loads(idx_f.read_text()) if idx_f.exists() else {"articles": []}
    idx["articles"] = [x for x in idx["articles"] if x["file"] != name] + [{"file": name, "season": facts["season"], "week": week, "kind": a.kind,
                                                                           "headline": doc["headline"], "dek": doc["dek"], "generated_utc": doc["generated_utc"], "writer": writer}]
    idx["articles"].sort(key=lambda x: (x["season"], x["week"], x["kind"] == "preview"), reverse=True)
    idx_f.write_text(json.dumps(idx, indent=1))
    print(f"Wrote {name} ({writer})", file=sys.stderr)


if __name__ == "__main__":
    main()
