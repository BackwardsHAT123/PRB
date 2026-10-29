"""Export PRB wells as three flat CSV files for Kingdom's ASCII loader, in NAD83 UTM Zone 13N, US survey feet.

    python3 tools/kingdom/export_kingdom.py --operator Ballard --formation Turner -o ballard_turner_kingdom.zip
    python3 tools/kingdom/export_kingdom.py --all -o prb_kingdom.zip

Files in the zip: well_headers.csv (one row per well), deviation_surveys.csv (complete surveys only, same rule as the GeoGraphix export),
production.csv (one row per well and month). Wells are keyed by UWI = API10 (no dashes). The state's latitude/longitude are taken as NAD83
(not verified against the state's datum note). Offsets in deviation_surveys.csv are from the surface location, true north, minimum curvature.
"""
import argparse, io, json, math, os, re, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "geographix"))
from export_ascii4 import station_rows, survey_complete, num          # same minimum curvature and completeness rule as the GeoGraphix export

FT = 1200 / 3937                                                       # metres per US survey foot
A, F, K0, FE, LON0 = 6378137.0, 1 / 298.257222101, 0.9996, 500000.0, -105.0   # GRS80, UTM zone 13 central meridian
_n = F / (2 - F)
_AA = A / (1 + _n) * (1 + _n ** 2 / 4 + _n ** 4 / 64 + _n ** 6 / 256)
_AL = (_n / 2 - 2 * _n ** 2 / 3 + 5 * _n ** 3 / 16 + 41 * _n ** 4 / 180, 13 * _n ** 2 / 48 - 3 * _n ** 3 / 5 + 557 * _n ** 4 / 1440,
       61 * _n ** 3 / 240 - 103 * _n ** 4 / 140, 49561 * _n ** 4 / 161280)


def utm13_ft(lon, lat):
    """(lon, lat) NAD83 degrees -> (easting, northing) in US survey feet, UTM zone 13N (Krueger series, good to well under a millimetre)."""
    p, dl = math.radians(lat), math.radians(lon - LON0)
    q = 2 * math.sqrt(_n) / (1 + _n)
    t = math.sinh(math.atanh(math.sin(p)) - q * math.atanh(q * math.sin(p)))
    xi, eta = math.atan2(t, math.cos(dl)), math.atanh(math.sin(dl) / math.sqrt(1 + t * t))
    x = xi + sum(a * math.sin(2 * j * xi) * math.cosh(2 * j * eta) for j, a in enumerate(_AL, 1))
    y = eta + sum(a * math.cos(2 * j * xi) * math.sinh(2 * j * eta) for j, a in enumerate(_AL, 1))
    return (FE + K0 * _AA * y) / FT, K0 * _AA * x / FT


def q(s):
    s = "" if s is None else str(s)
    return '"' + s.replace('"', '""') + '"' if re.search(r'[",\r\n]', s) else s


def fx(v, nd):
    return "" if v is None or v == "" else f"{v:.{nd}f}"


HEAD = ["UWI", "WellName", "Operator", "Status", "Field", "County", "State", "Formation", "SpudDate", "CompletionDate", "GroundElev_ft",
        "TD_MD_ft", "SurfaceX_ft", "SurfaceY_ft", "BottomX_ft", "BottomY_ft", "SurfaceLat", "SurfaceLon", "BottomLat", "BottomLon", "Section"]
SURV = ["UWI", "MD_ft", "TVD_ft", "Inclination_deg", "Azimuth_deg", "NorthOffset_ft", "EastOffset_ft"]
PROD = ["UWI", "Month", "Year", "MonthNum", "Oil_bbl", "Gas_mcf", "Water_bbl", "DaysOn"]


def well_rows(d, prod, perfs, stations, keep=None):
    api10 = d["a"].replace("-", "")
    iv = [x for p in (perfs or []) for x in p]
    td = int(max(iv)) if iv else (int(float(str(d["td"]).replace(",", ""))) if d.get("td") else None)    # the state depth can read "17,968"
    sx = sy = bx = by = None
    if d.get("shl"): sx, sy = utm13_ft(d["shl"][0], d["shl"][1])
    if d.get("bhl"): bx, by = utm13_ft(d["bhl"][0], d["bhl"][1])
    shl, bhl = d.get("shl") or [None, None], d.get("bhl") or [None, None]
    h = [api10, d.get("n"), d.get("o") or d.get("oc"), d.get("s"), d.get("f"), d.get("cty"), "WY", d.get("r"), d.get("sd"), d.get("cd"),
         num(float(d["el"])) if d.get("el") else "", td if td else "", fx(sx, 2), fx(sy, 2), fx(bx, 2), fx(by, 2),
         fx(shl[1], 6), fx(shl[0], 6), fx(bhl[1], 6), fx(bhl[0], 6), d.get("sec")]
    s = []
    if stations and survey_complete(stations):
        for md, tvd, inc, azi, n, e in station_rows(stations):
            s.append(",".join([api10, fx(md, 2), fx(tvd, 2), fx(inc, 2), fx(azi, 2), fx(n, 2), fx(e, 2)]))
    p = []
    if prod and prod.get("s") and not prod.get("none"):
        y, m0 = map(int, prod["s"].split("-"))
        for i in range(len(prod["o"])):
            yy, mm = divmod(y * 12 + m0 - 1 + i, 12)
            if keep and not keep(f"{yy}-{mm + 1:02d}"): continue
            dd = prod.get("d") or []
            p.append(",".join([api10, f"{yy}-{mm + 1:02d}-01", str(yy), str(mm + 1), str(prod["o"][i] or 0), str((prod.get("g") or [])[i] or 0) if i < len(prod.get("g") or []) else "0",
                               str((prod.get("w") or [])[i] or 0) if i < len(prod.get("w") or []) else "0", str(dd[i]) if i < len(dd) and dd[i] is not None else ""]))
    return ",".join(q(v) for v in h), s, p


def build(wells, P, LS, SS, keep=None):
    hs, ss, ps = [",".join(HEAD)], [",".join(SURV)], [",".join(PROD)]
    for d in wells:
        h, s, p = well_rows(d, P.get(d["a"]), LS.get(d["a"]), SS.get(d["a"]), keep)
        hs.append(h); ss += s; ps += p
    return {"well_headers.csv": "\r\n".join(hs) + "\r\n", "deviation_surveys.csv": "\r\n".join(ss) + "\r\n", "production.csv": "\r\n".join(ps) + "\r\n"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", nargs="*"); ap.add_argument("--operator"); ap.add_argument("--formation"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--from", dest="frm"); ap.add_argument("--to")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    s = open(os.path.join(ROOT, "index.html")).read(); i = s.index("const D=") + 8
    D = json.loads(s[i:s.index(";\nconst GRID", i)])
    P = json.load(open(os.path.join(ROOT, "data", "production.json")))
    LS = json.load(open(os.path.join(ROOT, "data", "lateral_state.json")))
    SS = json.load(open(os.path.join(ROOT, "data", "survey_stations.json")))
    norm = lambda x: re.sub(r"\D", "", x)[:10]
    if a.api:
        want = {norm(x) for x in a.api}; wells = [d for d in D if norm(d["a"]) in want]
    elif a.operator or a.formation or a.all:
        wells = [d for d in D if (not a.operator or a.operator.lower() in d["oc"].lower()) and (not a.formation or a.formation.lower() == d["r"].lower())]
    else:
        ap.error("choose --api, --operator/--formation or --all")
    keep = (lambda k: not (a.frm and k < a.frm) and not (a.to and k > a.to)) if (a.frm or a.to) else None
    files = build(wells, P, LS, SS, keep)
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in files.items(): z.writestr(k, v.encode("utf-8"))
    print(f"{len(wells)} wells, {files['deviation_surveys.csv'].count(chr(10)) - 1} survey stations, {files['production.csv'].count(chr(10)) - 1} production rows -> {a.out}")


if __name__ == "__main__":
    main()
