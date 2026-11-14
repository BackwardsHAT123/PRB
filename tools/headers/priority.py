import csv, sys, collections, os
P = os.environ['HDR_WORK']
rows = list(csv.DictReader(open(f'{P}/header_readings.csv')))
orient = {r['log']: r for r in csv.DictReader(open(f'{P}/header_orientation_vendor.csv'))}
FIELDS = [('KB', 'KB_ft', 'KB_conf'), ('Bottom_Logged', 'Bottom_Logged_ft', 'BLI_conf'),
          ('Time_Since_Circ', 'Time_Since_Circ_hrs', 'CIRC_conf'), ('Max_Temp', 'Max_Temp_F', 'TEMP_conf')]
RANK = {'HIGH': 3, 'MED': 2, 'LOW': 1, '': 0}
wells = collections.defaultdict(list)
for r in rows:
    wells[r['API']].append(r)
out = []
tot_fields = collections.Counter()
for api, logs in wells.items():
    best = {}
    for name, vk, ck in FIELDS:
        cand = [(RANK[l[ck]], l) for l in logs if l[vk] != '']
        cand.sort(key=lambda t: -t[0])
        if cand and cand[0][0] >= 2:
            best[name] = ('OK', cand[0][1][vk], cand[0][1][ck])
        elif cand:
            best[name] = ('LOW', cand[0][1][vk], cand[0][1][ck])
        else:
            best[name] = ('MISSING', '', '')
    need_all = [n for n, v in best.items() if v[0] != 'OK']
    need = [n for n in need_all if n != 'KB']
    kb_need = 'KB' in need_all
    for n in need:
        tot_fields[n] += 1
    if not need:
        continue
    status = next((l.get('Review_Status', '') for l in logs if l.get('Review_Status')), '')
    if status == 'NO_INFO':
        continue
    l0 = logs[0]
    tifs = [f"induction_log_tifs/{l['API']}_{l['Log_ID']}.tif" for l in logs]
    vend = orient.get(f"{l0['API']}_{l0['Log_ID']}", {}).get('vendors', '') or 'UNKNOWN'
    nlow = sum(1 for n in need if best[n][0] == 'LOW')
    nmiss = len(need) - nlow
    # tier: A = 1-2 fields to fix, B = 3 fields, C = all 4 (usually unreadable header or damaged file)
    tier = 'P1_Temp' if 'Max_Temp' in need else ('P2_TimeSinceCirc' if 'Time_Since_Circ' in need else 'P3_BottomLogged')
    out.append(dict(
        Tier=tier, Rank=0, API=api, Well_Name=l0['Well_Name'], Operator=l0['Operator'], Spud_Year=l0['Spud_Year'], State_TD=l0['State_TD'],
        Review_Status=status, Fields_to_fill='; '.join(need), N_fields=len(need), KB_also_missing='Y' if kb_need else '',
        Unconfirmed_LOW_values='; '.join(f"{n}={best[n][1]}" for n in need if best[n][0] == 'LOW'),
        Vendor_guess=vend.split(';')[0], N_logs=len(logs), TIFs=' | '.join(tifs),
        Header_orientation_hint=orient.get(f"{l0['API']}_{l0['Log_ID']}", {}).get('best_rot', ''),
        KB_ft=best['KB'][1], Bottom_Logged_ft=best['Bottom_Logged'][1], Time_Since_Circ_hrs=best['Time_Since_Circ'][1], Max_Temp_F=best['Max_Temp'][1]))
out.sort(key=lambda d: ({'P1_Temp': 0, 'P2_TimeSinceCirc': 1, 'P3_BottomLogged': 2}[d['Tier']], d['N_fields'], d['API']))
for i, d in enumerate(out, 1):
    d['Rank'] = i
with open(f'{P}/manual_review_priority.csv', 'w', newline='') as w:
    cw = csv.DictWriter(w, fieldnames=list(out[0].keys()))
    cw.writeheader()
    cw.writerows(out)
print(len(wells), 'wells;', len(out), 'need manual work')
print('tiers', collections.Counter(d['Tier'] for d in out))
print('P1 wells needing only temp:', sum(1 for d in out if d['Tier']=='P1_Temp' and d['N_fields']==1))
print('fields still needed (wells):', dict(tot_fields))
