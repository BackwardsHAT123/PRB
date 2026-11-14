import sys, os, re, csv, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['TBL_DIR'] = ''
import logread2 as L
from PIL import Image, ImageFilter
Image.MAX_IMAGE_PIXELS = None
P = os.environ['HDR_WORK']
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
# logs whose temperature is still blank or implausible after the first reading pass (readC.csv from run_headers.sh)
rd = list(csv.DictReader(open(os.environ.get('HDR_READ') or f'{P}/_work/readC.csv')))
wells = {r['log'].split('_')[0] for r in rd}
logs = [r['log'] for r in rd if not (r['TEMP'] and 120 <= int(r['TEMP']) <= 350)]
logs = sorted(set(logs))
print(len(wells), 'wells;', len(logs), 'logs to retry')
VARIANTS = [('a', 4.0, False), ('b', 3.0, True), ('c', 5.0, False)]
HALF = 1100
meta = {}
n = 0
nolabel = 0
for b in logs:
    cands = []
    for src in ('header_ocr_tbl', 'header_ocr_ds'):
        for rot in (0, 90, 180, 270):
            p = f'{P}/{src}/{b}_r{rot}.tsv'
            if not os.path.exists(p):
                continue
            for it in L.load(p):
                if L.LABELS['TEMP'].search(it['t'].upper()):
                    cands.append((rot, it))
    if not cands:
        nolabel += 1
        continue
    seen = set()
    k = 0
    for rot, it in cands:
        key = (rot, round(it['x'], 2), round(it['y'], 2))
        if key in seen or k >= 3:
            continue
        seen.add(key)
        im = Image.open(f'{P}/header_crops_ds/{b}_r{rot}.png')
        W, H = im.size
        ls = max(it['h'] * H, 28)
        long_side = max(it['w'] * W, it['h'] * H)
        cy = (it['y'] + it['h'] / 2) * H
        cx = (it['x'] + it['w'] / 2) * W
        y0, y1 = int(max(0, cy - 1.6 * ls)), int(min(H, cy + 1.6 * ls))
        x0, x1 = int(max(0, cx - HALF)), int(min(W, cx + HALF))
        base = im.crop((x0, y0, x1, y1)).convert('L')
        for tag, sc, bold in VARIANTS:
            t = base
            if bold:
                t = t.point(lambda v: 255 - v).filter(ImageFilter.MaxFilter(3)).point(lambda v: 255 - v)
            t = t.resize((int(t.size[0] * sc), int(t.size[1] * sc)), Image.LANCZOS)
            name = f'{b}_r{rot}_{k}{tag}'
            t.save(f'{out}/{name}.png')
            meta[name] = dict(base=b, rot=rot, x0=x0, y0=y0, w=x1 - x0, h=y1 - y0, label=it['t'], lx=cx, ly=cy, lh=ls)
            n += 1
        k += 1
json.dump(meta, open(out + '/meta.json', 'w'))
print(n, 'strip images;', nolabel, 'logs had no temp label anywhere')
