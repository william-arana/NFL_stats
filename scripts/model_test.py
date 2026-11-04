"""One-off: same pressers through Haiku and Sonnet. Reads raw transcripts from the private repo
(path in argv[1]) and writes results there (argv[2]); nothing goes to this public repo."""
import json, sys, time, glob
from pathlib import Path
sys.path.insert(0, "scripts")
import update_pressers as up

priv, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
ids = json.load(open("scripts/model_test_ids.json"))
E = {e["id"]: e for f in glob.glob("data/pressers/20*.json") for e in json.load(open(f))}
ros = up.rosters()
res = []
for i in ids:
    e = E[i]
    f = priv / "transcripts" / "2026" / e["date"] / f"{e['team']} {i.split(':', 1)[1]}.txt"
    tx = f.read_text().split("\n", 3)[-1]
    v = {**e, "description": "", "transcript": tx}
    row = {"id": i, "team": e["team"], "date": e["date"], "kind": e.get("kind", ""), "words": len(tx.split())}
    for m in ("claude-haiku-5-5", "claude-sonnet-5-5"):
        t = time.time()
        try:
            s, u = up.summarize(m, v, ros.get(e["team"], {}))
            row[m] = {"out": s, "usage": u, "secs": round(time.time() - t, 1)}
        except Exception as ex:  # noqa: BLE001
            row[m] = {"error": str(ex)[:300]}
        print(i, m, row[m].get("usage"), row[m].get("secs"), row[m].get("error", ""), flush=True)
    res.append(row)
(out / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
