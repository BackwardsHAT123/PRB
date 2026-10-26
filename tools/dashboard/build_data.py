import json,math,collections,statistics as st
import numpy as np
S=open("index.html").read(); i=S.index("const D=")+8; D=json.loads(S[i:S.index(";\nconst GRID",i)])
P=json.load(open("production.json"))
FOCUS=("Ballard Petroleum","Sage Butte")
def hav(a,b):
    R=20902231; la1,lo1,la2,lo2=map(math.radians,(a[1],a[0],b[1],b[0]))
    x=math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(x))
def plen(ln): return sum(hav(a,b) for a,b in zip(ln,ln[1:])) if ln and len(ln)>1 else None
def metrics(d):
    p=P.get(d["a"])
    if not p or p.get("none"): return None
    o,g,w=p["o"],p["g"],p["w"]; y,m=map(int,p["s"].split("-"))
    k=next((j for j,v in enumerate(o) if v and v>0),None)
    if k is None: return None
    n=len(o)-k; fy=(y*12+m-1+k)//12; fm=(y*12+m-1+k)%12+1
    r={"api":d["a"],"name":d["n"],"op":d["oc"],"fm":d["r"],"field":d["f"],"cty":d["cty"],
       "twp":d["sec"].split("-",1)[1] if d.get("sec") else None,"first":f"{fy}-{fm:02d}","yr":fy,"months":n,
       "len":round(plen(d["ln"])) if plen(d["ln"]) else None,"status":d["s"],"lon":d["shl"][0] if d["shl"] else None,"lat":d["shl"][1] if d["shl"] else None}
    for N in (3,6,12):
        if n>=N:
            oo=sum(o[k:k+N]); ww=sum(w[k:k+N]); gg=sum(g[k:k+N])
            r[f"o{N}"]=round(oo); r[f"w{N}"]=round(ww); r[f"g{N}"]=round(gg)
            r[f"wor{N}"]=round(ww/oo,3) if oo>0 else None
        else: r[f"o{N}"]=r[f"w{N}"]=r[f"g{N}"]=r[f"wor{N}"]=None
    r["o12ft"]=round(r["o12"]/r["len"]*1000,1) if r["o12"] and r["len"] else None
    r["w12ft"]=round(r["w12"]/r["len"]*1000,1) if r["w12"] is not None and r["len"] else None
    # cumulative oil/water by month for first 24 months (for curves)
    r["_oc"]=np.cumsum(o[k:k+24]).tolist() if n>=1 else []
    r["_wc"]=np.cumsum(w[k:k+24]).tolist()
    return r
allr=[x for x in (metrics(d) for d in D) if x]
focus=[r for r in allr if r["op"] in FOCUS]
other=[r for r in allr if r["op"] not in FOCUS]
print(len(allr),len(focus),len(other))
json.dump(focus,open("focus_full.json","w")); json.dump(other,open("other_full.json","w"))
# ---- drivers: adjusted R2 on log10(oil12) 
def adjr2(y,X):
    X=np.column_stack([np.ones(len(y)),X]); b,res,rk,sv=np.linalg.lstsq(X,y,rcond=None)
    pred=X@b; ss=((y-pred)**2).sum(); tot=((y-y.mean())**2).sum(); n,p=X.shape
    return 1-(ss/(n-p))/(tot/(n-1)), p-1
def dummies(vals):
    cats=sorted(set(vals)); return np.array([[1.0 if v==c else 0.0 for c in cats[1:]] for v in vals])
rows=[r for r in focus if r["o12"] and r["o12"]>0 and r["len"]]
y=np.log10([r["o12"] for r in rows])
tw=collections.Counter(r["twp"] for r in rows)
area=[r["twp"] if tw[r["twp"]]>=4 else "other" for r in rows]
vint=[("<=2013" if r["yr"]<=2013 else "2014-15" if r["yr"]<=2015 else "2016-19" if r["yr"]<=2019 else "2020+") for r in rows]
lenf=np.log10([r["len"] for r in rows])
fmv=[r["fm"] for r in rows]; opv=[r["op"] for r in rows]
res={}
for name,X in [("Operator",dummies(opv)),("Formation",dummies(fmv)),("Area (township)",dummies(area)),("Vintage",dummies(vint)),("Lateral length",lenf.reshape(-1,1))]:
    a,k=adjr2(y,X); res[name]=(round(a,3),k); print(name,round(a,3),k)
def comb(*Xs): return np.column_stack(Xs)
base=comb(dummies(fmv),dummies(area),lenf.reshape(-1,1),dummies(vint))
a0,k0=adjr2(y,base); a1,k1=adjr2(y,comb(base,dummies(opv)))
print("base (formation+area+length+vintage)",round(a0,3),"+operator",round(a1,3))
# per-ft
rows2=[r for r in rows if r["o12ft"]]
y2=np.log10([r["o12ft"] for r in rows2])
tw2=collections.Counter(r["twp"] for r in rows2)
area2=[r["twp"] if tw2[r["twp"]]>=4 else "other" for r in rows2]
vint2=[("<=2013" if r["yr"]<=2013 else "2014-15" if r["yr"]<=2015 else "2016-19" if r["yr"]<=2019 else "2020+") for r in rows2]
for name,X in [("Operator",dummies([r["op"] for r in rows2])),("Formation",dummies([r["fm"] for r in rows2])),("Area",dummies(area2)),("Vintage",dummies(vint2))]:
    a,k=adjr2(y2,X); print("per-ft",name,round(a,3),k)
print("area counts",collections.Counter(area).most_common(15))
