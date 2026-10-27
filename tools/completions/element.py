"""element.py api -> per-zone rows from Element 'Zone Report - State Summary' pages."""
import sys,json,glob,re,statistics as st,pypdfium2 as pdfium
from stagecalc import boxes,val
from orient import oriented
NAMES=["zone","clean","slurry","pumpdown","tclean","tslurry","m100","prop","press","maxpress","intpress","maxint","conc"]
def parse(bx):
    nums=[((b[0]+b[2])/2,(b[1]+b[3])/2,val(b[4])) for b in bx if val(b[4]) is not None]
    xs=sorted(x for x,_,_ in nums); cols=[]
    for x in xs:
        if cols and x-cols[-1][-1]<14: cols[-1].append(x)
        else: cols.append([x])
    cols=[sum(c)/len(c) for c in cols if len(c)>=10]
    return nums,cols
def run(api):
    out={}
    for f in sorted(glob.glob(f"wells/{api}/f3_*.pdf")):
        doc=pdfium.PdfDocument(f)
        for i in range(min(len(doc),30)):
            im,_r=oriented(doc[i],2.2); bx=boxes(im)
            if sum(1 for b in bx if re.match(r"\s*\d{1,2}/\d{1,2}/\d{4}",b[4]))<10: continue
            nums,cols=parse(bx)
            if len(cols)<12: print("page",i+1,"cols",len(cols),file=sys.stderr); continue
            # zone column is leftmost; take 13 columns starting at zone col (leftmost small ints)
            def isz(cx): 
                v=[v for x,y,v in nums if abs(x-cx)<18]
                return len(v)>=8 and all(float(a).is_integer() and 0<a<200 for a in v) and sorted(v)==v[:0]+sorted(v)
            zi=next((k for k,cx in enumerate(cols) if isz(cx)),0)
            cols=cols[zi:zi+13]
            names=NAMES if len(cols)==13 else [n for n in NAMES if n!="pumpdown"]
            zc=cols[0]; zrows=sorted((y,int(v)) for x,y,v in nums if abs(x-zc)<18 and float(v).is_integer() and 0<v<200)
            for y,z in zrows:
                d={}
                for nm,cx in zip(names[1:],cols[1:]):
                    c=[v for x,yy,v in nums if abs(x-cx)<16 and abs(yy-y)<9]
                    d[nm]=c[0] if c else None
                out[z]=d
            print("page",i+1,"zones",len(zrows),"cols",len(cols),file=sys.stderr)
    return out
if __name__=="__main__":
    r=run(sys.argv[1]); json.dump(r,open(f"el_{sys.argv[1]}.json","w")); print(sys.argv[1],len(r))
    for z in sorted(r)[:4]+sorted(r)[-2:]: print(z,r[z])
