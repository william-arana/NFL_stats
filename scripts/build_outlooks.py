"""Weekly player outlooks: 2-3 lines per player written by Claude from a facts file only, plus one checkable claim
that gets graded after the games.

  python scripts/build_outlooks.py                 # facts + Claude (Batch API) + write
  python scripts/build_outlooks.py --facts-only    # write the facts file only (no API key needed)
  python scripts/build_outlooks.py --limit 20 --direct   # small test with direct calls

Players: everyone rostered in 67FFL + the top 300 QB/RB/WR/TE by this week's projection (no K / D/ST).
Every line has to cite fact ids, and every number in a line has to appear in a fact it cites; a reply that breaks this
gets one retry, then that player gets no outlook this week. Sleeper / ESPN numbers are never facts.

Outputs:
  data/site/outlooks/<gsis_id>.json   what the player card shows (lines + the facts they cite + the claim)
  data/outlooks/<season>_w<week>.json every claim in machine form (graded after the games)
  data/outlooks/facts_<season>_w<week>.json.gz   the full facts file sent to Claude (for checking)
"""
import argparse, gzip, json, os, re, sys, time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "data" / "site"
OUT_CARD = SITE / "outlooks"
OUT_CLAIMS = ROOT / "data" / "outlooks"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from projection_v0 import moved_teams, play_mult  # noqa: E402

MODEL = os.environ.get("OUTLOOK_MODEL", "claude-sonnet-5-5")
API = "https://api.anthropic.com/v1"
LEAGUE = "67FFL"
TOP_N = 300
POS = ("QB", "RB", "WR", "TE")
LINES_MAX, WORDS_MAX = 3, 32
# "off" = thinking {"type": "between_tools"} (lowest setting on Sonnet 5.5; "disabled" is a 400 there).
# "on" = no thinking field = the model's adaptive default. Most output tokens were thinking (11/15 test).
THINKING = os.environ.get("OUTLOOK_THINKING", "on").strip().lower()
MAX_TOKENS = 1500  # was 700: 8 of 20 replies came back cut off in the 11/14 test

# claim metric -> how to read it from next week's box score (players.json). value units as written in the claim.
CLAIM_METRICS = {
    "snap_pct": ("offense_pct", "snap %", 100), "targets": ("targets", "targets", 1), "carries": ("carries", "carries", 1),
    "opps": (("carries", "targets"), "carries + targets", 1), "receptions": ("receptions", "catches", 1),
    "rec_yds": ("receiving_yards", "receiving yards", 1), "rush_yds": ("rushing_yards", "rushing yards", 1),
    "pass_att": ("attempts", "pass attempts", 1), "pass_yds": ("passing_yards", "passing yards", 1),
    "pass_td": ("passing_tds", "passing TDs", 1), "rz_opps": (("rz_car", "rz_tgt"), "red zone carries + targets", 1),
    "ppr": ("fantasy_points_ppr", "PPR points", 1),
}
# a claim's line has to sit near his last-3 average: within 10% or this many units, whichever is bigger.
# (test run 11/14: Cooks <= 4 targets at 2.3 a game, Hooper <= 3 at 1.3 = gimmes that would inflate the hit rate)
CLAIM_BAND, CLAIM_FLOOR = 0.10, {"snap_pct": 5, "targets": 1, "carries": 2, "opps": 2, "receptions": 1, "rec_yds": 10,
                                 "rush_yds": 10, "pass_att": 3, "pass_yds": 20, "pass_td": 0.5, "rz_opps": 1, "ppr": 2}

SYSTEM = f"""You write short fantasy football outlooks for one player at a time, for a stats site.

You get a facts list. Each fact has an id (F1, F2, ...) and a text. Use ONLY these facts. No outside knowledge: no
contracts, draft history, reputations, team news or anything not in the list, even if you know it.

Write {LINES_MAX - 1} or {LINES_MAX} lines in total, never more. Each line is at most {WORDS_MAX - 4} words (count them), plain
sentences, no hype, no emojis. The bullets below are what the lines cover, not one line each:
- What his role and production look like right now (usage trend first, points second).
- Plain words a fantasy player would use, like a friend in your league talking. Aim for about 20 words a line, one sentence or two short ones.
- Each line says something different. Compare recent vs season in at most one line, and only where it changed.
  Other angles: share of team targets or carries, snaps, red-zone or goal-line work, the matchup, the coach.
- No stat jargon or made-up phrases ("cut to 75% of normal", "snap-heavy role", "volume profile"). Say what
  happened: "played 74% of snaps", "saw 8 targets". No stacked adjectives.
- What matters for the coming week (matchup, availability, coach comments) when the facts have it.
- Each line cites the fact ids it uses. Every number you write must appear exactly as written in a fact the line cites
  (same rounding: write 74%, not 0.74 or 75%). Don't compute new numbers (no differences, sums or percentages of your own).
- Coach comments are what the coach said, not facts about the future: write "the coach said ...".
- Don't tell the reader to start, sit, add or drop anyone.

Then one checkable claim about his NEXT game (the week in the facts), gradable from the box score:
- metric: one of {", ".join(CLAIM_METRICS)} (snap_pct in percent, e.g. 60)
- op: ">=" or "<="
- value: a number within 10% of his last-3-game average for that metric (the check rejects anything further away),
  on the side you think is more likely true. Not a gimme.
- f: the fact ids it rests on.
If he has a bye, is out, or the facts say he likely won't play, use "claim": null.

Reply with JSON only:
{{"lines":[{{"t":"...","f":["F3","F4"]}}],"claim":{{"metric":"targets","op":">=","value":6,"f":["F5"]}}}}"""


# ---------- data ----------

def tab(n):
    j = json.loads((SITE / n).read_text())
    return pd.DataFrame({c: j["data"][c] for c in j["cols"]})


def rd(n, d=None):
    p = SITE / n
    return json.loads(p.read_text()) if p.exists() else d


def ordn(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 < 14 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def f1(x):
    return f"{x:.1f}"


def pct(x):
    return f"{round(100 * x)}%"


def players_for(meta, P, proj):
    """67FFL rostered + top N by projection, QB/RB/WR/TE only."""
    pos = P.sort_values("week").groupby("player_id").position.last()
    keep = {k for k, p in pos.items() if p in POS}
    lg = next((x for x in (rd("leagues.json", {}) or {}).get("leagues", []) if x.get("name") == LEAGUE), None)
    rost = {p for r in (lg or {}).get("rosters", []) for p in (r.get("players") or [])} & keep
    top = [k for k, _ in sorted(((k, v) for k, v in (proj.get("p") or {}).items() if k in keep), key=lambda kv: -kv[1])[:TOP_N]]
    return sorted(rost | set(top)), rost


def dvp(P):
    """{(team, pos): rank} 1 = allows the most PPR per game to that position."""
    g = P.groupby(["opponent_team", "week", "position"]).fantasy_points_ppr.sum().reset_index()
    a = g.groupby(["opponent_team", "position"]).fantasy_points_ppr.mean().reset_index()
    a["rk"] = a.groupby("position").fantasy_points_ppr.rank(ascending=False, method="min")
    return {(t, p): int(r) for t, p, r in zip(a.opponent_team, a.position, a.rk)}


def build_facts(pid, P, S, meta, proj, status, mult, ranks, dv, pos_rank_ros, moved=None, names=None):
    W, L = meta["next_week"], meta["last_completed_week"]
    g = P[(P.player_id == pid) & (P.week <= L)].sort_values("week")
    if g.empty:
        return None
    name, pos, was = g.player_display_name.iloc[-1], g.position.iloc[-1], g.team.iloc[-1]
    team = (moved or {}).get(pid, was)  # traded / signed elsewhere since his last game (status.json "moved")
    facts = []
    add = lambda t, src: facts.append({"id": f"F{len(facts) + 1}", "t": t, "src": src})  # noqa: E731
    l3 = g.tail(3)
    team_games = len(set(P[(P.team == was) & (P.week <= L)].week))
    add(f"{name}, {pos}, {team}. Played {len(g)} of {was}'s {team_games} games (wks 1–{L}).", "players.json")
    if team != was:
        add(f"Moved from {was} to {team} (Sleeper roster); no games for {team} yet.", "status.json moved (Sleeper)")
    # projections (ours)
    p = (proj.get("p") or {}).get(pid)
    if p is not None:
        rk = ranks.get(pid)
        add(f"Our Wk {W} projection: {f1(p)} PPR" + (f", {ordn(rk)} among {pos}s." if rk else "."), "proj.json p (v0.1)")
    r = (proj.get("r") or {}).get(pid)
    if r is not None:
        rk = pos_rank_ros.get(pid)
        add(f"Our rest-of-season projection (Wk {W}–18): {f1(r)} PPR" + (f", {ordn(rk)} among {pos}s." if rk else "."), "proj.json r (ROS v0)")
    m = mult.get(pid)
    if m and m[0] < 1:
        why = re.sub(r"00-\d{7}", lambda x: (names or {}).get(x.group(0), "another QB"), m[1])  # "backup QB (<id> starts)" -> name
        add(f"Availability: our Wk {W} projection has him at 0 ({why})." if m[0] == 0 else
            f"Availability: our Wk {W} projection gives him a {pct(m[0])} chance to play ({why}).", "projection_v0.play_mult")
    st = (status.get("p") or {}).get(pid) or {}
    if st.get("season"):
        add("Listed as out for the season.", "status.json")
    elif st.get("s") in ("IR", "PUP", "Out", "NFI"):
        add(f"Sleeper status: {st['s']}.", "status.json")
    inj = (meta.get("injuries") or {}).get(pid)
    if inj and (len(inj) < 3 or inj[2] == W):
        add(f"Wk {W} injury report: {inj[0].replace('Practice: ', 'practice ')}" + (f" ({inj[1]})." if inj[1] else "."), "meta.json injuries")

    def both(label, col, fmt, per_game=True, src="players.json"):
        s, t = g[col].dropna(), l3[col].dropna()
        if s.empty:
            return
        fs = (lambda x: x.mean()) if per_game else (lambda x: x.sum())
        if t.empty:
            add(f"{label}: {fmt(fs(s))} season.", src)
            return
        wk = ", ".join(str(int(w)) for w in l3.loc[t.index, "week"])
        add(f"{label}: {fmt(fs(t))} over his last {len(t)} game{'s' if len(t) > 1 else ''} (wk{'s' if len(t) > 1 else ''} {wk}), {fmt(fs(s))} season.", src)

    both("Snap %", "offense_pct", pct, src="players.json offense_pct (snap counts)")
    if pos == "QB":
        both("Pass attempts per game", "attempts", f1)
        both("Passing yards per game", "passing_yards", f1)
        both("Passing TDs per game", "passing_tds", f1)
        both("Interceptions per game", "passing_interceptions", f1)
        both("Carries per game", "carries", f1)
        both("Rushing yards per game", "rushing_yards", f1)
    else:
        if pos == "RB" or g.carries.sum() >= 10:
            both("Carries per game", "carries", f1)
        both("Targets per game", "targets", f1)
        both("Target share", "target_share", pct)
        both("Catches per game", "receptions", f1)
        if pos == "RB":
            both("Rushing yards per game", "rushing_yards", f1)
        both("Receiving yards per game", "receiving_yards", f1)
        g = g.assign(rz=g.rz_car.fillna(0) + g.rz_tgt.fillna(0))
        l3 = g.tail(3)
        both("Red zone carries + targets per game", "rz", f1, src="players.json rz_car + rz_tgt (play-by-play)")
    both("PPR points per game", "fantasy_points_ppr", f1)
    if g.xfp.notna().any():
        both("Expected PPR points (xFP) per game, from usage", "xfp", f1, src="players.json xfp (ffopportunity)")
    tds = int(g[["passing_tds", "rushing_tds", "receiving_tds"]].fillna(0).sum().sum())
    add(f"Total TDs this season: {tds}.", "players.json")
    # next game
    gm = S[(S.week == W) & ((S.home_team == team) | (S.away_team == team))]
    if gm.empty:
        add(f"Wk {W}: {team} has a bye.", "schedule.json")
    else:
        x = gm.iloc[0]
        home = x.home_team == team
        opp = x.away_team if home else x.home_team
        imp = x.home_implied if home else x.away_implied
        t = f"Wk {W}: {'vs' if home else 'at'} {opp}"
        if pd.notna(imp):
            t += f", {team} implied team total {f1(imp)} points (Vegas)"
        rk = dv.get((opp, pos))
        if rk:
            t += f"; {opp} allows the {ordn(rk)}-most PPR points per game to {pos}s"
        add(t + ".", "schedule.json + players.json")
    # coach comments, last 21 days (our own summaries)
    sp = SITE / "presser_signals" / f"{pid}.json"
    if sp.exists():
        j = json.loads(sp.read_text())
        cut = (pd.Timestamp(meta["updated_utc"][:10]) - pd.Timedelta(days=21)).strftime("%Y-%m-%d")
        rows = []
        for vi, sig, topic, claim, note, _q, *_ in j.get("p") or []:
            v = (j.get("v") or [])[vi] if vi < len(j.get("v") or []) else []
            if v and v[0] >= cut and (claim or note):
                rows.append((v[0], v[2] or "coach", sig, topic, claim or note))
        for d, coach, sig, topic, txt in sorted(rows, reverse=True)[:3]:
            add(f"Coach {coach} ({d}, {topic or 'comment'}, signal {sig}): {txt}", "presser_signals (our summary)")
    l3c = {}  # last-3 average per claim metric, in claim units (for the claim band check)
    for k, (col, _, mul) in CLAIM_METRICS.items():
        cols = list(col) if isinstance(col, tuple) else [col]
        if all(c in l3 for c in cols) and l3[cols].notna().any().any():
            l3c[k] = round(float(l3[cols].fillna(0).sum(axis=1).mean()) * mul, 2)
    return {"id": pid, "name": name, "pos": pos, "team": team, "week": W, "facts": facts, "l3": l3c}


# ---------- check a reply ----------

NUM = re.compile(r"\d+(?:\.\d+)?")
BANNED = re.compile(r"\b(sleeper|espn|yahoo|start him|sit him|must[- ]start|pick him up|drop him)\b", re.I)


def nums(t):
    return {float(x) for x in NUM.findall(t.replace(",", ""))}


def check(reply, F):
    """-> (clean outlook, None) or (None, reason)."""
    fx = {f["id"]: f["t"] for f in F["facts"]}
    lines = reply.get("lines")
    if not isinstance(lines, list) or not 2 <= len(lines) <= LINES_MAX:
        return None, "needs 2-3 lines"
    out = []
    for ln in lines:
        t, ids = str(ln.get("t") or "").strip(), [i for i in (ln.get("f") or []) if i in fx]
        if not t or not ids:
            return None, f"line without valid fact ids: {t[:60]}"
        if len(t.split()) > WORDS_MAX:
            return None, f"line too long ({len(t.split())} words)"
        if BANNED.search(t):
            return None, f"banned phrase in: {t[:60]}"
        ok = set().union(*(nums(fx[i]) for i in ids)) | {float(F["week"])}
        bad = [n for n in nums(t) if n not in ok]
        if bad:
            return None, f"number(s) {bad} not in cited facts {ids}: {t[:80]}"
        out.append([t, ids])
    c = reply.get("claim")
    claim = None
    if c:
        m, op, v = c.get("metric"), c.get("op"), c.get("value")
        if m not in CLAIM_METRICS or op not in (">=", "<=") or not isinstance(v, (int, float)) or v < 0:
            return None, f"bad claim {c}"
        if m == "snap_pct" and not 0 < v <= 100:
            return None, f"bad snap % claim {v}"
        avg = (F.get("l3") or {}).get(m)
        if avg is not None:
            band = max(CLAIM_BAND * avg, CLAIM_FLOOR.get(m, 0))
            if abs(v - avg) > band:
                return None, (f"claim value {v} is too far from his last-3 average {avg:g} {m}: "
                              f"pick a value between {max(0, avg - band):.1f} and {avg + band:.1f}")
        claim = {"metric": m, "op": op, "value": v, "f": [i for i in (c.get("f") or []) if i in fx]}
        claim["t"] = claim_text(F, claim)
    return {"lines": out, "claim": claim}, None


def claim_text(F, c):
    unit = CLAIM_METRICS[c["metric"]][1]
    v = int(c["value"]) if float(c["value"]).is_integer() else c["value"]
    lead = "At least" if c["op"] == ">=" else "At most"
    if c["metric"] == "snap_pct":
        return f"{lead} {v}% of snaps in Wk {F['week']}."
    return f"{lead} {v} {unit} in Wk {F['week']}."


# ---------- Claude ----------

def headers():
    return {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"}


def params(F, note=""):
    msg = f"Player: {F['name']} ({F['pos']}, {F['team']}). Coming week: Wk {F['week']}.\nFacts:\n" + \
          "\n".join(f"{f['id']}: {f['t']}" for f in F["facts"])
    if note:
        msg += f"\n\nYour last reply was rejected: {note}. Fix that and reply with JSON only, short lines."
    p = {"model": MODEL, "max_tokens": MAX_TOKENS,
         "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
         "messages": [{"role": "user", "content": msg}]}
    if THINKING == "off":
        p["thinking"] = {"type": "between_tools"}
    return p


class ReplyError(ValueError):
    """Claude answered, but not with usable JSON (raw text kept for the run file)."""
    def __init__(self, why, raw):
        super().__init__(why)
        self.raw = raw


def parse(msg, R=None):
    stop = msg.get("stop_reason") or "?"
    if R is not None:
        R[stop] = R.get(stop, 0) + 1
        for blk in msg.get("content", []):  # which kinds of output the tokens went to (text vs thinking)
            k = "block_" + str(blk.get("type"))
            R[k] = R.get(k, 0) + 1
    txt = "".join(b.get("text", "") for b in msg.get("content", []) if b.get("type") == "text").strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt).strip()
    try:
        return json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
    except ValueError as e:
        raise ReplyError(f"bad JSON (stop: {stop}, {len(txt)} chars): {e}", txt[:2000]) from None


def usage_add(U, msg):
    for k, v in (msg.get("usage") or {}).items():
        if isinstance(v, int):
            U[k] = U.get(k, 0) + v


def direct(F, note, U, R):
    import requests
    r = requests.post(f"{API}/messages", timeout=180, headers=headers(), json=params(F, note))
    r.raise_for_status()
    m = r.json()
    usage_add(U, m)
    U["direct_calls"] = U.get("direct_calls", 0) + 1
    return parse(m, R)


def run_batch(FS, U, R, wait_min):
    """{pid: reply dict}. Half price; whatever isn't back within wait_min comes back missing (caller goes direct)."""
    import requests
    out = {}
    r = requests.post(f"{API}/messages/batches", timeout=120, headers=headers(),
                      json={"requests": [{"custom_id": F["id"].replace("-", "_"), "params": params(F)} for F in FS]})
    if r.status_code != 200:
        print(f"batch submit failed ({r.status_code}: {r.text[:200]})", file=sys.stderr)
        return out
    bid = r.json()["id"]
    print(f"batch {bid}: {len(FS)} players ({MODEL})", file=sys.stderr)
    end, st = time.time() + 60 * wait_min, {}
    while time.time() < end:
        st = requests.get(f"{API}/messages/batches/{bid}", timeout=60, headers=headers()).json()
        if st.get("processing_status") == "ended":
            break
        time.sleep(30)
    if st.get("processing_status") != "ended":
        print(f"batch {bid} not done after {wait_min} min; cancelling, the rest go direct", file=sys.stderr)
        requests.post(f"{API}/messages/batches/{bid}/cancel", timeout=60, headers=headers())
        time.sleep(20)
        st = requests.get(f"{API}/messages/batches/{bid}", timeout=60, headers=headers()).json()
    if st.get("results_url"):
        res = requests.get(st["results_url"], timeout=300, headers=headers())
        for line in res.text.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("result", {}).get("type") != "succeeded":
                continue
            m = row["result"]["message"]
            usage_add(U, m)
            U["batch_calls"] = U.get("batch_calls", 0) + 1
            try:
                out[row["custom_id"].replace("_", "-")] = parse(m, R)
            except ReplyError as e:  # retried direct with the reason
                out[row["custom_id"].replace("_", "-")] = {"_err": str(e), "_raw": e.raw}
    return out


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts-only", action="store_true")
    ap.add_argument("--direct", action="store_true", help="direct calls instead of the Batch API (tests)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--wait", type=int, default=50, help="minutes to wait for the batch")
    a = ap.parse_args()
    meta, P, S = rd("meta.json"), tab("players.json"), tab("schedule.json")
    proj, status = rd("proj.json", {}), rd("status.json", {})
    W = meta["next_week"]
    if proj.get("week") != W:
        print(f"proj.json is for week {proj.get('week')}, site is on week {W}: projections left out", file=sys.stderr)
        proj = {}
    mult = play_mult(SITE, W, S)
    pos = P.sort_values("week").groupby("player_id").position.last()
    def rank(d):
        s = pd.Series(d, dtype=float)
        s = s[s.index.isin(pos.index)]
        return s.groupby(pos.reindex(s.index)).rank(ascending=False, method="min").astype(int).to_dict()
    ranks, ros_ranks = rank(proj.get("p") or {}), rank(proj.get("r") or {})
    dv = dvp(P[P.week <= meta["last_completed_week"]])
    ids, rost = players_for(meta, P, proj)
    if a.limit:  # test runs: the top N by this week's projection (not the first N by id)
        pp = proj.get("p") or {}
        ids = sorted(ids, key=lambda k: -(pp.get(k) or 0))[:a.limit]
    moved = moved_teams(SITE)
    names = P.sort_values("week").groupby("player_id").player_display_name.last().to_dict()
    FS = [F for F in (build_facts(i, P, S, meta, proj, status, mult, ranks, dv, ros_ranks, moved, names) for i in ids) if F]
    print(f"Wk {W}: {len(FS)} players ({len(rost)} rostered in {LEAGUE}), "
          f"{sum(len(F['facts']) for F in FS) / max(1, len(FS)):.1f} facts each", file=sys.stderr)
    OUT_CLAIMS.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT_CLAIMS / f"facts_{meta['season']}_w{W}.json.gz", "wt") as fh:
        json.dump(FS, fh)
    if a.facts_only:
        return
    U, R, replies = {}, {}, {}
    if not a.direct:
        replies = run_batch(FS, U, R, a.wait)
    done, failed, raws = {}, {}, {}
    for F in FS:
        rep, note, raw = replies.get(F["id"]), "", None
        for attempt in (1, 2):  # batch reply (or a direct call if none came back), then one retry with the reason
            if rep is None or attempt == 2:
                try:
                    rep = direct(F, note if attempt == 2 else "", U, R)
                except ReplyError as e:
                    rep = {"_err": str(e), "_raw": e.raw}
                except Exception as e:  # noqa: BLE001
                    rep = {"_err": f"API error {e}"}
            if "_err" in rep:
                note, raw, rep = rep["_err"], rep.get("_raw"), None
                continue
            ok, note = check(rep, F)
            if ok:
                done[F["id"]] = ok
                break
            raw, rep = json.dumps(rep)[:2000], None
        else:
            failed[F["id"]] = note
            raws[F["id"]] = raw
    U["stop_reasons"] = R
    write(meta, FS, done, failed, U, raws)


def write(meta, FS, done, failed, U, raws=None):
    W = meta["next_week"]
    asof = pd.Timestamp.now(tz="America/Los_Angeles").strftime("%Y-%m-%d")
    OUT_CARD.mkdir(parents=True, exist_ok=True)
    for f in OUT_CARD.glob("*.json"):  # last week's outlooks go away (a player with no outlook this week shows none)
        f.unlink()
    claims = []
    for F in FS:
        o = done.get(F["id"])
        if not o:
            continue
        fx = {f["id"]: f["t"] for f in F["facts"]}
        used = sorted({i for _, ids in o["lines"] for i in ids} | set((o["claim"] or {}).get("f", [])), key=lambda x: int(x[1:]))
        card = {"w": W, "asof": asof, "lines": o["lines"], "facts": {i: fx[i] for i in used},
                "claim": (o["claim"] or {}).get("t")}
        (OUT_CARD / f"{F['id']}.json").write_text(json.dumps(card, separators=(",", ":")))
        if o["claim"]:
            claims.append({"id": F["id"], "name": F["name"], "pos": F["pos"], "team": F["team"], **{k: o["claim"][k] for k in ("metric", "op", "value", "t", "f")},
                           "facts": [fx[i] for i in o["claim"]["f"]]})
    (OUT_CLAIMS / f"{meta['season']}_w{W}.json").write_text(json.dumps(
        {"season": meta["season"], "week": W, "asof": asof, "model": MODEL, "players": len(FS), "written": len(done),
         "failed": failed, "usage": U, "claims": claims, "failed_raw": raws or {}}, indent=1))
    print(f"wrote {len(done)} outlooks, {len(claims)} claims; {len(failed)} failed; usage {U}", file=sys.stderr)


if __name__ == "__main__":
    main()
