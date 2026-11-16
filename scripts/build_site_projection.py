"""Writes data/site/proj.json: our projection v0.2 (scripts/projection_v0.py: (v0 + RB/WR depth adjustment) x chance he plays) for next week, PPR, for the site
(Compare's "Our proj" column) and `r` = rest-of-season PPR through week 18 (Compare ROS pts, Waivers ROS). Uses only the site's own data files; no Sleeper/ESPN numbers.
Run after scripts/update_data.py (update-data workflow)."""
import json
from pathlib import Path
import pandas as pd
from projection_v0 import ours_v01, ros, ROS_LAST_WEEK

SITE = Path(__file__).resolve().parents[1] / "data" / "site"


def rows(n):
    j = json.loads((SITE / n).read_text())
    return pd.DataFrame({c: j["data"][c] for c in j["cols"]})


def main():
    meta = json.loads((SITE / "meta.json").read_text())
    week = meta["next_week"]
    P, T, S = rows("players.json"), rows("teams.json"), rows("schedule.json")
    K = rows("kickers.json") if (SITE / "kickers.json").exists() else pd.DataFrame()
    o = ours_v01(P, K, S, week, T, SITE)
    p = {r.key: round(float(r.ours_ppr), 1) for r in o.itertuples() if pd.notna(r.ours_ppr)}
    # depth / vacated opportunity: points added or removed + reason, for the Waivers "Why" tags
    dp = {r.key: [round(float(r.depth), 1), r.depth_why] for r in o.itertuples() if "depth" in o and abs(r.depth) >= 0.3 and r.avail > 0}
    r = ros(P, K, S, week, T, SITE)  # rest of season, weeks week..ROS_LAST_WEEK
    out = {"season": meta["season"], "week": week, "model": "v0.2", "scoring": "PPR", "updated_utc": meta.get("updated_utc"), "p": p, "dp": dp,
           "ros_through": ROS_LAST_WEEK, "r": r}
    (SITE / "proj.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"proj.json: week {week}, {len(p)} players/defenses, ROS for {len(r)}, depth adjustments {len(dp)}")


if __name__ == "__main__":
    main()
