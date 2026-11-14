import sys, os, re, csv, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['TBL_DIR'] = ''
import logread2 as L
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
P = os.environ['HDR_WORK']
readcsv, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
rd = {r['log']: r for r in csv.DictReader(open(readcsv))}
SCALE = 3.0
HALF = 1500
meta = {}
n = 0
for b, r in rd.items():
    for fld in ('BLI', 'CIRC', 'TEMP'):
        if r[fld]:
            continue
        cands = []
        for src in ('header_ocr_tbl', 'header_ocr_ds'):
            for rot in (0, 90, 180, 270):
                p = f'{P}/{src}/{b}_r{rot}.tsv'
                if not os.path.exists(p):
                    continue
                for it in L.load(p):
                    up = it['t'].upper()
                    if it['h'] < 0.04 and L.LABELS[fld].search(up) and not (fld == 'BLI' and 'TOP' in up):
                        cands.append((it['c'], rot, it))
        seen = set()
        k = 0
        for c, rot, it in sorted(cands, key=lambda t: -t[0]):
            key = (rot, round(it['y'], 2))
            if key in seen or k >= 2:
                continue
            seen.add(key)
            ip = f'{P}/header_crops_ds/{b}_r{rot}.png'
            im = Image.open(ip)
            W, H = im.size
            cy = (it['y'] + it['h'] / 2) * H
            lh = max(it['h'] * H, 28)
            y0, y1 = int(max(0, cy - 1.5 * lh)), int(min(H, cy + 1.5 * lh))
            lx = (it['x'] + it['w'] / 2) * W
            x0, x1 = int(max(0, lx - HALF)), int(min(W, lx + HALF))
            t = im.crop((x0, y0, x1, y1)).convert('L')
            t = t.resize((int(t.size[0] * SCALE), int(t.size[1] * SCALE)), Image.LANCZOS)
            name = f'{b}_r{rot}_{fld}_{k}'
            t.save(f'{out}/{name}.png')
            meta[name] = dict(base=b, rot=rot, fld=fld, x0=x0, y0=y0, w=x1 - x0, h=y1 - y0, label=it['t'], lx=lx, ly=cy)
            k += 1
            n += 1
json.dump(meta, open(out + '/meta.json', 'w'))
print(n, 'strips')
