import sys, os, glob
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
src, out, hdr = sys.argv[1], sys.argv[2], int(sys.argv[3])
os.makedirs(out, exist_ok=True)
n = 0
for p in sorted(glob.glob(os.path.join(src, '*.tif'))):
    base = os.path.basename(p)[:-4]
    if os.path.exists(f'{out}/{base}_r0.png'):
        continue
    try:
        im = Image.open(p)
        w, h = im.size
        c = im.crop((0, 0, w, min(h, hdr))).convert('1')
        for rot in (0, 90, 180, 270):
            r = c if rot == 0 else c.rotate(rot, expand=True)
            r.save(f'{out}/{base}_r{rot}.png')
        n += 1
    except Exception as e:
        print('FAIL', base, str(e)[:80])
print('prepared', n)
