"""orient.py: find the rotation (0/90/180/270) that makes a scanned page read upright, using OCR text quality on a small render."""
import re,numpy as np
from rapidocr_onnxruntime import RapidOCR
_ocr=RapidOCR()
WORDS=set("the and of to for total average pressure rate stage fluid proppant max min time volume treatment well sand mesh psi bbl lbs api date report summary job design clean slurry final isip frac gradient zone customer company data".split())
def score(im):
    res,_=_ocr(np.array(im)); s=0.0
    for b,t,c in res or []:
        c=float(c); t=t.strip()
        if c<0.7 or not t: continue
        s+=c*len(t)
        s+=8*sum(1 for x in re.findall(r"[a-z]{3,}",t.lower()) if x in WORDS)
    return s
def best_rotation(page,scale=1.8):
    im=page.render(scale=scale).to_pil().convert("RGB")
    sc={r:score(im.rotate(r,expand=True) if r else im) for r in (0,90,180,270)}
    r=max(sc,key=sc.get)
    if sc[0]>=0.85*sc[r]: r=0
    if sc[r]<150 and scale<3:   # tiny print: re-score at higher resolution
        return best_rotation(page,3.2)
    return r,sc
def oriented(page,scale):
    r,_=best_rotation(page)
    im=page.render(scale=scale).to_pil().convert("RGB")
    return (im.rotate(r,expand=True) if r else im),r
