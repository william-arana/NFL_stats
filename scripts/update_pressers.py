"""Weekly head-coach press-conference digest for the NFL_stats Pressers page.

For each team site (all 32 run the same NFL club platform):
  1. Read its video sitemap and keep press conferences / media sessions from the last few days.
     Weekly mode (default): head coach only, two per team: the day-after-game presser and the
     first-practice-day presser = the two most recent non-postgame HC pressers on different days.
  2. Load each video page in headless Chromium, catch the caption playlist (subs.m3u8) and
     stitch the WebVTT segments into a transcript.
  3. Have Claude turn the transcript into a structured summary (injuries, roles, fantasy signals).

Writes:
  data/pressers/YYYY-MM-DD.json   that day's summaries, all teams
  data/pressers/index.json        available dates + every video already processed

Transcripts are only held in memory: the repo (and the site) publish summaries and short quotes,
never the full captions.

Run:  python scripts/update_pressers.py                     (teams from PRESSERS_TEAMS, default ALL)
      python scripts/update_pressers.py LV KC DET           (just these teams)
      python scripts/update_pressers.py LV --dry-run        (find videos + captions, no Claude calls, no writes)
      --all             every press video (old daily behaviour), not just the weekly HC pick
      --save-dir=DIR    also write each transcript to DIR/<date>/<team> <slug>.txt (private use only:
                        never point this inside the public repo / site)
Env:  ANTHROPIC_API_KEY, PRESSERS_MODEL (default claude-haiku-5-5), PRESSERS_DAYS (default 8),
      PRESSERS_MAX (max new videos per run, default 150)
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "pressers"
INDEX = OUT_DIR / "index.json"
PLAYERS = ROOT / "data" / "site" / "players.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

TEAMS = {
    "ARI": "azcardinals.com", "ATL": "atlantafalcons.com", "BAL": "baltimoreravens.com", "BUF": "buffalobills.com",
    "CAR": "panthers.com", "CHI": "chicagobears.com", "CIN": "bengals.com", "CLE": "clevelandbrowns.com",
    "DAL": "dallascowboys.com", "DEN": "denverbroncos.com", "DET": "detroitlions.com", "GB": "packers.com",
    "HOU": "houstontexans.com", "IND": "colts.com", "JAX": "jaguars.com", "KC": "chiefs.com",
    "LA": "therams.com", "LAC": "chargers.com", "LV": "raiders.com", "MIA": "miamidolphins.com",
    "MIN": "vikings.com", "NE": "patriots.com", "NO": "neworleanssaints.com", "NYG": "giants.com",
    "NYJ": "newyorkjets.com", "PHI": "philadelphiaeagles.com", "PIT": "steelers.com", "SEA": "seahawks.com",
    "SF": "49ers.com", "TB": "buccaneers.com", "TEN": "tennesseetitans.com", "WAS": "commanders.com",
}

# Head coach per team (2026). Matched by last name in the title/description/tags.
COACHES = {
    "ARI": "Mike LaFleur", "ATL": "Kevin Stefanski", "BAL": "Jesse Minter", "BUF": "Joe Brady",
    "CAR": "Dave Canales", "CHI": "Ben Johnson", "CIN": "Zac Taylor", "CLE": "Todd Monken",
    "DAL": "Brian Schottenheimer", "DEN": "Sean Payton", "DET": "Dan Campbell", "GB": "Matt LaFleur",
    "HOU": "DeMeco Ryans", "IND": "Shane Steichen", "JAX": "Liam Coen", "KC": "Andy Reid",
    "LA": "Sean McVay", "LAC": "Jim Harbaugh", "LV": "Klint Kubiak", "MIA": "Jeff Hafley",
    "MIN": "Kevin O'Connell", "NE": "Mike Vrabel", "NO": "Kellen Moore", "NYG": "John Harbaugh",
    "NYJ": "Aaron Glenn", "PHI": "Nick Sirianni", "PIT": "Mike McCarthy", "SEA": "Mike Macdonald",
    "SF": "Kyle Shanahan", "TB": "Todd Bowles", "TEN": "Robert Saleh", "WAS": "Dan Quinn",
}
POSTGAME = re.compile(r"post-?game", re.I)


def is_head_coach(team: str, title: str, desc: str, tags: list[str]) -> bool:
    """Title only: descriptions of coordinator/player videos often mention the head coach too."""
    last = COACHES[team].split()[-1]
    pat = re.escape(last).replace("'", "['’]?")  # O'Connell / O’Connell / OConnell
    if re.search(r"\b(?:asst\.?|assistant)\s+(?:head coach|HC)\b", title, re.I):
        return bool(re.search(rf"\b{pat}\b", title, re.I))
    return bool(re.search(rf"\b{pat}\b", title, re.I) or re.search(r"\bhead coach\b|\bHC\b", title, re.I))


# Each club tags its videos a little differently ("Press Conferences", "Media Pass", Detroit's
# "Media Sessions", SF's "49ers Press Pass", the Giants' "Interviews"), so match tags and titles.
PRESSER_TAG = re.compile(r"press conference|news conference|media pass|media session|press pass|^interviews$|media availability|scrums?$|coaches (?:and|&|/) executives", re.I)
PRESSER_TITLE = re.compile(r"press conference|news conference|presser|media availability|\bscrums?\b|postgame (?:press|interview|availability)", re.I)
SKIP = re.compile(r"espa[nñ]ol|spanish|highlight|podcast|cheer|trailer|mic'?d up|sights (?:&|and) sounds", re.I)
MIN_SEC, MAX_SEC = 60, 3600

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "v": "http://www.google.com/schemas/sitemap-video/1.1"}


def log(msg: str) -> None:
    print(f"[pressers] {msg}", flush=True)


def get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# ---------- 1. discover ----------

def discover(team: str, since: date) -> list[dict]:
    domain = TEAMS[team]
    root = ET.fromstring(get(f"https://www.{domain}/sitemap-video-fast-changing.xml"))
    found = []
    for u in root.findall("s:url", NS):
        v = u.find("v:video", NS)
        if v is None:
            continue
        title = unescape(v.findtext("v:title", "", NS)).strip()
        tags = [t.strip() for t in unescape(v.findtext("v:tag", "", NS)).split(",") if t.strip()]
        pub_ts = v.findtext("v:publication_date", "", NS)
        pub = pub_ts[:10]
        dur = int(v.findtext("v:duration", "0", NS) or 0)
        hay = " ".join([title, *tags])
        if not pub or date.fromisoformat(pub) < since or SKIP.search(hay):
            continue
        if not (any(PRESSER_TAG.search(t) for t in tags) or PRESSER_TITLE.search(title)):
            continue
        if dur and not (MIN_SEC <= dur <= MAX_SEC):
            continue
        url = u.findtext("s:loc", "", NS)
        desc = unescape(re.sub(r"<[^>]+>", "", v.findtext("v:description", "", NS))).strip()
        found.append({
            "id": f"{team}:{url.rstrip('/').rsplit('/', 1)[-1]}", "team": team, "url": url, "title": title,
            "description": desc, "tags": tags, "date": pub, "ts": pub_ts, "duration": dur,
            "hc": is_head_coach(team, title, desc, tags), "postgame": bool(POSTGAME.search(hay) or POSTGAME.search(url)),
            "thumb": v.findtext("v:thumbnail_loc", "", NS),
        })
    return found


SCHEDULE = ROOT / "data" / "site" / "schedule.json"
def kickoffs(team: str, now: datetime) -> list[datetime]:
    """UTC kickoff times of the team's games that have started, newest first (nflverse: ET)."""
    from zoneinfo import ZoneInfo
    try:
        d = json.loads(SCHEDULE.read_text())["data"]
    except (OSError, KeyError, ValueError):
        return []
    et = ZoneInfo("America/New_York")
    out = []
    for day, tm, a, h in zip(d["gameday"], d["gametime"], d["away_team"], d["home_team"]):
        if team in (a, h) and day and tm:
            k = datetime.fromisoformat(f"{day}T{tm}").replace(tzinfo=et).astimezone(timezone.utc)
            if k < now:
                out.append(k)
    return sorted(out, reverse=True)


def _ts(v: dict) -> datetime:
    try:
        t = datetime.fromisoformat(v["ts"].replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.fromisoformat(v["date"]).replace(tzinfo=timezone.utc)


def pick_weekly(vids: list[dict], team: str = "", now: datetime | None = None) -> list[dict]:
    """Head coach only, two per week, anchored on the team's last game (nflverse schedule):
    day_after = first HC presser posted 12h+ after kickoff (so the postgame presser is skipped),
    first_practice = the next HC presser on a later (ET) day. If the last game has no presser
    after it yet (run right after a game), use the game before. No schedule: two most recent."""
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    now = now or datetime.now(timezone.utc)
    hc = sorted((v for v in vids if v["hc"] and not v["postgame"]), key=_ts)
    ks = kickoffs(team, now) if team else []
    window: list[dict] = []
    def after_game(v: dict, k: datetime) -> bool:
        # next ET calendar day, from 6 AM on (late postgame uploads land just after midnight);
        # sitemaps without a time of day only give the date, so then just "a later date"
        t, kd = _ts(v).astimezone(et), k.astimezone(et).date()
        if (t.hour, t.minute, t.second) == (0, 0, 0) or (_ts(v).hour, _ts(v).minute) == (0, 0):
            return t.date() > kd or _ts(v).date() > kd
        return t.date() > kd and (t.date() > kd + timedelta(days=1) or t.hour >= 6)

    for i, k in enumerate(ks[:3]):
        end = ks[i - 1] if i else now + timedelta(days=1)
        window = [v for v in hc if after_game(v, k) and _ts(v) < end]
        if window:
            break
    if not ks:
        window = hc[-2:]
    picked: list[dict] = []
    for v in window:
        if all(_ts(p).astimezone(et).date() != _ts(v).astimezone(et).date() for p in picked):
            picked.append(v)
        if len(picked) == 2:
            break
    for v, kind in zip(picked, ["day_after", "first_practice"]):
        v["kind"] = kind
    return picked


# ---------- 2. captions ----------

def vtt_to_text(vtt: str) -> str:
    """WebVTT segments -> plain transcript, one line per speaker turn (">>" in broadcast captions)."""
    lines: list[str] = []
    for raw in vtt.splitlines():
        t = unescape(raw.strip())
        if not t or t.startswith(("WEBVTT", "X-TIMESTAMP", "NOTE")) or "-->" in t or t.isdigit():
            continue
        if lines and lines[-1] == t:  # segment boundaries repeat the last cue
            continue
        lines.append(t)
    text = re.sub(r"\s+", " ", " ".join(lines))
    return re.sub(r"\s*>>\s*", "\n>> ", text).strip()


class Stuck(Exception):
    pass


def _alarm(*_):
    raise Stuck("took over 120s")


def fetch_captions(videos: list[dict]) -> None:
    _fetch_captions(videos)
    retry = [v for v in videos if not v.get("transcript")]
    if retry:
        log(f"retrying {len(retry)} video(s) once")
        for v in retry:
            v.pop("error", None)
        _fetch_captions(retry)


def _fetch_captions(videos: list[dict]) -> None:
    """Fill v["transcript"] (or v["error"]) for each video, using one headless browser.
    Each video gets a 120 s watchdog so one stuck page can't eat the whole run."""
    import signal
    from playwright.sync_api import sync_playwright

    signal.signal(signal.SIGALRM, _alarm)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 800})
        for v in videos:
            page = ctx.new_page()
            page.set_default_timeout(30000)
            signal.alarm(120)
            subs: list[str] = []
            page.on("request", lambda r: subs.append(r.url) if "subs.m3u8" in r.url else None)
            try:
                page.goto(v["url"], wait_until="domcontentloaded", timeout=45000)
                # The page JSON pairs each slug with its MCP (video platform) id; the caption
                # segments live under /<mcpID>/, which tells us which playlist is this video's.
                slug = v["url"].rstrip("/").rsplit("/", 1)[-1]
                html = page.content()
                m = re.search(r'"slug":"%s".*?"mcpID":"(\d+)"' % re.escape(slug), html, re.S)
                mcp = m.group(1) if m else None
                for _ in range(40):
                    if subs:
                        break
                    page.wait_for_timeout(500)
                    if _ == 10:  # nudge the player if autoplay didn't start
                        page.evaluate("try{document.querySelector('video')?.play?.()?.catch?.(()=>{})}catch(e){}")
                v["transcript"] = pick_transcript(subs, mcp)
                if not v["transcript"]:
                    v["error"] = "no captions found"
            except Exception as e:  # noqa: BLE001
                v["error"] = f"{type(e).__name__}: {e}"[:200]
            finally:
                signal.alarm(0)
                try:
                    page.close()
                except Exception:  # noqa: BLE001
                    pass
            log(f"  {v['id']}: {len(v.get('transcript', '').split())} words" + (f" ({v['error']})" if v.get("error") else ""))
        browser.close()


def pick_transcript(sub_urls: list[str], mcp: str | None) -> str:
    for su in dict.fromkeys(sub_urls):
        segs = [l for l in get(su).splitlines() if l.startswith("http")]
        if not segs or (mcp and f"/{mcp}/" not in segs[0]):
            continue  # a preroll or a different video on the page
        parts = []
        for seg in segs:  # sequential: parallel fetches got 403s from the caption CDN
            try:
                parts.append(get(seg, timeout=15))
            except Exception:  # noqa: BLE001
                import time
                time.sleep(2)
                parts.append(get(seg, timeout=15))
        return vtt_to_text("\n".join(parts))
    return ""


# ---------- 3. signals ----------
# One Claude call per presser -> JSON. Plain Messages API (same as build_articles.py), no SDK.

SIGNAL_TOPICS = ["role", "usage", "injury", "depth_chart", "scheme", "matchup", "trade_or_roster", "other"]

SYSTEM = """You turn one NFL head coach press conference transcript into structured fantasy-football signals.

The transcript comes from auto-generated broadcast captions: names are often misspelled, there are no speaker names,
and ">>" marks a new speaker (usually a reporter question, then the coach's answer). Use the roster to correct names and
only name a player when you are confident who is meant. Attribute statements to the coach, not to the reporter asking.

Return ONLY a JSON object (no code fences, no prose) with these keys:
{
 "headline": one line, the most useful takeaway for a fantasy manager,
 "summary": a thorough paragraph (5-8 sentences) of what the coach said, in your own words,
 "injuries": [{"player", "status": one of out|doubtful|questionable|limited|full|returning|ir|unclear, "detail"}],
 "signals": [{
    "player": exact roster name,
    "topic": one of role|usage|injury|depth_chart|scheme|matchup|trade_or_roster|other,
    "signal": "up" | "down" | "watch",
    "tone": "positive" | "negative" | "neutral" | "hedged"   (how the coach talked about him),
    "claim": what the coach said or implied will happen, as a checkable statement
             (e.g. "will get more snaps at RB this week"; "" if nothing checkable),
    "note": one sentence, why it matters for fantasy,
    "quote": the coach's own words backing it, verbatim, max 15 words ("" if none)
 }],
 "topics": [{"topic", "detail"}]  other subjects (scheme, opponent, team news), 1-2 sentences each,
 "opponent": next opponent if discussed, else ""
}
Rules: one signal per player per topic. Skip players who were only mentioned in passing. Paraphrase everything except
"quote". Leave a list empty rather than padding it. Never invent a quote."""


def rosters() -> dict[str, dict[str, str]]:
    """team -> {display name: gsis player_id} for the latest season rows."""
    try:
        d = json.loads(PLAYERS.read_text())["data"]
    except (OSError, KeyError, ValueError):
        return {}
    out: dict[str, dict[str, str]] = {}
    for pid, name, team, pos in zip(d["player_id"], d["player_display_name"], d["team"], d["position"]):
        if team and name:
            out.setdefault(team, {})[name] = pid
    # O-line (has ids) and defenders (names only) so the model can fix misheard names there too
    for f, idk in (("oline.json", "player_id"), ("defenders.json", None)):
        try:
            x = json.loads((PLAYERS.parent / f).read_text())["data"]
        except (OSError, KeyError, ValueError):
            continue
        ids = x[idk] if idk else [""] * len(x["name"])
        for pid, name, team in zip(ids, x["name"], x["team"]):
            if team and name:
                out.setdefault(team, {}).setdefault(name, pid)
    return out


def _norm(n: str) -> str:
    return re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", n.lower()))


def link_ids(items: list[dict], roster: dict[str, str]) -> None:
    by = {_norm(k): v for k, v in roster.items()}
    for it in items:
        it["player_id"] = roster.get(it.get("player", "")) or by.get(_norm(it.get("player", "")), "")


def summarize(model: str, v: dict, roster: dict[str, str]) -> tuple[dict, dict]:
    import requests

    key = os.environ["ANTHROPIC_API_KEY"]
    msg = (
        f"Team: {v['team']} (head coach {COACHES[v['team']]})\nVideo title: {v['title']}\nDescription: {v['description']}\n"
        f"Posted: {v['date']} ({v.get('kind', '')})\nRoster: {', '.join(sorted(roster)) or 'n/a'}\n\n"
        f"<transcript>\n{v['transcript']}\n</transcript>"
    )
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=180,
                      headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                      json={"model": model, "max_tokens": 6000, "system": SYSTEM,
                            "messages": [{"role": "user", "content": msg}]})
    if r.status_code != 200:
        raise RuntimeError(f"Claude API {r.status_code}: {r.text[:200]}")
    data = r.json()
    txt = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip()).strip()
    out = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
    for k in ("injuries", "signals", "topics"):
        out[k] = [x for x in out.get(k) or [] if isinstance(x, dict)]
    for sg in out["signals"]:
        if sg.get("topic") not in SIGNAL_TOPICS:
            sg["topic"] = "other"
        if len((sg.get("quote") or "").split()) > 15:  # keep quotes short (no transcript republishing)
            sg["quote"] = ""
    link_ids(out["signals"], roster)
    link_ids(out["injuries"], roster)
    u = data.get("usage", {})
    return out, {"input_tokens": u.get("input_tokens", 0), "output_tokens": u.get("output_tokens", 0)}


# ---------- 4. write ----------

def load_index() -> dict:
    try:
        return json.loads(INDEX.read_text())
    except (OSError, ValueError):
        return {"dates": [], "done": {}}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    every = "--all" in sys.argv
    save_dir = next((Path(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--save-dir=")), None)
    env_teams = os.environ.get("PRESSERS_TEAMS", "ALL").replace(",", " ").split()
    teams = [t.upper() for t in (args or env_teams)]
    if teams == ["ALL"]:
        teams = list(TEAMS)
    days = int(os.environ.get("PRESSERS_DAYS", "8"))
    cap = int(os.environ.get("PRESSERS_MAX", "150"))
    model = os.environ.get("PRESSERS_MODEL", "claude-haiku-5-5")
    since = datetime.now(timezone.utc).date() - timedelta(days=days)

    index = load_index()
    new: list[dict] = []
    for t in teams:
        try:
            allv = discover(t, since)
        except Exception as e:  # noqa: BLE001
            log(f"{t}: sitemap FAILED ({e})")
            continue
        if "--list" in sys.argv:
            for v in sorted(allv, key=lambda v: v["date"]):
                log(f"    {v['ts'][:19]} {'HC ' if v['hc'] else '   '}{'PG ' if v['postgame'] else '   '}{v['duration']:>5}s {v['title'][:70]} | {', '.join(v['tags'])[:50]}")
        vids = allv if every else pick_weekly(allv, t)
        vids = [v for v in vids if v["id"] not in index["done"]]
        n_hc = sum(v["hc"] for v in allv)
        log(f"{t}: {len(allv)} press videos since {since}, {n_hc} head coach, picked: "
            + (", ".join(f"{v['date']} {v.get('kind', '')} '{v['title'][:60]}'" for v in vids) or "none"))
        new += vids
    if len(new) > cap:
        log(f"capping {len(new)} -> {cap} videos this run (the rest wait for tomorrow)")
        new = sorted(new, key=lambda v: v["date"], reverse=True)[:cap]
    if not new:
        log("nothing new")
        return

    fetch_captions(new)
    ready = [v for v in new if v.get("transcript")]
    log(f"captions: {len(ready)}/{len(new)}")
    if save_dir:
        for v in ready:
            f = save_dir / v["date"] / f"{v['team']} {v['id'].split(':', 1)[1]}.txt"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(f"{v['title']}\n{v['url']}\n\n{v['transcript']}\n")
        log(f"saved {len(ready)} transcripts under {save_dir}")
    if dry:
        for v in new:
            log(f"  [dry] {v['date']} {v['team']} {v['title']} -> {len(v.get('transcript', '').split())} words")
        return

    ros = rosters()
    tok = {"input_tokens": 0, "output_tokens": 0}
    by_date: dict[str, list[dict]] = {}
    for v in ready:
        try:
            s, u = summarize(model, v, ros.get(v["team"], {}))
            tok = {k: tok[k] + u[k] for k in tok}
        except Exception as e:  # noqa: BLE001
            log(f"  {v['id']}: summary FAILED ({e})")
            continue
        entry = {k: v[k] for k in ("id", "team", "url", "title", "date", "duration", "thumb")}
        entry["kind"] = v.get("kind", "")
        entry["coach"] = COACHES[v["team"]]
        entry.update(words=len(v["transcript"].split()), model=model, **s)
        by_date.setdefault(v["date"], []).append(entry)
        index["done"][v["id"]] = v["date"]
        log(f"  {v['id']}: {s['headline'][:90]}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for d, entries in by_date.items():
        f = OUT_DIR / f"{d}.json"
        old = json.loads(f.read_text()) if f.exists() else []
        merged = {e["id"]: e for e in old + entries}
        f.write_text(json.dumps(sorted(merged.values(), key=lambda e: (e["team"], e["id"])), ensure_ascii=False, indent=1))
    index["dates"] = sorted({*index["dates"], *by_date}, reverse=True)
    index["updated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    INDEX.write_text(json.dumps(index, indent=1, sort_keys=True))
    log(f"wrote {sum(map(len, by_date.values()))} summaries across {len(by_date)} day(s); "
        f"tokens in {tok['input_tokens']:,} / out {tok['output_tokens']:,}")


if __name__ == "__main__":
    main()
