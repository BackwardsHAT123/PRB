"""Gather every filed directional survey (MD, inclination, azimuth per station) into data/survey_stations.json.
Reads the survey_stations*.jsonl files from the survey work folders; the longest table wins when a well appears more than once.
    python3 tools/geographix/collect_stations.py <jsonl> [<jsonl> ...]
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
best = {}
for f in sys.argv[1:]:
    for l in open(f):
        if not l.strip(): continue
        r = json.loads(l); st = {}
        for md, inc, azi in r["st"]: st[md] = [md, inc, azi]
        st = [st[k] for k in sorted(st)]
        if len(st) >= 2 and (r["api"] not in best or len(st) > len(best[r["api"]])): best[r["api"]] = st
json.dump(best, open(os.path.join(ROOT, "data", "survey_stations.json"), "w"), separators=(",", ":"))
print(len(best), "wells,", sum(map(len, best.values())), "stations")
