#!/usr/bin/env python3
"""Generate tools/SURVEY_COVERAGE.md (computed, never hand-edited) and data/survey_review.json.

    python3 tools/survey_coverage.py

Coverage comes from the wells in index.html: fx 7 = filed certification form, 8/9/17 = filed directional survey,
6 = operator design / permit plat, 10-16 = point fixes, 0 = state track or straight line.
Review state per well is stored in data/survey_review.json:
    applied  = a survey path is on the map (fx 8, 9, 17)
    tried    = the reader has been run on the well (it is in survey_summary.json) but no survey path was applied
    untried  = still on a straight line / state track and never read   <- the to-do list
`first_seen` is kept from the previous run, so a new "untried" well shows how long it has waited.
"""
import collections, datetime, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SURVEYED = {8, 9, 17}


def load_wells():
    s = open(os.path.join(ROOT, "index.html")).read()
    i = s.index("const D=") + 8
    return json.loads(s[i:s.index(";\nconst GRID", i)])


def source(w):
    fx = w.get("fx", 0)
    if fx in SURVEYED:
        return "survey"
    if fx == 7:
        return "cert form"
    if fx == 6:
        return "design/plat"
    if w.get("surv"):
        return "state track"
    return "straight"


def main():
    wells = load_wells()
    today = datetime.date.today().isoformat()
    sf = os.path.join(ROOT, "data", "survey_summary.json")
    tried = set(json.load(open(sf))) if os.path.exists(sf) else set()
    rf = os.path.join(ROOT, "data", "survey_review.json")
    old = json.load(open(rf)) if os.path.exists(rf) else {}
    rev = {}
    for w in wells:
        a = w["a"]
        st = "applied" if w.get("fx", 0) in SURVEYED else "tried" if a in tried else "untried"
        prev = old.get(a, {})
        rev[a] = {"status": st, "since": prev.get("since") if prev.get("status") == st else today,
                  "first_seen": prev.get("first_seen", today)}
    json.dump(rev, open(rf, "w"), separators=(",", ":"), sort_keys=True)

    cols = ["survey", "cert form", "design/plat", "state track", "straight"]
    by = collections.defaultdict(collections.Counter)
    for w in wells:
        by[(w.get("cty") or "?", w.get("oc") or w.get("o") or "?")][source(w)] += 1
    out = [f"# PRB survey coverage (generated {today} by tools/survey_coverage.py)", "",
           f"{len(wells)} wells on the map. Do not edit by hand; narrative history is in SURVEY_STATUS.md.", "",
           "## All wells by source", "", "| Source | Wells | Share |", "|---|---|---|"]
    tot = collections.Counter(source(w) for w in wells)
    for c in cols:
        out.append(f"| {c} | {tot[c]} | {tot[c] / len(wells):.0%} |")
    for cty in sorted({k[0] for k in by}):
        out += ["", f"## {cty}", "", "| Operator | " + " | ".join(cols) + " | total | % surveyed |", "|---|" + "---|" * (len(cols) + 2)]
        rows = sorted(((k[1], c) for k, c in by.items() if k[0] == cty), key=lambda r: -sum(r[1].values()))
        for op, c in rows:
            n = sum(c.values())
            out.append(f"| {op} | " + " | ".join(str(c[x]) for x in cols) + f" | {n} | {c['survey'] / n:.0%} |")
    un = collections.Counter((w.get("cty"), w.get("oc") or w.get("o")) for w in wells
                             if rev[w["a"]]["status"] == "untried" and source(w) in ("straight", "state track") and "Permit" not in (w.get("s") or ""))
    out += ["", "## Never read (straight line or state track, not permits)", "", f"{sum(un.values())} wells; largest groups:", ""]
    out += [f"* {c} / {o}: {n}" for (c, o), n in un.most_common(12)]
    open(os.path.join(ROOT, "tools", "SURVEY_COVERAGE.md"), "w").write("\n".join(out) + "\n")
    print("wrote tools/SURVEY_COVERAGE.md and data/survey_review.json;", dict(collections.Counter(r["status"] for r in rev.values())))


if __name__ == "__main__":
    main()
