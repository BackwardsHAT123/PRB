"""eog.py api -> eog_<api>.json: per-stage rows from EOG's own printed 'Completion Report.xlsx' (ave/max rate, ave/max pressure, sand lb, water and slurry bbl)."""
import sys,json,glob,re,statistics as st,pypdfium2 as pdfium
from stagecalc import boxes,val
from orient import best_rotation
from lib import cols_of,colvals
RNG={"press":(3000,13500),"maxpress":(3000,14500),"rate":(30,140),"maxrate":(30,150),"fluid":(3000,40000),"prop":(100000,1500000)}
def page_rows(bx):
    nums,cl=cols_of(bx,tol=16,minn=8)
    D=[(cx,colvals(nums,cx,16)) for cx in cl]
    med=lambda d:st.median(v for _,v in d[1])
    while len(D)>10 and med(D[-1])==0: D=D[:-1]
    if len(D)<9: return None
    m={"maxpress":D[-1],"press":D[-2],"maxrate":D[-3],"rate":D[-4],"fluid":D[-5],"prop":D[-8]}
    if not (30<=med(m["rate"])<=140 and 3000<=med(m["press"])<=13500): return None
    if not (100000<=med(m["prop"])<=1500000): return None
    ys=sorted({y for k in ("press","rate","prop") for y,_ in m[k][1]}); yc=[]
    for y in ys:
        if yc and y-yc[-1][-1]<8: yc[-1].append(y)
        else: yc.append([y])
    rows=[]
    for c in yc:
        y=sum(c)/len(c); r={}
        for k,d in m.items():
            v=[x for yy,x in d[1] if abs(yy-y)<8]; r[k]=v[0] if v else None
        rows.append(r)
    pm=st.median([r["prop"] for r in rows if r["prop"]] or [0])
    rows=[r for r in rows if not (r["prop"] and pm and r["prop"]>4*pm)]
    return rows
def clean(r):
    for k,(lo,hi) in RNG.items():
        v=r.get(k)
        if v is not None and not lo<=v<=hi: r[k]=None
    return r
def run(api):
    best=[]
    for f in sorted(glob.glob(f"wells/{api}/f3_*.pdf")):
        doc=pdfium.PdfDocument(f); txt=json.load(open(f.replace(".pdf",".json")))
        for i in range(len(doc)):
            t=txt[i].lower().replace(" ","") if i<len(txt) else ""
            if not ("additivesamounts" in t or ("propp" in t and "slurry" in t and "ave" in t and "psi" in t) or (i>=2 and 0<len(t)<800 and ("pressure" in t or "psi" in t or "rate" in t))): continue
            r0,_=best_rotation(doc[i]); im=doc[i].render(scale=2.6).to_pil().convert("RGB")
            for rot in dict.fromkeys((r0,0,90,270)):
                rows=page_rows(boxes(im.rotate(rot,expand=True) if rot else im))
                if rows and len(rows)>=8: best.append((i+1,rot,[clean(r) for r in rows])); break
    return best
if __name__=="__main__":
    b=run(sys.argv[1]); json.dump(b,open(f"eog_{sys.argv[1]}.json","w"))
    for p,rot,rows in b: print(sys.argv[1],"page",p,"rot",rot,"rows",len(rows),rows[:2],rows[-1])
