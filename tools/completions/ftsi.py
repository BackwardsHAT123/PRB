"""ftsi.py api -> per-stage summary boxes from FTS International treatment reports (one box per stage)."""
import sys,json,glob,re,pypdfium2 as pdfium
from stagecalc import boxes
from orient import oriented
LB={"avg_stp":r"average\s*stp","avg_rate":r"average\s*rate","isip":r"final\s*isip","fg":r"final\s*f\.?\s*g","max_stp":r"max\s*stp","max_rate":r"max\s*rate"}
num=re.compile(r"-?\d[\d,]*\.?\d*")
def rd(bx,label):
    out=[]
    for b in bx:
        if re.search(label,b[4].lower()) and not num.fullmatch(b[4].strip()):
            cy=(b[1]+b[3])/2; h=b[3]-b[1]
            m=num.search(b[4].split(":")[-1]) if ":" in b[4] and num.search(b[4].split(":")[-1]) else None
            if m: out.append((b[1],float(m.group().replace(",",""))));continue
            c=[c for c in bx if c[0]>=b[2]-5 and abs((c[1]+c[3])/2-cy)<h*0.8 and num.search(c[4])]
            if c:
                c=min(c,key=lambda c:c[0]); out.append((b[1],float(num.search(c[4]).group().replace(",",""))))
    return out
def run(api):
    res=[]
    for f in sorted(glob.glob(f"wells/{api}/f3_*.pdf")):
        doc=pdfium.PdfDocument(f); txt=json.load(open(f.replace(".pdf",".json")))
        for i in range(len(doc)):
            if i<len(txt) and txt[i] and "stp" not in txt[i].lower() and i<44: continue
            im,_r=oriented(doc[i],2.0); bx=boxes(im)
            if not any(re.search(LB["avg_stp"],b[4].lower()) for b in bx): continue
            d={k:rd(bx,p) for k,p in LB.items()}
            n=max(len(v) for v in d.values())
            for j in range(n):
                res.append({"page":i+1,**{k:(v[j][1] if j<len(v) else None) for k,v in d.items()}})
    return res
if __name__=="__main__":
    r=run(sys.argv[1]); json.dump(r,open(f"ftsi_{sys.argv[1]}.json","w")); print(len(r)); [print(x) for x in r[:6]]
