"""retry.py -> re-pull Form 3 PDFs that came back as tiny error pages (or never downloaded), then OCR them."""
import glob,os,re,subprocess,sys,time
OCRPY="../conv2/ocrenv/bin/python"; BASE="https://pipeline.wyo.gov/whatups/whatupcomps.cfm?nautonum="
for d in sorted(glob.glob("wells/*/")):
    if not os.path.exists(d+"done") or not os.path.exists(d+"comp.html"): continue
    docs=sorted(set(re.findall(r"whatupcomps\.cfm\?nautonum=(\d+)",open(d+"comp.html",errors="replace").read())))
    for nn in docs:
        pdf=d+f"f3_{nn}.pdf"; js=d+f"f3_{nn}.json"
        if os.path.exists(pdf) and os.path.getsize(pdf)>=2000 and os.path.exists(js): continue
        for t in range(3):
            p=subprocess.run(["curl","-sL","-m","180","-A","Mozilla/5.0","-o",pdf,"-w","%{http_code} %{size_download}",BASE+nn],capture_output=True,text=True)
            if os.path.exists(pdf) and os.path.getsize(pdf)>=2000: break
            time.sleep(10*(t+1))
        ok=os.path.exists(pdf) and os.path.getsize(pdf)>=2000
        print(d,nn,"pdf",os.path.getsize(pdf) if os.path.exists(pdf) else 0,flush=True)
        if ok:
            if os.path.exists(js): os.remove(js)
            subprocess.run([OCRPY,"ocrpdf.py",pdf,js],capture_output=True,text=True)
            print("  OCR",os.path.exists(js),flush=True)
        time.sleep(8)
