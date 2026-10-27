"""build_prod.py -> production.html: monthly production comparison charts (cumulative oil/ft, water cut vs cumulative liquid, cumulative water/ft, WOR) for chosen operators' Niobrara wells."""
import json,re,sys
R="/private/tmp/claude-501/-Users-tom-Documents-Claude-Projects/5960602b-6fb9-47bc-b1f8-6bb8837f81e9/scratchpad/pub2/"
OPS=["Ballard Petroleum","WRC Energy"]
W=json.load(open(R+"dashboard/data/wells.json")); P=json.load(open(R+"data/production.json"))
wells=[]
for w in sorted((w for w in W if w["fm"]=="Niobrara" and w["op"] in OPS and w.get("len")),key=lambda x:(OPS.index(x["op"]),x["yr"],x["name"])):
    p=P.get(w["api"])
    if not p or p.get("none"): continue
    k=next((i for i,v in enumerate(p["o"]) if v>0),None)
    if k is None: continue
    o=p["o"][k:]; wa=p["w"][k:]
    while o and o[-1]==0 and wa[-1]==0: o.pop(); wa.pop()      # trailing months with nothing reported
    wells.append({"api":w["api"],"name":w["name"].strip(),"op":w["op"],"yr":w["yr"],"len":w["len"],"o":o,"w":wa})
cur=open(R+"completions.html").read()
styles="".join(re.findall(r"<style>.*?</style>",cur,re.S)[:2])
tpl=open("template.html").read()
html=tpl.replace("/*STYLES*/",styles).replace("/*DATA*/",json.dumps({"ops":OPS,"wells":wells},separators=(",",":")))
open("production.html","w").write(html)
print(len(wells),"wells,",len(html)//1024,"KB")
