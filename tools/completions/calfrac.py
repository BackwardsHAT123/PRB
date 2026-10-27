"""calfrac.py api -> calfrac_<api>.json: well-level job summary (avg/max pressure, avg/max rate, ISIP, frac gradient) from the Calfrac 'SUMMARY - FRACTURING' page."""
import sys,json,glob,re,pypdfium2 as pdfium
from stagecalc import boxes,val
from orient import best_rotation
def run(api):
    out=[]
    for f in sorted(glob.glob(f"wells/{api}/f3_*.pdf")):
        doc=pdfium.PdfDocument(f); txt=json.load(open(f.replace(".pdf",".json")))
        for i in range(len(doc)):
            t=txt[i].lower().replace(" ","") if i<len(txt) else ""
            if "fracturingzone" not in t: continue
            r0,_=best_rotation(doc[i]); im=doc[i].render(scale=2.6).to_pil().convert("RGB")
            if r0: im=im.rotate(r0,expand=True)
            bx=boxes(im); out.append(parse(bx))
    return [o for o in out if o]
def parse(bx):
    lab=lambda b:b[4].lower().replace(" ","")
    yT=[(b[1]+b[3])/2 for b in bx if lab(b)=="treatment"]; yK=[(b[1]+b[3])/2 for b in bx if lab(b).startswith("technical")]; yM=[(b[1]+b[3])/2 for b in bx if lab(b).startswith("materials")]
    if not yT or not yK: return None
    y0,y1=min(yT),min(yK); y2=min(yM) if yM else y1+260
    num=lambda lo,hi:[((b[0]+b[2])/2,(b[1]+b[3])/2,val(b[4]),b) for b in bx if lo<(b[1]+b[3])/2<hi and val(b[4]) is not None]
    fix=lambda v:v
    def units(lo,hi):
        u=[]
        for b in bx:
            y=(b[1]+b[3])/2
            if lo<y<hi:
                s=lab(b)
                if re.match(r"^[\[\(i\|]?(psi|ps|psl|psf)",s) and "ft" not in s: u.append(((b[0]+b[2])/2,y,"psi"))
                elif "min" in s and ("bb" in s or "b6" in s or "bl" in s): u.append(((b[0]+b[2])/2,y,"rate"))
        return u
    res={}
    U=units(y0,y1); N=num(y0,y1)
    if U:
        uy=max(u[1] for u in U)
        data=[n for n in N if n[1]>uy+2]
        grp={"psi":[],"rate":[]}
        for cx,cy,v,b in data:
            u=min(U,key=lambda u:abs(u[0]-cx))
            if abs(u[0]-cx)<45: grp[u[2]].append(v)
        P=[v if v>=1000 else v*1000 for v in grp["psi"] if v>=3]
        R=[v for v in grp["rate"] if 20<=v<=200]
        if len(P)>=2: res["press"]=min(P); res["maxpress"]=max(P)
        if len(R)>=2: res["rate"]=min(R); res["maxrate"]=max(R)
    # technical band: ISIP by header, frac gradient by value
    Nt=num(y1,y2); isip=[b for b in bx if y1<(b[1]+b[3])/2<y2 and "isip" in lab(b)]
    if isip:
        h=isip[0]; hx=(h[0]+h[2])/2; hy=(h[1]+h[3])/2
        c=[n for n in Nt if n[1]>hy and abs(n[0]-hx)<60]
        c.sort(key=lambda n:(abs(n[0]-hx),n[1]))
        for n in c:
            v=n[2]; v=v*1000 if v<100 else v
            if 3000<=v<=9500: res["isip"]=v; break
    fg=[n[2] for n in Nt if 0.6<=n[2]<=1.3 and abs(n[2]*100-round(n[2]*100))<1e-6]
    if fg: res["fg"]=fg[-1]
    return res or None
if __name__=="__main__":
    r=run(sys.argv[1]); json.dump(r,open(f"calfrac_{sys.argv[1]}.json","w")); print(sys.argv[1],r)
