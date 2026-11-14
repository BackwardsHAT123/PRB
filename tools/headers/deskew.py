import sys, os, glob
import numpy as np
from PIL import Image
from multiprocessing import Pool
Image.MAX_IMAGE_PIXELS = None
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
ANGLES = np.arange(-8.0, 8.01, 0.25)


def best_angle(im):
    w, h = im.size
    s = im.convert('L').resize((w // 4, h // 4), Image.BILINEAR)
    best, ba = -1, 0.0
    scores = []
    for a in ANGLES:
        r = s.rotate(float(a), resample=Image.BILINEAR, fillcolor=255)
        ink = 255 - np.asarray(r, dtype=np.float32)
        rows = ink.sum(axis=1)
        v = float(np.var(rows))
        scores.append(v)
        if v > best:
            best, ba = v, float(a)
    # refine around best
    for a in np.arange(ba - 0.25, ba + 0.26, 0.05):
        r = s.rotate(float(a), resample=Image.BILINEAR, fillcolor=255)
        v = float(np.var((255 - np.asarray(r, dtype=np.float32)).sum(axis=1)))
        if v > best:
            best, ba = v, float(a)
    return ba


def work(base):
    if os.path.exists(f'{out}/{base}_r270.png'):
        return base, None, None
    try:
        a0 = best_angle(Image.open(f'{src}/{base}_r0.png'))
        a90 = best_angle(Image.open(f'{src}/{base}_r90.png'))
        for rot, a in ((0, a0), (180, a0), (90, a90), (270, a90)):
            im = Image.open(f'{src}/{base}_r{rot}.png')
            r = im.rotate(a, resample=Image.BICUBIC, fillcolor=255)
            r.convert('1').save(f'{out}/{base}_r{rot}.png')
        return base, a0, a90
    except Exception as e:
        return base, 'ERR ' + str(e)[:60], None


if __name__ == '__main__':
    bases = sorted({os.path.basename(p).rsplit('_r', 1)[0] for p in glob.glob(src + '/*_r0.png')})
    with Pool(6) as pool, open(out + '/angles.csv', 'a') as f:
        for i, (b, a0, a90) in enumerate(pool.imap_unordered(work, bases, chunksize=2)):
            if a0 is not None:
                f.write(f'{b},{a0},{a90}\n')
                f.flush()
            if i % 50 == 0:
                print(i, len(bases), flush=True)
    print('done')
