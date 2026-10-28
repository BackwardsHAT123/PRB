"""backfill_days_full.py: make 'd' (days on production) cover every month for the wells in data/production.json.
Older entries kept days for the first eight months only; prod.py now stores every month, so this refetches the wells whose 'd' is shorter than 'o'.
Run from the repo root: python3 tools/dashboard/backfill_days_full.py [threads=3] [gap=4] [bunch=60] [pause=45]
Wells on the dashboard go first, newest first. Gentle on the state site: a few parallel requests with a gap between each, a pause between bunches, and it stops if the site
stops answering. Create a file named STOP in the repo root to stop cleanly. Safe to re-run: finished wells are skipped ('dfx': 1 marks wells with no day data anywhere)."""
import json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.getcwd())
import prod
threads = int(sys.argv[1]) if len(sys.argv) > 1 else 3
gap = float(sys.argv[2]) if len(sys.argv) > 2 else 4
bunch = int(sys.argv[3]) if len(sys.argv) > 3 else 60
pause = int(sys.argv[4]) if len(sys.argv) > 4 else 45
P = json.load(open("data/production.json"))
H = json.load(open("data/headers.json"))
pk = {v["API Number"]: k for k, v in H.items()}
try:
    dash = {w["api"] for w in json.load(open("dashboard/data/wells.json"))}
except OSError:
    dash = set()
need = lambda a: not P[a].get("none") and not P[a].get("dfx") and P[a].get("o") and len(P[a].get("d") or []) < len(P[a]["o"]) and a in pk
todo = [a for a in P if need(a)]
todo.sort(key=lambda a: (a not in dash, P[a].get("s", "")), reverse=False)
todo.sort(key=lambda a: (a not in dash, tuple(-ord(ch) for ch in P[a].get("s", ""))))      # dashboard wells first, then newest first
if os.environ.get("LIMIT"): todo = todo[:int(os.environ["LIMIT"])]       # for a quick test
log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)
log(f"{len(todo)} wells need days for every month ({sum(1 for a in todo if a in dash)} on the dashboard)")
lock = threading.Lock(); state = {"done": 0, "fails": 0, "stop": False}


def full_days(a, tmp):
    """List of days aligned with P[a]['o'], or None on failure, [] when the state has no day data for the well."""
    txt = prod.fetch(pk[a], tmp)
    if txt is None:
        return None
    d = prod.parse(txt) if txt else None
    if d and d["s"] == P[a]["s"] and len(d["d"]) == len(P[a]["o"]):
        return d["d"]
    dm = prod.fetch_days_wyoprod(pk[a], gap)       # export empty or a different series: read the Days rows from the monthly tables
    if dm is None:
        return None
    y, m = int(P[a]["s"][:4]), int(P[a]["s"][5:])
    ds = []
    for _ in range(len(P[a]["o"])):
        ds.append(dm.get(f"{y}-{m:02d}", 0)); m += 1
        if m > 12: y, m = y + 1, 1
    return ds if any(ds) else []


def work(args):
    i, a = args
    tmp = f"days_{threading.get_ident()}.tmp"
    if state["stop"] or os.path.exists("STOP"):
        return
    r = full_days(a, tmp)
    with lock:
        if r is None:
            state["fails"] += 1
            if state["fails"] >= 6 or not prod.fetch(prod.CONTROL, tmp):
                log("site not answering, stopping"); state["stop"] = True
            return
        state["fails"] = 0
        if r: P[a]["d"] = r; P[a].pop("dw", None)
        else: P[a]["dfx"] = 1
        state["done"] += 1
        if state["done"] % 25 == 0:
            json.dump(P, open("data/production.json", "w"), separators=(",", ":")); log(f"{state['done']}/{len(todo)} done")
    time.sleep(gap)


for b in range(0, len(todo), bunch):
    if state["stop"] or os.path.exists("STOP"):
        log("stopping"); break
    with ThreadPoolExecutor(threads) as ex:
        list(ex.map(work, list(enumerate(todo[b:b + bunch]))))
    log(f"bunch done, pausing {pause}s"); time.sleep(pause)
json.dump(P, open("data/production.json", "w"), separators=(",", ":"))
for f in os.listdir("."):
    if (f.startswith("days_") or f.startswith("prod2_")) and f.endswith(".tmp"): os.remove(f)
log(f"finished: {state['done']} wells updated")
