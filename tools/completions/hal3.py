"""hal3.py api -> per-stage rows from the older Halliburton 'Stage Summary' spreadsheet page (landscape; one row per interval).
Columns left to right: Interval | Average Pressure, Rate, Visc, Temp, pH | Max Pressure, Rate | fluid pairs (gal, bbl) per fluid | Total Fluid (gal, bbl) | proppant lbs per type | Total Proppant.
The fluid pair with the largest volumes is Total Fluid (gal and bbl differ by a factor of 42); the last column is Total Proppant.
Output {stage: {press, rate, maxpress, maxrate, fluid (bbl), prop (lb)}}."""
import sys,json,glob,re,statistics as st,pypdfium2 as pdfium
from stagecalc import boxes,val
from orient import best_rotation
api=sys.argv[1]; out=f"hal3_{api}.json"; res={}
def parse(bx):
    nums=[((b[0]+b[2])/2,(b[1]+b[3])/2,val(b[4])) for b in bx if val(b[4]) is not None]
    if len(nums)<60: return None
    xs=sorted(n[0] for n in nums); cl=[]
    for x in xs:
        if cl and x-cl[-1][-1]<14: cl[-1].append(x)
        else: cl.append([x])
    cols=[sum(c)/len(c) for c in cl if len(c)>=6]
    if len(cols)<12: return None
    cellsby=[]
    for cx in cols:
        cellsby.append(sorted((y,v) for x,y,v in nums if abs(x-cx)<10))
    # the stage-number column is small print that OCR often misses, so rows come from the data columns: the interval rows form the first
    # evenly spaced block; the Planned / Recorded summary rows sit below a larger gap
    big=max(cellsby,key=len); ys=sorted(y for y,_ in big)
    gaps=[b-a for a,b in zip(ys,ys[1:])]; med=st.median(gaps)
    cut=next((i+1 for i,g in enumerate(gaps) if g>2.2*med),len(ys))
    ys=ys[:cut]; n=len(ys)
    if n<3: return None
    ytol=med*0.45
    colvals=[]
    for c in cellsby:
        d={}
        for y,v in c:
            j=min(range(n),key=lambda i:abs(ys[i]-y))
            if abs(ys[j]-y)<ytol: d[j+1]=v
        colvals.append(d)
    ic=-1
    data=colvals[ic+1:]
    ok=[d for d in data if len(d)>=max(4,n*0.6)]
    if len(ok)<8: return None
    press,rate=ok[0],ok[1]
    mx=[d for d in ok if True]
    # max pressure / max rate: the columns after pH (pH column is values ~9-12 with a decimal)
    ph=next((i for i,d in enumerate(ok) if i>=2 and 5<=st.median(d.values())<=13 and any(abs(v-round(v))>1e-9 for v in d.values())),None)
    maxp=ok[ph+1] if ph is not None and ph+1<len(ok) else None
    maxr=ok[ph+2] if ph is not None and ph+2<len(ok) else None
    # total fluid: adjacent pair with ratio 42 and the largest volumes
    best=None
    for i in range(len(ok)-1):
        a,b=ok[i],ok[i+1]; common=[k for k in a if k in b and b[k]]
        if len(common)>=max(4,n*0.6) and sum(1 for k in common if abs(a[k]/b[k]-42)<2.1)>=0.6*len(common):      # OCR drops a digit now and then, so most rows must fit
            best=(0,i)       # keep the right-most pair: Total Fluid sits just before the proppant columns
    fluid=None
    if best:
        ga,bb=ok[best[1]],ok[best[1]+1]; fluid={}
        for k in set(ga)|set(bb):       # barrels = gallons / 42: take the value the two columns agree on, else the one that fits the neighbouring stages
            c=[]
            if k in bb: c.append(bb[k])
            if k in ga: c.append(ga[k]/42)
            if len(c)==2 and abs(c[0]-c[1])<0.03*c[1]: fluid[k]=c[0]
            elif c: fluid[k]=c
        med=st.median(v if not isinstance(v,list) else v[0] for v in fluid.values())
        fluid={k:(v if not isinstance(v,list) else min(v,key=lambda x:abs(x-med))) for k,v in fluid.items()}
    prop=ok[-1]
    def clean(d,tol=0.35):      # blank values far from the median (a misread digit)
        if not d: return d
        m=st.median(d.values()); return {k:v for k,v in d.items() if abs(v-m)<=tol*m}
    prop=clean(prop); fluid=clean(fluid) if fluid else fluid
    for d in (press,rate,maxp,maxr):
        if d: d.update(clean(d,0.3)); [d.pop(k) for k in [k for k in d if k not in clean(d,0.3)]]
    rows={}
    for k in range(1,n+1):
        r={}
        if k in press: r["press"]=press[k]
        if k in rate: r["rate"]=rate[k]
        if maxp and k in maxp: r["maxpress"]=maxp[k]
        if maxr and k in maxr: r["maxrate"]=maxr[k]
        if fluid and k in fluid: r["fluid"]=fluid[k]
        if k in prop: r["prop"]=prop[k]
        rows[k]=r
    keys=sorted(rows); lead=0
    while lead<len(keys) and len(rows[keys[lead]])<3: lead+=1          # a header or units row read as an interval
    return {i+1:rows[k] for i,k in enumerate(keys[lead:])}
def pages_for(txt):
    key=[i for i,t in enumerate(txt) if any(k in (t or "").lower().replace(" ","") for k in ("stagesummary","wellsummary"))]
    short=[i for i,t in enumerate(txt) if len((t or ""))<1200 and i not in key]      # scanned pages whose OCR text is too poor to name the page
    return key+short[::-1]
for f in sorted(glob.glob(f"wells/{api}/f3_*.pdf")):
    doc=pdfium.PdfDocument(f); txt=json.load(open(f.replace(".pdf",".json")))
    for i in pages_for(txt)[:6]:
        if i>=len(doc): continue
        r,_=best_rotation(doc[i]); im=doc[i].render(scale=3.0).to_pil().convert("RGB")
        if r: im=im.rotate(r,expand=True)
        rows=parse(boxes(im))
        if rows and len(rows)>=3: res=rows; break
    if res: break
json.dump({str(k):v for k,v in res.items()},open(out,"w")); print(api,len(res),"stages")
