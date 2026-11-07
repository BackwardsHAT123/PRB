"""Read labeled NAD83 points (surface, KOP, landing, bottom hole) from the text layer of an APD survey plat."""
import re,sys,glob,json
import pypdfium2 as pdfium
PT=re.compile(r"NAD\s*83\s*\(\s*([A-Z][A-Z \-/]*?)\s*\)\s*LATITUDE\s*=\s*[^()]*\(\s*(-?\d+\.\d+)\s*°?\s*\)\s*LONGITUDE\s*=\s*[^()]*\(\s*(-?\d+\.\d+)\s*°?\s*\)",re.S)
KEY={"SURFACE HOLE LOCATION":"shl","SURFACE HOLE":"shl","KICK OFF POINT":"kop","LANDING POINT":"lp","BOTTOM HOLE LOCATION":"bhl","BOTTOM HOLE":"bhl"}
SV=re.compile(r"(SURFACE LOCATION|PENETRATION POINT|FIRST PENETRATION POINT|KICK ?OFF POINT|BOTTOM HOLE LOCATION)\s*\n(?:[^\n]*\n){1,2}?\s*N=[\d.]+\s*E=[\d.]+\s*LAT\.:\s*N\s*(\d+\.\d+)\s*LONG\.:\s*W\s*(\d+\.\d+)\s*N=[\d.]+\s*E=[\d.]+\s*LAT\.:\s*N\s*(\d+\.\d+)\s*LONG\.:\s*W\s*(\d+\.\d+)",re.S)
SVKEY={"SURFACE LOCATION":"shl","PENETRATION POINT":"lp","FIRST PENETRATION POINT":"lp","KICKOFF POINT":"kop","KICK OFF POINT":"kop","BOTTOM HOLE LOCATION":"bhl"}
def read(f):
    d=pdfium.PdfDocument(f); out={}
    for i in range(len(d)):
        t=d[i].get_textpage().get_text_range()
        for m in PT.finditer(t):
            k=KEY.get(re.sub(r"\s+"," ",m.group(1).upper()))
            if k and k not in out: out[k]=(float(m.group(2)),float(m.group(3)),i+1)
    if not out:      # surveyor layout with NAD27 then NAD83 N=/E=/LAT./LONG. blocks (second pair is NAD83)
        for i in range(len(d)):
            t=d[i].get_textpage().get_text_range()
            for m in SV.finditer(t):
                k=SVKEY.get(m.group(1).replace("  "," "))
                if k and k not in out: out[k]=(float(m.group(4)),-float(m.group(5)),i+1)
    return out
if __name__=="__main__":
    for f in sorted(glob.glob(sys.argv[1])):
        r=read(f); print(f.split("/")[-1],{k:v[:2] for k,v in r.items()},"pages",{v[2] for v in r.values()})
