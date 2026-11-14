import sys, os, json, csv, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logread2 as L
P = os.environ['HDR_WORK']
meta = json.load(open(f'{P}/temp_strips/meta.json'))
out = sys.argv[1]
votes = collections.defaultdict(collections.Counter)
raw = collections.defaultdict(list)
for name, m in meta.items():
    p = f'{P}/temp_strips_ocr/{name}.tsv'
    if not os.path.exists(p):
        continue
    sc = {'a': 4.0, 'b': 3.0, 'c': 5.0}[name[-1]]
    left, right, allit = [], [], []
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
        if re.search(r'\d', t[0]) and not (abs(cx - m['lx']) < 30 and abs(cy - m['ly']) < 30):
            allit.append((cx, cy, t[0]))
        if abs(cy - m['ly']) > 1.0 * m['lh'] + 8:
            continue
        if not re.search(r'\d', t[0]):
            continue
        if abs(cx - m['lx']) < 30 and re.search(r'REC|TEMP', t[0].upper()):
            continue
        (left if cx < m['lx'] else right).append((abs(cx - m['lx']), t[0]))
    left.sort(); right.sort()
    # column mode: values stacked above/below the label in the same column
    col = []
    for cx, cy, tx in allit:
        dx, dy = abs(cx - m['lx']), cy - m['ly']
        if dx <= max(m['lh'], 60) * 1.0 and 0.4 * m['lh'] <= abs(dy) <= 8 * m['lh'] and re.search(r'\d{3}\s*[°º˚oO0]?\s*(?:D?EG\.?\s*)?F', tx, re.I):
            col.append((abs(dy), tx))
    col.sort()
    for side, items in (('L', left), ('R', right), ('C', col)):
        toks = []
        for _, s in items[:3]:
            toks += L.ints(s)
        good = [v for v in toks if 120 <= v <= 350]
        if good:
            votes[m['base']][good[0]] += 1
            raw[m['base']].append((name, side, good[0]))
rows = []
for b, c in votes.items():
    (v, n), = c.most_common(1)
    tot = sum(c.values())
    rows.append((b, v, n, tot, json.dumps(dict(c.most_common(3)))))
with open(out, 'w', newline='') as w:
    cw = csv.writer(w)
    cw.writerow(['log', 'value', 'votes', 'total_reads', 'alts'])
    cw.writerows(rows)
print(len(rows), 'logs with a plausible temperature;', sum(1 for r in rows if r[2] >= 2), 'with >=2 agreeing reads')
