import json, urllib.request
H = {"User-Agent": "Mozilla/5.0", "Origin": "https://william-arana.github.io"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30) as r: return json.loads(r.read())
out = {}
for name, ID in [("crosby", "3916655"), ("hutchinson", "4372099"), ("gibbs", "4429795")]:
    o = get(f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{ID}/overview")
    f = get(f"https://site.api.espn.com/apis/fantasy/v2/games/ffl/news/players?playerId={ID}&limit=50")
    out[name] = {"overview_rotowire": o.get("rotowire"), "overview_news_count": len(o.get("news") or []),
                 "overview_news_heads": [(n.get("published"), n.get("type"), n.get("headline")) for n in (o.get("news") or [])[:5]],
                 "fantasy_meta": {k: v for k, v in f.items() if k != "feed"}, "fantasy_count": len(f.get("feed") or []),
                 "fantasy_heads": [(n.get("published"), n.get("type"), (n.get("headline") or "")[:80]) for n in (f.get("feed") or [])[:4]]}
print(json.dumps(out, indent=1))
