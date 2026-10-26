"""Rebuild the dashboard tables for every operator on the PRB map.
Reads index.html (the map page, for well records) and production.json in the current folder.
Writes wells.json, bench.json and curves.json."""
import json, math, collections
import numpy as np

S = open("index.html").read(); i = S.index("const D=") + 8; D = json.loads(S[i:S.index(";\nconst GRID", i)])
P = json.load(open("production.json"))
H = (3, 6, 12)

def hav(a, b):
    R = 20902231; la1, lo1, la2, lo2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    x = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))
def plen(ln): return sum(hav(a, b) for a, b in zip(ln, ln[1:])) if ln and len(ln) > 1 else None
def rnd(x, n=0): return None if x is None else round(x, n)

wells = []; cum = {}
for d in D:
    p = P.get(d["a"])
    if not p or p.get("none"): continue
    o, w = p["o"], p["w"]; y, m = map(int, p["s"].split("-"))
    k = next((j for j, v in enumerate(o) if v and v > 0), None)
    if k is None: continue
    n = len(o) - k; fy = (y * 12 + m - 1 + k) // 12
    L = plen(d["ln"]); L = round(L) if L else None
    r = {"api": d["a"], "name": d["n"], "op": d["oc"], "fm": d["r"], "cty": d["cty"], "twp": d["sec"].split("-", 1)[1] if d.get("sec") else None,
         "yr": fy, "len": L, "lon": d["shl"][0] if d.get("shl") else None, "lat": d["shl"][1] if d.get("shl") else None,
         "ln": [round(c, 4) for pt in d["ln"] for c in pt] if d.get("ln") and len(d["ln"]) > 1 else None}   # simplified lateral path, lon,lat pairs
    for h in H:
        if n >= h:
            oo = sum(o[k:k + h]); ww = sum(w[k:k + h])
            r[f"o{h}"] = round(oo); r[f"w{h}"] = round(ww)
            r[f"of{h}"] = round(oo / L * 1000, 1) if L else None; r[f"wf{h}"] = round(ww / L * 1000, 1) if L else None
        else:
            r[f"o{h}"] = r[f"w{h}"] = r[f"of{h}"] = r[f"wf{h}"] = None
    wells.append(r)
    cum[d["a"]] = (np.cumsum(o[k:k + 24]), np.cumsum(w[k:k + 24]))
json.dump(wells, open("wells.json", "w"), separators=(",", ":"))
print("wells", len(wells), "operators", len(set(r["op"] for r in wells)))

KEYS = [f"{p}{h}" for h in H for p in ("o", "w", "of", "wf")]
def med(v):
    v = [x for x in v if x is not None]; return float(np.median(v)) if v else None
# benchmark: median well per formation across every operator (needs 8+ wells with 12 months)
bench = []
byf = collections.defaultdict(list)
for r in wells: byf[r["fm"]].append(r)
for f, rs in byf.items():
    n12 = sum(1 for r in rs if r["o12"] is not None)
    if n12 >= 8:
        b = {"fm": f, "n": len(rs), "n12": n12}
        for k in KEYS: b[k] = rnd(med(r[k] for r in rs), 1 if "f" in k else 0)
        bench.append(b)
json.dump(bench, open("bench.json", "w"), separators=(",", ":"))
print("bench", [(b["fm"], b["n12"]) for b in bench])
BM = {b["fm"]: b for b in bench}

# curves: median cumulative oil and water by month since first oil, per series
def series(label, op, fm, rs, minw):
    rs = [r for r in rs if r["len"]]
    out = {"series": label, "op": op, "fm": fm, "n": [], "oil": [], "water": [], "oil_ft": [], "water_ft": []}
    for m in range(24):
        sel = [r for r in rs if len(cum[r["api"]][0]) > m]
        if len(sel) < minw: break
        out["n"].append(len(sel))
        out["oil"].append(rnd(med(cum[r["api"]][0][m] for r in sel)))
        out["water"].append(rnd(med(cum[r["api"]][1][m] for r in sel)))
        out["oil_ft"].append(rnd(med(cum[r["api"]][0][m] / r["len"] * 1000 for r in sel), 1))
        out["water_ft"].append(rnd(med(cum[r["api"]][1][m] / r["len"] * 1000 for r in sel), 1))
    return out if out["n"] else None
curves = []
def add(c):
    if c: curves.append(c)
ALL = "All operators"
add(series(ALL, ALL, None, wells, 8))
for f, rs in byf.items(): add(series(f"{ALL} / {f}", ALL, f, rs, 8))
byo = collections.defaultdict(list); byof = collections.defaultdict(list)
for r in wells: byo[r["op"]].append(r); byof[(r["op"], r["fm"])].append(r)
for o, rs in byo.items(): add(series(o, o, None, rs, 5))
for (o, f), rs in byof.items():
    if len(rs) >= 4: add(series(f"{o} / {f}", o, f, rs, 4))
json.dump(curves, open("curves.json", "w"), separators=(",", ":"))
print("curves series", len(curves))
