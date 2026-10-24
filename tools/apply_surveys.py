"""Apply accepted survey paths from survey_out.jsonl (and survey_stations.jsonl) to the repo copy and the local map.
   python3 apply_surveys.py [--include-adjusted]
   fx 8 = path from the filed directional survey; fx 9 = same, shifted to end on the header bottom hole."""
import json,sys,os,collections
INCL_ADJ="--include-adjusted" in sys.argv
R={}
for l in open("survey_out.jsonl"):
    r=json.loads(l); R[r["api"]]=r
S={}
for l in open("survey_stations.jsonl"):
    r=json.loads(l); S[r["api"]]=r
def risky(api):   # a big depth gap inside the curve/lateral makes the path shape unreliable
    st=(S.get(api) or {}).get("st") or []
    return any(b[0]-a[0]>1200 and min(a[1],b[1])>15 for a,b in zip(st,st[1:]))
POP_OLD="d.fx==7?"
POP_NEW="d.fx==9?'<br><b>Path: from the filed directional survey, adjusted to the header bottom hole</b>':d.fx==8?'<br><b>Path: from the filed directional survey (simplified)</b>':d.fx==7?"
ovp="prb/data/overrides.json"; ov=json.load(open(ovp))
def patch(path,store):
    s=open(path).read(); i=s.index("const D=")+8; j=s.index(";\nconst GRID",i); D=json.loads(s[i:j]); n=collections.Counter()
    for d in D:
        r=R.get(d["a"])
        if not r or r["status"]!="ok" or d.get("fx") or len(d["ln"])>2: continue
        if risky(d["a"]): n["skipped (depth gap in lateral)"]+=1; continue
        if r.get("warp") and not INCL_ADJ: n["held (adjusted)"]+=1; continue
        fx=9 if r.get("warp") else 8
        d["ln"]=r["path"]; d["surv"]=True; d["fx"]=fx; n[f"applied fx{fx}"]+=1
        if store is not None: store[d["a"]]={"ln":r["path"],"fx":fx}
    if POP_NEW not in s:
        assert s.count(POP_OLD)==1; s=s.replace(POP_OLD,POP_NEW)
    open(path,"w").write(s[:i]+json.dumps(D,separators=(",",":"))+s[j:]); return dict(n)
print("repo :",patch("prb/index.html",ov)); json.dump(ov,open(ovp,"w"),indent=1)
print("local:",patch("/Users/tom/Documents/Claude Projects/campbell_wy_laterals/map_streetmap.html",None))
