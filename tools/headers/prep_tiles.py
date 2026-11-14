import sys, os, re, glob, json
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
ocr_dir, img_dir, out = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
TBL = re.compile(r'RUN\s*NO|DEPTH.{0,3}(DRILLER|LOGGER)|LOG\w*\s*INTER|SINCE\s*CIRC|REC\.?\s*TEMP|BIT\s*SIZE|CASING|TYPE\s*FLUID|WITNESSED|RECORDED\s*BY|MAX\.?\s*REC')
SCALE = 2.5
TILE, OVER = 1800, 300
meta = {}


def load(p):
    rows = []
    for l in open(p, encoding='utf-8', errors='replace'):
        t = l.rstrip('\n').split('\t')
        if len(t) >= 6:
            try:
                rows.append((t[0], float(t[1]), float(t[2]), float(t[3]), float(t[4])))
            except ValueError:
                pass
    return rows


bases = sorted({os.path.basename(p).rsplit('_r', 1)[0] for p in glob.glob(ocr_dir + '/*_r0.tsv')})
nt = 0
for b in bases:
    best = None
    for rot in (0, 90, 180, 270):
        p = f'{ocr_dir}/{b}_r{rot}.tsv'
        if not os.path.exists(p):
            continue
        labs = [r for r in load(p) if TBL.search(r[0].upper()) and r[4] < 0.04]
        if best is None or len(labs) > len(best[1]):
            best = (rot, labs)
    rot, labs = best
    if len(labs) < 2:
        continue
    im = Image.open(f'{img_dir}/{b}_r{rot}.png')
    W, H = im.size
    ys = sorted(r[2] for r in labs)
    # trim outliers: use 5th..95th percentile span
    lo = ys[int(len(ys) * 0.05)]
    hi = max(r[2] + r[4] for r in labs if r[2] <= ys[min(len(ys) - 1, int(len(ys) * 0.95))])
    y0 = max(0, int((lo - 0.03) * H))
    y1 = min(H, int((hi + 0.03) * H))
    if y1 - y0 > 0.65 * H:
        y1 = y0 + int(0.65 * H)
    x = 0
    i = 0
    while x < W:
        x1 = min(W, x + TILE)
        t = im.crop((x, y0, x1, y1)).convert('L')
        t = t.resize((int(t.size[0] * SCALE), int(t.size[1] * SCALE)), Image.LANCZOS)
        name = f'{b}_r{rot}_t{i}'
        t.save(f'{out}/{name}.png')
        meta[name] = dict(base=b, rot=rot, x=x, y0=y0, w=x1 - x, h=y1 - y0, W=W, H=H)
        nt += 1
        i += 1
        if x1 >= W:
            break
        x = x1 - OVER
json.dump(meta, open(out + '/meta.json', 'w'))
print(len(bases), 'logs;', nt, 'tiles;', len({m['base'] for m in meta.values()}), 'logs with tables')
