"""assemble.py -> writes the top-5 base plus every rest_<op>.json into ../dash/site3/completions.html (idempotent)."""
import json,re,glob
p='../dash/site3/completions.html'; s=open(p).read()
m=re.search(r"const D=(\{.*?\});\nconst W=|const D=(\{.*?\});\nconst ALL=",s,re.S)
g=1 if m.group(1) else 2
D=json.loads(m.group(g))
top=[w for w in D['wells'] if w.get('grp')!='more']
for a in list(D['stages']):
    if any(w['api']==a and w.get('grp')=='more' for w in D['wells']): D['stages'].pop(a); D['src'].pop(a,None)
more=[]
for f in sorted(glob.glob('rest_*.json')):
    r=json.load(open(f)); more+=r['wells']; D['stages'].update(r['stages']); D['src'].update(r['src'])
D['wells']=top+more
def cv(v):
    """Vendor name only: drop parenthetical notes and customer names, shorten known companies."""
    v=re.sub(r"\s*\(.*?\)","",v or "").strip()
    for k,n in (("liberty","Liberty"),("pressure summary","Liberty"),("per-stage final isip","Liberty"),("element","Element"),("halliburton","Halliburton"),("calfrac","Calfrac"),("fts","FTS International"),("baker","Baker Hughes"),("schlumberger","Schlumberger")):
        if v.lower().startswith(k): return n
    return v
for w in D['wells']: w['vendor']=cv(w.get('vendor'))
FM={w['api']:w['fm'] for w in json.load(open('../pub2/dashboard/data/wells.json'))}     # every well carries its formation (the page used to assume Niobrara for untagged ones)
for w in D['wells']: w['fm']=w.get('fm') or FM.get(w['api']) or 'Niobrara'
# lateral = span of the state's Producing Intervals (same rule as tools/dashboard/build_all.py); the mapped path length stays in len_path and is the fallback
LS=json.load(open('../pub2/data/lateral_state.json'))
def state_len(api,path_len):
    rows=[(x,y) for x,y in LS.get(api,[]) if y>x]
    if not rows or not path_len: return None
    sp=max(y for x,y in rows)-min(x for x,y in rows)
    return round(sp) if 3000<=sp<=20000 and 0.55*path_len<=sp<=1.1*path_len else None
LO=json.load(open('../pub2/data/lateral_override.json'))
nst=0
for w in D['wells']:
    base=w.get('len_path') or w.get('len')
    if not base: continue
    w['len_path']=base; sl=state_len(w['api'].replace('-','').replace('49','',1) if False else w['api'],base)
    ov=LO.get(w['api'],{}).get('len')          # hand-checked laterals (data/lateral_override.json) beat the state interval and the path
    w['len']=ov or sl or base; nst+=bool(sl or ov)
    if w.get('o12'): w['oil1k']=round(w['o12']/w['len']*1000)
print(nst,'of',len(D['wells']),'wells use the state producing-interval lateral')
s=s[:m.start(g)]+json.dumps(D,separators=(',',':'))+s[m.end(g):]
s=re.sub(r'<meta name="description" content="[^"]*">','<meta name="description" content="Stages, proppant, fluid type, vendor and treating data for horizontal wells in the Powder River Basin.">',s)
open(p,'w').write(s)
print(len(top),'top-5 wells +',len(more),'more;',len(D['stages']),'wells with stage rows')
