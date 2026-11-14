import sys, os, csv, re, collections, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['TBL_DIR'] = ''
import logread2 as L
P = os.environ['HDR_WORK']
tempfill, out = sys.argv[1], sys.argv[2]
have = {r['log'] for r in csv.DictReader(open(tempfill))}
rd = list(csv.DictReader(open(os.environ.get('HDR_READ') or f'{P}/_work/readC.csv')))
logs = sorted({r['log'] for r in rd if not (r['TEMP'] and 120 <= int(r['TEMP']) <= 350)} - have)
BHT = re.compile(r'(R[A-Z]{1,3}\s*[@GE•Ðð(\|]*\s*B\.?H\.?T)|(@\s*BHT)|(\bBHT\b)')
PAT = re.compile(r'[@•Oo0]?\s*(\d{3})\s*[°º˚o]?\s*(?:D?EG\.?\s*)?F\b', re.I)
rows = []
for b in logs:
    votes = collections.Counter()
    for src in ('header_ocr_tbl', 'header_ocr_ds', 'header_regions_ocr'):
        for rot in (0, 90, 180, 270):
            p = f'{P}/{src}/{b}_r{rot}.tsv'
            if not os.path.exists(p):
                continue
            items = L.load(p)
            for lab in items:
                if not BHT.search(lab['t'].upper()):
                    continue
                tol = max(lab['h'], 0.012) * 0.9
                cand = [lab] + [i for i in items if i is not lab and abs(L.cy(i) - L.cy(lab)) <= tol]
                cand.sort(key=lambda i: abs((i['x'] + i['w'] / 2) - (lab['x'] + lab['w'] / 2)))
                for i in cand[:5]:
                    m = PAT.search(i['t'])
                    if m and 120 <= int(m.group(1)) <= 350:
                        votes[int(m.group(1))] += 1
                        break
    if votes:
        v, n = votes.most_common(1)[0]
        rows.append((b, v, n, sum(votes.values()), json.dumps(dict(votes.most_common(3)))))
with open(out, 'w', newline='') as w:
    cw = csv.writer(w)
    cw.writerow(['log', 'value', 'votes', 'total_reads', 'alts'])
    cw.writerows(rows)
print(len(logs), 'logs without label-based temp;', len(rows), 'got an Rm@BHT temperature;', sum(1 for r in rows if r[2] >= 2), 'with >=2 agreeing')
