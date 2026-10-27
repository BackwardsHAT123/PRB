"""hal2.py api -> per-stage rows from Halliburton 'Stage Summary' (stages in columns; continuation pages have no labels)."""
import sys,json,glob,re,statistics as st,pypdfium2 as pdfium
from stagecalc import boxes,val
from orient import best_rotation
LAB={"press":r"avg\s*treating\s*press","rate":r"average\s*rate","isip":r"final\s*isip","fg":r"final\s*f\.?\s*g","tvd":r"true\s*vertical","fluid":r"^tota.{0,2}\s*volume","prop":r"(stage|suge|stape|suare|stag).{0,3}tota|^total\s*\(lbm","m100":r"^100\s*mesh","m4070":r"^40.{0,2}70\s*white"}
def rowcl(ys,tol=9):
    ys=sorted(ys); out=[]
    for y in ys:
        if out and y-out[-1][-1]<tol: out[-1].append(y)
        else: out.append([y])
    return [sum(c)/len(c) for c in out]
def grid(bx):
    nums=[((b[0]+b[2])/2,(b[1]+b[3])/2,val(b[4]),b[2]-b[0]) for b in bx if val(b[4]) is not None]
    if len(nums)<60: return None
    xs=sorted(x for x,_,_,_ in nums); cols=[]
    for x in xs:
        if cols and x-cols[-1][-1]<35: cols[-1].append(x)
        else: cols.append([x])
    cols=[sum(c)/len(c) for c in cols if len(c)>=15]
    if len(cols)<3: return None
    # drop label-side column if spacing irregular: keep columns with regular spacing
    sp=st.median(b-a for a,b in zip(cols,cols[1:]))
    cols=[c for c in cols if True]
    rows=rowcl([y for _,y,_,_ in nums],tol=7)
    rows=[r for r in rows if sum(1 for x,y,_,_ in nums if abs(y-r)<9)>=max(3,len(cols)//2)]
    g={}
    for ci,cx in enumerate(cols):
        for x,y,v,w in nums:
            if abs(x-cx)<sp*0.4:
                ri=min(range(len(rows)),key=lambda i:abs(rows[i]-y)) if rows else None
                if ri is not None and abs(rows[ri]-y)<9: g[(ci,ri)]=v
    return cols,rows,g
def fix(k,v):
    if v is None: return None
    if k in('isip','press','tvd','fluid') and v<100: v=round(v*1000)
    if k in('prop','m100','m4070') and v<2000: v=round(v*1000)
    if k=='fg' and v>100: v=round(v/1000,3)
    if k=='rate' and not 30<=v<=140: return None
    if k=='fg' and not 0.7<=v<=1.2: return None
    if k=='isip' and not 3000<=v<=9500: return None
    if k=='press' and not 5000<=v<=13500: return None
    return v
def read(api):
    res={}; labidx=None; nxt=0
    for f in sorted(glob.glob(f"wells/{api}/f3_*.pdf")):
        txt=json.load(open(f.replace(".pdf",".json"))); doc=pdfium.PdfDocument(f)
        for i,t in enumerate(txt):
            tl=t.lower()
            if len(t)>300 and not ("stage summary" in tl or "isip" in tl): continue
            im=doc[i].render(scale=3.5).to_pil().convert("RGB"); best=None
            r0,_s=best_rotation(doc[i])
            for rot in dict.fromkeys((r0,0,90,270)):
                bx=boxes(im.rotate(rot,expand=True) if rot else im); gr=grid(bx)
                if gr and (best is None or len(gr[2])>len(best[1][2])): best=(bx,gr,rot)
            if not best: continue
            bx,(cols,rows,g),rot=best
            if labidx is None:
                labs={}
                for k,p in LAB.items():
                    c=[b for b in bx if val(b[4]) is None and re.search(p,b[4].lower().strip())]
                    c=sorted(c,key=lambda b:b[1])
                    if k in("prop","m100","m4070"): c=c[1:2] if len(c)>=2 else []
                    if c and rows:
                        y=(c[0][1]+c[0][3])/2; labs[k]=min(range(len(rows)),key=lambda i:abs(rows[i]-y))
                if "isip" in labs: labidx=labs; nrows=len(rows); nxt=0; ref=[(r-rows[0])/(rows[-1]-rows[0]) for r in rows]
                else: continue
            print("page",i+1,"rot",rot,"cols",len(cols),"rows",len(rows),"expected",nrows,file=sys.stderr)
            if len(rows)<nrows-8 or len(rows)>nrows+2: continue
            nr=[(r-rows[0])/(rows[-1]-rows[0]) for r in rows]
            m={ri:min(range(nrows),key=lambda j:abs(ref[j]-n)) for ri,n in enumerate(nr)} if len(rows)!=nrows else {i:i for i in range(nrows)}
            inv={}
            for ri,j in m.items(): inv.setdefault(j,ri)
            for ci in range(len(cols)):
                res[nxt]={k:fix(k,(g.get((ci,inv[j])) if j in inv else None)) for k,j in labidx.items()}; nxt+=1
    return res
if __name__=="__main__":
    r=read(sys.argv[1]); json.dump(r,open(f"hal2_{sys.argv[1]}.json","w"))
    for s in sorted(r): print(s,r[s])
