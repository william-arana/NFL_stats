import json, re, urllib.request
ID = "3916655"  # Maxx Crosby
H = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1", "Origin": "https://william-arana.github.io"}
URLS = {
  "fantasy_news": f"https://site.api.espn.com/apis/fantasy/v2/games/ffl/news/players?playerId={ID}&limit=50",
  "fantasy_news_web": f"https://site.web.api.espn.com/apis/fantasy/v2/games/ffl/news/players?playerId={ID}&limit=50",
  "site_news_athlete": f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?athlete={ID}&limit=50",
  "common_v3_news": f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{ID}/news",
  "common_v3_overview": f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{ID}/overview",
  "page": f"https://www.espn.com/nfl/player/news/_/id/{ID}/maxx-crosby",
}
out = {}
for k, u in URLS.items():
    r = {"url": u}
    try:
        req = urllib.request.Request(u, headers=H)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", "replace")
            r["status"] = resp.status
            r["acao"] = resp.headers.get("Access-Control-Allow-Origin")
        if k == "page":
            m = re.search(r"window\['__espnfitt__'\]\s*=\s*(\{.*?\});</script>", body, re.S)
            r["len"] = len(body)
            urls = sorted(set(re.findall(r"https?://[a-z.]*espn[a-z.]*\.com/apis/[^\"'\\s<>]+", body)))[:40]
            r["api_urls_in_page"] = urls
            if m:
                j = json.loads(m.group(1))
                s = json.dumps(j)
                r["fitt_keys"] = list(j.get("page", {}).get("content", {}).keys())[:20]
                # find news-looking lists
                i = s.find('"news"'); r["news_snip"] = s[i:i+3000] if i >= 0 else None
            heads = re.findall(r'"headline":"([^"]{5,200})"', body)[:10]
            r["headlines"] = heads
        else:
            j = json.loads(body)
            r["top_keys"] = list(j.keys())[:20]
            arr = j.get("feed") or j.get("articles") or j.get("news") or (j.get("news", {}) if isinstance(j.get("news"), dict) else None)
            if isinstance(arr, dict):
                arr = arr.get("articles") or arr.get("items")
            if isinstance(arr, list):
                r["count"] = len(arr)
                r["sample"] = [{"headline": a.get("headline"), "type": a.get("type"), "published": a.get("published"), "byline": a.get("byline"),
                                "desc": (a.get("description") or "")[:160], "story": (a.get("story") or "")[:200],
                                "keys": list(a.keys())[:25]} for a in arr[:6]]
            else:
                r["snip"] = body[:1500]
    except Exception as e:
        r["error"] = repr(e)[:300]
    out[k] = r
print(json.dumps(out, indent=1))
