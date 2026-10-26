import json
G=json.load(open("groups.json"))
def verdict(g):
    if g["level"]=="benchmark": return None,None
    if g["n12"]<5: return "Too few wells","neutral"
    o,w=g.get("iof12"),g.get("iwf12")
    if o is None or w is None: return "No basin benchmark","neutral"
    og,ob=o>=1.10,o<0.90; wg,wb=w<=0.90,w>1.20
    score=(1 if og else 0)-(1 if ob else 0)+(1 if wg else 0)-(1 if wb else 0)
    if og and wg: lab="Strong"
    elif ob and wb: lab="Weak"
    elif not(og or ob or wg or wb): lab="Typical"
    else:
        parts=[]
        parts.append("strong oil" if og else "weak oil" if ob else None)
        parts.append("low water" if wg else "high water" if wb else None)
        lab=", ".join(p for p in parts if p).capitalize()
    return lab,("good" if score>=1 else "bad" if score<=-1 else "neutral")
for g in G:
    g["key"]=g["level"]+"|"+(g["op"] or "")+"|"+(g["fm"] or "")
    g["read"],g["tone"]=verdict(g)
json.dump(G,open("groups.json","w"),separators=(",",":"))
for g in G:
    if g["level"] in ("operator","opfm"): print(g["key"],g["n12"],g.get("iof12"),g.get("iwf12"),g["read"],g["tone"])
