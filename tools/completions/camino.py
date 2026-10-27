"""camino.py api -> camino_<api>.json: per-stage rows from the Camino/RIMBase 'Stimulation Job Report' (Halliburton jobs for WRC): n,fg,press(avg),maxpress,rate(avg),isip,fluid,prop."""
import sys,json,glob,re,statistics as st,pypdfium2 as pdfium
from stagecalc import boxes,val
from orient import best_rotation
from lib import cols_of,colvals
RNG={"isip":(2500,9500),"press":(5000,13500),"maxpress":(5000,14000),"rate":(30,140),"fg":(0.7,1.3),"fluid":(3000,40000),"prop":(100000,1500000)}
def page_rows(bx):
    nums,cl=cols_of(bx,tol=18,minn=8)
    D=[(cx,colvals(nums,cx,18)) for cx in cl]
    med=lambda d:st.median(v for _,v in d[1])
    dec=lambda d:sum(1 for _,v in d[1] if abs(v-round(v))>1e-9)/len(d[1])
    fgs=[i for i,d in enumerate(D) if 0.7<=med(d)<=1.3 and dec(d)>0.8]
    if not fgs or fgs[0]+9>=len(D): return None
    j=fgs[0]; m={"fg":D[j],"maxpress":D[j+2],"press":D[j+3],"rate":D[j+4],"isip":D[j+6],"fluid":D[j+8],"prop":D[j+9]}
    if not (30<=med(m["rate"])<=140): return None
    stage=D[j-2] if j>=2 else None
    ys=sorted({y for k in ("press","rate","isip") for y,_ in m[k][1]}); yc=[]
    for y in ys:
        if yc and y-yc[-1][-1]<8: yc[-1].append(y)
        else: yc.append([y])
    rows=[]
    for c in yc:
        y=sum(c)/len(c); r={}
        for k,d in m.items():
            v=[x for yy,x in d[1] if abs(yy-y)<8]; r[k]=v[0] if v else None
        if stage:
            v=[x for yy,x in stage[1] if abs(yy-y)<8]; r["n"]=int(v[0]) if v and float(v[0]).is_integer() else None
        rows.append(r)
    return rows
def clean(r):
    for k,(lo,hi) in RNG.items():
        v=r.get(k)
        if v is not None and not lo<=v<=hi:
            v2=v*1000 if k in("isip","press","maxpress") and v<100 else None
            r[k]=v2 if v2 is not None and lo<=v2<=hi else None
    return r
def run(api):
    best=[]
    for f in sorted(glob.glob(f"wells/{api}/f3_*.pdf")):
        doc=pdfium.PdfDocument(f); txt=json.load(open(f.replace(".pdf",".json")))
        for i in range(len(doc)):
            t=txt[i].lower().replace(" ","") if i<len(txt) else ""
            if "stimulationjobreport" not in t: continue
            r0,_=best_rotation(doc[i]); im=doc[i].render(scale=2.6).to_pil().convert("RGB")
            for rot in dict.fromkeys((r0,0)):
                rows=page_rows(boxes(im.rotate(rot,expand=True) if rot else im))
                if rows and len(rows)>=8: best.append((i+1,rot,[clean(r) for r in rows])); break
    return best
if __name__=="__main__":
    b=run(sys.argv[1]); json.dump(b,open(f"camino_{sys.argv[1]}.json","w"))
    for p,rot,rows in b: print(sys.argv[1],"page",p,"rot",rot,"rows",len(rows),rows[:2],rows[-1])
