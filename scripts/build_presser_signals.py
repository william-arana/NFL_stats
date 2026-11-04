"""Per-player press conference signals for the player-card News section.

Reads data/pressers/<date>.json (our own summaries, never transcripts) and writes
data/site/presser_signals.json:

  {"updated_utc": "...", "v": [[date, team, coach, url], ...],
   "p": {"<gsis_id>": [[v_index, signal, topic, claim, note, quote], ...]}}   (newest first)

Only signals that were matched to a player id are included. Run after any pressers update.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "pressers"
OUT = ROOT / "data" / "site" / "presser_signals.json"


def main():
    by, vids, vix = {}, [], {}
    n = 0
    for f in sorted(SRC.glob("20*.json")):
        for e in json.loads(f.read_text()):
            for s in e.get("signals") or []:
                pid = s.get("player_id")
                if not pid or s.get("signal") not in ("up", "down", "watch"):
                    continue
                if e["id"] not in vix:
                    vix[e["id"]] = len(vids)
                    vids.append([e.get("date", f.stem), e.get("team", ""), e.get("coach", ""), e.get("url", "") or ""])
                by.setdefault(pid, []).append([
                    vix[e["id"]], s["signal"], s.get("topic", "") or "", s.get("claim", "") or "",
                    s.get("note", "") or "", s.get("quote", "") or "",
                ])
                n += 1
    for v in by.values():
        v.sort(key=lambda r: vids[r[0]][0], reverse=True)
    OUT.write_text(json.dumps({
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "v": vids, "p": by}, ensure_ascii=False, separators=(",", ":")))
    print(f"presser_signals.json: {n} signals for {len(by)} players, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
