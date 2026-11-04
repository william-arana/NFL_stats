"""Debug: load one team video page and log every media request (m3u8/vtt) for 60 s.
Usage: python scripts/debug_captions.py <video url>"""
import sys, time
from playwright.sync_api import sync_playwright
url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    seen = []
    pg.on("request", lambda r: seen.append(r.url) if any(k in r.url for k in ("m3u8", ".vtt", "subs", "caption")) else None)
    t0 = time.time()
    try:
        pg.goto(url, wait_until="commit", timeout=30000)
        print(f"commit after {time.time()-t0:.1f}s", flush=True)
    except Exception as e:
        print("goto failed:", e, flush=True)
    for i in range(60):
        pg.wait_for_timeout(1000)
        if i in (5, 15):
            try:
                pg.evaluate("try{document.querySelector('video')?.play?.()}catch(e){}")
            except Exception as e:
                print("eval failed", e)
        if any("subs.m3u8" in u for u in seen):
            print(f"subs after {time.time()-t0:.1f}s", flush=True); break
    for u in dict.fromkeys(seen):
        print("REQ", u[:160])
    try:
        html = pg.content(); print("html bytes", len(html), "mcpID" in html)
    except Exception as e:
        print("content failed", e)
    b.close()
