import os, struct, sys, csv, collections
COUNTY = os.environ.get('HDR_COUNTY', '')   # state header county filter (blank = all)
dbf, readcsv = sys.argv[1], sys.argv[2]
f = open(dbf, 'rb')
h = f.read(32)
n, hl, rl = struct.unpack('<IHH', h[4:12])
offs = {}
o = 1
while True:
    d = f.read(32)
    if d[0] == 0x0D:
        break
    offs[d[:11].split(b'\0')[0].decode()] = (o, d[16])
    o += d[16]
f.seek(hl)
ref = {}
for _ in range(n):
    r = f.read(rl)
    g = lambda k: r[offs[k][0]:offs[k][0] + offs[k][1]].decode('latin-1').strip()
    if COUNTY and g('COUNTYTXT').upper() != COUNTY.upper():
        continue
    a = int(float(g('APINO')))
    api = '49-%03d-%05d' % (a // 100000, a % 100000)
    def num(k):
        try:
            return float(g(k))
        except ValueError:
            return None
    ref[api] = dict(kb=num('ELEVKB'), gl=num('ELEV'), td=num('TD'))
tot = ok = near = bad = 0
badl = []
for r in csv.DictReader(open(readcsv)):
    api = r['log'].split('_')[0]
    rf = ref.get(api)
    if not rf:
        continue
    if r['KB']:
        tot += 1
        v = int(r['KB'])
        cands = [x for x in (rf['kb'], rf['gl']) if x and x > 1000]
        if not cands:
            tot -= 1
            noref = globals().get('noref', 0) + 1
            globals()['noref'] = noref
            continue
        d = min([abs(v - c) for c in cands] or [9999])
        if d == 0:
            ok += 1
        elif d <= 30:
            near += 1
        else:
            bad += 1
            badl.append((r['log'], v, rf['kb'], rf['gl'], r['KB_votes']))
print('KB read', tot, 'exact', ok, 'within30ft', near, 'off', bad)
for b in badl[:15]:
    print(b)
# BLI vs TD
t = c = 0
for r in csv.DictReader(open(readcsv)):
    api = r['log'].split('_')[0]
    rf = ref.get(api)
    if rf and r['BLI'] and rf['td']:
        t += 1
        if abs(int(r['BLI']) - rf['td']) <= 600:
            c += 1
print('BLI read', t, 'within 600ft of state TD', c)
