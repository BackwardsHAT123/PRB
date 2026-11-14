import sys, os, glob, re, csv, collections
ocr_dir, out = sys.argv[1], sys.argv[2]
KW = ['ELEV', 'KB', 'KELLY', 'BOTTOM', 'LOGGED', 'INTERVAL', 'CIRC', 'TEMP', 'BHT', 'DEPTH', 'DRILLER', 'RUN', 'COUNTY', 'FIELD', 'WELL', 'COMPANY', 'MUD', 'CASING', 'BIT', 'DATE', 'WITNESS', 'MAX']
VEND = {
    'SCHLUMBERGER': ['SCHLUMBERGER', 'SCHLUM'],
    'HALLIBURTON': ['HALLIBURTON', 'HALLIB'],
    'BAKER': ['BAKER', 'ATLAS', 'BAKER HUGHES'],
    'WEATHERFORD': ['WEATHERFORD'],
    'DRESSER': ['DRESSER'],
    'GEARHART': ['GEARHART'],
    'WELEX': ['WELEX'],
    'COMPUTALOG': ['COMPUTALOG'],
    'PETRO': ['PETROLOG', 'PETRO-LOG'],
    'NABORS': ['NABORS'],
    'CORE LAB': ['CORE LAB'],
    'MCCULLOUGH': ['MCCULLOUGH'],
    'WESTERN': ['WESTERN ATLAS'],
    'EXLOG': ['EXLOG'],
    'PROBE': ['PROBE'],
    'SPERRY': ['SPERRY'],
}
def load(p):
    rows = []
    for l in open(p, encoding='utf-8', errors='replace'):
        t = l.rstrip('\n').split('\t')
        if len(t) >= 6:
            rows.append((t[0], float(t[1]), float(t[2]), float(t[3]), float(t[4]), float(t[5])))
    return rows
bases = sorted({os.path.basename(p).rsplit('_r', 1)[0] for p in glob.glob(ocr_dir + '/*_r0.tsv')})
res = []
for b in bases:
    best = (-1, None)
    scores = {}
    for rot in (0, 90, 180, 270):
        p = f'{ocr_dir}/{b}_r{rot}.tsv'
        if not os.path.exists(p):
            continue
        rows = load(p)
        txt = ' '.join(r[0].upper() for r in rows)
        s = sum(txt.count(k) for k in KW)
        scores[rot] = s
        if s > best[0]:
            best = (s, rot, txt, len(rows))
    s, rot, txt, nl = best
    vend = [v for v, ks in VEND.items() if any(k in txt for k in ks)]
    res.append((b, rot, s, nl, ';'.join(vend), scores))
with open(out, 'w', newline='') as w:
    cw = csv.writer(w)
    cw.writerow(['log', 'best_rot', 'kw_score', 'lines', 'vendors', 'scores'])
    for r in res:
        cw.writerow(r)
print(len(res), 'logs')
print('rot', collections.Counter(r[1] for r in res))
print('vendor', collections.Counter(r[4] or 'UNKNOWN' for r in res).most_common(15))
low = [r for r in res if r[2] < 8]
print('low kw score (<8):', len(low))
