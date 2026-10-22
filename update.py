#!/usr/bin/env python3
"""Daily refresh for the Campbell County horizontal wells map.

Pulls wells, tracks and statuses from the WOGCC Data Explorer (GeoServer WFS),
fetches full headers only for new or changed wells, pulls drilling-rig call-ins
from the WOGCC drilling activity report, and rewrites the data blocks in index.html.

    python3 update.py            rebuild index.html
    python3 update.py --push     also commit and push when the data changed
"""
import collections, concurrent.futures as cf, datetime, html, json, math, os, re, subprocess, sys, time
import urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(ROOT, "index.html")
HEADERS = os.path.join(ROOT, "data", "headers.json")
OVERRIDES = os.path.join(ROOT, "data", "overrides.json")
WFS = "https://dataexplorer.wogcc.wyo.gov/geoserver/wfs"
ED = "https://dataexplorer.wogcc.wyo.gov/ED.aspx?KeyName=PKey&KeyValue={}&KeyType=Integer&DetailXML=WellDetails.xml"
DRILL = "https://pipeline.wyo.gov/drillactivityByCallIn.cfm"
UA = {"User-Agent": "Mozilla/5.0 (campbell-wells-map daily update)"}
MIN_API = "49-005-35840"        # API 49005358400000 and up
RIG_DAYS = 14                   # a rig is "active" if it reported casing work this recently
DROP_FORMATIONS = {"Big George", "Anderson"}
FORMATION_MERGE = {"Frontier-Turner": "Turner", "Niobrara-Turner": "Niobrara"}
OUTLIER_M = 1500                # drop track vertices farther than this from the SHL-BHL line

OPERATORS = {
    "ANSCHUTZ EXPLORATION CORPORATION": "Anschutz", "ANSCHUTZ OIL COMPANY LLC": "Anschutz",
    "BALLARD PETROLEUM HOLDINGS LLC": "Ballard Petroleum", "BAYTEX ENERGY USA LLC": "Baytex",
    "BURNETT OIL CO INC": "Burnett Oil", "CAMCO OPERATING LLC": "Camco", "CENERGY RESOURCES LLC": "Cenergy",
    "CENTURY OIL AND GAS LLC": "Century", "CHIPCORE LLC": "Chipcore", "CITATION OIL & GAS CORPORATION": "Citation",
    "CONTANGO RESOURCES LLC": "Contango", "CONTINENTAL RESOURCES INC": "Continental", "DENBURY ONSHORE LLC": "Denbury",
    "DEVON ENERGY PRODUCTION COMPANY LP": "Devon", "EMEP II OPERATING LLC": "EMEP II", "EOG RESOURCES INC": "EOG",
    "FDL OPERATING LLC": "FDL", "LOIL OIL LLC": "LOIL", "MDS ENERGY DEVELOPMENT LLC": "MDS Energy",
    "NAVIGATION POWDER RIVER LLC": "Navigation Powder River", "PEAK POWDER RIVER RESOURCES LLC": "Peak Powder River",
    "PETRO-HUNT LLC": "Petro-Hunt", "ROCKIES RESOURCES HOLDINGS LLC": "Rockies Resources",
    "SAGE BUTTE PRB OPERATING, LLC": "Sage Butte", "THE TERMO COMPANY": "Termo", "THREE CROWN PETROLEUM LLC": "Three Crown",
    "TITAN EXPLORATION LLC": "Titan", "TRUE OIL LLC": "True Oil", "VALKYRIE OPERATING LLC": "Valkyrie",
    "WAVE PETROLEUM OPERATING LLC": "Wave Petroleum", "WELLSTAR CORPORATION": "Wellstar", "WRC ENERGY LLC": "WRC Energy",
}
RIG_NAMES = {"PRECISION 719": "Precision 719", "PRECISION 720": "Precision 720", "PATTERSON 901": "Patterson 901",
             "NABORS B16": "Nabors B16", "CYCLONE 36": "Cyclone 36 (Anschutz)"}
HEADER_FIELDS = ["API Number", "Well Name and Number", "Operator", "Well Status", "Well Status Date", "Confidential?",
                 "Spud Date", "Completion Date", "Well Class", "Deviation", "County", "Completed Reservoir",
                 "Producing Reservoir", "Field", "Mineral and Surface Ownership", "Depth", "Elevation", "SHL QTR1",
                 "SHL QTR2", "SHL Footage N/S", "SHL Footage E/W", "SHL SEC", "SHL TWP", "SHL RGE",
                 "SHL Latitude (NAD83)", "SHL Longitude (NAD83)", "BHL QTR1", "BHL QTR2", "BHL Footage N/S",
                 "BHL Footage E/W", "BHL SEC", "BHL TWP", "BHL RGE", "BHL Latitude (NAD83)", "BHL Longitude (NAD83)"]


def get(url, data=None, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            return urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
        except Exception as e:
            err = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"GET failed: {url[:90]} ({err})")


def wfs(layer, cql):
    q = urllib.parse.urlencode({"service": "WFS", "version": "1.1.0", "request": "GetFeature", "typeName": "WY_SHPS:" + layer,
                                "outputFormat": "application/json", "CQL_FILTER": cql})
    return json.loads(get(WFS + "?" + q))["features"]


def operator_short(name):
    if not name:
        return "Unknown"
    if name in OPERATORS:
        return OPERATORS[name]
    base = re.sub(r"[,.]", "", name.upper())
    base = re.sub(r"^THE ", "", base)
    base = re.sub(r"\b(LLC|INC|LP|LTD|CORP|CORPORATION|COMPANY|CO|HOLDINGS|OPERATING|PRODUCTION)\b", "", base)
    return " ".join(w.capitalize() for w in base.split()) or name.title()


def parse_header(text):
    text = re.sub(r"<script.*?</script>", "", text, flags=re.S)
    items = [x.strip() for x in html.unescape(re.sub(r"<[^>]+>", "|", text)).split("|") if x.strip()]
    d = {}
    for label in HEADER_FIELDS:
        if label in items:
            v = items[items.index(label) + 1] if items.index(label) + 1 < len(items) else ""
            d[label] = None if v in HEADER_FIELDS or v.endswith(("Lot / Tract #", "Measured From")) else v
    return d


def fetch_header(pkey):
    return pkey, parse_header(get(ED.format(pkey)))


def meters(a, b):
    return math.hypot((a[0] - b[0]) * 111195 * math.cos(math.radians(a[1])), (a[1] - b[1]) * 111195)


def off_axis(p, a, b):
    k = math.cos(math.radians(a[1])) * 111195
    bx, by = (b[0] - a[0]) * k, (b[1] - a[1]) * 111195
    px, py = (p[0] - a[0]) * k, (p[1] - a[1]) * 111195
    L = bx * bx + by * by or 1e-9
    t = max(0, min(1, (px * bx + py * by) / L))
    return math.hypot(px - t * bx, py - t * by)


def _dp(p, e):
    if len(p) < 3:
        return p
    (x1, y1), (x2, y2) = p[0], p[-1]
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1e-12
    m, k = 0, 0
    for n in range(1, len(p) - 1):
        d = abs(dy * (p[n][0] - x1) - dx * (p[n][1] - y1)) / L
        if d > m:
            m, k = d, n
    return _dp(p[:k + 1], e)[:-1] + _dp(p[k:], e) if m > e else [p[0], p[-1]]


def rescale_track(line, shl, bhl):
    """Some state tracks have the right shape but are 3.28x too short (feet/meters) measured from the surface
    location. Detect that against the header bottom hole, scale the shape back up and pin both ends."""
    a, b = meters(shl, bhl), meters(shl, line[-1])
    if b < 5 or not 3.2 <= a / b <= 3.4:
        return None
    pts = [line[0]]
    for p in line[1:]:
        if p != pts[-1]:
            pts.append(p)
    pts = _dp(pts, 0.00006)
    S = 1 / 0.3048
    pts = [[shl[0] + (x - shl[0]) * S, shl[1] + (y - shl[1]) * S] for x, y in pts]
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    s0 = [shl[0] - pts[0][0], shl[1] - pts[0][1]]
    s1 = [bhl[0] - pts[-1][0], bhl[1] - pts[-1][1]]
    return [[x + s0[0] * (1 - c / cum[-1]) + s1[0] * c / cum[-1], y + s0[1] * (1 - c / cum[-1]) + s1[1] * c / cum[-1]]
            for (x, y), c in zip(pts, cum)]



def build_wells(log):
    cql = f"WellId LIKE '49-005-%' AND WellId >= '{MIN_API}' AND Slant='H'"
    wells = wfs("WELL", cql)
    tracks = {f["properties"]["PKey"]: f for f in wfs("WELLTRACK", cql)}
    log(f"state layer: {len(wells)} horizontal wells, {len(tracks)} tracks")
    cache = json.load(open(HEADERS)) if os.path.exists(HEADERS) else {}
    stale = [w["properties"]["PKey"] for w in wells
             if w["properties"]["PKey"] not in cache
             or cache[w["properties"]["PKey"]].get("Well Status") != w["properties"]["WellStatus"]
             or cache[w["properties"]["PKey"]].get("Well Status") in ("Active Permit", "Well Spudded")]
    log(f"headers to fetch: {len(stale)} (new, status changed, or still permit/spud)")
    with cf.ThreadPoolExecutor(4) as ex:
        for k, d in ex.map(fetch_header, stale):
            if d.get("API Number"):
                cache[k] = d
    json.dump(cache, open(HEADERS, "w"), separators=(",", ":"))
    overrides = json.load(open(OVERRIDES)) if os.path.exists(OVERRIDES) else {}
    out, dropped, fixed = [], 0, []
    for w in wells:
        k = w["properties"]["PKey"]
        d = cache.get(k)
        if not d:
            continue
        form = (d.get("Producing Reservoir") or d.get("Completed Reservoir") or "Unknown").title()
        form = FORMATION_MERGE.get(form, form)
        if form in DROP_FORMATIONS:
            dropped += 1
            continue
        try:
            shl = [float(d["SHL Longitude (NAD83)"]), float(d["SHL Latitude (NAD83)"])]
        except (TypeError, ValueError, KeyError):
            shl = w["geometry"]["coordinates"]
        try:
            bhl = [float(d["BHL Longitude (NAD83)"]), float(d["BHL Latitude (NAD83)"])]
        except (TypeError, ValueError, KeyError):
            bhl = None
        t = tracks.get(k)
        line = [[x, y] for part in t["geometry"]["coordinates"] for x, y in part] if t else None
        fx = 0
        if line and bhl and len(line) > 2:
            scaled = rescale_track(line, shl, bhl)
            if scaled:
                line, fx = scaled, 4
                fixed.append(d["API Number"] + " (rescaled)")
        if line and bhl and len(line) > 2 and not fx:
            keep = [p for p in line if off_axis(p, shl, bhl) < OUTLIER_M]
            if len(keep) != len(line):
                line, fx = keep, 1
                fixed.append(d["API Number"])
        if not line:
            line = [shl, bhl] if bhl else None
        multi = bool(line and len(line) > 2)
        api = d["API Number"]
        if api in overrides:
            line, fx = overrides[api]["ln"], overrides[api].get("fx", 2)
            multi = len(line) > 2
        rec = {"a": api, "n": d.get("Well Name and Number"), "o": d.get("Operator"), "s": d.get("Well Status"),
               "sd": d.get("Spud Date"), "cd": d.get("Completion Date"), "f": d.get("Field"), "r": form,
               "td": d.get("Depth"), "el": d.get("Elevation"),
               "sec": f'{d.get("SHL SEC")}-{d.get("SHL TWP")}-{d.get("SHL RGE")}',
               "shl": [round(shl[0], 5), round(shl[1], 5)], "bhl": [round(bhl[0], 5), round(bhl[1], 5)] if bhl else None,
               "ln": [[round(x, 5), round(y, 5)] for x, y in line] if line else None, "surv": multi,
               "oc": operator_short(d.get("Operator"))}
        if fx:
            rec["fx"] = fx
        out.append(rec)
    out.sort(key=lambda r: r["a"])
    log(f"{len(out)} wells on map ({dropped} dropped by formation); tracks auto-cleaned: {fixed or 'none'}")
    return out


def build_rigs(wells, log):
    today = datetime.date.today()
    start = today - datetime.timedelta(days=60)
    body = urllib.parse.urlencode({"bmon": start.month, "bday": start.day, "byear": start.year,
                                   "emon": today.month, "eday": today.day, "eyear": today.year,
                                   "SubmitClassDate": "GoFind"}).encode()
    page = re.sub(r"<script.*?</script>|<style.*?</style>", "", get(DRILL, data=body), flags=re.S)
    rows = [[html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, flags=re.S)]
            for r in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.S)]
    pos = [n for n, r in enumerate(rows) if r and r[0] == "Campbell County"]
    if not pos:
        log("rig report: no Campbell County section")
        return []
    cells = rows[pos[0] + 1]
    rec = cells[cells.index("Well Class") + 1:] if "Well Class" in cells else []
    idx = [n for n, x in enumerate(rec) if re.fullmatch(r"49-\d{3}-\d{5}", x)]
    recs = [rec[a:b][:13] for a, b in zip(idx, idx[1:] + [len(rec)]) if len(rec[a:b]) >= 13]

    def norm(r):
        r = r.upper().replace("ANSCHUTZ / ", "").replace("ANSCHUTZ/", "")
        r = re.sub(r"^PD ?(\d+).*", r"PRECISION \1", r)
        return re.sub(r"^PRECISION (\d+)ST$", r"PRECISION \1", r)

    byrig = collections.defaultdict(list)
    for r in recs:
        byrig[norm(r[2])].append((datetime.datetime.strptime(r[1], "%m/%d/%Y").date(), r))
    byapi = {w["a"]: w for w in wells}
    rigs = []
    for rig, l in byrig.items():
        l.sort(key=lambda x: x[0])
        d, r = l[-1]
        age = (today - d).days
        if age > RIG_DAYS:
            continue
        loc = byapi[r[0]]["shl"] if r[0] in byapi else None
        if not loc:  # well isn't one of the horizontals on the map: look it up in the state well layer
            f = wfs("WELL", f"WellId='{r[0]}'")
            loc = [round(f[0]["geometry"]["coordinates"][0], 5), round(f[0]["geometry"]["coordinates"][1], 5)] if f else None
        if not loc:
            log(f"rig {rig}: no location for {r[0]}")
            continue
        pad = sorted({x[1][5] for x in l if x[1][8:11] == r[8:11] and (today - x[0]).days <= 30})
        rigs.append({"rig": RIG_NAMES.get(rig, rig.title()), "last": str(d), "age": age, "work": r[4], "well": r[5],
                     "api": r[0], "sec": f"{r[8]}-{r[9]}N-{r[10]}W", "loc": loc, "wells": pad})
    rigs.sort(key=lambda r: r["age"])
    log(f"{len(recs)} call-in records; active rigs: {[(r['rig'], r['age']) for r in rigs]}")
    return rigs


def write_index(wells, rigs):
    s = open(INDEX).read()
    i = s.index("const D=") + 8
    j = s.index(";\nconst GRID", i)
    s = s[:i] + json.dumps(wells, separators=(",", ":")) + s[j:]
    i = s.index("const RIGS=") + 11
    j = s.index(";\nconst rigLayer", i)
    s = s[:i] + json.dumps(rigs, separators=(",", ":")) + s[j:]
    stamp = datetime.date.today().strftime("%b %-d, %Y")
    s = re.sub(r'(<span id="asof">)[^<]*(</span>)', rf"\g<1>{stamp}\g<2>", s)
    s = re.sub(r"as of [A-Z][a-z]{2} \d{1,2}, \d{4}</small>", f"as of {stamp}</small>", s)
    open(INDEX, "w").write(s)


def main():
    log = lambda m: print(datetime.datetime.now().strftime("%H:%M:%S"), m, flush=True)
    wells = build_wells(log)
    if len(wells) < 1000:
        sys.exit(f"only {len(wells)} wells came back, expected about 1,400; leaving index.html unchanged")
    rigs = build_rigs(wells, log)
    before = open(INDEX).read()
    write_index(wells, rigs)
    changed = open(INDEX).read() != before
    log("index.html " + ("updated" if changed else "unchanged"))
    if "--push" in sys.argv and changed:
        run = lambda *a: subprocess.run(a, cwd=ROOT, check=True)
        run("git", "add", "index.html", "data/headers.json")
        run("git", "commit", "-q", "-m", f"Daily data update {datetime.date.today()}")
        run("git", "push", "-q", "origin", "main")
        log("pushed")


if __name__ == "__main__":
    main()
