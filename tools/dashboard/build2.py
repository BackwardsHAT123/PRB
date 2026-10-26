import json,math,collections,statistics as st,datetime
import numpy as np
focus=json.load(open("focus_full.json")); other=json.load(open("other_full.json"))
H=(3,6,12)
def add_ft(r):
    for h in H:
        L=r["len"]
        r[f"of{h}"]=round(r[f"o{h}"]/L*1000,1) if r[f"o{h}"] is not None and L else None
        r[f"wf{h}"]=round(r[f"w{h}"]/L*1000,1) if r[f"w{h}"] is not None and L else None
for r in focus+other: add_ft(r)
def med(v):
    v=[x for x in v if x is not None]
    return float(np.median(v)) if v else None
def rnd(x,n=0): return None if x is None else round(x,n)
KEYS=[f"{p}{h}" for h in H for p in ("o","w","of","wf")]
# benchmark: other operators by formation, n>=8 (wells with >=12 months)
bench={}
byf=collections.defaultdict(list)
for r in other: byf[r["fm"]].append(r)
for f,rs in byf.items():
    n12=[r for r in rs if r["o12"] is not None]
    if len(n12)>=8: bench[f]={k:med(r[k] for r in rs) for k in KEYS}; bench[f]["n"]=len(n12)
print("bench formations",{f:b["n"] for f,b in bench.items()})
# well-level index vs bench (same formation), higher = more oil, lower = less water
for r in focus:
    b=bench.get(r["fm"])
    for h in H:
        for p,q in (("o","io"),("w","iw"),("of","iof"),("wf","iwf")):
            v=r[f"{p}{h}"]; bm=b[f"{p}{h}"] if b else None
            r[f"{q}{h}"]=round(v/bm,2) if (v is not None and bm and bm>0) else None
# ---------- wells dataset
WELL_COLS=["api","name","op","fm","field","cty","twp","first","yr","months","len","status","lon","lat"]+KEYS+[f"{q}{h}" for h in H for q in ("io","iw","iof","iwf")]+[f"wor{h}" for h in H]
wells=[{c:r.get(c) for c in WELL_COLS} for r in focus]
json.dump(wells,open("wells.json","w"),separators=(",",":"))
# ---------- groups dataset
def grow(level,op,fm,rs):
    g={"level":level,"op":op,"fm":fm,"n":len(rs),"n12":sum(1 for r in rs if r["o12"] is not None),"len":rnd(med(r["len"] for r in rs)),
       "yr_min":min(r["yr"] for r in rs),"yr_max":max(r["yr"] for r in rs)}
    for h in H:
        for p in ("o","w","of","wf"):
            g[f"{p}{h}"]=rnd(med(r[f"{p}{h}"] for r in rs),1 if "f" in p else 0)
        for q in ("io","iw","iof","iwf"):
            g[f"{q}{h}"]=rnd(med(r[f"{q}{h}"] for r in rs),2)
        wo=[r[f"wor{h}"] for r in rs if r[f"wor{h}"] is not None]
        g[f"wor{h}"]=rnd(float(np.median(wo)),2) if wo else None
    return g
groups=[]
for op in ("Ballard Petroleum","Sage Butte"):
    groups.append(grow("operator",op,None,[r for r in focus if r["op"]==op]))
fms=collections.Counter(r["fm"] for r in focus)
for f,n in fms.items():
    if n>=3: groups.append(grow("formation",None,f,[r for r in focus if r["fm"]==f]))
ofm=collections.Counter((r["op"],r["fm"]) for r in focus)
for (op,f),n in ofm.items():
    if n>=3: groups.append(grow("opfm",op,f,[r for r in focus if r["op"]==op and r["fm"]==f]))
for f,b in bench.items():
    g={"level":"benchmark","op":None,"fm":f,"n":b["n"],"n12":b["n"]}
    for k in KEYS: g[k]=rnd(b[k],1 if "f" in k else 0)
    groups.append(g)
json.dump(groups,open("groups.json","w"),separators=(",",":"))
print("groups",len(groups))
# ---------- curves: median cumulative per month by operator and by op x fm (n>=8 wells with >=12 months)
def curve(label,rs,op,fm):
    out=[]
    for m in range(1,25):
        sel=[r for r in rs if len(r["_oc"])>=m and r["len"]]
        if len(sel)<5: break
        out.append({"series":label,"op":op,"fm":fm,"month":m,"n":len(sel),
          "oil":rnd(med(r["_oc"][m-1] for r in sel)),"water":rnd(med(r["_wc"][m-1] for r in sel)),
          "oil_ft":rnd(med(r["_oc"][m-1]/r["len"]*1000 for r in sel),1),"water_ft":rnd(med(r["_wc"][m-1]/r["len"]*1000 for r in sel),1)})
    return out
curves=[]
for op in ("Ballard Petroleum","Sage Butte"):
    curves+=curve(op,[r for r in focus if r["op"]==op],op,None)
for (op,f),n in ofm.items():
    if n>=8: curves+=curve(f"{op} / {f}",[r for r in focus if r["op"]==op and r["fm"]==f],op,f)
json.dump(curves,open("curves.json","w"),separators=(",",":"))
print("curves rows",len(curves),sorted(set(c['series'] for c in curves)))
# ---------- vintage buckets
def bucket(y): return "2013 and earlier" if y<=2013 else "2014-2015" if y<=2015 else "2016-2019" if y<=2019 else "2020 and later"
vint=[]
for op in ("Ballard Petroleum","Sage Butte"):
    for b in ("2013 and earlier","2014-2015","2016-2019","2020 and later"):
        rs=[r for r in focus if r["op"]==op and bucket(r["yr"])==b]
        if len(rs)>=3:
            vint.append({"op":op,"bucket":b,"n":len(rs),"len":rnd(med(r["len"] for r in rs)),"o12":rnd(med(r["o12"] for r in rs)),"w12":rnd(med(r["w12"] for r in rs)),
                         "of12":rnd(med(r["of12"] for r in rs),1),"wf12":rnd(med(r["wf12"] for r in rs),1),"iof12":rnd(med(r["iof12"] for r in rs),2),"iwf12":rnd(med(r["iwf12"] for r in rs),2)})
json.dump(vint,open("vintage.json","w"),separators=(",",":")); print("vintage",len(vint))
# ---------- area (township-range) table n>=4
tw=collections.defaultdict(list)
for r in focus:
    if r["twp"]: tw[r["twp"]].append(r)
area=[]
for t,rs in tw.items():
    if len(rs)>=4:
        ops=collections.Counter(r["op"] for r in rs)
        fmc=collections.Counter(r["fm"] for r in rs)
        area.append({"twp":t,"n":len(rs),"ballard":ops.get("Ballard Petroleum",0),"sage":ops.get("Sage Butte",0),"top_fm":fmc.most_common(1)[0][0],
          "cty":collections.Counter(r["cty"] for r in rs).most_common(1)[0][0],"len":rnd(med(r["len"] for r in rs)),
          "o12":rnd(med(r["o12"] for r in rs)),"w12":rnd(med(r["w12"] for r in rs)),"of12":rnd(med(r["of12"] for r in rs),1),"wf12":rnd(med(r["wf12"] for r in rs),1),
          "iof12":rnd(med(r["iof12"] for r in rs),2),"iwf12":rnd(med(r["iwf12"] for r in rs),2),
          "lon":rnd(float(np.mean([r["lon"] for r in rs])),4),"lat":rnd(float(np.mean([r["lat"] for r in rs])),4)})
area.sort(key=lambda a:-(a["of12"] or 0))
json.dump(area,open("area.json","w"),separators=(",",":")); print("area",len(area))
# ---------- drivers: adjusted R2 by outcome and factor
def dummies(vals):
    cats=sorted(set(vals)); return np.array([[1.0 if v==c else 0.0 for c in cats[1:]] for v in vals])
def adjr2(y,X):
    X=np.column_stack([np.ones(len(y)),X]); b=np.linalg.lstsq(X,y,rcond=None)[0]
    ss=((y-X@b)**2).sum(); tot=((y-y.mean())**2).sum(); n,p=X.shape
    return max(0.0,1-(ss/(n-p))/(tot/(n-1)))
drivers=[]
for outcome,key,label in (("Oil per 1,000 ft, 12 months","of12","oil"),("Water per 1,000 ft, 12 months","wf12","water"),("Water-oil ratio, 12 months","wor12","wor")):
    rs=[r for r in focus if r.get(key) and r[key]>0 and r["len"]]
    y=np.log10([r[key] for r in rs])
    tw_=collections.Counter(r["twp"] for r in rs)
    area_=[r["twp"] if tw_[r["twp"]]>=4 else "other" for r in rs]
    v=[bucket(r["yr"]) for r in rs]; f=[r["fm"] for r in rs]; o=[r["op"] for r in rs]
    lenx=np.log10([r["len"] for r in rs]).reshape(-1,1)
    F={"Formation":dummies(f),"Area (township and range)":dummies(area_),"Operator":dummies(o),"Year first produced":dummies(v),"Lateral length":lenx}
    for fac,X in F.items():
        drivers.append({"outcome":outcome,"factor":fac,"adj_r2":round(adjr2(y,X),3),"n":len(rs),"kind":"alone"})
    base=np.column_stack([F["Formation"],F["Area (township and range)"],F["Year first produced"],F["Lateral length"]])
    a0=adjr2(y,base); a1=adjr2(y,np.column_stack([base,F["Operator"]]))
    drivers.append({"outcome":outcome,"factor":"Operator, added after formation, area, year and length","adj_r2":round(max(0,a1-a0),3),"n":len(rs),"kind":"added"})
    drivers.append({"outcome":outcome,"factor":"All five together","adj_r2":round(a1,3),"n":len(rs),"kind":"all"})
json.dump(drivers,open("drivers.json","w"),separators=(",",":"))
for d in drivers: print(d["outcome"][:22],d["factor"][:40],d["adj_r2"],d["kind"])
