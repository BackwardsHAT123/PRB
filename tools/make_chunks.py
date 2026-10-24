"""Targets for the survey pipeline: wells in the chosen operators that still have a straight-line path, shuffled into chunks."""
import json,random,collections,sys
size=int(sys.argv[1]) if len(sys.argv)>1 else 100
keep=("Ballard Petroleum","EOG","Devon","Peak Powder River")
S=open("prb/index.html").read(); i=S.index("const D=")+8; D=json.loads(S[i:S.index(";\nconst GRID",i)])
H=json.load(open("prb/data/headers.json")); pk={v["API Number"]:k for k,v in H.items()}
t=[{"d":{"a":d["a"],"n":d["n"],"shl":d["shl"],"bhl":d["bhl"],"oc":d["oc"]},"pk":pk[d["a"]]} for d in D if d["oc"] in keep and not d.get("fx") and not d.get("pr") and len(d["ln"])<=2 and d["bhl"] and d["a"] in pk]
random.seed(7); random.shuffle(t)
for n,c in enumerate([t[i:i+size] for i in range(0,len(t),size)],1):
    json.dump(c,open(f"targets_chunk{n}.json","w")); print("chunk",n,len(c),dict(collections.Counter(x["d"]["oc"] for x in c)))
