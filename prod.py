"""Monthly production from the WOGCC comma-delimited export (one request per well), merged across reservoirs."""
import collections, datetime, json, os, re, subprocess, time

EXPORT = "https://pipeline.wyo.gov/DWPRODPIMS.cfm?uniquenumber={k}&Oops=OkieDokie&oneapi={k}&GoGet=8"
CONTROL = "545589"          # a well that always has production, used to tell "no data" from "blocked"


def fetch(pkey, tmp="prod.tmp"):
    """CSV text, '' when the well has no production, None when the request keeps failing."""
    for t in range(4):
        p = subprocess.run(["curl", "-sL", "-m", "90", "-A", "Mozilla/5.0", "-w", "%{http_code}", EXPORT.format(k=pkey), "-o", tmp],
                           capture_output=True, text=True, timeout=120)
        if p.stdout.strip() == "200":
            b = open(tmp, "rb").read().decode("latin-1")
            if b.startswith("Api_Res"):
                return b
            if len(b) < 400:
                return ""
        time.sleep(4 * (t + 1))
    return None


def parse(txt):
    mon = collections.defaultdict(lambda: [0, 0, 0])
    dys = collections.defaultdict(int)      # days on production per month (the largest across reservoirs)
    for r in re.split(r"[\r\n]+", txt)[1:]:
        c = r.split(",")
        if len(c) < 6:
            continue
        try:
            m, y = c[1].split("/")
            v = [int(float(x or 0)) for x in c[2:5]]
        except ValueError:
            continue
        k = f"{y}-{m}"
        for i in range(3):
            mon[k][i] += v[i]
        try:
            dys[k] = max(dys[k], int(float(c[5] or 0)))
        except (ValueError, IndexError):
            pass
    nz = [k for k in sorted(mon) if any(mon[k])]
    if not nz:
        return None
    ks, (y, m), (ey, em) = [], map(int, nz[0].split("-")), map(int, nz[-1].split("-"))
    y, m = int(y), int(m)
    while (y, m) <= (int(ey), int(em)):
        ks.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    z = [0, 0, 0]
    return {"s": nz[0], "o": [mon.get(k, z)[0] for k in ks], "g": [mon.get(k, z)[1] for k in ks], "w": [mon.get(k, z)[2] for k in ks],
            "d": [dys.get(k, 0) for k in ks[:8]]}      # days on production, first eight months only


def _curl(url, tmp="prod2.tmp"):
    for t in range(4):
        p = subprocess.run(["curl", "-sL", "-m", "90", "-A", "Mozilla/5.0", "-w", "%{http_code}", url, "-o", tmp], capture_output=True, text=True, timeout=120)
        if p.stdout.strip() == "200":
            return open(tmp, "rb").read().decode("latin-1")
        time.sleep(4 * (t + 1))
    return None


def _cells(page):
    page = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    import html as _h
    return [_h.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", page, flags=re.S)]


def fetch_wyoprod(pkey, gap=3):
    """Fallback for wells whose comma-delimited export is empty: the per-reservoir 'wyoprod' tables (oil, gas, water by month)
    plus the cumulative totals from the reservoir listing. Returns (series dict or None, cumulative [oil, gas, water] or None)."""
    lst = _curl(f"https://pipeline.wyo.gov/reservoir.cfm?nAPINO={pkey}")
    if lst is None:
        return None, None
    codes = sorted(set(re.findall(r"wyoprod\.cfm\?[^\"']*nApino=(\d+)", lst, flags=re.I)))
    m = re.search(r"Cumulative Production.*?Oil\s*([\d,]+)\s*BBLS.*?Gas\s*([\d,]+)\s*MCF.*?Water\s*([\d,]+)\s*BBLS", re.sub(r"<[^>]+>", " ", lst), flags=re.S)
    cum = [int(x.replace(",", "")) for x in m.groups()] if m else None
    mon = collections.defaultdict(lambda: [0, 0, 0])
    num = lambda x: int(float(x.replace(",", ""))) if re.fullmatch(r"-?[\d,]*\.?\d+", x or "") else 0
    for code in codes:
        time.sleep(gap)
        pg = _curl(f"https://pipeline.wyo.gov/wyoprod.cfm?UserOk=Y&oops=ID26069&nApino={code}")
        if pg is None:
            return None, cum
        c = _cells(pg)
        for i, x in enumerate(c):
            if re.fullmatch(r"(19|20)\d\d", x) and i + 1 < len(c) and c[i + 1] == "Oil BBLS":
                year = x
                for lab, idx in (("Oil BBLS", 0), ("Gas MCF", 1), ("Water BBLS", 2)):
                    try:
                        j = c.index(lab, i + 1, i + 70)
                    except ValueError:
                        continue
                    for mth in range(12):
                        mon[f"{year}-{mth + 1:02d}"][idx] += num(c[j + 1 + mth])
    nz = [k for k in sorted(mon) if any(mon[k])]
    if not nz:
        return None, cum
    ks, y, mm = [], int(nz[0][:4]), int(nz[0][5:])
    ey, em = int(nz[-1][:4]), int(nz[-1][5:])
    while (y, mm) <= (ey, em):
        ks.append(f"{y}-{mm:02d}")
        mm += 1
        if mm > 12:
            y, mm = y + 1, 1
    z = [0, 0, 0]
    return {"s": nz[0], "o": [mon.get(k, z)[0] for k in ks], "g": [mon.get(k, z)[1] for k in ks], "w": [mon.get(k, z)[2] for k in ks]}, cum


def refresh(path, items, log, max_per_run=60, stale_days=25, gap=4):
    """items: [(api, pkey)]. Fetch wells that have no data yet first, then the stalest, up to max_per_run."""
    res = json.load(open(path)) if os.path.exists(path) else {}
    today = datetime.date.today()
    def age(api):
        u = res.get(api, {}).get("u")
        return 10 ** 6 if not u else (today - datetime.date.fromisoformat(u)).days
    due = sorted((it for it in items if age(it[0]) >= stale_days), key=lambda it: -age(it[0]))[:max_per_run]
    done = 0
    for api, pk in due:
        txt = fetch(pk)
        if txt is None:
            if not fetch(CONTROL):
                log("production: export blocked (control well failed too); stopping")
                break
            continue
        d = parse(txt) if txt else None
        if d is None:      # empty export: fall back to the per-reservoir tables
            d, _cum = fetch_wyoprod(pk)
        res[api] = dict(d or {"none": 1}, u=str(today))
        done += 1
        time.sleep(gap)
    json.dump(res, open(path, "w"), separators=(",", ":"))
    log(f"production: refreshed {done} of {len(due)} due wells ({len(res)} wells on file)")
    return res
