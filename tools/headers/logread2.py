"""Generic row-geometry header reader for OCR'd scanned logs.
For each of the 4 rotations, find label items, then collect numeric items on the same row (either side),
nearest first. Vote across rotations."""
import sys, os, re, glob, csv, collections, json

class _Bli:
    INT = re.compile(r'(INT|NTER|ERVA|NERV|MERV)')
    LOG = re.compile(r'(LOG|LAG|LOCC|LOGG)')
    TOP = re.compile(r'(^|\W)(TOP|TCP|CP|OP|TOR|OPE)\b')
    BOT = re.compile(r'(^|\W)(B|3)[A-Z0-9]{1,5}(\W|$)')

    def search(self, up):
        if not (self.INT.search(up) and self.LOG.search(up)):
            return None
        if self.TOP.search(up) or 'TOP' in up:
            return None
        return self.BOT.search(up) or re.search(r'BOTTOM|BTM|BOTOM|BOSOM', up)


LABELS = {
    'BLI': _Bli(),
    'CIRC': re.compile(r'(SINCE\s*C)|(TINE\s*SINCE)|(IME\s*SINCE)|(TIME\s*CIRC)|(CIRC\w*\s*TIME)'),
    'TEMP': re.compile(r'(MA[XK]|[VW7]X|V[XK])\.?\s*[RP]E[CO]\b|MA[XK]\.?\s*TEMP|MA[XK]\w*\s*RECORD|[RP]EC\.?\s*T[EO][MN]?[MP]'),
    'KB': re.compile(r'(\bK\.?\s?B\.?\b)|(KELLY)'),
    'STOP': re.compile(r'(CIRC\w*\.?\s*(STOP|END))|(END\s*CIRC)|(STOPPED)'),
    'LOB': re.compile(r'(L[AO]GG?[EA]R\s*[OC]N\s*[BD])|(LOG\w*\s*ON\s*B)|(TIME\s*ON\s*BOT)|(ON\s*BOTTOM)|(ON\s*BATBOR)'),
}
NUM = re.compile(r'\d[\d,]*\.?\d*')


def load(p):
    rows = []
    for l in open(p, encoding='utf-8', errors='replace'):
        t = l.rstrip('\n').split('\t')
        if len(t) >= 6:
            try:
                rows.append(dict(t=t[0], x=float(t[1]), y=float(t[2]), w=float(t[3]), h=float(t[4]), c=float(t[5])))
            except ValueError:
                pass
    return rows


def cy(r):
    return r['y'] + r['h'] / 2


def row_values(items, lab, tol_mult=0.45):
    """items on same row as label, excluding label itself and other label-ish text, split left/right."""
    tol = max(lab['h'], 0.012) * tol_mult
    left, right = [], []
    for r in items:
        if r is lab:
            continue
        if abs(cy(r) - cy(lab)) > tol:
            continue
        if not re.search(r'\d', r['t']):
            continue
        if r['x'] + r['w'] / 2 < lab['x'] + lab['w'] / 2:
            left.append(r)
        else:
            right.append(r)
    # nearest first
    left.sort(key=lambda r: -(r['x'] + r['w']))
    right.sort(key=lambda r: r['x'])
    return left, right


TBL_DIR = os.environ.get('TBL_DIR', '')
REG_DIR = os.environ.get('REG_DIR', '')


def candidates(base, ocr_dir):
    out = collections.defaultdict(list)  # field -> list of (rot, label_text, [value strings nearest-first], side)
    srcs = []
    for rot in (0, 90, 180, 270):
        srcs.append((rot, f'{ocr_dir}/{base}_r{rot}.tsv'))
        if TBL_DIR:
            srcs.append((rot, f'{TBL_DIR}/{base}_r{rot}.tsv'))
        if REG_DIR:
            srcs.append((rot, f'{REG_DIR}/{base}_r{rot}.tsv'))
    for rot, p in srcs:
        if not os.path.exists(p):
            continue
        items = load(p)
        for r in items:
            up = r['t'].upper()
            for f, rx in LABELS.items():
                if not rx.search(up):
                    continue
                if f == 'BLI' and 'TOP' in up:
                    continue
                left, right = row_values(items, r, 0.75 if f == 'KB' else (0.95 if f in ('CIRC', 'STOP', 'LOB') else 0.45))
                # number inside the label text itself (e.g. "Elev.: K.B. 5104")
                inner = NUM.findall(r['t'])
                vals_l = [v['t'] for v in left]
                vals_r = [v['t'] for v in right]
                out[f].append(dict(rot=rot, label=r['t'], inner=inner, inner_txt=[re.sub(r'^[^\d]*', '', r['t'])] if re.search(r'\d', r['t']) and f in ('CIRC',) else [], left=vals_l, right=vals_r, conf=r['c']))
    return out


def ints(s):
    s = re.sub(r'(?<!\d)(\d{1,2})\.(\d{3})(?!\d)', r'\1,\2', s)
    return [int(x.replace(',', '')) for x in re.findall(r'\d[\d,]*', s) if x.replace(',', '').isdigit()]


def parse_field(f, cands, api_suffix=''):
    """return list of (value, support-key)"""
    vals = collections.Counter()
    for c in cands:
        for side in ('left', 'right'):
            toks = []
            for s in c[side][:3]:
                toks += ints(s) if f != 'CIRC' else [s]
            if f == 'BLI':
                good = [v for v in toks if 500 <= v <= 20000 and str(v) != api_suffix]
                if good:
                    vals[max(good)] += 1
            elif f == 'TEMP':
                good = [v for v in toks if 60 <= v <= 400]
                if good:
                    vals[max(good)] += 1
            elif f == 'KB':
                pool = [v for v in (ints(' '.join(c['inner'])) + toks) if 3000 <= v <= 9000]
                if pool:
                    vals[pool[0]] += 1
            elif f == 'CIRC':
                pool = list(c['inner_txt']) + c[side][:4]
                for s in pool:
                    u = s.upper().strip()
                    u = re.sub(r'^S(?=\s*H[RK])', '5', u)
                    u = re.sub(r'^[IL|](?=\s*H[RK])', '1', u)
                    u = u.replace('O', '0') if re.fullmatch(r'[\dO\.\s]+', u) else u
                    m = re.fullmatch(r'\s*(\d{1,2}(?:\.\d+)?)(?:\s+(\d)/(\d))?\s*(?:HRS?\.?|HKS\.?|HOURS?|H)\.?\s*', u)
                    if not m:
                        m = re.fullmatch(r'\s*(\d{1,2}(?:\.\d)?)\s*', u) if s is not None and not re.search(r'[:]', u) else None
                    if m:
                        v = float(m.group(1))
                        if m.lastindex and m.lastindex >= 3 and m.group(2):
                            v += int(m.group(2)) / int(m.group(3))
                        if 0.25 <= v <= 96:
                            vals[str(v)] += 1
                            break
    return vals


def read_log(base, ocr_dir):
    cands = candidates(base, ocr_dir)
    res = {}
    if 'CIRC' not in cands or not parse_field('CIRC', cands['CIRC']):
        def clock(cs):
            out = collections.Counter()
            for c in cs:
                pool = [re.sub(r'^[^\d]*', '', c['label'])] + c['left'][:3] + c['right'][:3]
                for tk in pool:
                    u = tk.upper().replace('O', '0').strip()
                    m = re.fullmatch(r'(\d{1,2}):(\d{2})(?::\d{2})?\s*(?:HRS?|HOURS?)?\.?', u) or re.fullmatch(r'(\d{2})(\d{2})\s*(?:HRS?|HOURS?)?\.?', u)
                    if m:
                        hh, mm = int(m.group(1)), int(m.group(2))
                        if hh < 24 and mm < 60:
                            out[hh * 100 + mm] += 1
                            break
            return out
        st, lb = clock(cands.get('STOP', [])), clock(cands.get('LOB', []))
        if st and lb:
            a, b = st.most_common(1)[0][0], lb.most_common(1)[0][0]
            d = ((b // 100 * 60 + b % 100) - (a // 100 * 60 + a % 100)) % 1440 / 60.0
            if 0.5 <= d <= 48:
                res['CIRC'] = (str(round(d, 2)), 1, 2, {'clock': f'{a:04d}->{b:04d}'})
    for f in ('KB', 'BLI', 'CIRC', 'TEMP'):
        if f == 'CIRC' and 'CIRC' in res:
            continue
        v = parse_field(f, cands.get(f, []), str(int(base.split('_')[0].split('-')[2])))
        if v:
            best = v.most_common()
            res[f] = (best[0][0], best[0][1], len(cands.get(f, [])), dict(best[:3]))
    return res


if __name__ == '__main__':
    ocr_dir, out = sys.argv[1], sys.argv[2]
    bases = sorted({os.path.basename(p).rsplit('_r', 1)[0] for p in glob.glob(ocr_dir + '/*_r0.tsv')})
    rows = []
    cover = collections.Counter()
    for b in bases:
        r = read_log(b, ocr_dir)
        row = [b]
        for f in ('KB', 'BLI', 'CIRC', 'TEMP'):
            if f in r:
                row += [r[f][0], r[f][1], json.dumps(r[f][3])]
                cover[f] += 1
            else:
                row += ['', 0, '']
        rows.append(row)
    with open(out, 'w', newline='') as w:
        cw = csv.writer(w)
        cw.writerow(['log', 'KB', 'KB_votes', 'KB_alts', 'BLI', 'BLI_votes', 'BLI_alts', 'CIRC', 'CIRC_votes', 'CIRC_alts', 'TEMP', 'TEMP_votes', 'TEMP_alts'])
        cw.writerows(rows)
    print(len(bases), 'logs; fields found:', dict(cover))
