"""Export PRB wells and monthly production as a GeoGraphix ASCII4 (.WB4) file.

    python3 tools/geographix/export_ascii4.py --api 49-005-61788 49-005-63118 -o test.WB4
    python3 tools/geographix/export_ascii4.py --operator Ballard --formation Turner -o ballard_turner.WB4
    python3 tools/geographix/export_ascii4.py --all -o prb_all.WB4

Reads index.html (wells), data/production.json (monthly oil/gas/water) and data/lateral_state.json (state producing
intervals). The layout was worked out from a Drillinginfo export (Powder Test GeoGraphix ASCII4.WB4): fixed-width records,
CRLF line ends, a two-letter record type in columns 1-2 and the 14-digit UWI in columns 15-28. See tools/geographix/ASCII4_FORMAT.md.
KB elevation (WH col 246) comes from data/kb.json, built from the Form 3 reports by tools/completions/kb_extract.py.
Written records: WH (well header), B0 (legal), CP (completion), SD (survey header), ST (survey stations, from data/survey_stations.json),
PF (perforations, from the state producing intervals), PT (production). The other record types (FT tops, MC casing, IT/IP initial
potential) are left out; their section comments are kept.
"""
import argparse, json, math, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEN = {"WH": 988, "B0": 397, "CP": 146, "SD": 327, "ST": 152, "PF": 448, "PT": 237}       # record lengths seen in the sample


class Rec:
    """A blank fixed-width record; columns are 1-based like the layout notes."""
    def __init__(self, typ):
        self.t, self.c = typ, [" "] * LEN[typ]
        self.put(1, typ)

    def put(self, col, text):                    # left-aligned, starts at col
        for i, ch in enumerate(str(text)):
            self.c[col - 1 + i] = ch if ord(ch) < 128 else "?"

    def putr(self, end, text):                   # right-aligned, ends at col end
        text = str(text)
        self.put(end - len(text) + 1, text)

    def __str__(self):
        return "".join(self.c)


def num(v):
    if v is None or v == "":
        return ""
    return f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def split_name(name):
    """'ROUSH FED 44-24-1X TH' -> ('ROUSH FED', '44-24-1X TH'): the number starts at the first token that begins with a digit."""
    toks = (name or "").split()
    for i, t in enumerate(toks):
        if t[0].isdigit():
            return " ".join(toks[:i]), " ".join(toks[i:])
    return " ".join(toks), ""


def station_rows(st):
    """[(md, inc, azi)] -> [(md, tvd, inc, azi, north, east)] by minimum curvature from a vertical tie-in at the surface (md 0)."""
    if not st or st[0][0] > 0:
        st = [[0.0, 0.0, 0.0]] + list(st)
    out = [(st[0][0], 0.0, st[0][1], st[0][2], 0.0, 0.0)]; tv = n = e = 0.0
    for (m0, i0, a0), (m1, i1, a1) in zip(st, st[1:]):
        r0, r1, b0, b1 = map(math.radians, (i0, i1, a0, a1)); dm = m1 - m0
        dl = math.acos(max(-1.0, min(1.0, math.cos(r1 - r0) - math.sin(r0) * math.sin(r1) * (1 - math.cos(b1 - b0)))))
        rf = 1.0 if dl < 1e-9 else 2 / dl * math.tan(dl / 2)
        n += dm / 2 * (math.sin(r0) * math.cos(b0) + math.sin(r1) * math.cos(b1)) * rf
        e += dm / 2 * (math.sin(r0) * math.sin(b0) + math.sin(r1) * math.sin(b1)) * rf
        tv += dm / 2 * (math.cos(r0) + math.cos(r1)) * rf
        out.append((m1, tv, i1, a1, n, e))
    return out


def survey_complete(st):
    """True when the table runs from (near) the surface to the bottom: it starts within 3,000 ft MD at under 5 degrees and has no gap over 600 ft
    once the well is past 10 degrees. Tables that hold only the lateral (the build section is missing) would give wrong TVD and offsets."""
    f = [r for r in st if r[0] > 0] or st
    return bool(f) and f[0][0] <= 3000 and f[0][1] <= 5 and all(not (y[0] - x[0] > 600 and max(x[1], y[1]) > 10) for x, y in zip(f, f[1:]))


STATUS = {"Producing Oil Well": "OIL+ACTIVE", "Producing Gas Well": "GAS+ACTIVE", "Active Injector": "WATER INJ+ACTIVE"}


def well_records(d, prod, perfs, stations=None, kb=None):
    api = d["a"]; u14 = api.replace("-", "") + "0000"; api10 = api.replace("-", "")
    out = ["## ****************** NEW WELLHEADER ******************"]
    nm, no = split_name(d.get("n"))
    iv = [x for p in (perfs or []) for x in p]
    td = int(max(iv)) if iv else (int(float(d["td"])) if d.get("td") else None)    # measured depth: deepest perf (the state depth is vertical)
    r = Rec("WH"); r.put(15, u14)
    r.put(52, (d.get("oc") or d.get("o") or "").upper())
    r.putr(128, nm.upper()); r.putr(148, no.upper())
    if d.get("shl"):
        r.put(151, f"{d['shl'][1]:.6f}"); r.put(160, f"{d['shl'][0]:.6f}")
    r.put(201, STATUS.get(d.get("s"), (d.get("s") or "").upper()))
    r.put(228, "GAS" if d.get("s") == "Producing Gas Well" else "WATER" if d.get("s") == "Active Injector" else "OIL")
    if kb:
        r.putr(246, num(float(kb)))                           # KB from the Form 3 (data/kb.json), where one was found
    if d.get("el"):
        r.putr(262, num(float(d["el"])))                      # state elevation is ground level (matches the sample's GL, not KB)
    if td:
        r.putr(294, td)
    r.put(309, (d.get("r") or "").upper())
    r.put(363, d.get("sd") or ""); r.put(373, d.get("cd") or "")
    r.putr(527, (d.get("f") or "").upper()); r.putr(547, "WY"); r.put(565, (d.get("cty") or "").upper())
    r.put(585, "UNITED STATES"); r.putr(617, "TEMP" + api10); r.put(628, "KB")
    r.putr(783, nm.upper()); r.put(907, api10)
    out.append(str(r))
    out.append(f"## Legal Congress Records (B0) for {u14} :")
    m = re.match(r"(\d+)-(\d+)([NS])-(\d+)([EW])", d.get("sec") or "")
    if m:
        b = Rec("B0"); b.put(15, u14); b.put(33, "Congress")
        b.putr(74, int(m[1])); b.putr(80, int(m[2])); b.put(84, m[3]); b.putr(89, int(m[4])); b.put(93, m[5])
        out.append(str(b))
    out.append(f"## Completions Table Records (CP) for {u14} :")
    if iv:
        c = Rec("CP"); c.put(15, u14); c.put(44, "1"); c.put(57, d.get("cd") or "")
        f = (d.get("r") or "").upper()
        c.put(81, f); c.putr(96, int(min(iv))); c.putr(106, int(max(iv))); c.put(121, f); c.put(141, f[:6])        # the last formation field is 6 wide (cols 141-146)
        out.append(str(c))
    out.append(f"## Formation Table Records (FT) for {u14} :")
    out.append(f"## Survey Dir Table Records (SD) for {u14} :")
    if d.get("bhl"):
        s = Rec("SD"); s.put(15, u14); s.put(54, "Default"); s.put(94, "Minimum Curvature")
        s.put(146, f"{d['bhl'][1]:.6f} {d['bhl'][0]:.6f}")
        out.append(str(s))
    out.append(f"## Survey Station Table Records (ST) for {u14} :")
    for md, tvd, inc, azi, n, e in station_rows(stations) if stations and survey_complete(stations) else []:
        t = Rec("ST"); t.put(15, u14); t.put(34, "Default")
        for end, v, nd in ((83, md, 2), (94, tvd, 2), (102, inc, 1), (110, azi, 1), (120, n, 2), (130, e, 2)):
            t.putr(end, num(round(v, nd)) or "0")
        out.append(str(t))
    out.append(f"## Casing Table Records (MC) for {u14} :")
    out.append(f"## Perforation Records (PF) for {u14} :")
    seen = set()
    for top, bot in sorted((min(p), max(p)) for p in (perfs or []) if len(p) == 2 and p[0] != p[1]):
        if (top, bot) in seen: continue
        seen.add((top, bot))
        f = Rec("PF"); f.put(15, u14); f.putr(44, 1); f.putr(60, len(seen)); f.putr(80, int(top)); f.putr(90, int(bot))
        out.append(str(f))
    for t, name in (("IT", "IP Treatment"), ("IP", "Initial Potential")):
        out.append(f"## {name} Records ({t}) for {u14} :")
    out.append(f"## Production Records (PT) for {u14} :")
    if prod and prod.get("s") and not prod.get("none"):
        y, m0 = map(int, prod["s"].split("-"))
        form = (d.get("r") or "").upper()
        for i in range(len(prod["o"])):
            yy, mm = divmod(y * 12 + m0 - 1 + i, 12)
            p = Rec("PT"); p.put(15, u14); p.put(34, "Default"); p.put(67, form); p.put(75, "Production")
            p.putr(127, prod["o"][i] or 0); p.putr(140, (prod.get("g") or [0] * (i + 1))[i] or 0); p.putr(153, (prod.get("w") or [0] * (i + 1))[i] or 0)
            p.put(219, f"{mm + 1:02d}/01/{yy}"); p.putr(232, 100)
            if i < len(prod.get("d") or []):
                p.putr(236, prod["d"][i])        # days on production (blank where the backfill has not reached the well)
            out.append(str(p))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", nargs="*", help="API numbers, with or without dashes")
    ap.add_argument("--operator"); ap.add_argument("--formation"); ap.add_argument("--all", action="store_true")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    s = open(os.path.join(ROOT, "index.html")).read(); i = s.index("const D=") + 8
    D = json.loads(s[i:s.index(";\nconst GRID", i)])
    P = json.load(open(os.path.join(ROOT, "data", "production.json")))
    LS = json.load(open(os.path.join(ROOT, "data", "lateral_state.json")))
    SS = json.load(open(os.path.join(ROOT, "data", "survey_stations.json")))
    KB = json.load(open(os.path.join(ROOT, "data", "kb.json")))
    norm = lambda x: re.sub(r"\D", "", x)[:10]
    if a.api:
        want = {norm(x) for x in a.api}; wells = [d for d in D if norm(d["a"]) in want]
    elif a.operator or a.formation or a.all:
        wells = [d for d in D if (not a.operator or a.operator.lower() in d["oc"].lower()) and (not a.formation or a.formation.lower() == d["r"].lower())]
    else:
        ap.error("choose --api, --operator/--formation or --all")
    lines = ["## ASCII4 exported from PRB map", "## Exported As EN:", "## Well Records:"]
    for d in wells:
        lines += well_records(d, P.get(d["a"]), LS.get(d["a"]), SS.get(d["a"]), KB.get(d["a"]))
    with open(a.out, "w", encoding="latin1", newline="") as fh:
        fh.write("\r\n".join(lines) + "\r\n")
    print(f"{len(wells)} wells ({sum(1 for d in wells if d['a'] in SS and survey_complete(SS[d['a']]))} with survey stations, {sum(1 for d in wells if d['a'] in SS and not survey_complete(SS[d['a']]))} partial surveys skipped, {sum(1 for d in wells if LS.get(d['a']))} with perforations), {len(lines)} lines -> {a.out}")


if __name__ == "__main__":
    main()
