"""Debug: Bears page with ads/trackers blocked; log caption requests for 60 s."""
import sys, time, re
from playwright.sync_api import sync_playwright
url = sys.argv[1]
ALLOW = re.compile(r"chicagobears\.com|clubs\.nfl\.com|nfl\.com|lura\.live|anvato|uplynk|akamai|cloudfront|fonts\.|jwplayer|brightcove", re.I)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    blocked = set()
    def route(r):
        if ALLOW.search(r.request.url): return r.continue_()
        blocked.add(r.request.url.split("/")[2]); return r.abort()
    ctx.route("**/*", route)
    pg = ctx.new_page(); pg.set_default_timeout(20000)
    seen = []
    pg.on("request", lambda r: seen.append(r.url) if ("m3u8" in r.url or ".vtt" in r.url) else None)
    t0 = time.time()
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=30000); print(f"dcl after {time.time()-t0:.1f}s", flush=True)
    except Exception as e:
        print("goto failed:", e, flush=True)
    for i in range(40):
        try: pg.wait_for_timeout(1000)
        except Exception as e: print("wait failed", e); break
        if any("subs.m3u8" in u for u in seen): print(f"subs after {time.time()-t0:.1f}s", flush=True); break
        if i in (8, 20):
            try: pg.evaluate("try{document.querySelector('video')?.play?.()?.catch?.(()=>{})}catch(e){}")
            except Exception as e: print("eval", str(e)[:100])
    for u in dict.fromkeys(seen): print("REQ", u[:200])
    print("blocked hosts:", sorted(blocked)[:40])
    b.close()
