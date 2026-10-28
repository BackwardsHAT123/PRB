"""lib2.py api -> per-stage rows from the Liberty Engineering completion-report table (Stage | AveSurfacePSI | MaxSurfacePSI | AvePSI | MaxPSI).
Used for the 2025 Liberty reports, where the pressure table is a scanned page (the stage-number column does not OCR, so stages are
numbered by row order) and the rate / ISIP / gradient pages are charts. Output: [{n, press (AvePSI), maxp (MaxPSI)}]."""
import sys,json,glob,re,pypdfium2 as pdfium
from stagecalc import boxes,val
from orient import best_rotation
api=sys.argv[1]; out=f"lib2_{api}.json"; res=[]
for f in sorted(glob.glob(f"wells/{api}/f3_*.pdf")):
    doc=pdfium.PdfDocument(f); txt=json.load(open(f.replace(".pdf",".json")))
    for i in range(len(doc)):
        t=((txt[i] if i<len(txt) else "") or "").lower().replace(" ","")
        if not ("operator" in t and "stage" in t) and "avepsi" not in t: continue
        r,_=best_rotation(doc[i]); im=doc[i].render(scale=3.0).to_pil().convert("RGB")
        if r: im=im.rotate(r,expand=True)
        bx=boxes(im)
        hd={b[4].lower().replace(" ",""):b for b in bx}
        ha=next((b for k,b in hd.items() if k=="avepsi"),None); hm=next((b for k,b in hd.items() if k=="maxpsi"),None)
        if not ha or not hm: continue
        xa,xm=(ha[0]+ha[2])/2,(hm[0]+hm[2])/2; ytab=ha[3]
        cells=[]
        for b in bx:
            v=val(b[4]); 
            if v is None or b[1]<ytab: continue
            cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2
            if abs(cx-xa)<50: cells.append((cy,"a",v,"," in b[4]))
            elif abs(cx-xm)<50: cells.append((cy,"m",v,"," in b[4]))
        stop=min([c[0] for c in cells if c[3]],default=1e9)       # the Min / Max / Average / Totals block uses thousands separators
        summ={k:sorted((c[0],c[2]) for c in cells if c[3] and c[1]==k) for k in "am"}      # printed [min, max, average, total] per column, top to bottom
        cells=sorted(c for c in cells if c[0]<stop-5)
        rows=[]
        for cy,k,v,_ in cells:
            if rows and abs(cy-rows[-1]["y"])<13: rows[-1][k]=v
            else: rows.append({"y":cy,k:v})
        rows=[r for r in rows if "a" in r]
        if len(rows)>=8:
            res=[{"n":j+1,"press":r["a"],"maxp":r.get("m")} for j,r in enumerate(rows)]
            # the scan misreads a digit now and then: use the printed min / max to blank values outside them, and blank a pair where average > max
            lim={k:(v[0][1],v[1][1]) for k,v in summ.items() if len(v)>=2}
            for r in res:
                if "a" in lim and r["press"] is not None and not lim["a"][0]<=r["press"]<=lim["a"][1]: r["press"]=None
                if "m" in lim and r["maxp"] is not None and not lim["m"][0]<=r["maxp"]<=lim["m"][1]: r["maxp"]=None
                if r["press"] is not None and r["maxp"] is not None and r["press"]>r["maxp"]: r["press"]=r["maxp"]=None
            break
    if res: break
json.dump(res,open(out,"w")); print(api,len(res),"stages;",sum(1 for r in res if r["press"] is None),"blanked by the printed limits")
