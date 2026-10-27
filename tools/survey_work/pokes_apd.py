"""pokes_apd.py: for each permitted well, fetch the APD from the state, read the survey plat (page 11), return NAD83 surface, KOP, landing point and bottom hole."""
import json,re,subprocess,sys,time,os
import numpy as np,pypdfium2 as pdfium
from rapidocr_onnxruntime import RapidOCR
ocr=RapidOCR()
BASE="https://pipeline.wyo.gov/"
def curl(url,out=None):
    a=["curl","-sL","-m","180","-A","Mozilla/5.0"]+(["-o",out] if out else [])+[url]
    p=subprocess.run(a,capture_output=True)
    return p.stdout.decode("utf-8","replace") if not out else p.returncode
def apd_links(api):
    n=str(int(api.split("-")[1]))+api.split("-")[2]
    m=curl(BASE+f"Wellapino.cfm?napino={n}&s1=Y")
    return sorted(set(re.findall(r"whatupapds\.cfm\?nautonum=(\d+)",m))),m
def plat(doc,page=10):
    for i in [page]+[j for j in range(len(doc)) if j!=page]:
        im=doc[i].render(scale=3.2).to_pil().convert("RGB")
        res,_=ocr(np.array(im)); bx=[(((b[0][0]+b[2][0])/2),((b[0][1]+b[2][1])/2),t) for b,t,c in (res or [])]
        txt=" ".join(t for _,_,t in bx).upper().replace(" ","")
        if "SURFACEPOSITION" in txt and ("LP/PPP" in txt or "BHL/EXIT" in txt or "LANDING" in txt):
            return i,bx,im.size
    return None,None,None
PAIR=re.compile(r"\(\s*(-?\d{2,3}\.\d{6})\s*°?\s*([NW])\s*\)")
def parse(bx,size):
    W=size[0]; vals=[]
    for x,y,t in bx:
        m=PAIR.search(t.replace("O","0") if False else t)
        if m: vals.append((x,y,float(m.group(1)),m.group(2)))
    # the left of the two datum columns is NAD83 (it is printed first); take values left of the column gap
    xs=sorted(v[0] for v in vals)
    if not xs: return None
    gap=max(range(1,len(xs)),key=lambda i:xs[i]-xs[i-1]) if len(xs)>1 else 0
    cut=(xs[gap-1]+xs[gap])/2 if len(xs)>1 else W
    left=sorted([v for v in vals if v[0]<cut],key=lambda v:v[1])
    N=[v for v in left if v[3]=="N"]; Wv=[v for v in left if v[3]=="W"]
    return [(n[2],-w[2]) for n,w in zip(N,Wv)]       # (lat, lon) top to bottom: surface, KOP, LP, BHL
if __name__=="__main__":
    wells=json.load(open(sys.argv[1])); out={}
    os.makedirs("apd",exist_ok=True)
    for w in wells:
        a=w["a"]; docs,menu=apd_links(a); time.sleep(3)
        rec={"name":w["n"],"docs":docs}
        for dnum in docs[-1:]:
            f=f"apd/{a}_{dnum}.pdf"
            if not os.path.exists(f) or os.path.getsize(f)<5000: curl(BASE+f"whatups/whatupapds.cfm?nautonum={dnum}",f); time.sleep(3)
            try: doc=pdfium.PdfDocument(f)
            except Exception as e: rec["error"]=str(e); continue
            i,bx,size=plat(doc)
            rec["pages"]=len(doc); rec["plat_page"]=None if i is None else i+1
            if bx:
                title=" ".join(t for _,_,t in bx if "POKES" in t.upper() or "FED" in t.upper())[:120]
                rec["title"]=title; rec["pts"]=parse(bx,size)
        out[a]=rec; print(a,w["n"],rec.get("plat_page"),rec.get("pts"),flush=True)
    json.dump(out,open(sys.argv[2],"w"),indent=1)
