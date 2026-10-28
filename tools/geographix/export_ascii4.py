"""Export PRB wells and monthly production as a GeoGraphix ASCII4 (.WB4) file.

    python3 tools/geographix/export_ascii4.py --api 49-005-61788 49-005-63118 -o test.WB4
    python3 tools/geographix/export_ascii4.py --operator Ballard --formation Turner -o ballard_turner.WB4
    python3 tools/geographix/export_ascii4.py --all -o prb_all.WB4

Reads index.html (wells), data/production.json (monthly oil/gas/water) and data/lateral_state.json (state producing
intervals). The layout was worked out from a Drillinginfo export (Powder Test GeoGraphix ASCII4.WB4): fixed-width records,
CRLF line ends, a two-letter record type in columns 1-2 and the 14-digit UWI in columns 15-28. See tools/geographix/ASCII4_FORMAT.md.
Written records: WH (well header), B0 (legal), CP (completion), SD (survey header), PT (production). The other record types
(FT tops, ST stations, MC casing, PF perforations, IT/IP initial potential) are left out; their section comments are kept.
"""
import argparse, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEN = {"WH": 988, "B0": 397, "CP": 146, "SD": 327, "PT": 237}       # record lengths seen in the sample


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


STATUS = {"Producing Oil Well": "OIL+ACTIVE", "Producing Gas Well": "GAS+ACTIVE"}


def well_records(d, prod, perfs):
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
    r.put(228, "GAS" if d.get("s") == "Producing Gas Well" else "OIL")
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
        c.put(81, f); c.putr(96, int(min(iv))); c.putr(106, int(max(iv))); c.put(121, f); c.put(141, f)
        out.append(str(c))
    out.append(f"## Formation Table Records (FT) for {u14} :")
    out.append(f"## Survey Dir Table Records (SD) for {u14} :")
    if d.get("bhl"):
        s = Rec("SD"); s.put(15, u14); s.put(54, "Default"); s.put(94, "Minimum Curvature")
        s.put(146, f"{d['bhl'][1]:.6f} {d['bhl'][0]:.6f}")
        out.append(str(s))
    for t, name in (("ST", "Survey Station Table"), ("MC", "Casing Table"), ("PF", "Perforation"), ("IT", "IP Treatment"), ("IP", "Initial Potential")):
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
                p.putr(236, prod["d"][i])        # days on production: stored for the first 8 months only
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
    norm = lambda x: re.sub(r"\D", "", x)[:10]
    if a.api:
        want = {norm(x) for x in a.api}; wells = [d for d in D if norm(d["a"]) in want]
    elif a.operator or a.formation or a.all:
        wells = [d for d in D if (not a.operator or a.operator.lower() in d["oc"].lower()) and (not a.formation or a.formation.lower() == d["r"].lower())]
    else:
        ap.error("choose --api, --operator/--formation or --all")
    lines = ["## ASCII4 exported from PRB map", "## Exported As EN:", "## Well Records:"]
    for d in wells:
        lines += well_records(d, P.get(d["a"]), LS.get(d["a"]))
    with open(a.out, "w", encoding="latin1", newline="") as fh:
        fh.write("\r\n".join(lines) + "\r\n")
    print(f"{len(wells)} wells, {len(lines)} lines -> {a.out}")


if __name__ == "__main__":
    main()
