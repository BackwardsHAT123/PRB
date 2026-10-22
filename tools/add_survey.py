#!/usr/bin/env python3
"""Import operator survey .txt files (Wyoming East State Plane, grid-north offsets from the surface location),
decimate each to a handful of map vertices, and store the result as a path override for the matching well.

    python3 tools/add_survey.py "/path/one.txt" "/path/two.txt"     report only (dry run)
    python3 tools/add_survey.py --apply "/path/one.txt" ...         write data/overrides.json and index.html

Only the decimated path is stored. The raw survey stations are never copied into the repo.
"""
import json, math, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERRIDES = os.path.join(ROOT, "data", "overrides.json")
INDEX = os.path.join(ROOT, "index.html")
TOL_M = 15.0           # decimation tolerance
FT = 1200 / 3937       # US survey foot in metres

# NAD83 Wyoming East zone: transverse Mercator, GRS80
a = 6378137.0; f = 1 / 298.257222101; e2 = f * (2 - f); ep2 = e2 / (1 - e2)
lat0 = math.radians(40.5); lon0 = math.radians(-105 - 10 / 60); k0 = 0.9999375; FE = 200000.0


def _M(p):
    return a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * p - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * p)
                + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * p) - (35 * e2 ** 3 / 3072) * math.sin(6 * p))


M0 = _M(lat0)


def fwd(lat, lon):
    p, l = math.radians(lat), math.radians(lon)
    N = a / math.sqrt(1 - e2 * math.sin(p) ** 2); T = math.tan(p) ** 2; C = ep2 * math.cos(p) ** 2; A = (l - lon0) * math.cos(p)
    x = FE + k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * A ** 5 / 120)
    y = k0 * (_M(p) - M0 + N * math.tan(p) * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * A ** 4 / 24 + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * A ** 6 / 720))
    return x, y


def inv(x, y):
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2)); m = M0 + y / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    p1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu) + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu)
    N1 = a / math.sqrt(1 - e2 * math.sin(p1) ** 2); T1 = math.tan(p1) ** 2; C1 = ep2 * math.cos(p1) ** 2
    R1 = a * (1 - e2) / (1 - e2 * math.sin(p1) ** 2) ** 1.5; D = (x - FE) / (N1 * k0)
    p = p1 - (N1 * math.tan(p1) / R1) * (D * D / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * ep2) * D ** 4 / 24 + (61 + 90 * T1 + 298 * C1 + 45 * T1 * T1 - 252 * ep2 - 3 * C1 * C1) * D ** 6 / 720)
    l = lon0 + (D - (1 + 2 * T1 + C1) * D ** 3 / 6 + (5 - 2 * C1 + 28 * T1 - 3 * C1 * C1 + 8 * ep2 + 24 * T1 * T1) * D ** 5 / 120) / math.cos(p1)
    return math.degrees(p), math.degrees(l)


def parse(path):
    text = open(path, encoding="latin-1").read()
    lines = text.splitlines()
    rows = []
    for ln in lines:
        m = re.match(r"\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+) ([NS])\s+([\d.]+) ([EW])\s+(-?[\d.]+)\s+([\d.]+)\s*$", ln)
        if m:
            md, inc, az, tvd, n, ns, e, ew = m.groups()[:8]
            rows.append((float(md), float(n) * (1 if ns == "N" else -1), float(e) * (1 if ew == "E" else -1)))
    title = next((l.strip() for l in lines[:6] if re.search(r"design|plan|survey", l, re.I)), lines[1].strip() if len(lines) > 1 else "")
    zone = re.search(r"Coordinate System is ([^\n]+)", text)
    conv = re.search(r"Convergence at Surface is (-?[\d.]+)", text)
    ref = "grid" if re.search(r"relative to Grid North", text) else "true" if re.search(r"relative to True North", text) else "other"
    return {"rows": rows, "title": title, "zone": zone.group(1).strip() if zone else "", "ref": ref,
            "conv": float(conv.group(1)) if conv else None}


def norm(s):
    s = re.sub(r"\s*-\s*(design|plan|survey).*$", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def dp(p, e):
    if len(p) < 3:
        return p
    (x1, y1), (x2, y2) = p[0], p[-1]
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1e-9
    m, k = 0, 0
    for n in range(1, len(p) - 1):
        d = abs(dy * (p[n][0] - x1) - dx * (p[n][1] - y1)) / L
        if d > m:
            m, k = d, n
    return dp(p[:k + 1], e)[:-1] + dp(p[k:], e) if m > e else [p[0], p[-1]]


def meters(a_, b_):
    return math.hypot((a_[0] - b_[0]) * 111195 * math.cos(math.radians(a_[1])), (a_[1] - b_[1]) * 111195)


def main():
    apply = "--apply" in sys.argv
    forced = {x.split("=", 1)[1] for x in sys.argv if x.startswith("--accept=")}   # --accept=49-005-xxxxx to accept a large bottom-hole gap
    files = [x for x in sys.argv[1:] if not x.startswith("--")]
    s = open(INDEX).read()
    i = s.index("const D=") + 8
    j = s.index(";\nconst GRID", i)
    D = json.loads(s[i:j])
    byname = {}
    for d in D:
        byname.setdefault(norm(d["n"] or ""), []).append(d)
    ov = json.load(open(OVERRIDES))
    done = []
    for path in files:
        sv = parse(path)
        name = os.path.basename(path)
        if not sv["rows"]:
            print(f"SKIP {name}: no survey rows recognised")
            continue
        if not re.search(r"Wyoming East", sv["zone"]) or sv["ref"] == "other" or (sv["ref"] == "true" and sv["conv"] is None):
            print(f"SKIP {name}: expected Wyoming East State Plane with grid or true north; got '{sv['zone']}' / {sv['ref']}'")
            continue
        cands = byname.get(norm(sv["title"])) or byname.get(norm(os.path.splitext(name)[0])) or []
        if len(cands) != 1:
            print(f"SKIP {name}: could not match one well from '{sv['title']}' ({[c['n'] for c in cands] or 'no match'})")
            continue
        w = cands[0]
        x0, y0 = fwd(w["shl"][1], w["shl"][0])
        def project(rot):   # rot: radians, clockwise, applied to the survey's N/E offsets
            return [list(inv(x0 + (e * math.cos(rot) + n * math.sin(rot)) * FT, y0 + (n * math.cos(rot) - e * math.sin(rot)) * FT))[::-1]
                    for md, n, e in sv["rows"]]   # [lon, lat]
        note = ""
        if sv["ref"] == "grid":
            pts = project(0.0)
        else:   # true-north offsets: rotate by the grid convergence; the header bottom hole picks the direction
            r1 = math.radians(-sv["conv"]); opts = [project(r1), project(-r1)]
            gaps = [meters(o[-1], w["bhl"]) if w["bhl"] else 1e9 for o in opts]
            pts = opts[0] if gaps[0] <= gaps[1] else opts[1]
            note = f" [true north, convergence {sv['conv']}; rotation checks {gaps[0]:.0f} m / {gaps[1]:.0f} m]"
        bh = pts[-1]
        gap = meters(bh, w["bhl"]) if w["bhl"] else None
        dec = dp([[p[0], p[1]] for p in pts], TOL_M / 111195)
        dec = [[round(p[0], 5), round(p[1], 5)] for p in dec]
        dec[0] = list(w["shl"])
        dec[-1] = [round(bh[0], 5), round(bh[1], 5)]
        ok = gap is not None and (gap < 50 or w["a"] in forced)
        print(f"{'OK  ' if ok else 'WARN'} {name} -> {w['n']} ({w['a']}): {len(sv['rows'])} stations -> {len(dec)} vertices, "
              f"survey bottom hole is {gap:.0f} m from the header's{note}" if gap is not None else f"WARN {name}: no header bottom hole to compare")
        if ok and apply:
            ov[w["a"]] = {"ln": dec, "fx": 6}
            done.append(w["a"])
    if apply and done:
        json.dump(ov, open(OVERRIDES, "w"), indent=1)
        for d in D:
            if d["a"] in done:
                d["ln"] = ov[d["a"]]["ln"]; d["surv"] = True; d["fx"] = 6
        open(INDEX, "w").write(s[:i] + json.dumps(D, separators=(",", ":")) + s[j:])
        print(f"applied {len(done)} wells; run update.py or push to publish")
    elif not apply:
        print("dry run only; add --apply to write the changes")


if __name__ == "__main__":
    main()
