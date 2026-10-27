"""reocr.py: for fetched wells without stage rows, find Form 3 attachment pages whose first OCR (done unrotated) is garbled, re-OCR them in the detected orientation and save the better text.
usage: reocr.py [api ...]   (no args: every fetched well in nio_rest.json that has no reader output)"""
import json,glob,os,re,sys,time
import numpy as np,pypdfium2 as pdfium
from rapidocr_onnxruntime import RapidOCR
from orient import best_rotation
ocr=RapidOCR()
WORDS=set("the and well pressure stage stages total rate volume treatment proppant summary report average maximum max min clean slurry fluid water sand gal bbl psi isip frac fracture job time pump pumping design actual customer operator county formation date field acid breakdown flush pad sweep zone zones perforation interval depth top bottom size mesh lbs rig completion stimulation".split())
def words(t): return sum(1 for w in re.findall(r"[a-z]{3,}",t.lower()) if w in WORDS)
def read(img):
    res,_=ocr(np.array(img)); return " | ".join(t for b,t,c in (res or []))
def targets():
    out=[]
    for w in json.load(open("nio_rest.json")):
        a=w["api"]
        if not os.path.exists(f"wells/{a}/done"): continue
        if any(os.path.exists(f"{p}_{a}.json") and os.path.getsize(f"{p}_{a}.json")>5 for p in ("lib","el","hal2","ftsi","camino","eog")): continue
        out.append(a)
    return out
def run(a):
    n=0
    for f in sorted(glob.glob(f"wells/{a}/f3_*.pdf")):
        js=f.replace(".pdf",".json")
        if not os.path.exists(js) or os.path.getsize(f)<2000: continue
        if os.path.exists(js+".orig"): continue            # already reprocessed
        txt=json.load(open(js)); doc=pdfium.PdfDocument(f); new=list(txt); changed=0
        for i in range(min(len(doc),len(txt))):
            t=txt[i]
            if i<2 or words(t)>=4 and len(t)>400: continue     # Form 3 pages and readable pages are fine
            r,_=best_rotation(doc[i])
            if r==0 and words(t)>=2: continue
            im=doc[i].render(scale=2.0).to_pil().convert("RGB")
            if r: im=im.rotate(r,expand=True)
            t2=read(im)
            if words(t2)>words(t): new[i]=t2; changed+=1
        if changed:
            os.replace(js,js+".orig"); json.dump(new,open(js,"w")); n+=changed
        else:
            open(js+".orig","w").write("unchanged")
    return n
if __name__=="__main__":
    L=sys.argv[1:] or targets()
    print(len(L),"wells",flush=True)
    for a in L:
        t=time.time(); n=run(a); print(time.strftime("%H:%M:%S"),a,"pages re-read:",n,f"({int(time.time()-t)}s)",flush=True)
