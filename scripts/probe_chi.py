"""One-off probe: why CHI captions fail, and can we get them without a browser.
Prints URL patterns only (no transcript text). Compares a working team (DET) with CHI."""
import re, sys, time, signal, threading
from datetime import date, timedelta
import xml.etree.ElementTree as ET
sys.path.insert(0, "scripts")
import update_pressers as up

def hr(t): print(f"\n===== {t} =====", flush=True)

def sitemap_entry(team):
    sm = f"https://www.{up.TEAMS[team]}/sitemap-video-fast-changing.xml"
    root = ET.fromstring(up.get(sm))
    for u in root.findall("s:url", up.NS):
        v = u.find("v:video", up.NS)
        if v is not None and up.PRESSER_TITLE.search(v.findtext("v:title", "", up.NS)):
            hr(f"{team} raw sitemap video element")
            for c in v:
                tag = c.tag.split("}")[-1]
                if tag in ("description",):
                    continue
                print(f"  {tag}: {(c.text or '')[:200]}")
            return

def plain_fetch(team, url):
    hr(f"{team} plain HTTP fetch {url}")
    t = time.time()
    try:
        html = up.get(url, timeout=30)
    except Exception as e:
        print("  FAILED", e); return
    print(f"  {len(html)} bytes in {time.time()-t:.1f}s")
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    m = re.search(r'"slug":"%s".*?"mcpID":"(\d+)"' % re.escape(slug), html, re.S)
    print("  mcpID (slug-matched):", m.group(1) if m else None)
    print("  all mcpIDs:", sorted(set(re.findall(r'"mcpID":"(\d+)"', html)))[:10])
    for k in ("videoId", "mcpPlaybackId", "playbackUrl", "hlsUrl", "m3u8", "vtt", "subs", "captions", "brightcove", "jwplayer", "player"):
        hits = sorted(set(re.findall(r'[^"\s]{0,120}%s[^"\s]{0,120}' % k, html)))[:4]
        if hits:
            print(f"  [{k}]")
            for h in hits:
                print("     ", h[:240])
    i = html.find('"mcpID"')
    if i > 0:
        print("  context around first mcpID:\n     ", re.sub(r"\s+", " ", html[max(0, i-700):i+500]))

def browser(team, url, secs=60):
    hr(f"{team} browser requests {url}")
    from playwright.sync_api import sync_playwright
    seen = []
    t0 = time.time()
    def rec(r):
        u = r.url
        if any(k in u for k in ("m3u8", ".vtt", "subs", "mcp", "video", "player", "manifest", "playback")):
            seen.append(f"{time.time()-t0:5.1f}s {r.resource_type:9} {u[:220]}")
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        pg = b.new_context(user_agent=up.UA, viewport={"width": 1280, "height": 800}).new_page()
        pg.on("request", rec)
        done = threading.Event()
        def run():
            try:
                pg.goto(url, wait_until="commit", timeout=45000)
                print(f"  committed at {time.time()-t0:.1f}s", flush=True)
            except Exception as e:
                print("  goto error:", e, flush=True)
            done.set()
        th = threading.Thread(target=run, daemon=True); th.start()
        th.join(secs)
        try:
            pg.wait_for_timeout(15000)
        except Exception as e:
            print("  wait error:", e)
        for s in seen[:60]:
            print("  ", s)
        print(f"  ({len(seen)} matching requests)")
        try: b.close()
        except Exception: pass

since = date.today() - timedelta(days=12)
for team in ("DET", "CHI"):
    try:
        sitemap_entry(team)
    except Exception as e:
        print(team, "sitemap failed", e)
    vids = [v for v in up.discover(team, since) if v["hc"] and not v["postgame"]][:1]
    if not vids:
        vids = [v for v in up.discover(team, since, deep=True) if v["hc"]][:1]
    if not vids:
        print(team, "no HC video found"); continue
    url = vids[0]["url"]
    plain_fetch(team, url)
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError("probe watchdog")))
    signal.alarm(150)
    try:
        browser(team, url)
    except Exception as e:
        print("  browser probe died:", e)
    signal.alarm(0)
