"""One-off probe: can we get CHI captions straight from the club video platform (no page player)?
Prints formats/subtitle URL patterns only, no transcript text."""
import json, subprocess, sys, re
sys.path.insert(0, "scripts")
import update_pressers as up
from datetime import date, timedelta

since = date.today() - timedelta(days=12)
for team in ("DET", "CHI"):
    vids = [v for v in up.discover(team, since) if v["hc"]][:2]
    for v in vids:
        print(f"\n===== {team} {v['url']}", flush=True)
        r = subprocess.run(["yt-dlp", "-J", "--skip-download", "--no-warnings", v["url"]],
                           capture_output=True, text=True, timeout=120)
        if r.returncode:
            print("  yt-dlp failed:", r.stderr[-600:]); continue
        j = json.loads(r.stdout)
        if j.get("_type") == "playlist":
            j = (j.get("entries") or [{}])[0]
        print("  extractor:", j.get("extractor"), "| id:", j.get("id"), "| duration:", j.get("duration"))
        print("  formats:", len(j.get("formats") or []))
        subs = {**(j.get("subtitles") or {}), **{f"auto:{k}": x for k, x in (j.get("automatic_captions") or {}).items()}}
        for lang, lst in subs.items():
            for s in lst[:3]:
                print(f"  sub {lang} {s.get('ext')}: {re.sub(r'([?&](?:encp|token|hdnts|anvack)=)[^&]+', r'\\1…', s.get('url',''))[:200]}")
        if not subs:
            print("  no subtitles listed")
