"""Export the directional surveys held in data/survey_stations.json as one CSV.

    python3 tools/surveys/export_surveys.py --operator Ballard --formation Turner -o ballard_turner_surveys.csv
    python3 tools/surveys/export_surveys.py --all -o prb_surveys.csv

One row per station: UWI (14 digits: API10 plus 0000, no dashes), well name, MD, inclination, azimuth (as filed) and, for COMPLETE surveys only, TVD and north/east offsets from the
surface location (minimum curvature, true north). Complete uses the same rule as the GeoGraphix and OpenWorks exports (survey_complete): a table that starts near the
surface and has no big gaps once the well is past 10 degrees. Partial surveys (for example lateral-only tables) are included with Complete = N and no TVD/offsets,
so nothing is hidden; a complete survey that starts below the surface gets a tie-in row at MD 0 (0 inclination, 0 azimuth).
"""
import argparse, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "geographix"))
from export_ascii4 import station_rows, survey_complete

HEAD = ["UWI", "WellName", "MD_ft", "Inclination_deg", "Azimuth_deg", "TVD_ft", "NorthOffset_ft", "EastOffset_ft", "Complete"]


def q(s):
    s = "" if s is None else str(s)
    return '"' + s.replace('"', '""') + '"' if re.search(r'[",\r\n]', s) else s


def fx(v):
    return f"{v:.2f}"


def well_rows(d, stations):
    if not stations:
        return []
    uwi = d["a"].replace("-", "") + "0000"; nm = q(d.get("n"))
    if survey_complete(stations):
        return [",".join([uwi, nm, fx(md), fx(inc), fx(azi), fx(tvd), fx(n), fx(e), "Y"]) for md, tvd, inc, azi, n, e in station_rows(stations)]
    return [",".join([uwi, nm, fx(md), fx(inc), fx(azi), "", "", "", "N"]) for md, inc, azi in stations]


def build(wells, SS):
    out = [",".join(HEAD)]
    for d in wells:
        out += well_rows(d, SS.get(d["a"]))
    return "\r\n".join(out) + "\r\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", nargs="*"); ap.add_argument("--operator"); ap.add_argument("--formation"); ap.add_argument("--all", action="store_true")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    s = open(os.path.join(ROOT, "index.html")).read(); i = s.index("const D=") + 8
    D = json.loads(s[i:s.index(";\nconst GRID", i)])
    SS = json.load(open(os.path.join(ROOT, "data", "survey_stations.json")))
    norm = lambda x: re.sub(r"\D", "", x)[:10]
    if a.api:
        want = {norm(x) for x in a.api}; wells = [d for d in D if norm(d["a"]) in want]
    elif a.operator or a.formation or a.all:
        wells = [d for d in D if (not a.operator or a.operator.lower() in d["oc"].lower()) and (not a.formation or a.formation.lower() == d["r"].lower())]
    else:
        ap.error("choose --api, --operator/--formation or --all")
    text = build(wells, SS)
    with open(a.out, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    n = sum(1 for d in wells if SS.get(d["a"])); c = sum(1 for d in wells if SS.get(d["a"]) and survey_complete(SS[d["a"]]))
    print(f"{len(wells)} wells, {n} with a survey ({c} complete, {n - c} partial), {text.count(chr(10)) - 1} station rows -> {a.out}")


if __name__ == "__main__":
    main()
