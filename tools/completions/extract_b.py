import json,re,glob,collections
import sys,os
W=[w for w in json.load(open("nio_rest.json")) if os.path.exists("wells/"+w["api"]+"/done") and sys.argv[1].lower() in w["op"].lower()]
VENDORS=[("Element","Element Technical Services"),("Liberty","Liberty"),("HES","Halliburton"),("Halliburton","Halliburton"),("Baker","Baker Hughes"),("BHGE","Baker Hughes"),("Schlumberger","Schlumberger"),("SLB","Schlumberger"),("ProFrac","ProFrac"),("Pro Frac","ProFrac"),("NexTier","NexTier"),("Patterson","Patterson-UTI"),("Calfrac","Calfrac"),("Keane","Keane/NexTier"),("BJ ","BJ Services"),("Weatherford","Weatherford"),("Superior","Superior Well Services"),("Basic","Basic Energy"),("Cudd","Cudd/RPC"),("FTS","FTS International"),("Stallion","Stallion"),("USWS","U.S. Well Services"),("U.S. Well","U.S. Well Services"),("Trican","Trican"),("Mesa","Mesa Fluids"),("Nine","NINE Energy"),("Select","Select Energy"),("Premier","Premier"),("Nabors","Nabors")]
def tret(path):
    s=open(path,errors="replace").read()
    t=re.sub(r"<script.*?</script>|<style.*?</style>","",s,flags=re.S)
    rows=[]
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>",t,flags=re.S|re.I):
        c=[re.sub(r"\s+"," ",re.sub(r"&nbsp;?"," ",re.sub(r"<[^>]+>"," ",x))).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>",r,flags=re.S|re.I)]
        if len(c)>=7 and re.match(r"^\d",c[0]): rows.append(c[:8])
    return rows
num=lambda x:int(re.sub(r"[^\d]","",x) or 0)
SIZES=r"(?:100|200)\s*[- ]?mesh|(?:20|30|40|50|70|16|12|8)\s*/\s*(?:20|30|40|50|70|100|120|140|170|18|40)\b(?:\s*mesh)?"
MESH=re.compile(r"(?<![\d/])("+SIZES+r")(?![\d/])",re.I)
WL={"100mesh","200mesh","40/70","30/50","20/40","40/120","30/70","50/140","40/140","70/140","16/30","12/20","12/18","8/16","20/40","30/60","50/100","30/100","40/100","100/200","16/20"}
rows_out=[]
for w in W:
    d=f"wells/{w['api']}"
    tr=tret(d+"/tret.html"); fr=[r for r in tr if "frac" in r[2].lower()] or tr
    main=max(fr,key=lambda r:num(r[4])) if fr else None
    texts=[]
    for p in sorted(glob.glob(d+"/f3_*.json")): texts+=json.load(open(p))
    full=" | ".join(texts); p1=texts[0] if texts else ""
    ven=sorted({v for k,v in VENDORS if re.search(r"\b"+re.escape(k.strip())+r"\b",p1,re.I)})
    ven_all=sorted({v for k,v in VENDORS if re.search(r"\b"+re.escape(k.strip())+r"\b",full[:200000],re.I)})
    mesh=collections.Counter(re.sub(r"mesh$","",re.sub(r"\s|-","",m.group(1)).lower()) if "/" in m.group(1) else "100mesh" for m in MESH.finditer(full))
    mesh=collections.Counter({k:v for k,v in mesh.items() if k in {x.replace("mesh","") if x.endswith("mesh") else x for x in WL}|{"100mesh"}})
    fl=full.lower()
    sys_=[]
    if re.search(r"slick\s?-?water|slickwater",fl): sys_.append("slickwater")
    if "hvfr" in fl or "high viscosity" in fl: sys_.append("HVFR")
    if re.search(r"cross\s?-?link|x-link|borate|linear gel|hybrid",fl): sys_.append("crosslink/hybrid words")
    rows_out.append({"api":w["api"],"name":w["name"],"op":w["op"],"stages":int(main[6].replace(",","")) if main and main[6].replace(",","").isdigit() else None,
        "proppant_lb":num(main[4]) if main else None,"fluid_bbl":num(main[3]) if main else None,"tret_type":main[2] if main else None,"frac_date":main[7] if main else None,
        "vendor_p1":ven,"vendor_any":ven_all,"mesh":dict(mesh.most_common(5)),"fluid_words":sys_,"pages":len(texts)})
json.dump(rows_out,open("extract_"+sys.argv[1].replace(" ","_")+".json","w"),indent=0)
for r in rows_out: print(f"{r['op'][:12]:<12}{r['name'][:30]:<31} stages {r['stages']!s:>4} | sand {(r['proppant_lb'] or 0):>11,} lb | fluid {(r['fluid_bbl'] or 0):>9,} bbl | v:{','.join(r['vendor_p1']) or ('~'+','.join(r['vendor_any'][:2]))} | mesh {r['mesh']} | {','.join(r['fluid_words'])}")
