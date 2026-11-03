"""Writes data/site/proj.json: our projection v0 (scripts/projection_v0.py) for next week, PPR, for the site
(Compare's "Our proj" column). Uses only the site's own data files; no Sleeper/ESPN numbers.
Run after scripts/update_data.py (update-data workflow)."""
import json
from pathlib import Path
import pandas as pd
from projection_v0 import ours

SITE = Path(__file__).resolve().parents[1] / "data" / "site"


def rows(n):
    j = json.loads((SITE / n).read_text())
    return pd.DataFrame({c: j["data"][c] for c in j["cols"]})


def main():
    meta = json.loads((SITE / "meta.json").read_text())
    week = meta["next_week"]
    P, T, S = rows("players.json"), rows("teams.json"), rows("schedule.json")
    K = rows("kickers.json") if (SITE / "kickers.json").exists() else pd.DataFrame()
    o = ours(P, K, S, week, T)
    p = {r.key: round(float(r.ours_ppr), 1) for r in o.itertuples() if pd.notna(r.ours_ppr)}
    out = {"season": meta["season"], "week": week, "model": "v0", "scoring": "PPR", "updated_utc": meta.get("updated_utc"), "p": p}
    (SITE / "proj.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"proj.json: week {week}, {len(p)} players/defenses")


if __name__ == "__main__":
    main()
