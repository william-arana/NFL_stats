"""Pull Sleeper league rosters for the leagues in data/leagues.json.

Writes:
  data/site/leagues.json     who is rostered where (players as nflverse gsis ids, defenses as "DEF:TEAM")
  data/site/sleeper_map.json sleeper_id -> gsis_id for offensive players + kickers, so the browser can
                             map a live Sleeper roster fetch onto the stats.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "data" / "leagues.json").read_text())
OUT = ROOT / "data" / "site"
API = "https://api.sleeper.app/v1"
POS = {"QB", "RB", "WR", "TE", "K"}

# Sleeper uses a few different team codes than nflverse
TEAM_FIX = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS"}


def get(path: str):
    r = requests.get(API + path, timeout=60)
    r.raise_for_status()
    return r.json()


def main() -> None:
    players = get("/players/nfl")
    smap: dict[str, str] = {}
    for sid, p in players.items():
        gsis = (p.get("gsis_id") or "").strip()
        if gsis and (p.get("position") in POS or set(p.get("fantasy_positions") or []) & POS):
            smap[sid] = gsis
    # fill gaps from nflverse/dynastyprocess id map when available
    try:
        import nflreadpy as nfl

        ids = nfl.load_ff_playerids().select("sleeper_id", "gsis_id").drop_nulls()
        for sid, gsis in ids.iter_rows():
            sid = str(sid).split(".")[0]
            smap.setdefault(sid, gsis)
    except Exception as e:  # noqa: BLE001
        print(f"[sleeper] ff_playerids unavailable ({e})")

    def to_key(sid: str) -> str | None:
        if sid in smap:
            return smap[sid]
        p = players.get(sid) or {}
        if p.get("position") == "DEF" or (len(sid) <= 3 and sid.isalpha()):
            return "DEF:" + TEAM_FIX.get(sid, sid)
        return None

    state = get("/state/nfl")
    leagues = []
    for lg in CFG["leagues"]:
        info = get(f"/league/{lg['id']}")
        users = {u["user_id"]: u for u in get(f"/league/{lg['id']}/users")}
        rosters = []
        unmapped = 0
        for r in get(f"/league/{lg['id']}/rosters"):
            u = users.get(r.get("owner_id")) or {}
            keys = []
            for sid in r.get("players") or []:
                k = to_key(str(sid))
                if k:
                    keys.append(k)
                else:
                    unmapped += 1
            rosters.append({
                "roster_id": r["roster_id"],
                "owner": u.get("display_name") or "",
                "team_name": (u.get("metadata") or {}).get("team_name") or u.get("display_name") or f"Team {r['roster_id']}",
                # custom team logo if they set one in Sleeper, else their profile avatar
                "avatar": (u.get("metadata") or {}).get("avatar") or (f"https://sleepercdn.com/avatars/thumbs/{u['avatar']}" if u.get("avatar") else None),
                "players": keys,
                "starters": [to_key(str(s)) for s in (r.get("starters") or []) if to_key(str(s))],
                "faab_left": (info.get("settings") or {}).get("waiver_budget", 100) - (r.get("settings") or {}).get("waiver_budget_used", 0),
                "wins": (r.get("settings") or {}).get("wins", 0),
                "losses": (r.get("settings") or {}).get("losses", 0),
                "ties": (r.get("settings") or {}).get("ties", 0),
                "fpts": round((r.get("settings") or {}).get("fpts", 0) + (r.get("settings") or {}).get("fpts_decimal", 0) / 100, 2),
                "fpts_against": round((r.get("settings") or {}).get("fpts_against", 0) + (r.get("settings") or {}).get("fpts_against_decimal", 0) / 100, 2),
            })
        week = state.get("display_week") or state.get("week") or 1
        try:
            mus = [{"matchup_id": m.get("matchup_id"), "roster_id": m["roster_id"], "points": m.get("points") or 0}
                   for m in get(f"/league/{lg['id']}/matchups/{week}") if m.get("matchup_id") is not None]
        except Exception as e:  # noqa: BLE001
            print(f"[sleeper] {lg['name']}: matchups unavailable ({e})")
            mus = []
        leagues.append({"week": week, "matchups": mus, **{k: lg[k] for k in ("id", "name", "teams", "my_roster_id")}, "default": bool(lg.get("default")), "viewers": lg.get("viewers", []),
                        "rosters": rosters, "unmapped": unmapped})
        print(f"[sleeper] {lg['name']}: {len(rosters)} rosters, {sum(len(r['players']) for r in rosters)} players, {unmapped} unmapped")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "leagues.json").write_text(json.dumps({"updated_utc": now, "leagues": leagues}, separators=(",", ":")))
    (OUT / "sleeper_map.json").write_text(json.dumps({"updated_utc": now, "team_fix": TEAM_FIX, "map": smap}, separators=(",", ":")))
    print(f"[sleeper] map: {len(smap)} players")


if __name__ == "__main__":
    main()
