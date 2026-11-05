"""Per-player press conference signals for the player-card News section.

Reads data/pressers/<date>.json (our own summaries, never transcripts) and writes one small file per
player, data/site/presser_signals/<gsis_id>.json, so a card only downloads its own player's pressers:

  {"v": [[date, team, coach, url, presser_id], ...],
   "p": [[v_index, signal, topic, claim, note, quote, n, t, t_exact], ...]}   (newest first; v_index into this file's v)

t = seconds into the video (null if unknown), t_exact = 1 when the quote was matched in the captions.

Only signals that were matched to a player id are included. Coaches repeat themselves across a
week's pressers, so the same player + week + topic + direction is kept once (the newest) with
n = how many pressers said it. Run after any pressers update.
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "pressers"
OUT = ROOT / "data" / "site" / "presser_signals"


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
                    vids.append([e.get("date", f.stem), e.get("team", ""), e.get("coach", ""), e.get("url", "") or "", e["id"]])
                row = [vix[e["id"]], s["signal"], s.get("topic", "") or "", s.get("claim", "") or "",
                       s.get("note", "") or "", s.get("quote", "") or "", 1,
                       s.get("t"), 1 if s.get("t_exact") else 0]
                wk = e.get("after_week", e.get("date", f.stem))
                k = (wk, row[2], row[1])
                p = by.setdefault(pid, {})
                if k in p:  # same player, week, topic, direction: keep the newest, count the pressers
                    old = p[k]
                    if vids[row[0]][0] >= vids[old[0]][0]:
                        row[6] = old[6] + 1
                        p[k] = row
                    else:
                        old[6] += 1
                else:
                    p[k] = row
                n += 1
    by = {pid: sorted(p.values(), key=lambda r: vids[r[0]][0], reverse=True) for pid, p in by.items()}
    if OUT.exists():
        shutil.rmtree(OUT)  # players who no longer have signals lose their file
    OUT.mkdir(parents=True)
    old = OUT.parent / "presser_signals.json"  # the old all-players file
    if old.exists():
        old.unlink()
    total = 0
    for pid, rows in by.items():
        loc: dict[int, int] = {}
        v = []
        for r in rows:
            if r[0] not in loc:
                loc[r[0]] = len(v)
                v.append(vids[r[0]])
        f = OUT / f"{pid}.json"
        f.write_text(json.dumps({"v": v, "p": [[loc[r[0]], *r[1:]] for r in rows]}, ensure_ascii=False, separators=(",", ":")))
        total += f.stat().st_size
    print(f"presser_signals/: {n} signals ({sum(map(len, by.values()))} after grouping) for {len(by)} players, "
          f"{total // 1024} KB total, {total // max(1, len(by))} bytes per player")

if __name__ == "__main__":
    main()
