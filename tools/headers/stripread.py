import sys, os, json, csv, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logread2 as L
P = os.environ['HDR_WORK']
meta = json.load(open(f'{P}/header_strips/meta.json'))
out = sys.argv[1]
fill = collections.defaultdict(collections.Counter)
for name, m in meta.items():
    p = f'{P}/header_strips_ocr/{name}.tsv'
    if not os.path.exists(p):
        continue
    left, right = [], []
    for l in open(p, encoding='utf-8', errors='replace'):
        t = l.rstrip('\n').split('\t')
        if len(t) < 6:
            continue
        try:
            xn, yn, wn, hn = map(float, t[1:5])
        except ValueError:
            continue
        cx = m['x0'] + (xn + wn / 2) * m['w']
        cy = m['y0'] + (yn + hn / 2) * m['h']
        if abs(cy - m['ly']) > 0.9 * max(hn * m['h'], 28) + 6:
            continue
        if not re.search(r'\d', t[0]):
            continue
        # skip the label's own text
        if abs(cx - m['lx']) < 40 and t[0].upper()[:6] == m['label'].upper()[:6]:
            continue
        (left if cx < m['lx'] else right).append((abs(cx - m['lx']), t[0]))
    left.sort()
    right.sort()
    cand = dict(rot=m['rot'], label=m['label'], inner=[], inner_txt=[], left=[t for _, t in left], right=[t for _, t in right], conf=1.0)
    api_suffix = str(int(m['base'].split('_')[0].split('-')[2]))
    v = L.parse_field(m['fld'], [cand], api_suffix)
    for val, n in v.items():
        fill[(m['base'], m['fld'])][val] += n
rows = []
for (b, f), c in fill.items():
    val, n = c.most_common(1)[0]
    rows.append((b, f, val, n))
with open(out, 'w', newline='') as w:
    cw = csv.writer(w)
    cw.writerow(['log', 'field', 'value', 'votes'])
    cw.writerows(rows)
print(len(rows), 'strip fills;', collections.Counter(r[1] for r in rows))
