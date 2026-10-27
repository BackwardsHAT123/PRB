"""Collect completion records for a list of wells: Treatments table, Completion (Form 3) page and PDFs, Sundry list; OCR the PDFs.
usage: fetch2.py bunch pause"""
import json,os,re,subprocess,sys,time
H=os.path.dirname(os.path.abspath(__file__)); os.chdir(H)
shard,ns=0,1; BUNCH=int(sys.argv[1]); PAUSE=int(sys.argv[2]); nb=0
OCRPY=os.path.join(H,"../conv2/ocrenv/bin/python")
wells=json.load(open("nio_rest.json"))
BASE="https://pipeline.wyo.gov/"
def log(m): print(time.strftime("%H:%M:%S"),m,flush=True)
fails=0
def get(url,out):
    global fails
    for t in range(3):
        p=subprocess.run(["curl","-sL","-m","120","-A","Mozilla/5.0","-o",out,"-w","%{http_code} %{size_download}",url],capture_output=True,text=True)
        code,size=(p.stdout.split()+["0","0"])[:2]
        if code=="200" and int(size)>200: fails=0; return True
        time.sleep(5*(t+1))
    fails+=1
    if fails>=4: log("STOP: repeated failures, site may be blocking"); open("STOP","w").write("blocked"); sys.exit(2)
    return False
for i,w in enumerate(wells):
    if i%ns!=shard: continue
    if os.path.exists("STOP"): log("STOP file present"); break
    a=w["api"]; n=str(int(a.split("-")[1]))+a.split("-")[2]
    d=os.path.join("wells",a); os.makedirs(d,exist_ok=True)
    done=os.path.join(d,"done")
    if os.path.exists(done): continue
    log(f"{a} {w['name']} ({w['op']})")
    for page,url in (("tret",f"wyotret.cfm?nAPI={n}"),("comp",f"wyocomp.cfm?nAPI={n}"),("sund",f"wyosund.cfm?napi={n}")):
        f=os.path.join(d,page+".html")
        if not os.path.exists(f): get(BASE+url,f); time.sleep(8)
    if not os.path.exists(os.path.join(d,"comp.html")):
        log("  comp page missing, skipping for now"); continue
    comp=open(os.path.join(d,"comp.html"),errors="replace").read()
    docs=sorted(set(re.findall(r"whatupcomps\.cfm\?nautonum=(\d+)",comp)))
    for nn in docs:
        pdf=os.path.join(d,f"f3_{nn}.pdf"); js=os.path.join(d,f"f3_{nn}.json")
        if not os.path.exists(pdf): get(BASE+f"whatups/whatupcomps.cfm?nautonum={nn}",pdf); time.sleep(8)
        if os.path.exists(pdf) and not os.path.exists(js):
            r=subprocess.run([OCRPY,"ocrpdf.py",pdf,js],capture_output=True,text=True)
            log(f"  OCR f3_{nn}: {'ok' if os.path.exists(js) else 'FAILED '+r.stderr[-120:]}")
    open(done,"w").write("ok")
    nb+=1
    if nb%BUNCH==0:
        log(f"bunch done ({nb} wells), pausing {PAUSE}s"); time.sleep(PAUSE)
log("shard finished")
