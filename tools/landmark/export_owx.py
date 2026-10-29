"""Export PRB wells as a Landmark OpenWorks OWX ASCII (.ASC) file, laid out like Tom's Drillinginfo example (Niobrara_2026-10-29 Openworks OWX.ASC).

    python3 tools/landmark/export_owx.py --operator Ballard --formation Turner -o ballard_turner.asc
    python3 tools/landmark/export_owx.py --all -o prb_all.asc

Fixed-width records, CRLF line ends, the record name in columns 1-6 ('WELL  ', '2WELL ', ... a digit prefix marks a continuation line), fields
left-aligned from the 1-based columns noted below. Written per well: WELL (+2..8: name, operator, lease, number, lat/lon surface and bottom hole,
KB/elevation, TD, county, state, spud, status, field, basin), CNGR (township/range/section), COMP (+2COMP: completion date, perforated interval,
formation), WPERF (+2WPERF: the state producing intervals), DSV1/DSV6/DSV7 (directional survey MD/inclination/azimuth, complete surveys only).
WLTRT (treatment totals: stages, proppant lb, fluid bbl, fluid type) comes from the completions page data for the wells that have it.
Left out because the map has no data for them: PICK (formation tops), WTEST (initial potential), CASG (casing), LINR (liner).
KB comes from data/kb.json (Form 3, built by tools/completions/kb_extract.py); a well without one gets the state ground elevation with no KB label.
"""
import argparse, csv, json, os, re, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "geographix"))
from export_ascii4 import split_name, survey_complete, num          # same name split, survey completeness rule and number text as the GeoGraphix export

LEN = {"WELL": 113, "2WELL": 113, "3WELL": 122, "4WELL": 58, "5WELL": 102, "6WELL": 12, "7WELL": 170, "8WELL": 148, "CNGR": 77, "COMP": 101, "2COMP": 46,
       "WLTRT": 131, "2WLTRT": 83, "3WLTRT": 44, "WPERF": 132, "2WPERF": 80, "DSV1": 37, "DSV6": 44, "DSV7": 44}    # record lengths in the example
STATUS = {"Producing Oil Well": "OIL+ACTIVE", "Producing Gas Well": "GAS+ACTIVE", "Shut-In": "OIL+SHUT-IN", "Temporarily Abandoned": "OIL+SHUT-IN",
          "Well Spudded": "OIL+DRILLED", "Subsequent Report of Abandonment": "OIL+P & A", "Permanently Abandoned": "OIL+P & A",
          "Notice of Intent to Abandon": "OIL+ACTIVE", "Active Permit": "OIL+PERMITTED", "Proposed (APD)": "OIL+PERMITTED", "Active Injector": "WATER INJ+ACTIVE",
          "Gas Lift": "OIL+ACTIVE", "Pumping Rods": "OIL+ACTIVE", "Suspended Operations": "OIL+SHUT-IN"}


class Rec:
    """A blank fixed-width line; columns are 1-based like the layout notes."""
    def __init__(self, typ):
        self.c = [" "] * LEN[typ]
        self.put(1, typ if typ[0].isdigit() else typ.ljust(6))
        if typ[0].isdigit(): self.put(1, typ)

    def put(self, col, text):
        for i, ch in enumerate(str(text)):
            self.c[col - 1 + i] = ch if ord(ch) < 128 else "?"

    def __str__(self):
        return "".join(self.c)


def line(typ, **cols):
    r = Rec(typ)
    for col, text in cols.items():
        r.put(int(col[1:]), text)
    return str(r)


def deg(v):
    return f"{v:.7f}"


def fluid_type(s):
    """OpenWorks treatment fluid text from the completions page's fluid system note."""
    s = (s or "").lower()
    sw, cl = "slickwater" in s or "hvfr" in s, "crosslink" in s or "gel" in s or "hybrid" in s
    if "hybrid" in s and "words" not in s: return "HYBRID CROSS"
    if sw and cl: return "SLICKCROSSLI"
    return "CROSSLINK" if cl else "SLICKWATER" if sw else ""


def well_records(d, perfs, stations, kb=None, tr=None):
    api10 = d["a"].replace("-", ""); u14 = api10 + "0000"
    nm, no = split_name(d.get("n"))
    iv = [x for p in (perfs or []) for x in p]
    st = list(stations) if stations and survey_complete(stations) else []
    td = int(max(r[0] for r in stations)) if stations else (int(max(iv)) if iv else (int(float(str(d["td"]).replace(",", ""))) if d.get("td") else None))
    out = []
    out.append(line("WELL", c7=u14, c34=d.get("n") or ""))
    out.append(line("2WELL", c7=(d.get("o") or d.get("oc") or "").upper()[:40], c48=nm.upper()[:40], c89=no.upper()[:15]))
    sh, bh = d.get("shl"), d.get("bhl")
    c3 = {}
    if sh: c3["c39"], c3["c55"] = deg(sh[1]), deg(sh[0])
    if bh: c3["c97"], c3["c110"] = deg(bh[1]), deg(bh[0])
    out.append(line("3WELL", **c3))
    c4 = {"c49": "H"}
    if kb: c4["c7"] = "KB"; c4["c10"] = num(float(kb))                  # KB from the Form 3 (data/kb.json)
    elif d.get("el"): c4["c10"] = num(float(d["el"]))                    # none found: the state ground elevation, without the KB label
    if td: c4["c23"] = td
    out.append(line("4WELL", **c4))
    out.append(line("5WELL", c7=(d.get("cty") or "").upper(), c33="WY", c55="UNITED STATES", **({"c92": d["sd"][6:10] + d["sd"][0:2] + d["sd"][3:5]} if d.get("sd") else {})))
    out.append(line("6WELL"))
    out.append(line("7WELL", c130=STATUS.get(d.get("s"), "OIL+" + (d.get("s") or "").upper())))
    out.append(line("8WELL", c48="WC" if d.get("f") == "Wildcat" else (d.get("f") or "").upper(), c89="POWDER RIVER"))
    m = re.match(r"(\d+)-(\d+)([NS])-(\d+)([EW])", d.get("sec") or "")
    if m:
        out.append(line("CNGR", c47=int(m[2]), c55=m[3], c58=int(m[4]), c66=m[5], c69=f"{int(m[1]):02d}"))
    if d.get("cd") or iv:
        out.append(line("COMP", c7="1", **({"c12": d["cd"]} if d.get("cd") else {}), **({"c77": int(min(iv)), "c90": int(max(iv))} if iv else {})))
        out.append(line("2COMP", c7=(d.get("r") or "").upper()))
    if tr and (tr["stages"] or tr["sand"] or tr["fluid"]):          # treatment totals from data/completions/PRB_niobrara_completions.csv
        ft = fluid_type(tr["system"])
        c = {"c7": "1", "c12": "2" if ft else "1", "c56": "1", "c92": (d.get("r") or "").upper()}
        if ft: c["c43"] = ft
        if tr["stages"]: c["c61"] = tr["stages"]
        if iv: c["c66"], c["c79"] = int(min(iv)), int(max(iv))
        out.append(line("WLTRT", **c))
        c = {}
        if tr["sand"]: c["c7"] = tr["sand"]
        if tr["fluid"]: c["c59"], c["c72"] = tr["fluid"], "BBL"
        out.append(line("2WLTRT", **c)); out.append(line("3WLTRT"))
    seen = []
    for top, bot in sorted((min(p), max(p)) for p in (perfs or []) if len(p) == 2 and p[0] != p[1]):
        if (top, bot) in seen: continue
        seen.append((top, bot))
        out.append(line("WPERF", c7="1", c12=len(seen), c67=int(top), c121=int(bot)))
        out.append(line("2WPERF"))
    if st:
        if st[0][0] > 0: st = [[0.0, 0.0, 0.0]] + st
        out.append(line("DSV1", c7="UWI: " + u14))
        out.append(line("DSV6", c7="Measr. Depth", c20="Deviation", c33="Direction"))
        for md, inc, azi in st:
            out.append(line("DSV7", c7=num(round(md, 2)) or "0", c20=num(round(inc, 2)) or "0", c33=num(round(azi, 2)) or "0"))
    return out


def build(wells, LS, SS, label, stamp, KB=None, TR=None):
    lines = ["            Well Data Export", f"Project             :  {label}", "Depth Mode          :  MD", "Depth Unit          :  feet",
             "Distance Unit       :  feet", f"Date                :  {stamp}", "    "]
    for d in wells:
        lines += well_records(d, LS.get(d["a"]), SS.get(d["a"]), (KB or {}).get(d["a"]), (TR or {}).get(d["a"].replace("-", "")))
    return "\r\n".join(lines) + "\r\n"


def stamp_now():
    t = time.localtime()
    return time.strftime("%a %b ", t) + f"{t.tm_mday:2d}" + time.strftime(" %H:%M:%S %Y", t)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", nargs="*"); ap.add_argument("--operator"); ap.add_argument("--formation"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--stamp", help="date text for the header (default: now)"); ap.add_argument("--label", default="PRB map Openworks OWX")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    s = open(os.path.join(ROOT, "index.html")).read(); i = s.index("const D=") + 8
    D = json.loads(s[i:s.index(";\nconst GRID", i)])
    LS = json.load(open(os.path.join(ROOT, "data", "lateral_state.json")))
    SS = json.load(open(os.path.join(ROOT, "data", "survey_stations.json")))
    KB = json.load(open(os.path.join(ROOT, "data", "kb.json")))
    TR = {r["api"]: {"stages": r["stages"], "sand": r["sand_lb"], "fluid": r["fluid_bbl"], "system": r["fluid_system"]}
          for r in csv.DictReader(open(os.path.join(ROOT, "data", "completions", "PRB_niobrara_completions.csv"), newline=""))}
    norm = lambda x: re.sub(r"\D", "", x)[:10]
    if a.api:
        want = {norm(x) for x in a.api}; wells = [d for d in D if norm(d["a"]) in want]
    elif a.operator or a.formation or a.all:
        wells = [d for d in D if (not a.operator or a.operator.lower() in d["oc"].lower()) and (not a.formation or a.formation.lower() == d["r"].lower())]
    else:
        ap.error("choose --api, --operator/--formation or --all")
    with open(a.out, "w", encoding="latin1", newline="") as fh:
        fh.write(build(wells, LS, SS, a.label, a.stamp or stamp_now(), KB, TR))
    print(f"{len(wells)} wells -> {a.out}")


if __name__ == "__main__":
    main()
