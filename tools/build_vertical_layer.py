"""Build data/vertical_wells.json (the public 'vertical wells with induction logs' map layer) from one or more
well-list CSVs (columns: API, Well Name, Operator, Spud Year, TD_ft).  Public state data only.

    python3 tools/build_vertical_layer.py LIST.csv [LIST2.csv ...] --dbf 110326WH.DBF [--out data/vertical_wells.json]

Lat/lon come from the WOGCC GeoServer WFS (batches of 25, gentle); formation (BOTFORM) from the well-header DBF.
Wells whose WFS lookup fails are reported and left out (re-run to retry; nothing is overwritten unless every list loaded)."""
import argparse, csv, json, os, struct, subprocess, time, urllib.parse, urllib.request

WFS = "https://dataexplorer.wogcc.wyo.gov/geoserver/wfs"
here = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("lists", nargs="+")
ap.add_argument("--dbf", required=True)
ap.add_argument("--out", default=os.path.join(here, "..", "data", "vertical_wells.json"))
a = ap.parse_args()


def wfs(apis):
    cql = "WellId IN (" + ",".join("'%s'" % x for x in apis) + ")"
    url = WFS + "?" + urllib.parse.urlencode({"service": "WFS", "version": "1.1.0", "request": "GetFeature", "typeName": "WY_SHPS:WELL",
                                              "outputFormat": "application/json", "CQL_FILTER": cql})
    for i in range(4):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=90).read())["features"]
        except Exception:
            time.sleep(3 * (i + 1))
    try:
        return json.loads(subprocess.run(["curl", "-s", "-m", "90", url], capture_output=True).stdout)["features"]
    except ValueError:
        return []     # WFS layer unavailable; the DBF fallback below fills in


def dbf_coords(path):
    """Fallback surface locations from the well-header DBF (LAT/LON; same values as the WFS layer) when the WFS is down."""
    f = open(path, "rb"); h = f.read(32); n, hl, rl = struct.unpack("<IHH", h[4:12]); fl = []
    while True:
        d = f.read(32)
        if d[0] == 0x0D: break
        fl.append((d[:11].split(b"\0")[0].decode(), d[16]))
    off, o = {}, 1
    for nm, ln in fl: off[nm] = (o, ln); o += ln
    f.seek(hl); res = {}
    for _ in range(n):
        r = f.read(rl)
        g = lambda k: r[off[k][0]:off[k][0] + off[k][1]].decode("latin-1").strip() if k in off else ""
        try:
            res[str(int(round(float(g("APINO")))))] = (float(g("LON")), float(g("LAT")))
        except ValueError:
            pass
    return res


def api_key(api):
    return str(int(api[3:6]) * 100000 + int(api[7:]))


def botform(path):
    f = open(path, "rb"); h = f.read(32); n, hl, rl = struct.unpack("<IHH", h[4:12]); fl = []
    while True:
        d = f.read(32)
        if d[0] == 0x0D: break
        fl.append((d[:11].split(b"\0")[0].decode(), d[16]))
    off, o = {}, 1
    for nm, ln in fl: off[nm] = (o, ln); o += ln
    f.seek(hl); res = {}
    for _ in range(n):
        r = f.read(rl)
        g = lambda k: r[off[k][0]:off[k][0] + off[k][1]].decode("latin-1").strip() if k in off else ""
        try:
            res[str(int(round(float(g("APINO")))))] = g("BOTFORM")      # APINO = county code*100000 + well number
        except ValueError:
            pass
    return res


wells = {}
for p in a.lists:
    for r in csv.DictReader(open(p)):
        wells[r["API"]] = r
apis = sorted(wells)
loc = {}
for i in range(0, len(apis), 25):
    for f in wfs(apis[i:i + 25]):
        loc[f["properties"]["WellId"]] = f["geometry"]["coordinates"]
    if (i // 25) % 10 == 0:
        print(f"{min(i + 25, len(apis))}/{len(apis)} located", flush=True)
    time.sleep(1)
bf = botform(a.dbf)
dc = dbf_coords(a.dbf)
for api in apis:
    if api not in loc and api_key(api) in dc and dc[api_key(api)][1]:
        loc[api] = list(dc[api_key(api)])
out, miss = [], []
for api in apis:
    r = wells[api]
    if api not in loc:
        miss.append(api); continue
    spud = r.get("Spud Year", "")
    td = r.get("TD_ft", "")
    out.append({"a": api, "n": r["Well Name"], "o": r["Operator"], "y": int(spud) if spud.isdigit() else None,
                "td": int(float(td)) if td else None, "f": bf.get(str(int(api[3:6]) * 100000 + int(api[7:])), ""),
                "ll": [round(loc[api][0], 5), round(loc[api][1], 5)]})
json.dump(out, open(a.out, "w"), separators=(",", ":"))
print(f"{len(out)} wells written to {a.out}; {len(miss)} without a location: {miss[:10]}")
