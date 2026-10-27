"""build_rest.py operator -> rest_<op>.json: dashboard well records (grp 'more') + stage rows for every fetched well of that operator."""
import json,os,re,sys,statistics as st
op=sys.argv[1]; slug=op.replace(" ","_")
os.system(f"python3 extract_b.py '{op}' >/dev/null && python3 merge.py '{op}' >/dev/null")
ex={x['api']:x for x in json.load(open(f'extract_{slug}.json'))}
sf=json.load(open(f'stage_{slug}.json')); base={w['api']:w for w in json.load(open('nio_rest.json'))}
def tret(path):
    s=open(path,errors="replace").read(); t=re.sub(r"<script.*?</script>|<style.*?</style>","",s,flags=re.S); rows=[]
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>",t,flags=re.S|re.I):
        c=[re.sub(r"\s+"," ",re.sub(r"&nbsp;?"," ",re.sub(r"<[^>]+>"," ",x))).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>",r,flags=re.S|re.I)]
        if len(c)>=7 and re.match(r"^\d",c[0]): rows.append(c[:8])
    return rows
n_=lambda x:int(re.sub(r"[^\d]","",x) or 0)
wells=[]
for a,e in ex.items():
    b=base[a]; allr=tret(f'wells/{a}/tret.html'); rows=[r for r in allr if 'frac' in r[2].lower()] or allr
    top=min((n_(r[0]) for r in rows),default=0); bot=max((n_(r[1]) for r in rows),default=0)
    eff=bot-top if bot>top else None
    st_rows=sf['stages'].get(a,[]); src=sf['src'].get(a,'')
    def mean(k):
        v=[r[k] for r in st_rows if r.get(k) is not None]; return v if len(v)>=5 else None
    rate,press,isip,fg=mean('rate'),mean('press'),mean('isip'),mean('fg')
    ven=''
    if src: ven=("Liberty" if src.startswith("Liberty") else "Halliburton" if src.startswith("Halli") else "Element Technical Services (frac report)" if src.startswith("Element") else "FTS International")
    elif e['vendor_p1']: ven=e['vendor_p1'][0]
    elif e['vendor_any']: ven=e['vendor_any'][0]
    fw=e['fluid_words']; ft=''
    if 'slickwater' in fw or 'HVFR' in fw: ft='Slickwater'+(' (HVFR)' if 'HVFR' in fw else '')
    if 'crosslink/hybrid words' in fw: ft=(ft+'; ' if ft else '')+'crosslink or gel mentioned'
    mesh=', '.join(('100 mesh' if k=='100mesh' else k) for k in list(e['mesh'])[:3])
    stages=e['stages'] or None
    if not stages:
        import glob
        txt=" ".join(" ".join(json.load(open(p))[:12]) for p in glob.glob(f'wells/{a}/f3_*.json'))
        m=re.findall(r"(?:Niobrara|Intervals)[^|]{0,6}?(\d{2,3})\s*Intervals",txt,re.I)
        if m: stages=int(m[0])
    w=dict(api=a,name=b['name'],op=b['op'],cty=b['cty'],yr=b['yr'],len=b['len'],o12=b['o12'],stages=stages,sand=e['proppant_lb'] or None,fluid_bbl=e['fluid_bbl'] or None,sizes=mesh,vendor=ven,ftype=ft,
        rate=round(st.mean(rate),1) if rate else None,press=round(st.mean(press)) if press else None,fg=round(st.mean(fg),2) if fg else None,isip=round(st.mean(isip)) if isip else None,
        basis=f'mean of per-stage values ({src}, OCR-parsed)' if (rate or press or isip) else '',has_stage=a in sf['stages'],eff=eff,
        slen=round(eff/stages) if eff and stages else None,slen_src='calc' if eff and stages else '',oil1k=round(b['o12']/b['len']*1000) if b.get('o12') and b.get('len') else None,twp=b['twp'],grp='more')
    wells.append(w)
json.dump(dict(wells=wells,stages=sf['stages'],src=sf['src']),open(f'rest_{slug}.json','w'),separators=(',',':'))
print(len(wells),'wells;',len(sf['stages']),'with stage rows')
for w in wells: print(w['name'][:32].ljust(33),w['stages'],w['sand'],w['vendor'][:14],w['ftype'],w['rate'],w['press'],w['isip'],w['fg'],w['slen'],w['oil1k'])
