"""Pull Yahoo league rosters + this week's matchups for the Yahoo leagues in data/leagues.json.

Merges them into data/site/leagues.json next to the Sleeper leagues (same shape: rosters of nflverse
gsis ids / "DEF:TEAM", matchups, records), so every page treats them the same. Yahoo has no
browser-readable API, so the site always uses this snapshot for Yahoo leagues.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from yahoo_common import ROOT, access_token, api, items, merge

CFG = json.loads((ROOT / "data" / "leagues.json").read_text())
OUT = ROOT / "data" / "site" / "leagues.json"
TEAM_FIX = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS"}


def id_map() -> dict[str, str]:
    import nflreadpy as nfl

    ids = nfl.load_ff_playerids().select("yahoo_id", "gsis_id").drop_nulls()
    return {str(y).split(".")[0]: g for y, g in ids.iter_rows()}


def fetch_league(lg: dict, tok: str, ymap: dict[str, str]) -> dict:
    key = f"nfl.l.{lg['yahoo_league_id']}"
    meta = merge(api(f"league/{key}", tok)["league"])
    week = int(meta.get("current_week") or 1)
    teams_raw = items(merge(api(f"league/{key}/teams/roster", tok)["league"]).get("teams", {}), "team")
    stand = {}
    st = merge(api(f"league/{key}/standings", tok)["league"]).get("standings") or [{}]
    st = st[0] if isinstance(st, list) else st
    for t in items(st.get("teams") or {}, "team"):
        tm = merge(t)
        ts = tm.get("team_standings") or {}
        ot = ts.get("outcome_totals") or {}
        stand[int(tm["team_id"])] = {"wins": int(ot.get("wins") or 0), "losses": int(ot.get("losses") or 0), "ties": int(ot.get("ties") or 0),
                                     "fpts": float(ts.get("points_for") or 0), "fpts_against": float(ts.get("points_against") or 0)}
    rosters, unmapped, mine = [], 0, None
    for t in teams_raw:
        tm = merge(t)
        tid = int(tm["team_id"])
        mgr = merge((items(tm.get("managers") or {}, "manager") or [{}])[0]) if isinstance(tm.get("managers"), dict) else {}
        if not mgr and isinstance(tm.get("managers"), list):
            mgr = (tm["managers"][0] or {}).get("manager", {})
        name = (tm.get("name") or f"Team {tid}").strip()
        norm = lambda x: "".join(c for c in x.lower() if c.isalnum())
        if lg.get("viewer_team") and (norm(name) == norm(lg["viewer_team"]) or (mine is None and norm(lg["viewer_team"]) in norm(name))):
            mine = tid
        keys, starters = [], []
        roster = tm.get("roster") or {}
        pcoll = (roster.get("0") or {}).get("players") if isinstance(roster, dict) else None
        for p in items(pcoll or {}, "player"):
            pm = merge(p)
            pid, pos = str(pm.get("player_id") or ""), pm.get("display_position") or pm.get("primary_position") or ""
            if pos == "DEF":
                abbr = (pm.get("editorial_team_abbr") or "").upper()
                k = "DEF:" + TEAM_FIX.get(abbr, abbr) if abbr else None
            else:
                k = ymap.get(pid)
            if not k:
                unmapped += 1
                continue
            keys.append(k)
            sel = merge(pm.get("selected_position") or [])
            if sel.get("position") not in (None, "BN", "IR", "IR+"):
                starters.append(k)
        rosters.append({"roster_id": tid, "owner": "", "team_name": name,
                        "avatar": (merge(tm.get("team_logos") or [{}]).get("team_logo") or {}).get("url") if isinstance(tm.get("team_logos"), list) else None,
                        "players": keys, "starters": starters, "faab_left": int(tm["faab_balance"]) if str(tm.get("faab_balance") or "").isdigit() else None,
                        **stand.get(tid, {"wins": 0, "losses": 0, "ties": 0, "fpts": 0, "fpts_against": 0})})
    mus = []
    try:
        sb = merge(api(f"league/{key}/scoreboard;week={week}", tok)["league"]).get("scoreboard") or {}
        sb = sb.get("0") or sb
        for i, m in enumerate(items(sb.get("matchups") or {}, "matchup"), 1):
            mm = merge(m) if isinstance(m, list) else m
            tcoll = (mm.get("0") or {}).get("teams") or mm.get("teams") or {}
            for t in items(tcoll, "team"):
                tm = merge(t)
                mus.append({"matchup_id": i, "roster_id": int(tm["team_id"]), "points": float((tm.get("team_points") or {}).get("total") or 0)})
    except Exception as e:  # noqa: BLE001
        print(f"[yahoo] {lg['name']}: scoreboard unavailable ({e})")
    if mine is None:
        print(f"[yahoo] {lg['name']}: team '{lg.get('viewer_team')}' not found; teams: {[r['team_name'] for r in rosters]}")
        mine = rosters[0]["roster_id"] if rosters else 1
    viewer = next((r["team_name"] for r in rosters if r["roster_id"] == mine), lg.get("viewer_team", ""))
    res = {"id": lg["id"], "provider": "yahoo", "name": lg.get("name") or meta.get("name"), "yahoo_name": meta.get("name"),
                "url": meta.get("url") or f"https://football.fantasysports.yahoo.com/f1/{lg['yahoo_league_id']}",
                "teams": int(meta.get("num_teams") or len(rosters)), "my_roster_id": mine, "default": False,
                "viewers": [{"roster_id": mine, "label": viewer}], "week": week, "matchups": mus, "rosters": rosters, "unmapped": unmapped}
    print(f"[yahoo] {lg['name']}: {len(rosters)} teams, {sum(len(r['players']) for r in rosters)} players, {unmapped} unmapped, viewing as {viewer}")
    return res


def main() -> None:
    yl = [lg for lg in CFG["leagues"] if lg.get("provider") == "yahoo"]
    if not yl:
        print("[yahoo] no Yahoo leagues configured")
        return
    ymap = id_map()
    tokens: dict[str, str] = {}
    snap = json.loads(OUT.read_text()) if OUT.exists() else {"leagues": []}
    keep = [lg for lg in snap.get("leagues", []) if lg.get("provider") != "yahoo"]
    out = []
    for lg in yl:
        acct = lg.get("yahoo_account") or "william"
        try:
            tok = tokens[acct] = tokens.get(acct) or access_token(acct)
        except FileNotFoundError as e:
            print(f"[yahoo] {lg['name']}: not connected yet ({e})")
            out += [x for x in snap.get("leagues", []) if x.get("id") == lg["id"]]  # keep the last snapshot if any
            continue
        try:
            out.append(fetch_league(lg, tok, ymap))
        except Exception as e:  # noqa: BLE001  one broken league shouldn't stop the others
            print(f"[yahoo] {lg['name']}: failed ({e})")
            out += [x for x in snap.get("leagues", []) if x.get("id") == lg["id"]]
    snap["leagues"] = keep + out
    snap["updated_utc"] = snap.get("updated_utc") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    snap["yahoo_updated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    OUT.write_text(json.dumps(snap, separators=(",", ":")))


if __name__ == "__main__":
    main()
