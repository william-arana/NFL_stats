"""Pull NFL headlines + fantasy news for the home page sidebar.

Writes data/site/news.json. Every source is fetched independently; a source that fails
keeps its last good items (from the previous news.json) and is marked stale.
"""
from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "site" / "news.json"
UA = {"User-Agent": "Mozilla/5.0 (NFL_stats personal dashboard; +https://william-arana.github.io/NFL_stats/)"}
MAX = 20


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso(s: str | None) -> str | None:
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:  # noqa: BLE001
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:  # noqa: BLE001
        return None


def clean(s: str | None, n: int = 220) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def get(url: str) -> requests.Response:
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r


def rss(url: str) -> list[dict]:
    root = ET.fromstring(get(url).content)
    items = []
    for it in root.iter("item"):
        t = it.findtext("title")
        link = it.findtext("link")
        if not t or not link:
            continue
        items.append({"title": clean(t, 200), "link": link.strip(), "published": iso(it.findtext("pubDate")),
                      "summary": clean(it.findtext("description"))})
    return items[:MAX]


def espn() -> list[dict]:
    j = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=30").json()
    out = []
    for a in j.get("articles", []):
        link = ((a.get("links") or {}).get("web") or {}).get("href")
        if not a.get("headline") or not link:
            continue
        out.append({"title": clean(a["headline"], 200), "link": link, "published": iso(a.get("published")),
                    "summary": clean(a.get("description"))})
    return out[:MAX]


def nfl_com() -> list[dict]:
    page = get("https://www.nfl.com/news/series/around-the-nfl-news").text
    out, seen = [], set()
    # article cards link to /news/<slug>; the headline is the link's text (or an h3 inside it)
    for m in re.finditer(r'<a[^>]+href="((?:https://www\.nfl\.com)?/news/(?!series/)[a-z0-9-]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
        href, inner = m.group(1), m.group(2)
        link = href if href.startswith("http") else "https://www.nfl.com" + href
        h = re.search(r"<h\d[^>]*>(.*?)</h\d>", inner, re.S)
        title = clean(h.group(1) if h else inner, 200)
        if len(title) < 20 or link in seen:
            continue
        seen.add(link)
        out.append({"title": title, "link": link, "published": None, "summary": ""})
    return out[:MAX]


def sleeper_trending() -> list[dict]:
    adds = get("https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours=24&limit=25").json()
    players = get("https://api.sleeper.app/v1/players/nfl").json()
    out = []
    for a in adds:
        p = players.get(str(a["player_id"])) or {}
        name = p.get("full_name") or (f"{p.get('team') or a['player_id']} D/ST" if p.get("position") == "DEF" else str(a["player_id"]))
        out.append({"sleeper_id": str(a["player_id"]), "gsis_id": (p.get("gsis_id") or "").strip() or None, "name": name,
                    "pos": p.get("position"), "team": p.get("team"), "adds": a.get("count", 0),
                    "injury": p.get("injury_status")})
    return out


SOURCES = [
    # id, name, group, homepage, fetcher
    ("nfl", "NFL.com · Around the NFL", "headlines", "https://www.nfl.com/news/series/around-the-nfl-news", nfl_com),
    ("espn", "ESPN · Top headlines", "headlines", "https://www.espn.com/nfl/", espn),
    ("pft", "ProFootballTalk", "headlines", "https://www.nbcsports.com/nfl/profootballtalk", lambda: rss("https://www.nbcsports.com/profootballtalk.rss")),
    ("cbs", "CBS Sports NFL", "headlines", "https://www.cbssports.com/nfl/", lambda: rss("https://www.cbssports.com/rss/headlines/nfl/")),
    ("rotowire", "RotoWire · Player news", "fantasy", "https://www.rotowire.com/football/news.php?view=top", lambda: rss("https://www.rotowire.com/rss/news.php?sport=NFL")),
]


def main() -> None:
    prev = {}
    if OUT.exists():
        try:
            prev = {s["id"]: s for s in json.loads(OUT.read_text()).get("sources", [])}
        except Exception:  # noqa: BLE001
            prev = {}
    sources = []
    for sid, name, group, home, fn in SOURCES:
        try:
            items = fn()
            if not items:
                raise ValueError("no items parsed")
            sources.append({"id": sid, "name": name, "group": group, "url": home, "ok": True, "fetched": now(), "items": items})
            print(f"[news] {sid}: {len(items)} items")
        except Exception as e:  # noqa: BLE001
            old = prev.get(sid)
            sources.append({"id": sid, "name": name, "group": group, "url": home, "ok": False, "error": str(e)[:200],
                            "fetched": old.get("fetched") if old else None, "items": old.get("items", []) if old else []})
            print(f"[news] {sid}: FAILED ({e})")
    trending = None
    try:
        trending = {"fetched": now(), "items": sleeper_trending()}
        print(f"[news] sleeper trending: {len(trending['items'])}")
    except Exception as e:  # noqa: BLE001
        print(f"[news] sleeper trending: FAILED ({e})")
        try:
            trending = json.loads(OUT.read_text()).get("trending")
        except Exception:  # noqa: BLE001
            trending = None
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"updated_utc": now(), "sources": sources, "trending": trending}, separators=(",", ":")))


if __name__ == "__main__":
    main()
