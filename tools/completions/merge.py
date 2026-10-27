"""merge.py operator -> stage_<op>.json {stages:{api:[rows]},src:{api:str},wells:{api:summary}} from reader outputs + Form 3 extract."""
import json,os,sys,re,statistics as st
op=sys.argv[1]; slug=op.replace(" ","_")
ex={x['api']:x for x in json.load(open(f'extract_{slug}.json'))}
def norm(r):
    o={}
    def put(k,v,lo,hi,scale=None):
        if v is None: return
        for s in ((1,1000,0.1,0.01,10,100) if scale else (1,)):
            x=v*s
            if lo<=x<=hi: o[k]=round(x,3) if hi<10 else round(x,1) if hi<200 else round(x); return
    put('isip',r.get('isip'),3000,9500,1); put('press',r.get('press'),5000,13500,1); put('maxpress',r.get('maxpress'),5000,14000,1)
    put('rate',r.get('rate'),30,140,1); put('fg',r.get('fg'),0.7,1.2,1)
    put('fluid',r.get('fluid'),3000,40000); put('prop',r.get('prop'),100000,1500000)
    return o
out={}; src={}
for a,e in ex.items():
    n=e.get('stages')
    f=f'lib_{a}.json'
    if os.path.exists(f) and os.path.getsize(f)>5:
        b=json.load(open(f)); p,rot,rows=max(b,key=lambda t:len(t[2]))
        A=any(r.get('fg') is not None for r in rows)
        rows=[r for r in rows if r.get('n',0)>0]
        if n: rows=rows[:n]
        out[a]=[dict(n=r['n'],**norm(r)) for r in rows]; src[a]="Liberty "+("pressure summary" if A else "stage summary"); continue
    f=f'hal2_{a}.json'
    if os.path.exists(f) and os.path.getsize(f)>5:
        h=json.load(open(f)); out[a]=[dict(n=int(k),**norm(v)) for k,v in sorted(h.items(),key=lambda t:int(t[0])) if int(k)>0]; src[a]="Halliburton stage summary"; continue
    f=f'el_{a}.json'
    if os.path.exists(f) and os.path.getsize(f)>5:
        z=json.load(open(f)); rows=[dict(n=int(k),**norm(dict(press=v.get('press'),maxpress=v.get('maxpress'),fluid=v.get('tclean'),prop=v.get('prop')))) for k,v in sorted(z.items(),key=lambda t:int(t[0]))]
        out[a]=rows; src[a]="Element zone report"; continue
    f=f'ftsi_{a}.json'
    if os.path.exists(f) and os.path.getsize(f)>5:
        rows=[dict(n=i+1,**norm(dict(isip=r['isip'],press=r['avg_stp'],maxpress=r['max_stp'],rate=r['avg_rate'],fg=r['fg']))) for i,r in enumerate(json.load(open(f)))]
        out[a]=rows; src[a]="FTS International treatment report"
for a,r in out.items(): print(a,src[a],len(r),'of',ex[a].get('stages'),{k:sum(1 for x in r if k in x) for k in ('isip','press','rate','fg','fluid','prop')})
json.dump(dict(stages=out,src=src),open(f'stage_{slug}.json','w'))
