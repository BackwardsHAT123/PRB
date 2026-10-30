"""Write data/survey_summary.json: for every well with survey stations, [number of stations, 1 if the survey is complete else 0].

    python3 tools/surveys/build_summary.py

The map popup reads this small file (the full data/survey_stations.json is about 4 MB). Rerun it, and push the result, whenever data/survey_stations.json changes.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "geographix"))
from export_ascii4 import survey_complete

SS = json.load(open(os.path.join(ROOT, "data", "survey_stations.json")))
out = {api: [len(st), 1 if survey_complete(st) else 0] for api, st in sorted(SS.items()) if st}
json.dump(out, open(os.path.join(ROOT, "data", "survey_summary.json"), "w"), separators=(",", ":"))
print(len(out), "wells,", sum(v[1] for v in out.values()), "complete ->", "data/survey_summary.json")
