import json,re,math
def rows(page):
    items=sorted(page,key=lambda x:(x[0][0][1]+x[0][2][1])/2)
    out=[];cur=[];ly=None
    for b,t,c in items:
        y=(b[0][1]+b[2][1])/2; h=abs(b[2][1]-b[0][1])
        if ly is None or abs(y-ly)<=max(8,h*0.5): cur.append((b[0][0],t))
        else: out.append(cur);cur=[(b[0][0],t)]
        ly=y
    if cur: out.append(cur)
    return [[t for x,t in sorted(r)] for r in out]
def num(t):
    t=t.strip().replace(" ","")
    m=re.fullmatch(r"(-?)([\d,]*\d\.\d+|\d+)(-?)",t)   # "89-" style trailing minus
    if not m: return None
    v=float(m.group(2).replace(",",""))
    return -v if (m.group(1) or m.group(3)) else v
def mincurv(st):
    """st: list of (md,inc,azi) -> list of (N,E) in ft"""
    N=E=0.0; out=[(0.0,0.0)]
    for (m0,i0,a0),(m1,i1,a1) in zip(st,st[1:]):
        i0,i1,a0,a1=map(math.radians,(i0,i1,a0,a1)); dm=m1-m0
        c=math.cos(i1-i0)-math.sin(i0)*math.sin(i1)*(1-math.cos(a1-a0)); dl=math.acos(max(-1,min(1,c)))
        rf=1.0 if dl<1e-9 else 2/dl*math.tan(dl/2)
        N+=dm/2*(math.sin(i0)*math.cos(a0)+math.sin(i1)*math.cos(a1))*rf
        E+=dm/2*(math.sin(i0)*math.sin(a0)+math.sin(i1)*math.sin(a1))*rf
        out.append((N,E))
    return out
def extract2(pages):
    """rows -> (md,inc,azi) using only the first three numeric columns after an optional survey index"""
    out=[]
    for pn,p in enumerate(pages):
        for r in rows(p):
            toks=[t.strip() for t in r]
            vals=[(num(t),t) for t in toks]
            while vals and vals[0][0] is None: vals=vals[1:]
            if len(vals)<6 or any(v is None for v,_ in vals[:5]): continue
            if "." not in vals[0][1].replace(" ",""): vals=vals[1:]       # survey index column
            if len(vals)<5 or any(v is None for v,_ in vals[:4]): continue
            md,inc,azi=vals[0][0],vals[1][0],vals[2][0]
            if "." not in vals[1][1] or "." not in vals[2][1]: continue
            out.append((pn,md,inc,azi))
    return out
def screen(rows3):
    ok=[]
    for idx,(pn,md,inc,azi) in enumerate(rows3):
        if not(0<=inc<=125 and 0<=azi<=360.5 and 0<=md<=45000): continue
        if ok and md<=ok[-1][0]: continue
        if ok and md-ok[-1][0]>3000:      # a big jump is believed only if the next valid row follows it closely
            nxt=next((r for r in rows3[idx+1:idx+4] if 0<=r[1]<=45000),None)
            if not(nxt and 0<nxt[1]-md<=800): continue
        ok.append((md,inc,azi))
    # drop rows whose inc/azi jump away from both neighbours (isolated digit misreads)
    keep=[ok[0]] if ok else []
    for k in range(1,len(ok)-1):
        a,b,c=ok[k-1],ok[k],ok[k+1]
        dm1=max(b[0]-a[0],1)
        jump_i=abs(b[1]-a[1])>max(4,0.15*dm1) and abs(b[1]-c[1])>max(4,0.15*dm1) and abs(a[1]-c[1])<max(4,0.15*(c[0]-a[0]))
        d_az=lambda x,y:min(abs(x-y),360-abs(x-y))
        jump_a=b[1]>3 and d_az(b[2],a[2])>25 and d_az(b[2],c[2])>25 and d_az(a[2],c[2])<15
        if not(jump_i or jump_a): keep.append(b)
    if ok: keep.append(ok[-1])
    return keep
