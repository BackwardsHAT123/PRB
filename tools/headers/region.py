import sys, os, re, csv, json, statistics
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
P = os.environ['HDR_WORK']
readcsv, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
TBL = re.compile(r'RUN\s*NO|DEPTH|LOG\w*\s*INTER|INTERVAL|SINCE\s*CIRC|CIRC|REC\.?\s*TEMP|BIT\s*SIZE|CASING|TYPE\s*FLUID|WITNESSED|RECORDED\s*BY|MAX\.?\s*REC|EQUIP|LOCATION|MEAS\.?\s*TEMP|@\s*BHT|SOURCE\s*OF|VISC|DENS|FLUID\s*LOSS')
SCALE = 3.0
rd = list(csv.DictReader(open(readcsv)))
sel = [r['log'] for r in rd if sum(1 for f in ('BLI', 'CIRC', 'TEMP') if r[f]) <= 1]
print(len(sel), 'logs selected (<=1 table field read)')
n = 0
meta = {}
for b in sel:
    best = None
    for rot in (0, 90, 180, 270):
        p = f'{P}/header_ocr_ds/{b}_r{rot}.tsv'
        if not os.path.exists(p):
            continue
        its = []
        for l in open(p, encoding='utf-8', errors='replace'):
            t = l.rstrip('\n').split('\t')
            if len(t) >= 6 and TBL.search(t[0].upper()):
                try:
                    its.append((float(t[1]), float(t[2]), float(t[3]), float(t[4])))
                except ValueError:
                    pass
        if best is None or len(its) > len(best[1]):
            best = (rot, its)
    rot, its = best
    if len(its) < 4:
        continue
    mx = statistics.median(i[0] + i[2] / 2 for i in its)
    my = statistics.median(i[1] + i[3] / 2 for i in its)
    sx = max(0.12, statistics.median(abs(i[0] + i[2] / 2 - mx) for i in its) * 3)
    sy = max(0.12, statistics.median(abs(i[1] + i[3] / 2 - my) for i in its) * 3)
    keep = [i for i in its if abs(i[0] + i[2] / 2 - mx) <= sx and abs(i[1] + i[3] / 2 - my) <= sy]
    if len(keep) < 3:
        continue
    x0 = min(i[0] for i in keep); x1 = max(i[0] + i[2] for i in keep)
    y0 = min(i[1] for i in keep); y1 = max(i[1] + i[3] for i in keep)
    im = Image.open(f'{P}/header_crops_ds/{b}_r{rot}.png')
    W, H = im.size
    padx, pady = 0.06, 0.04
    box = (int(max(0, x0 - padx) * W), int(max(0, y0 - pady) * H), int(min(1, x1 + padx) * W), int(min(1, y1 + pady) * H))
    # widen to include value cells next to the labels
    c = im.crop(box).convert('L')
    for k, ang in ((0, 0), (90, 90), (270, -90)):
        v = c if ang == 0 else c.rotate(ang, expand=True)
        v = v.resize((int(v.size[0] * SCALE), int(v.size[1] * SCALE)), Image.LANCZOS)
        if max(v.size) > 12000:
            f = 12000 / max(v.size)
            v = v.resize((int(v.size[0] * f), int(v.size[1] * f)), Image.LANCZOS)
        v.save(f'{out}/{b}_r{k}.png')
        n += 1
    meta[b] = dict(rot=rot, box=box, size=c.size)
json.dump(meta, open(out + '/meta.json', 'w'))
print(n, 'region images for', len(meta), 'logs')
