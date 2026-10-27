"""stagecalc.py api -> prints per-stage derived averages. Spatial table parse of candidate pages."""
import sys,json,glob,re,statistics as st,numpy as np,pypdfium2 as pdfium
from rapidocr_onnxruntime import RapidOCR
ocr=RapidOCR()
KEYS={"isip":[r"isip"],"press":[r"avg.{0,12}(treat|press)",r"average.{0,12}(treat|press)",r"treating pressure"],"rate":[r"avg.{0,8}(rate|slurry)",r"average.{0,8}(rate|slurry)"],"fg":[r"f\.?g\b|frac.{0,3}grad|fracture grad"]}
RANGE={"isip":(2500,9500),"press":(5000,13500),"rate":(30,140),"fg":(0.6,1.3)}
num=re.compile(r"^-?\d[\d,]*\.?\d*$")
def val(t):
    t=t.strip().replace(" ","")
    if not num.match(t): return None
    try:return float(t.replace(",",""))
    except:return None
def boxes(im):
    res,_=ocr(np.array(im)); out=[]
    for b,t,c in res or []:
        xs=[p[0] for p in b];ys=[p[1] for p in b]; out.append((min(xs),min(ys),max(xs),max(ys),t))
    return out
def colparse(bx):
    nb=[(b,val(b[4])) for b in bx if val(b[4]) is not None]
    nb.sort(key=lambda t:(t[0][0]+t[0][2])/2); cols=[]
    for b,v in nb:
        cx=(b[0]+b[2])/2
        if cols and abs(cx-cols[-1]["cx"])<(b[2]-b[0])*0.5+8: cols[-1]["v"].append(v); cols[-1]["cx"]=(cols[-1]["cx"]*(len(cols[-1]["v"])-1)+cx)/len(cols[-1]["v"])
        else: cols.append({"cx":cx,"v":[v]})
    cols=[c for c in cols if len(c["v"])>=8]
    head=" ".join(b[4].lower().replace(" ","") for b in sorted(bx,key=lambda b:(b[1]//40,b[0])) if val(b[4]) is None)
    order=[k for _,k in sorted((m.start(),k) for k,p in {"isip":"isip","press":"avgpress|avgtreat|treatingpress|avgpressure","rate":"avgrate|averagerate|avgslurry"}.items() for m in re.finditer(p,head))]
    seen=[];[seen.append(k) for k in order if k not in seen]
    data=[c for c in cols if 20<=st.median(c["v"])<=20000 and not (all(float(x).is_integer() and x<200 for x in c["v"]))]
    data=[c for c in data if st.median(c["v"])<50000]
    out={}
    if len(seen)>=2:
        # drop fluid-like trailing cols beyond named ones
        for k,c in zip(seen,data):
            lo,hi=RANGE[k]; out[k]=[x for x in c["v"] if lo<=x<=hi]
    return {k:v for k,v in out.items() if len(v)>=8}
def analyze(bx):
    g=colparse(bx)
    if len(g)>=2: return g
    return analyze2(bx)
def analyze2(bx):
    got={}
    for k,pats in KEYS.items():
        labs=[b for b in bx if any(re.search(p,b[4].lower()) for p in pats) and val(b[4]) is None]
        best=[]
        for L in labs:
            h=L[3]-L[1]; cy=(L[1]+L[3])/2; cx=(L[0]+L[2])/2; w=max(L[2]-L[0],60)
            row=[val(b[4]) for b in bx if b[0]>L[2]-5 and abs((b[1]+b[3])/2-cy)<h*0.45 and val(b[4]) is not None]
            col=[val(b[4]) for b in bx if b[1]>L[3] and abs((b[0]+b[2])/2-cx)<w*0.35 and val(b[4]) is not None]
            for v in (row,col):
                lo,hi=RANGE[k]; v=[x for x in v if lo<=x<=hi]
                if len(v)>len(best): best=v
        if len(best)>=8: got[k]=best
    return got
if __name__=="__main__":
    api=sys.argv[1]; res={}
    for f in sorted(glob.glob(f"wells/{api}/f3_*.pdf")):
        txt=json.load(open(f.replace(".pdf",".json"))); doc=pdfium.PdfDocument(f)
        for i,t in enumerate(txt):
            tl=t.lower()
            if not ("isip" in tl or "treating pressure" in tl or "avg" in tl and "press" in tl): continue
            im=doc[i].render(scale=2.2).to_pil().convert("RGB")
            for rot in (0,90,270):
                g=analyze(boxes(im.rotate(rot,expand=True) if rot else im))
                if len(g)>=2 or ("isip" in g):
                    res[f"{f}:{i+1}:{rot}"]={k:(len(v),round(st.mean(v),3 if k=='fg' else 1),round(st.median(v),3 if k=='fg' else 1)) for k,v in g.items()}; break
    print(api,json.dumps(res,indent=0))
