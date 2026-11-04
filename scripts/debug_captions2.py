"""Debug 2: (a) plain GET of the Bears page: what video/player data is in the HTML?
(b) a working team's page: full list of media requests, to see how the caption URL is built."""
import re, sys, urllib.request, json
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30).read().decode("utf-8", "replace")
bears = "https://www.chicagobears.com/video/ben-johnson-we-have-to-play-the-best-we-ve-played-all-year-on-monday-night-press-conference"
h = get(bears)
print("BEARS html", len(h))
slug = bears.rsplit("/", 1)[-1]
for pat in [r'"mcpID":"(\d+)"', r'"videoId":"([^"]+)"', r'(https?://[^"\s]+\.m3u8[^"\s]*)', r'"playbackUrl[^"]*":"([^"]+)"', r'data-video-id="([^"]+)"', r'"vod[^"]*":"([^"]+)"']:
    m = re.findall(pat, h)[:5]
    print(pat, m)
i = h.find(slug); print("slug context:", h[i-300:i+600].replace("\n", " ") if i > 0 else "none")
from playwright.sync_api import sync_playwright
url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    pg = b.new_page()
    seen = []
    pg.on("request", lambda r: seen.append(r.url))
    pg.goto(url, wait_until="domcontentloaded", timeout=45000)
    for i in range(40):
        pg.wait_for_timeout(500)
        if any("subs.m3u8" in u for u in seen): break
        if i == 10: pg.evaluate("try{document.querySelector('video')?.play?.()}catch(e){}")
    html = pg.content()
    m = re.search(r'"slug":"%s".*?"mcpID":"(\d+)"' % re.escape(url.rsplit("/", 1)[-1]), html, re.S)
    print("WORKING mcpID", m.group(1) if m else None)
    for u in dict.fromkeys(seen):
        if any(k in u for k in ("m3u8", "vtt", "subs", "manifest", "playback", "media", "video")) and not u.endswith((".js", ".css", ".jpg", ".png", ".webp", ".svg", ".woff2")):
            print("REQ", u[:300])
    b.close()
