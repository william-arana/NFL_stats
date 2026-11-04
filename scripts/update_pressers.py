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
OUT_DIR = Path(os.environ["PRESSERS_OUT"]) if os.environ.get("PRESSERS_OUT") else ROOT / "data" / "pressers"
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
    m = re.search(rf"\b{pat}\b", title, re.I)
    if m and _other_speaker_first(team, title[:m.start()]):
        return False  # "Case Keenum praises Ben Johnson", "Drake Maye on Mike Vrabel": a player talking about him
    return bool(m or re.search(r"\bhead coach\b|\bHC\b", title, re.I))


_NOT_A_PERSON = re.compile(r"^(?:head coach|press conference|news conference|media availability|new england|green bay|"
                           r"kansas city|las vegas|los angeles|new orleans|new york|san francisco|tampa bay|week \d+)$", re.I)


def _other_speaker_first(team: str, before: str) -> bool:
    """True if another person's name ("First Last") comes before the coach's name in the same title part."""
    before = re.split(r"[|:“”\"–—]", before)[-1]  # only the part of the title the coach's name is in
    before = re.sub(rf"\b{re.escape(COACHES[team].split()[0])}\s*$", "", before, flags=re.I)
    return any(not _NOT_A_PERSON.match(p) for p in re.findall(r"\b([A-Z][\w'’.-]+ [A-Z][\w'’.-]+)\b", before))


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

def parse_dur(raw: str | None) -> int:
    """Seconds from a sitemap duration: plain seconds, or ISO 8601 like 'PT45M', 'P0D', 'P2DT1H52M'
    (some club archives mix both). Unparseable -> 0 (= skip the length filter)."""
    raw = (raw or "").strip()
    if raw.isdigit():
        return int(raw)
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?", raw)
    if not m:
        return 0
    d, h, mi, se = (float(x) if x else 0 for x in m.groups())
    sec = int(d * 86400 + h * 3600 + mi * 60 + se)
    return 0 if sec > 86400 else sec  # multi-day values are bad metadata: don't filter on them


def video_sitemaps(domain: str) -> list[str]:
    """Every video sitemap the club site lists (robots.txt -> sitemap indexes), for backfills:
    the fast-changing one only covers the last few weeks."""
    seen, out, todo = set(), [], []
    try:
        todo = [l.split(":", 1)[1].strip() for l in get(f"https://www.{domain}/robots.txt").splitlines()
                if l.lower().startswith("sitemap:")]
    except Exception as e:  # noqa: BLE001
        log(f"{domain}: robots.txt failed ({e})")
    todo += [f"https://www.{domain}/sitemap.xml", f"https://www.{domain}/sitemap-index.xml"]
    for depth in range(3):
        nxt = []
        for u in todo:
            if u in seen:
                continue
            seen.add(u)
            try:
                root = ET.fromstring(get(u))
            except Exception:  # noqa: BLE001
                continue
            if root.tag.endswith("sitemapindex"):
                nxt += [x.findtext("s:loc", "", NS) for x in root.findall("s:sitemap", NS)]
            elif root.find("s:url/v:video", NS) is not None:
                out.append(u)
        todo = nxt
    fast = f"https://www.{domain}/sitemap-video-fast-changing.xml"
    return list(dict.fromkeys([fast, *out]))


def discover(team: str, since: date, deep: bool = False) -> list[dict]:
    domain = TEAMS[team]
    maps = video_sitemaps(domain) if deep else [f"https://www.{domain}/sitemap-video-fast-changing.xml"]
    if deep:
        log(f"{team}: video sitemaps: {', '.join(m.rsplit('/', 1)[-1] for m in maps)}")
    found, urls = [], set()
    for sm in maps:
        try:
            found += _discover_one(team, sm, since, urls)
        except Exception as e:  # noqa: BLE001
            log(f"{team}: {sm} FAILED ({e})")
    return found


def _discover_one(team: str, sitemap: str, since: date, urls: set) -> list[dict]:
    root = ET.fromstring(get(sitemap))
    found = []
    for u in root.findall("s:url", NS):
        v = u.find("v:video", NS)
        if v is None:
            continue
        title = unescape(v.findtext("v:title", "", NS)).strip()
        tags = [t.strip() for t in unescape(v.findtext("v:tag", "", NS)).split(",") if t.strip()]
        pub_ts = v.findtext("v:publication_date", "", NS)
        pub = pub_ts[:10]
        dur = parse_dur(v.findtext("v:duration", "0", NS))
        hay = " ".join([title, *tags])
        if not pub or date.fromisoformat(pub) < since or SKIP.search(hay):
            continue
        if not (any(PRESSER_TAG.search(t) for t in tags) or PRESSER_TITLE.search(title)):
            continue
        if dur and not (MIN_SEC <= dur <= MAX_SEC):
            continue
        url = u.findtext("s:loc", "", NS)
        if url in urls:
            continue
        urls.add(url)
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


def pick_backfill(vids: list[dict], team: str, weeks: range) -> list[dict]:
    """Backfill: for each of the team's games in `weeks`, the same two HC pressers the weekly run
    picks (day after the game, then first practice day), anchored on that game's kickoff."""
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    d = json.loads(SCHEDULE.read_text())["data"]
    games = sorted(
        (datetime.fromisoformat(f"{day}T{tm}").replace(tzinfo=et).astimezone(timezone.utc), wk)
        for wk, day, tm, a, h in zip(d["week"], d["gameday"], d["gametime"], d["away_team"], d["home_team"])
        if team in (a, h) and day and tm)
    out = []
    for i, (k, wk) in enumerate(games):
        if wk not in weeks:
            continue
        end = games[i + 1][0] if i + 1 < len(games) else datetime.now(timezone.utc)
        for v in pick_weekly([v for v in vids if _ts(v) < end], team, now=end):
            v["week"] = wk
            out.append(v)
    return list({v["id"]: v for v in out}.values())


def _games(team: str) -> list[tuple[datetime, int]]:
    """All of the team's games as (UTC kickoff, week), oldest first (nflverse schedule, ET times)."""
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    try:
        d = json.loads(SCHEDULE.read_text())["data"]
    except (OSError, KeyError, ValueError):
        return []
    return sorted(
        (datetime.fromisoformat(f"{day}T{tm}").replace(tzinfo=et).astimezone(timezone.utc), wk)
        for wk, day, tm, a, h in zip(d["week"], d["gameday"], d["gametime"], d["away_team"], d["home_team"])
        if team in (a, h) and day and tm)


def pick_all(vids: list[dict], team: str, weeks: range | None = None) -> list[dict]:
    """Every head coach presser, labeled by its place in the week (anchored on the nflverse schedule):
    postgame (within ~14h of kickoff, or tagged postgame), day_after (first later day), first_practice
    (next day after that), final_practice (last one within 2 days of the next game), midweek (the rest).
    v["week"] = week of the game it follows. One per (day, label): the longest video wins (clips of the
    same presser often get posted separately)."""
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    gs = _games(team)
    def when(v: dict) -> datetime:
        t = _ts(v)
        if (t.hour, t.minute, t.second) == (0, 0, 0):  # date-only sitemap: treat as end of that ET day
            t = datetime.combine(date.fromisoformat(v["date"]), datetime.max.time().replace(microsecond=0), et).astimezone(timezone.utc)
        return t
    slots: dict[tuple[int, str], list[dict]] = {}
    for v in sorted((v for v in vids if v["hc"]), key=when):
        t = when(v)
        prev = [g for g in gs if g[0] <= t]
        k, wk = prev[-1] if prev else (None, 0)
        if weeks is not None and wk not in weeks:
            continue
        v["week"] = wk
        v["_t"] = t
        pg = v["postgame"] or (k is not None and t - k < timedelta(hours=14)
                               and not (t.astimezone(et).date() > k.astimezone(et).date() and t.astimezone(et).hour >= 6))
        slots.setdefault((wk, "pg" if pg else "rest"), []).append(v)
    out: list[dict] = []
    for (wk, grp), lst in slots.items():
        days: dict[date, dict] = {}
        for v in lst:  # longest video per ET day
            dd = v["_t"].astimezone(et).date()
            if dd not in days or (v.get("duration") or 0) > (days[dd].get("duration") or 0):
                days[dd] = v
        for i, (dd, v) in enumerate(sorted(days.items())):
            if grp == "pg":
                v["kind"] = "postgame"
            else:
                nxt = next((g[0] for g in gs if g[0] > v["_t"]), None)
                close = nxt is not None and (nxt.astimezone(et).date() - dd).days <= 2
                v["kind"] = "day_after" if i == 0 else "first_practice" if i == 1 else "final_practice" if close else "midweek"
            out.append(v)
    for v in out:
        v.pop("_t", None)
    return sorted(out, key=_ts)


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


# Teams whose video page breaks headless Chrome: go straight to the video platform via yt-dlp.
# CHI: the page freezes during the pre-roll ad, before the player ever requests the video.
NO_BROWSER = set(os.environ.get("PRESSERS_NO_BROWSER", "CHI").upper().split())


def fetch_captions(videos: list[dict]) -> None:
    direct = [v for v in videos if v["team"] in NO_BROWSER]
    _fetch_captions_ytdlp(direct)
    browser = [v for v in videos if v["team"] not in NO_BROWSER]
    if browser:
        _fetch_captions(browser)
    retry = [v for v in browser if not v.get("transcript")]
    if retry:
        log(f"retrying {len(retry)} video(s) once")
        for v in retry:
            v.pop("error", None)
        _fetch_captions(retry)
    # last resort for anything still missing (any team): the video platform directly
    left = [v for v in videos if not v.get("transcript")]
    if left:
        log(f"yt-dlp fallback for {len(left)} video(s)")
        _fetch_captions_ytdlp(left)


def _fetch_captions_ytdlp(videos: list[dict]) -> None:
    """Club video pages run on the league's video platform (Lura/Anvato, id = mcpID). yt-dlp's
    nfl.com extractor asks the platform for the video and returns its official caption playlist
    (the same subs.m3u8 the page player loads), without opening the page in a browser."""
    import json as _json
    import subprocess
    for v in videos:
        v.pop("error", None)
        try:
            r = subprocess.run(["yt-dlp", "-J", "--skip-download", "--no-warnings", "--no-playlist", v["url"]],
                               capture_output=True, text=True, timeout=120)
            if r.returncode:
                raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else f"exit {r.returncode}")
            j = _json.loads(r.stdout)
            if j.get("_type") == "playlist":
                j = (j.get("entries") or [{}])[0]
            subs = [s["url"] for lang, lst in (j.get("subtitles") or {}).items() if lang.startswith("en")
                    for s in lst if "m3u8" in s.get("url", "") or s.get("ext") == "vtt"]
            v["transcript"] = pick_transcript(subs, None)  # URL comes from this exact video, no mcpID check needed
            if not v["transcript"]:
                v["error"] = "no captions found (yt-dlp)"
        except Exception as e:  # noqa: BLE001
            v["error"] = f"yt-dlp: {type(e).__name__}: {e}"[:200]
        log(f"  {v['id']}: {len(v.get('transcript', '').split())} words (yt-dlp)" + (f" ({v['error']})" if v.get("error") else ""))


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


API = "https://api.anthropic.com/v1"


def _headers() -> dict:
    return {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"}


def _params(model: str, v: dict, roster: dict[str, str]) -> dict:
    msg = (
        f"Team: {v['team']} (head coach {COACHES[v['team']]})\nVideo title: {v['title']}\nDescription: {v.get('description', '')}\n"
        f"Posted: {v['date']} ({v.get('kind', '')})\nRoster: {', '.join(sorted(roster)) or 'n/a'}\n\n"
        f"<transcript>\n{v['transcript']}\n</transcript>"
    )
    return {"model": model, "max_tokens": 6000, "system": SYSTEM, "messages": [{"role": "user", "content": msg}]}


def _parse(data: dict, roster: dict[str, str]) -> tuple[dict, dict]:
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


def summarize(model: str, v: dict, roster: dict[str, str]) -> tuple[dict, dict]:
    """One direct call (full price). Retries once if the reply isn't valid JSON."""
    import requests
    for attempt in (1, 2):
        r = requests.post(f"{API}/messages", timeout=180, headers=_headers(), json=_params(model, v, roster))
        if r.status_code != 200:
            raise RuntimeError(f"Claude API {r.status_code}: {r.text[:200]}")
        try:
            return _parse(r.json(), roster)
        except ValueError:
            if attempt == 2:
                raise


def summarize_batch(model: str, vids: list[dict], ros: dict) -> dict[str, tuple[dict, dict]]:
    """Message Batches API (half price; results usually in minutes, guaranteed within 24h).
    Waits up to PRESSERS_BATCH_WAIT minutes (default 45); anything not back by then, or that fails
    or isn't valid JSON, goes through summarize() directly so a run never ends empty-handed."""
    import time
    import requests
    out: dict[str, tuple[dict, dict]] = {}
    if not vids:
        return out
    cid = {f"p{i:04d}": v for i, v in enumerate(vids)}
    r = requests.post(f"{API}/messages/batches", timeout=120, headers=_headers(), json={"requests": [
        {"custom_id": c, "params": _params(model, v, ros.get(v["team"], {}))} for c, v in cid.items()]})
    if r.status_code != 200:
        log(f"batch submit failed ({r.status_code}: {r.text[:200]}); falling back to direct calls")
        bid = None
    else:
        bid = r.json()["id"]
        log(f"batch {bid}: {len(cid)} pressers submitted ({model}, half price)")
        deadline = time.time() + 60 * int(os.environ.get("PRESSERS_BATCH_WAIT", "45"))
        st = {}
        while time.time() < deadline:
            st = requests.get(f"{API}/messages/batches/{bid}", timeout=60, headers=_headers()).json()
            if st.get("processing_status") == "ended":
                break
            time.sleep(30)
        if st.get("processing_status") != "ended":
            log(f"batch {bid} not done after the wait ({st.get('request_counts')}); cancelling, rest go direct")
            requests.post(f"{API}/messages/batches/{bid}/cancel", timeout=60, headers=_headers())
            time.sleep(20)
            st = requests.get(f"{API}/messages/batches/{bid}", timeout=60, headers=_headers()).json()
        if st.get("results_url"):
            res = requests.get(st["results_url"], timeout=300, headers=_headers())
            for line in res.text.splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                v = cid.get(row.get("custom_id"))
                if not v or row.get("result", {}).get("type") != "succeeded":
                    continue
                try:
                    out[v["id"]] = _parse(row["result"]["message"], ros.get(v["team"], {}))
                except ValueError as e:
                    log(f"  {v['id']}: batch reply wasn't valid JSON ({e}); retrying direct")
        log(f"batch {bid}: {len(out)}/{len(cid)} back")
    for v in cid.values():
        if v["id"] in out:
            continue
        try:
            out[v["id"]] = summarize(model, v, ros.get(v["team"], {}))
            log(f"  {v['id']}: done direct")
        except Exception as e:  # noqa: BLE001
            log(f"  {v['id']}: summary FAILED ({e})")
    return out


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
    model = os.environ.get("PRESSERS_MODEL", "claude-sonnet-5-5")
    since = datetime.now(timezone.utc).date() - timedelta(days=days)
    bf = os.environ.get("PRESSERS_BACKFILL", "")  # e.g. "1-8": weeks to backfill
    weeks = range(int(bf.split("-")[0]), int(bf.split("-")[-1]) + 1) if bf else None
    if weeks:
        sd = json.loads(SCHEDULE.read_text())["data"]
        since = min(date.fromisoformat(g) for g, w in zip(sd["gameday"], sd["week"]) if g and w == weeks[0]) - timedelta(days=1)
        cap = max(cap, 40 * len(teams) * len(weeks))

    index = load_index()
    if OUT_DIR != ROOT / "data" / "pressers":  # parallel job: also skip what the branch already has
        try:
            index["done"].update(json.loads((ROOT / "data" / "pressers" / "index.json").read_text()).get("done", {}))
        except (OSError, ValueError):
            pass
    skip = os.environ.get("PRESSERS_SKIP", "").upper().split()  # e.g. CHI: page freezes the browser
    if skip:
        log(f"skipping {', '.join(skip)} (no working caption source yet)")
        teams = [t for t in teams if t not in skip]
    only = os.environ.get("PRESSERS_ONLY", "").upper().split()
    if only and only != ["ALL"]:
        teams = [t for t in teams if t in only]
    new: list[dict] = []
    for t in teams:
        try:
            allv = discover(t, since, deep=bool(weeks))
            if not weeks and not any(v["hc"] for v in allv):
                # some clubs (SF) leave pressers out of the fast sitemap: fall back to the full archive
                allv = discover(t, since, deep=True)
        except Exception as e:  # noqa: BLE001
            log(f"{t}: sitemap FAILED ({e})")
            continue
        if "--list" in sys.argv:
            for v in sorted(allv, key=lambda v: v["date"]):
                log(f"    {v['ts'][:19]} {'HC ' if v['hc'] else '   '}{'PG ' if v['postgame'] else '   '}{v['duration']:>5}s {v['title'][:70]} | {', '.join(v['tags'])[:50]}")
        if every:
            vids = allv
        elif os.environ.get("PRESSERS_PICK", "all") == "all":  # every HC presser, labeled (daily run + backfill)
            vids = pick_all(allv, t, weeks)
        else:  # "two": the original day-after + first-practice pick
            vids = pick_backfill(allv, t, weeks) if weeks else pick_weekly(allv, t)
        if os.environ.get("PRESSERS_REDO") != "1":  # REDO=1: re-summarize pressers already done (model change)
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

    if save_dir:  # transcripts we already saved privately: reuse them, no need to fetch captions again
        for v in new:
            f = save_dir / v["date"] / f"{v['team']} {v['id'].split(':', 1)[1]}.txt"
            if f.exists():
                v["transcript"] = f.read_text().split("\n", 3)[-1]
        log(f"reused {sum(bool(v.get('transcript')) for v in new)} saved transcript(s)")
    fetch_captions([v for v in new if not v.get("transcript")])
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
    if os.environ.get("PRESSERS_BATCH", "1") == "1":
        results = summarize_batch(model, ready, ros)
    else:
        results = {}
        for v in ready:
            try:
                results[v["id"]] = summarize(model, v, ros.get(v["team"], {}))
            except Exception as e:  # noqa: BLE001
                log(f"  {v['id']}: summary FAILED ({e})")
    for v in ready:
        if v["id"] not in results:
            continue
        s, u = results[v["id"]]
        tok = {k: tok[k] + u[k] for k in tok}
        entry = {k: v[k] for k in ("id", "team", "url", "title", "date", "duration", "thumb")}
        entry["kind"] = v.get("kind", "")
        if v.get("week") is not None:
            entry["after_week"] = v["week"]
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
