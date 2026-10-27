"""backfill_days.py: add 'd' (days on production, first eight months) to wells in data/production.json that lack it.
Run from the repo root: python3 tools/dashboard/backfill_days.py [bunch=50] [pause=120] [gap=5]
Gentle on the state site: one export request per well, a gap between requests, a pause between bunches, and it stops if the site stops answering.
Create a file named STOP in the repo root to stop cleanly. Safe to re-run: wells that already have 'd' are skipped."""
import json, os, sys, time
sys.path.insert(0, os.getcwd())
import prod
bunch = int(sys.argv[1]) if len(sys.argv) > 1 else 50
pause = int(sys.argv[2]) if len(sys.argv) > 2 else 120
gap = float(sys.argv[3]) if len(sys.argv) > 3 else 5
P = json.load(open("data/production.json"))
H = json.load(open("data/headers.json"))
pk = {v["API Number"]: k for k, v in H.items()}
todo = [a for a, p in P.items() if not p.get("none") and ("d" not in p or (p["d"] == [] and "dw" not in p)) and a in pk and p.get("s") and p["s"] >= "2000-01"]
todo.sort(key=lambda a: P[a]["s"], reverse=True)       # newest wells first
log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)
log(f"{len(todo)} wells need days on production")
fails = done = 0
for i, a in enumerate(todo):
    if os.path.exists("STOP"):
        log("STOP file present"); break
    if P[a].get("d") == []:                     # export empty: read the days row from the monthly tables instead
        dm = prod.fetch_days_wyoprod(pk[a], gap)
        if dm is None:
            fails += 1
            if fails >= 4 or not prod.fetch(prod.CONTROL):
                log("site not answering, stopping"); break
            continue
        fails = 0
        y, m = int(P[a]["s"][:4]), int(P[a]["s"][5:])
        ds = []
        for _ in range(8):
            ds.append(dm.get(f"{y}-{m:02d}", 0)); m += 1
            if m > 12: y, m = y + 1, 1
        P[a]["d"] = ds if any(ds) else []
        P[a]["dw"] = 1
        done += 1
        if done % 25 == 0:
            json.dump(P, open("data/production.json", "w"), separators=(",", ":")); log(f"{done}/{len(todo)} done")
        time.sleep(gap)
        if done % bunch == 0:
            log(f"bunch done, pausing {pause}s"); time.sleep(pause)
        continue
    txt = prod.fetch(pk[a])
    if txt is None:
        fails += 1
        if fails >= 4 or not prod.fetch(prod.CONTROL):
            log("site not answering, stopping"); break
        continue
    fails = 0
    d = prod.parse(txt) if txt else None
    if d and d["s"] == P[a]["s"]:
        P[a]["d"] = d["d"]
    else:
        P[a]["d"] = []          # no export rows (or a different series start): leave unadjusted, do not retry
    done += 1
    if done % 25 == 0:
        json.dump(P, open("data/production.json", "w"), separators=(",", ":")); log(f"{done}/{len(todo)} done")
    time.sleep(gap)
    if done % bunch == 0:
        log(f"bunch done, pausing {pause}s"); time.sleep(pause)
json.dump(P, open("data/production.json", "w"), separators=(",", ":"))
log(f"finished: {done} wells updated")
