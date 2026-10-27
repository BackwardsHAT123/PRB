"""lib.py api -> per-stage rows from Liberty 'Pressure Summary' (A) and 'Frac Summary, by Stage' (B) tables, any page rotation."""
import sys,json,glob,re,statistics as st,pypdfium2 as pdfium
from stagecalc import boxes,val
from orient import best_rotation
def cols_of(bx,tol=16,minn=8):
    nums=[((b[0]+b[2])/2,(b[1]+b[3])/2,val(b[4])) for b in bx if val(b[4]) is not None]
    xs=sorted(x for x,_,_ in nums); cl=[]
    for x in xs:
        if cl and x-cl[-1][-1]<tol: cl[-1].append(x)
        else: cl.append([x])
    cl=[sum(c)/len(c) for c in cl if len(c)>=minn]
    return nums,cl
def colvals(nums,cx,tol=16): return sorted((y,v) for x,y,v in nums if abs(x-cx)<tol)
def build(nums,cl):
    data=[(cx,colvals(nums,cx)) for cx in cl]
    rest=data
    med=lambda d:st.median(v for _,v in d[1])
    dec=lambda d:sum(1 for _,v in d[1] if abs(v-round(v))>1e-9)/len(d[1])
    ratec=[d for d in rest if 30<=med(d)<=140 and dec(d)>0.5]
    fgc=[d for d in rest if 0.7<=med(d)<=1.2 and dec(d)>0.8]
    out={}
    if fgc and len(ratec)>=2:   # A: Pressure Summary
        rate=ratec[1]; i=rest.index(rate); press=rest[i-1]
        fg=fgc[-1]; j=rest.index(fg); isip=rest[j-2]
        m={"press":press,"rate":rate,"isip":isip,"fg":fg}
    elif len(ratec)>=1:         # B: Frac summary by stage
        rate=ratec[0]; i=rest.index(rate)
        if i<2: return None
        m={"rate":rate,"press":rest[i-1],"isip":rest[i-2],"fluid":rest[i-3] if i>=3 else None}
        pc=[d for d in rest[i+1:] if 100000<=med(d)<=1500000]
        if pc: m["prop"]=pc[-1] if len(pc)>=1 else None
    else: return None
    ys=sorted({y for k in ("press","isip","rate") for yy in [m[k][1]] for y,_ in yy})
    yc=[]
    for y in ys:
        if yc and y-yc[-1][-1]<9: yc[-1].append(y)
        else: yc.append([y])
    base=1 if "fg" in m and len(ratec)>=2 else 0
    rows=[]
    for k,c in enumerate(yc):
        y=sum(c)/len(c); r={"n":base+len(rows)}
        for kk,d in m.items():
            if d is None: continue
            v=[val_ for yy,val_ in d[1] if abs(yy-y)<9]; r[kk]=v[0] if v else None
        rows.append(r)
    return rows
RNG={"isip":(2500,9500),"press":(5000,13500),"rate":(30,140),"fg":(0.7,1.2),"fluid":(3000,40000),"prop":(100000,1500000)}
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
            t=txt[i].lower() if i<len(txt) else ""
            if i<len(txt) and not any(k in t for k in ("isip","pressure summary","frac summary")): continue
            im=doc[i].render(scale=2.4).to_pil().convert("RGB")
            r0,_s=best_rotation(doc[i])
            for rot in dict.fromkeys((r0,0,90,270,180)):
                nums,cl=cols_of(boxes(im.rotate(rot,expand=True) if rot else im))
                rows=build(nums,cl) if len(cl)>=6 else None
                if rows and len(rows)>=8:
                    rows=[clean(r) for r in rows]
                    ok=sum(1 for r in rows if r.get("isip") and r.get("press"))
                    if ok>=8: best.append((i+1,rot,rows)); break
    return best
if __name__=="__main__":
    b=run(sys.argv[1]); json.dump(b,open(f"lib_{sys.argv[1]}.json","w"))
    for p,rot,rows in b: print(sys.argv[1],"page",p,"rot",rot,"rows",len(rows),rows[:2])
