"""process.py operator-substring -> runs applicable vendor stage readers on every fetched well of that operator (skips done outputs)."""
import json,glob,os,re,subprocess,sys,time
op=sys.argv[1].lower(); PY="../conv2/ocrenv/bin/python"
W=[w for w in json.load(open("nio_rest.json")) if op in w["op"].lower() and os.path.exists(f"wells/{w['api']}/done")]
def log(m): print(time.strftime("%H:%M:%S"),m,flush=True)
for w in W:
    a=w["api"]; txt=" ".join(" ".join(json.load(open(p))) for p in glob.glob(f"wells/{a}/f3_*.json")).lower().replace(" ","")
    if not txt: log(f"{a} no reports"); continue
    todo=[]
    if "liberty" in txt or "pressuresummary" in txt: todo.append(("lib",f"lib_{a}.json"))
    if "element" in txt or "zonereport" in txt: todo.append(("element",f"el_{a}.json"))
    if "halliburton" in txt or "stagesummary" in txt: todo.append(("hal2",f"hal2_{a}.json"))
    if "fts" in txt or "treatmentreport" in txt: todo.append(("ftsi",f"ftsi_{a}.json"))
    if "additivesamounts" in txt or op=="eog": todo.append(("eog",f"eog_{a}.json"))
    if "stimulationjobreport" in txt: todo.append(("camino",f"camino_{a}.json"))
    if "calfrac" in txt or "fracturingzone" in txt: todo.append(("calfrac",f"calfrac_{a}.json"))
    if not todo: log(f"{a} {w['name']}: no vendor keyword"); continue
    for rd,out in todo:
        if os.path.exists(out): log(f"{a} {rd} cached"); continue
        t=time.time(); r=subprocess.run([PY,f"{rd}.py",a],capture_output=True,text=True,timeout=3600)
        n=len(json.load(open(out))) if os.path.exists(out) else -1
        log(f"{a} {w['name']} {rd}: {n} ({int(time.time()-t)}s)")
log("done")
