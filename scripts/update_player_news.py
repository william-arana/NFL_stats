"""Per-player and per-defense news archive for the player cards and the Trade page.

Writes data/site/news/<gsis_id>.json for players and data/site/news/DEF_<TEAM>.json for defenses:
  {"id": ..., "name": ..., "updated_utc": ..., "items": [{"h", "s", "d", "src", "url"}, ...]}  (newest first)

Who gets a file: everyone rostered in a tracked Sleeper league, Sleeper's trending adds, and the top
fantasy scorers this season, so the Trade page has news for anyone worth trading for.

Sources (each optional; a failure just leaves the old items in place):
  - Sleeper player news (RotoWire, FantasyPros, RotoBaller): the newest 10 per player, ~2-3 weeks
  - ESPN fantasy player news: the newest ~8 per player (RotoWire blurbs + ESPN stories)
  - ESPN team news: up to 50 stories per team (for D/ST cards)
  - RotoWire's player-news RSS already saved in data/site/news.json, matched by name

Items are merged into what's already on disk, so the archive keeps growing all season even after a
source drops older stories. Run by .github/workflows/update-sleeper.yml three times a day.
"""
from __future__ import annotations

import html
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "data" / "site"
OUT = SITE / "news"
UA = {"User-Agent": "Mozilla/5.0 (NFL_stats personal dashboard; +https://william-arana.github.io/NFL_stats/)"}
TOP_SCORERS = 320      # also archive the top N fantasy scorers, rostered or not
KEEP = 200             # max items kept per player
TEAM_FIX = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS"}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso(s) -> str | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:  # noqa: BLE001
        return None


def clean(s, n: int = 600) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*Visit RotoWire\.com for more analysis on this update\.?$", "", s)
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s)
    return re.sub(r"[^a-z]", "", s)


session = requests.Session()
session.headers.update(UA)


def get_json(url: str):
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def espn_items(articles) -> list[dict]:
    out = []
    for a in articles or []:
        h = clean(a.get("headline"), 220)
        if not h:
            continue
        links = a.get("links") or {}
        url = ((links.get("web") or {}).get("href")) or ((links.get("mobile") or {}).get("href"))
        story = a.get("story") or ""
        # ESPN's short fantasy blurbs come in "story"; long articles are better summarized by "description"
        s = clean(story if story and len(story) < 1200 else (a.get("description") or story))
        kind = (a.get("type") or "").lower()
        src = "ESPN fantasy" if "headline" in kind or "rotowire" in kind else "ESPN"
        if a.get("byline") and "rotowire" in str(a.get("byline")).lower():
            src = "RotoWire via ESPN"
        out.append({"h": h, "s": s if s != h else "", "d": iso(a.get("published") or a.get("lastModified")), "src": src, "url": url})
    return out


def espn_player(espn_id: str) -> list[dict]:
    j = get_json(f"https://site.api.espn.com/apis/fantasy/v2/games/ffl/news/players?playerId={espn_id}&limit=50")
    return espn_items(j.get("feed"))


def espn_team(team_id: str) -> list[dict]:
    j = get_json(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?team={team_id}&limit=50")
    return espn_items(j.get("articles"))


SLEEPER_SRC = {"rotowire": "RotoWire", "fantasy_pros": "FantasyPros", "rotoballer": "RotoBaller"}


def sleeper_items(arr) -> list[dict]:
    out = []
    for a in arr or []:
        m = a.get("metadata") or {}
        h = clean(re.sub(r"^.{3,40}? - ", "", m.get("title") or ""), 220)
        if not h:
            continue
        s = clean(" ".join(x for x in [m.get("description"), m.get("analysis")] if x), 700)
        d = datetime.fromtimestamp(a["published"] / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if a.get("published") else None
        src = a.get("source") or ""
        out.append({"h": h, "s": s, "d": d, "src": SLEEPER_SRC.get(src, src.replace("_", " ").title()), "url": m.get("url")})
    return out


def sleeper_player(sid: str) -> list[dict]:
    return sleeper_items(get_json(f"https://api.sleeper.app/players/nfl/{sid}/news?limit=50"))


def key(it: dict) -> str:
    # headline, not URL: RotoWire links every blurb to the same player page
    return re.sub(r"\W", "", it["h"].lower())[:80]


def merge(old: list[dict], new: list[dict]) -> list[dict]:
    by = {}
    for it in old + new:  # newer fetch wins for the same story
        k = key(it)
        by[k] = {**by.get(k, {}), **{a: b for a, b in it.items() if b}}
    items = sorted(by.values(), key=lambda x: x.get("d") or "", reverse=True)
    return items[:KEEP]


def save(fid: str, name: str, new: list[dict]) -> bool:
    path = OUT / f"{fid.replace(':', '_')}.json"
    old = {}
    if path.exists():
        try:
            old = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            old = {}
    items = merge(old.get("items", []), new)
    if items == old.get("items") and old.get("name") == name:
        return False
    path.write_text(json.dumps({"id": fid, "name": name, "updated_utc": now(), "items": items}, separators=(",", ":"), ensure_ascii=False))
    return True


def load_rows(name: str) -> list[dict]:
    j = json.loads((SITE / f"{name}.json").read_text())
    return [{c: j["data"][c][i] for c in j["cols"]} for i in range(j["rows"])]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ids = json.loads((SITE / "ids.json").read_text()) if (SITE / "ids.json").exists() else {}
    names: dict[str, str] = {}
    want: set[str] = set()

    # top scorers this season
    tot: dict[str, float] = {}
    for r in load_rows("players"):
        names[r["player_id"]] = r["player_display_name"]
        tot[r["player_id"]] = tot.get(r["player_id"], 0) + (r.get("fantasy_points_ppr") or 0)
    want.update(sorted(tot, key=tot.get, reverse=True)[:TOP_SCORERS])

    # everyone rostered in a tracked league
    lg = json.loads((SITE / "leagues.json").read_text()) if (SITE / "leagues.json").exists() else {"leagues": []}
    for league in lg.get("leagues", []):
        for ros in league.get("rosters", []):
            want.update(p for p in ros.get("players", []) if not p.startswith("DEF:"))

    # trending adds
    try:
        tr = json.loads((SITE / "news.json").read_text()).get("trending") or {}
        for it in tr.get("items", []):
            if it.get("gsis_id"):
                want.add(it["gsis_id"])
                names.setdefault(it["gsis_id"], it["name"])
    except Exception:  # noqa: BLE001
        pass

    # Sleeper's player directory fills in ESPN ids + names for rostered players with no stats yet (kickers, rookies)
    try:
        sp = get_json("https://api.sleeper.app/v1/players/nfl")
        for p in sp.values():
            g = (p.get("gsis_id") or "").strip()
            if g in want:
                if p.get("espn_id") and g not in ids:
                    ids[g] = str(p["espn_id"])
                names.setdefault(g, p.get("full_name") or g)
    except Exception as e:  # noqa: BLE001
        print(f"[pnews] sleeper directory failed: {e}")

    sleeper_ids: dict[str, str] = {}
    try:
        sm = json.loads((SITE / "sleeper_map.json").read_text())["map"]
        sleeper_ids = {g: sid for sid, g in sm.items()}
    except Exception:  # noqa: BLE001
        pass

    # RotoWire blurbs already pulled by update_news.py ("Name: headline")
    rw: dict[str, list[dict]] = {}
    try:
        for s in json.loads((SITE / "news.json").read_text()).get("sources", []):
            if s.get("id") != "rotowire":
                continue
            for it in s.get("items", []):
                m = re.match(r"^(.+?):\s*(.+)$", it.get("title") or "")
                if m:
                    rw.setdefault(norm(m.group(1)), []).append({"h": m.group(2), "s": clean(it.get("summary")), "d": it.get("published"), "src": "RotoWire", "url": it.get("link")})
    except Exception:  # noqa: BLE001
        pass

    changed = fails = 0
    for i, g in enumerate(sorted(want)):
        new = list(rw.get(norm(names.get(g, "")), []))
        sid = sleeper_ids.get(g)
        if sid:
            try:
                new += sleeper_player(sid)
            except Exception as ex:  # noqa: BLE001
                fails += 1
                if fails <= 5:
                    print(f"[pnews] sleeper {names.get(g, g)}: {ex}")
            time.sleep(0.08)
        e = ids.get(g)
        if e:
            try:
                new += espn_player(e)
            except Exception as ex:  # noqa: BLE001
                fails += 1
                if fails <= 5:
                    print(f"[pnews] {names.get(g, g)}: {ex}")
            time.sleep(0.12)
        if new or (OUT / f"{g}.json").exists():
            changed += save(g, names.get(g, g), new)
    print(f"[pnews] players: {len(want)} checked, {changed} files changed, {fails} fetch failures")

    # defenses: every team (D/ST streamers are usually unrostered)
    try:
        teams = get_json("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams")
        tlist = [t["team"] for t in teams["sports"][0]["leagues"][0]["teams"]]
        tchanged = 0
        for t in tlist:
            ab = TEAM_FIX.get(t["abbreviation"], t["abbreviation"])
            try:
                tchanged += save("DEF:" + ab, t.get("displayName", ab), espn_team(t["id"]))
            except Exception as ex:  # noqa: BLE001
                print(f"[pnews] team {ab}: {ex}")
            time.sleep(0.12)
        print(f"[pnews] teams: {len(tlist)} checked, {tchanged} files changed")
    except Exception as ex:  # noqa: BLE001
        print(f"[pnews] team list failed: {ex}")


if __name__ == "__main__":
    main()
