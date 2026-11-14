import os, struct, sys, csv, re, json, collections
COUNTY = os.environ.get('HDR_COUNTY', '')   # state header county filter (blank = all)
dbf, readcsv, wellcsv, orient, out = sys.argv[1:6]
# state header reference
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
    def num(k):
        try:
            v = float(g(k))
            return v if v > 0 else None
        except ValueError:
            return None
    ref['49-%03d-%05d' % (a // 100000, a % 100000)] = dict(kb=num('ELEVKB'), gl=num('ELEV'), td=num('TD'))
wells = {r['API']: r for r in csv.DictReader(open(wellcsv))}
vend = {r['log']: (r['vendors'].split(';')[0] or 'UNKNOWN') for r in csv.DictReader(open(orient))}


def circ_hours(raw):
    if not raw:
        return None
    s = raw.upper().replace('O', '0') if re.fullmatch(r'[\dO\.\s]+', raw.upper()) else raw.upper()
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:HRS?|HOURS?|H\b)', s)
    if m:
        v = float(m.group(1))
    else:
        m = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*', s)
        if not m:
            return None
        v = float(m.group(1))
    return v if 0.25 <= v <= 120 else None


rows = []
cnt = collections.defaultdict(collections.Counter)
for r in csv.DictReader(open(readcsv)):
    log = r['log']
    api = log.split('_')[0]
    w = wells.get(api, {})
    rf = ref.get(api, {})
    row = dict(API=api, Log_ID=log.split('_')[1], Well_Name=w.get('Well Name', ''), Operator=w.get('Operator', ''),
               Spud_Year=w.get('Spud Year', ''), State_TD=w.get('TD_ft', ''), Vendor_guess=vend.get(log, ''))
    # KB
    kb = int(r['KB']) if r['KB'] else None
    conf = ''
    if kb:
        refs = [x for x in (rf.get('kb'), rf.get('gl')) if x and x > 1000]
        votes = int(r['KB_votes'])
        if refs:
            d = min(abs(kb - x) for x in refs)
            conf = 'HIGH' if d <= 30 else 'LOW'
        else:
            conf = 'MED' if (3500 <= kb <= 7500 and votes >= 2) else ('LOW' if not 3500 <= kb <= 7500 else 'MED')
    row.update(KB_ft=kb or '', KB_conf=conf or ('' if not kb else 'LOW'))
    # BLI
    bli = int(r['BLI']) if r['BLI'] else None
    conf = ''
    if bli:
        td = float(w['TD_ft']) if w.get('TD_ft') else None
        votes = int(r['BLI_votes'])
        if td and (bli > td + 200 or bli < 0.6 * td):
            conf = 'LOW'
        elif td and abs(bli - td) <= 600 and votes >= 2:
            conf = 'HIGH'
        else:
            conf = 'MED' if votes >= 2 or (td and abs(bli - td) <= 600) else 'LOW'
    row.update(Bottom_Logged_ft=bli or '', BLI_conf=conf)
    # CIRC
    ch = circ_hours(r['CIRC'])
    row.update(Time_Since_Circ_hrs=ch if ch is not None else '', Time_Since_Circ_raw=r['CIRC'],
               CIRC_conf=('' if not r['CIRC'] else ('LOW' if ch is None or ch > 48 else 'MED')))
    # TEMP
    tp = int(r['TEMP']) if r['TEMP'] else None
    conf = ''
    if tp:
        votes = int(r['TEMP_votes'])
        conf = ('HIGH' if votes >= 3 else 'MED') if 120 <= tp <= 350 else 'LOW'
    row.update(Max_Temp_F=tp or '', TEMP_conf=conf)
    sf = r.get('STRIP', '')
    row['Strip_Filled'] = sf.strip(';')
    for k, tag in (('BLI', 'BLI'), ('CIRC', 'CIRC'), ('TEMP', 'TEMP')):
        if tag in sf.split(';') and row[k + '_conf'] == 'HIGH':
            row[k + '_conf'] = 'MED'
    row['Temp_Source'] = r.get('TEMP_SRC', '')
    if r.get('TEMP_SRC') == 'Rm@BHT' and row['TEMP_conf'] == 'HIGH':
        row['TEMP_conf'] = 'MED'
    row['Needs_Review'] = 'Y' if any(row[k + '_conf'] in ('', 'LOW') for k in ('KB', 'BLI', 'CIRC', 'TEMP')) else 'N'
    for k in ('KB', 'BLI', 'CIRC', 'TEMP'):
        cnt[k][row[k + '_conf'] or 'none'] += 1
    rows.append(row)
cols = list(rows[0].keys())
with open(out, 'w', newline='') as w:
    cw = csv.DictWriter(w, fieldnames=cols)
    cw.writeheader()
    cw.writerows(rows)
print(len(rows), 'rows')
for k, c in cnt.items():
    print(k, dict(c))
