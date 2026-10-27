"""stagerows.py api -> JSON list of per-stage rows from column-layout tables (stage, isip, press, rate, fluid, prop)."""
import sys,json,glob,re,statistics as st,pypdfium2 as pdfium
from stagecalc import boxes,val
PAT={"isip":"isip","press":"avgpress|avgtreat|treatingpress|avgpressure","rate":"avgrate|averagerate|avgslurry","fluid":"totalfluid|cleanvol|totalclean","prop":"totalprop|proppant\\(lbs|totalsand"}
RNG={"isip":(2500,9500),"press":(5000,13500),"rate":(30,140),"fluid":(3000,40000),"prop":(100000,1500000)}
def page_rows(bx):
    nb=sorted([((b[0]+b[2])/2,(b[1]+b[3])/2,val(b[4]),b[3]-b[1]) for b in bx if val(b[4]) is not None])
    cols=[]
    for cx,cy,v,h in nb:
        if cols and abs(cx-cols[-1]["cx"])<28: c=cols[-1]; c["p"].append((cy,v)); c["cx"]=(c["cx"]*(len(c["p"])-1)+cx)/len(c["p"])
        else: cols.append({"cx":cx,"p":[(cy,v)]})
    cols=[c for c in cols if len(c["p"])>=8]
    head=" ".join(b[4].lower().replace(" ","") for b in sorted(bx,key=lambda b:(b[1]//40,b[0])) if val(b[4]) is None)
    order=[]
    for k,p in PAT.items():
        for m in re.finditer(p,head): order.append((m.start(),k))
    order=[k for _,k in sorted(order)]; seen=[]; [seen.append(k) for k in order if k not in seen]
    stagecol=[c for c in cols if all(float(v).is_integer() and 0<v<200 for _,v in c["p"])]
    data=[c for c in cols if c not in stagecol and st.median(v for _,v in c["p"])>=20]
    if len(seen)<2: return []
    mapped={k:c for k,c in zip(seen,data)}
    ys=sorted({y for c in mapped.values() for y,_ in c["p"]}); 
    rows=[]
    for y in ys:
        if rows and y-rows[-1]["y"]<14: continue
        rows.append({"y":y})
    out=[]
    for r in rows:
        d={}
        for k,c in mapped.items():
            near=[(abs(y-r["y"]),v) for y,v in c["p"] if abs(y-r["y"])<14]
            if near:
                v=min(near)[1]; lo,hi=RNG[k]
                if lo<=v<=hi: d[k]=v
        if stagecol:
            near=[(abs(y-r["y"]),v) for y,v in stagecol[0]["p"] if abs(y-r["y"])<14]
            if near: d["stage"]=int(min(near)[1])
        if len(d)>=2: out.append(d)
    return out
if __name__=="__main__":
    api=sys.argv[1]; allr=[]
    for f in sorted(glob.glob(f"wells/{api}/f3_*.pdf")):
        txt=json.load(open(f.replace(".pdf",".json"))); doc=pdfium.PdfDocument(f)
        for i,t in enumerate(txt):
            tl=t.lower()
            if not ("isip" in tl or "avg" in tl and "press" in tl): continue
            im=doc[i].render(scale=2.2).to_pil().convert("RGB")
            for rot in (0,90,270):
                r=page_rows(boxes(im.rotate(rot,expand=True) if rot else im))
                if len(r)>=8: allr+= [dict(x,page=i+1) for x in r]; break
    print("ROWS",api,json.dumps(allr))
