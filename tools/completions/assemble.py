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
s=s[:m.start(g)]+json.dumps(D,separators=(',',':'))+s[m.end(g):]
s=re.sub(r'<meta name="description" content="[^"]*">','<meta name="description" content="Stages, proppant, fluid type, vendor and treating data for Niobrara wells in the Powder River Basin.">',s)
open(p,'w').write(s)
print(len(top),'top-5 wells +',len(more),'more;',len(D['stages']),'wells with stage rows')
