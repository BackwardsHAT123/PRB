"""Full directional-survey pipeline for wells that still have straight-line paths.

For each well: list its survey documents on the WOGCC site, read the text surveys and OCR the scanned PDFs
(measured depth, inclination, azimuth), compute the path by minimum curvature from the surface location, and accept it only
if it ends within tolerance of the header bottom hole (a near miss is shifted to end on it and flagged). One line per well goes
to survey_out.jsonl; the stations read go to survey_stations.jsonl.

    SURVEY_OUT=out.jsonl python3 survey_pipeline.py targets.json [workers]
"""
import datetime, io, json, math, os, re, subprocess, sys, time, zipfile
import multiprocessing as mp

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.environ.get("SURVEY_OUT", os.path.join(HERE, "survey_out.jsonl"))
STOP = os.path.join(HERE, "SURVEY_STOP")
FT = 0.3048
CONTROL = "545589"
RM = "https://pipeline.wyo.gov/rm_Directionalapi.cfm?nApi={k}"
DOC = "https://pipeline.wyo.gov/whatups/{kind}.cfm?nautonum={n}"
ZIP = "https://pipeline.wyo.gov/whatups/whatupDirDownLoad.cfm?napi={k}"
GAP = 3.0           # seconds between state requests, across all workers
SCALE = 2.0
MAX_PAGES = 90


def curl(url, tmp, binary=True):
    for t in range(4):
        if os.path.exists(STOP):
            raise SystemExit("stopped")
        p = subprocess.run(["curl", "-sL", "-m", "120", "-A", "Mozilla/5.0", "-w", "%{http_code}", url, "-o", tmp],
                           capture_output=True, text=True, timeout=150)
        if p.stdout.strip() == "200" and os.path.getsize(tmp) > 0:
            b = open(tmp, "rb").read()
            return b if binary else b.decode("latin-1")
        time.sleep(4 * (t + 1))
    return None


def text_stations(txt):
    """(md, inc, azi) from a text survey: any line whose first three numbers look like depth, inclination, azimuth."""
    from parse_ocr import screen
    rows = []
    for ln in re.split(r"[\r\n]+", txt):
        toks = [t for t in re.split(r"[\t, ]+", ln.strip()) if t]
        nums = []
        for t in toks:
            try:
                nums.append(float(t.replace(",", "")))
            except ValueError:
                break
        if len(nums) >= 4 and nums[0] >= 0 and 0 <= nums[1] <= 125 and 0 <= nums[2] <= 360.5:
            rows.append((0, nums[0], nums[1], nums[2]))
    return screen(rows)


def ocr_stations(pdf_bytes, ocr):
    import numpy as np
    import pypdfium2 as pdfium
    from parse_ocr import extract2, screen
    pdf = pdfium.PdfDocument(pdf_bytes)
    pages = []
    for i in range(min(len(pdf), MAX_PAGES)):
        img = np.array(pdf[i].render(scale=SCALE).to_pil().convert("RGB"))
        res, _ = ocr(img)
        pages.append([[[[float(x) for x in p] for p in b], t, float(c)] for b, t, c in (res or [])])
    return screen(extract2(pages)), len(pdf)


def evaluate(st, d):
    """Path by minimum curvature from the header surface location; try the likely north references and keep the best."""
    from parse_ocr import mincurv
    if len(st) < 15:
        return None
    mc = mincurv(st)
    shl, bhl = d["shl"], d["bhl"]
    k = math.cos(math.radians(shl[1])) * 111195
    hn, he = (bhl[1] - shl[1]) * 111195 / FT, (bhl[0] - shl[0]) * k / FT
    disp = math.hypot(hn, he)
    gam = (shl[0] + 105.1667) * math.sin(math.radians(shl[1]))
    best = None
    for name, rot in (("true", 0.0), ("grid", gam), ("grid-", -gam), ("mag+", 8.7), ("mag-", -8.7)):
        r = math.radians(rot)
        n_, e_ = mc[-1]
        miss = math.hypot(n_ * math.cos(r) - e_ * math.sin(r) - hn, n_ * math.sin(r) + e_ * math.cos(r) - he) * FT
        if best is None or miss < best[0]:
            best = (miss, name, r)
    miss, name, r = best
    pts = []
    for n_, e_ in mc:
        N, E = n_ * math.cos(r) - e_ * math.sin(r), n_ * math.sin(r) + e_ * math.cos(r)
        lat = shl[1] + N * FT / 111195
        pts.append([shl[0] + E * FT / (111195 * math.cos(math.radians(lat))), lat])
    gaps = max(b[0] - a[0] for a, b in zip(st, st[1:]))
    tol1 = max(60.0, 0.02 * disp * FT)
    warp = False
    if tol1 < miss <= max(250.0, 0.05 * disp * FT):      # near miss: shift the path linearly so it ends on the header bottom hole
        warp = True
        tl = [0.0]
        for a, b in zip(pts, pts[1:]):
            tl.append(tl[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        dx, dy = bhl[0] - pts[-1][0], bhl[1] - pts[-1][1]
        pts = [[x + dx * t / (tl[-1] or 1), y + dy * t / (tl[-1] or 1)] for (x, y), t in zip(pts, tl)]
    return {"st": [[round(a, 1), round(b, 2), round(c, 2)] for a, b, c in st], "warp": warp, "miss_m": round(miss, 1), "ref": name,
            "disp_ft": round(disp), "stations": len(st), "last_md": st[-1][0], "max_gap": round(gaps), "pts": pts}


def decimate(pts, tol_m=15.0):
    def dp(p, e):
        if len(p) < 3:
            return p
        (x1, y1), (x2, y2) = p[0], p[-1]
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1e-12
        m, kk = 0, 0
        for n in range(1, len(p) - 1):
            dd = abs(dy * (p[n][0] - x1) - dx * (p[n][1] - y1)) / L
            if dd > m:
                m, kk = dd, n
        return dp(p[:kk + 1], e)[:-1] + dp(p[kk:], e) if m > e else [p[0], p[-1]]
    out = dp(pts, tol_m / 111195)
    return [[round(x, 5), round(y, 5)] for x, y in out]


_ocr = None
_last = [0.0]


def pace(w):
    wait = GAP * w - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()


def process(args):
    global _ocr
    d, pk, workers = args
    api = d["a"]
    res = {"api": api, "name": d["n"], "when": str(datetime.date.today())}
    try:
        if os.path.exists(STOP):
            return None
        if _ocr is None:
            os.environ["OMP_NUM_THREADS"] = "1"
            from rapidocr_onnxruntime import RapidOCR
            _ocr = RapidOCR()
        tmp = os.path.join(HERE, f"dl_{os.getpid()}.tmp")
        pace(workers)
        page = curl(RM.format(k=pk), tmp, binary=False)
        if page is None:
            res["status"] = "error"; return res
        docs = []
        for m in re.finditer(r"whatupDir(2?)\.cfm\?nautonum=(\d+)", page):
            docs.append(("whatupDir" + m.group(1), m.group(2)))
        docs = list(dict.fromkeys(docs))
        has_text = "whatupDirDownLoad" in page
        if not docs and not has_text:
            if "No Directional" in page:
                res["status"] = "none"; return res
            pace(workers)                      # blank page: is it the site or this well?
            ctl = curl(RM.format(k=CONTROL), tmp, binary=False) or ""
            if "whatupDir" not in ctl:
                open(STOP, "w").write("blocked")
                res["status"] = "blocked"; return res
            res["status"] = "none"; return res
        cands = []
        if has_text:
            pace(workers)
            z = curl(ZIP.format(k=pk), tmp)
            if z and z[:2] == b"PK":
                try:
                    zf = zipfile.ZipFile(io.BytesIO(z))
                    for nm in zf.namelist():
                        ev = evaluate(text_stations(zf.read(nm).decode("latin-1")), d)
                        if ev:
                            ev["src"] = "text:" + nm; cands.append(ev)
                except Exception:
                    pass
        tol = lambda ev: max(60.0, 0.02 * ev["disp_ft"] * FT)
        for kind, n in docs:
            if cands and min(c["miss_m"] for c in cands) <= 25:
                break
            pace(workers)
            b = curl(DOC.format(kind=kind, n=n), tmp)
            if not b:
                continue
            try:
                if b[:4] == b"%PDF":
                    st, npg = ocr_stations(b, _ocr)
                    ev = evaluate(st, d); src = f"ocr:{kind}:{n}:{npg}p"
                elif len(b) > 2000:
                    ev = evaluate(text_stations(b.decode("latin-1")), d); src = f"text:{kind}:{n}"
                else:
                    continue
            except Exception as e:
                res.setdefault("errors", []).append(str(e)[:80]); continue
            if ev:
                ev["src"] = src; cands.append(ev)
        if not cands:
            res["status"] = "unreadable"; return res
        best = min(cands, key=lambda c: c["miss_m"])
        with open(os.path.join(HERE, "survey_stations.jsonl"), "a") as sf:
            sf.write(json.dumps({"api": api, "src": best["src"], "st": best.get("st")}) + "\n")
        res.update({k: best[k] for k in ("miss_m", "ref", "disp_ft", "stations", "last_md", "max_gap", "src")})
        res["tried"] = len(cands)
        res["warp"] = best["warp"]
        if best["miss_m"] <= tol(best) or best["warp"]:
            res["status"] = "ok"; res["path"] = decimate([list(d["shl"])] + best["pts"][1:])
        else:
            res["status"] = "rejected"
        return res
    except SystemExit:
        return None
    except Exception as e:
        res["status"] = "error"; res["error"] = str(e)[:120]
        return res


def main():
    targets = json.load(open(sys.argv[1]))          # list of {"d": well record, "pk": pkey}
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    done = set()
    if os.path.exists(OUT):
        for ln in open(OUT):
            r = json.loads(ln)
            if r["status"] in ("ok", "rejected", "none", "unreadable"):
                done.add(r["api"])
    todo = [(t["d"], t["pk"], workers) for t in targets if t["d"]["a"] not in done]
    print(len(todo), "wells to process with", workers, "workers", flush=True)
    with mp.Pool(workers) as pool, open(OUT, "a") as out:
        for n, r in enumerate(pool.imap_unordered(process, todo), 1):
            if r is None:
                continue
            out.write(json.dumps(r) + "\n"); out.flush()
            print(n, r["api"], r.get("status"), r.get("miss_m", ""), r.get("src", ""), flush=True)
            if r.get("status") == "blocked":
                print("THROTTLED: state site is blocking requests", flush=True)
                pool.terminate(); break
    print("done", flush=True)


if __name__ == "__main__":
    main()
