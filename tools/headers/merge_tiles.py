import sys, os, json, collections
tile_ocr, meta_p, out = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
meta = json.load(open(meta_p))
groups = collections.defaultdict(list)
for name, m in meta.items():
    groups[(m['base'], m['rot'])].append(name)
n = 0
for (b, rot), names in groups.items():
    rows = []
    for name in sorted(names):
        m = meta[name]
        p = f'{tile_ocr}/{name}.tsv'
        if not os.path.exists(p):
            continue
        for l in open(p, encoding='utf-8', errors='replace'):
            t = l.rstrip('\n').split('\t')
            if len(t) < 6:
                continue
            try:
                xn, yn, wn, hn, c = map(float, t[1:6])
            except ValueError:
                continue
            x = (m['x'] + xn * m['w']) / m['W']
            y = (m['y0'] + yn * m['h']) / m['H']
            w = wn * m['w'] / m['W']
            h = hn * m['h'] / m['H']
            rows.append((t[0], x, y, w, h, c))
    # drop duplicates from tile overlap
    seen = []
    uniq = []
    for r in rows:
        dup = False
        for s in seen:
            if s[0] == r[0] and abs(s[1] - r[1]) < 0.004 and abs(s[2] - r[2]) < 0.004:
                dup = True
                break
        if not dup:
            seen.append(r)
            uniq.append(r)
    with open(f'{out}/{b}_r{rot}.tsv', 'w') as w:
        for r in uniq:
            w.write('%s\t%.4f\t%.4f\t%.4f\t%.4f\t%.2f\n' % r)
    n += 1
print('merged', n, 'table files')
