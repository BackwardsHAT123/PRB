"""Build an importable points CSV (for the GRID button on the map) from the vertical-well header readings.

    python3 tools/export_points.py [--readings ../header_readings.csv ../campbell_headers/header_readings.csv] [--out ../vertical_points.csv] [--dbf wells.dbf]

* one row per well (API); when a well has several logs the HIGH-confidence value wins, else the first non-blank one
* Lat/Lon come from the state well-header DBF when --dbf is given (same values as the WFS layer), else from the WOGCC GeoServer WFS (batched, ~25 wells per request - gentle on the server); WFS also fills any well the DBF lacks
* Formation comes from BOTFORM in the state well-header DBF if --dbf is given (the WFS layer has no formation); else blank
* re-run after importing manual review answers (review_sheet/import_answers.py) to refresh the CSV
"""
import argparse, csv, json, os, struct, subprocess, time, urllib.parse, urllib.request

WFS = "https://dataexplorer.wogcc.wyo.gov/geoserver/wfs"
ap = argparse.ArgumentParser()
here = os.path.dirname(os.path.abspath(__file__))
ap.add_argument("--readings", nargs="+", default=[os.path.join(here, "..", "..", "header_readings.csv"), os.path.join(here, "..", "..", "campbell_headers", "header_readings.csv")], help="one or more header_readings.csv files (Converse, Campbell, ...)")
ap.add_argument("--out", default=os.path.join(here, "..", "..", "vertical_points.csv"))
ap.add_argument("--dbf", default="")
a = ap.parse_args()


def wfs(apis):
    cql = "WellId IN (" + ",".join("'%s'" % x for x in apis) + ")"
    q = urllib.parse.urlencode({"service": "WFS", "version": "1.1.0", "request": "GetFeature", "typeName": "WY_SHPS:WELL",
                                "outputFormat": "application/json", "CQL_FILTER": cql})
    url = WFS + "?" + q
    for i in range(4):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=90).read())["features"]
        except Exception:
            time.sleep(3 * (i + 1))
    out = subprocess.run(["curl", "-s", "-m", "90", url], capture_output=True)
    try:
        return json.loads(out.stdout)["features"]
    except ValueError:
        return []     # WFS answered with an error page (layer unavailable); caller falls back to the DBF


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
            c = float(g("APINO")); res[str(int(round(c)))] = g("BOTFORM")   # APINO is county-code*100000 + well number, e.g. 905472 = 49-009-05472
        except ValueError:
            pass
    return res


rows = [r for p in a.readings if os.path.exists(p) for r in csv.DictReader(open(p))]
by = {}
for r in rows: by.setdefault(r["API"], []).append(r)
apis = sorted(by)
loc = {}
bf = botform(a.dbf) if a.dbf else {}
if a.dbf:      # the state well-header DBF carries the same surface lat/lon as the WFS layer, so use it first (fast, no server load)
    dc = dbf_coords(a.dbf)
    for api in apis:
        if api_key(api) in dc and dc[api_key(api)][1]:
            loc[api] = list(dc[api_key(api)])
    print(f"{len(loc)} of {len(apis)} locations from the DBF")
miss = [x for x in apis if x not in loc]
for i in range(0, len(miss), 25):          # WFS only for wells the DBF has no coordinates for
    for f in wfs(miss[i:i + 25]):
        loc[f["properties"]["WellId"]] = f["geometry"]["coordinates"]
    time.sleep(1)


def best(group, col, conf):
    vals = [(r[col], r.get(conf, "")) for r in group if r.get(col, "") != ""]
    if not vals: return "", ""
    for v, c in vals:
        if c == "HIGH": return v, c
    return vals[0]


out = []
for api in apis:
    g = by[api]; ll = loc.get(api)
    d = {"API": api, "Well_Name": g[0]["Well_Name"], "Operator": g[0]["Operator"], "Spud_Year": g[0]["Spud_Year"], "TD_ft": g[0]["State_TD"],
         "Lat": round(ll[1], 6) if ll else "", "Lon": round(ll[0], 6) if ll else "", "Formation": bf.get(str(int(api[3:6]) * 100000 + int(api[7:])), "")}
    for col, conf in (("KB_ft", "KB_conf"), ("Bottom_Logged_ft", "BLI_conf"), ("Time_Since_Circ_hrs", "CIRC_conf"), ("Max_Temp_F", "TEMP_conf")):
        v, c = best(g, col, conf); d[col] = v; d[conf] = c
    d["Temp_Source"] = next((r["Temp_Source"] for r in g if r["Max_Temp_F"] == d["Max_Temp_F"] and r.get("Temp_Source")), "")
    out.append(d)
with open(a.out, "w", newline="") as w:
    cw = csv.DictWriter(w, fieldnames=list(out[0].keys())); cw.writeheader(); cw.writerows(out)
n = lambda k: sum(1 for d in out if d[k] != "")
print(f"{len(out)} wells -> {a.out}; with location {n('Lat')}, formation {n('Formation')}, KB {n('KB_ft')}, BLI {n('Bottom_Logged_ft')}, circ {n('Time_Since_Circ_hrs')}, temp {n('Max_Temp_F')}")
