#!/usr/bin/env python3
"""Sanity checks on the well list before it is published.

    python3 tools/validate.py            check the wells currently in index.html
    (update.py also calls validate() before writing index.html, and refuses to push on errors)

Errors block a push. Warnings are printed and counted but never block.
"""
import collections, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COUNTY_BOX = {"Campbell": (43.15, 45.05, -106.45, -104.85), "Converse": (42.65, 43.65, -106.15, -104.8),
              "Johnson": (43.25, 44.75, -107.1, -105.85)}
MAX_DROP = 0.05          # more than 5% fewer wells than the last published map is treated as a bad pull


def validate(wells, previous_count=None, production=None):
    errors, warns = [], []
    seen = collections.Counter(w["a"] for w in wells)
    dups = [a for a, n in seen.items() if n > 1]
    if dups:
        errors.append(f"{len(dups)} duplicate API numbers, e.g. {dups[:3]}")
    if previous_count and len(wells) < previous_count * (1 - MAX_DROP):
        errors.append(f"well count fell from {previous_count} to {len(wells)} (more than {MAX_DROP:.0%})")
    bad_shl, bad_box, no_line, straight, hp_missing = [], [], [], collections.Counter(), []
    for w in wells:
        shl, ln, a = w.get("shl"), w.get("ln"), w["a"]
        if not shl or None in shl:
            bad_shl.append(a)
            continue
        box = COUNTY_BOX.get(w.get("cty"))
        if box and not (box[0] < shl[1] < box[1] and box[2] < shl[0] < box[3]):
            bad_box.append(a)
        if not ln:
            no_line.append(a)
        elif len(ln) <= 2 and not w.get("surv") and "Permit" not in (w.get("s") or "") and w.get("s") != "Proposed (APD)":
            straight[w.get("oc") or w.get("o") or "?"] += 1
        if w.get("bhl") and ln and len(ln) > 2 and w.get("surv"):
            e = ln[-1]
            if abs(e[0] - w["bhl"][0]) > 0.02 or abs(e[1] - w["bhl"][1]) > 0.02:     # ~1.6 km: path ends nowhere near its bottom hole
                warns.append(f"{a} path ends far from its bottom hole")
    if bad_shl:
        errors.append(f"{len(bad_shl)} wells with no surface location, e.g. {bad_shl[:3]}")
    if bad_box:
        errors.append(f"{len(bad_box)} wells with surface hole outside their county, e.g. {bad_box[:3]}")
    if no_line:
        warns.append(f"{len(no_line)} wells with no path at all (no BHL), e.g. {no_line[:3]}")
    if straight:
        warns.append(f"{sum(straight.values())} producing/completed wells still on a straight SHL-BHL line: "
                     + ", ".join(f"{k} {v}" for k, v in straight.most_common(6)))
    if production is not None:
        for w in wells:
            p = production.get(w["a"])
            if w.get("hp") and p and not p.get("none"):
                o, d = p.get("o", []), p.get("d", [])
                if d and len(d) != len(o):
                    warns.append(f"{w['a']} production months/days length mismatch")
                    break
        stale = [k for k, p in production.items() if p.get("u") and str(p["u"]) < "2000"]
        if stale:
            warns.append(f"{len(stale)} production records with a bad update date")
    return errors, warns


def main():
    import sys as _sys; _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import wellsio
    s = wellsio.read_index(os.path.join(ROOT, "index.html"))
    i = s.index("const D=") + 8
    wells = json.loads(s[i:s.index(";\nconst GRID", i)])
    pf = os.path.join(ROOT, "data", "production.json")
    prod = json.load(open(pf)) if os.path.exists(pf) else None
    errors, warns = validate(wells, production=prod)
    print(f"{len(wells)} wells checked")
    for m in warns:
        print("WARN ", m)
    for m in errors:
        print("ERROR", m)
    print("OK" if not errors else "FAILED")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
