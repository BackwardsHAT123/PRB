#!/bin/zsh
# Header-reader pipeline for scanned induction-log TIFs: OCR the header, find KB elevation, bottom logged interval,
# time since circulated and max recorded temperature, and write header_readings.auto.csv.
#
# usage: run_headers.sh WORKDIR TIF_DIR WELL_CSV STATE_DBF [COUNTY]
#   WORKDIR   scratch/output folder for one batch (created); intermediate files go in WORKDIR and WORKDIR/_work
#   TIF_DIR   folder of <API>_<logID>.tif
#   WELL_CSV  well list CSV with columns: API, "Well Name", Operator, "Spud Year", TD_ft
#   STATE_DBF the WOGCC state well-header DBF (for KB / ground elevation cross-check)
#   COUNTY    optional county name used to filter the DBF (e.g. CAMPBELL); blank = all
# Every stage skips work that is already done, so it can be re-run or resumed. It never touches an existing
# header_readings.csv: results go to header_readings.auto.csv, merge reviewed values yourself.
# Needs the OCR binary (build_ocr.sh, or HDR_OCR=/path/to/ocr); run it outside any sandbox that blocks Vision.
set -u
[ $# -ge 4 ] || { sed -n '2,16p' "$0"; exit 2; }
HERE=${0:A:h}; W=${1:A}; TIFS=${2:A}; WELLCSV=${3:A}; DBF=${4:A}; export HDR_COUNTY=${5:-}
export HDR_WORK=$W; S=$W/_work
mkdir -p "$W" "$S"; cd "$W" || exit 1
step() { echo "[$(date +%H:%M)] $1"; }
fail() { echo "FAILED $1"; exit 1; }
py() { python3 -I "$@"; }
mkdir -p tifs; for f in "$TIFS"/*.tif(N); do ln -sf "$f" tifs/; done; echo "$(ls tifs | wc -l | tr -d ' ') TIFs"

step "prep crops"; py $HERE/prep.py tifs header_crops 4800 2>&1 | tail -2 || fail prep
step "OCR crops"; $HERE/ocr_dir.sh header_crops header_ocr | tail -1
step "orient"; py $HERE/orient.py header_ocr $S/orient.csv 2>&1 | tail -2 || fail orient
mkdir -p header_crops_ds
step "deskew"; py $HERE/deskew.py header_crops header_crops_ds 2>&1 | tail -2 || fail deskew
step "OCR deskewed"; $HERE/ocr_dir.sh header_crops_ds header_ocr_ds | tail -1
step "tiles"; py $HERE/prep_tiles.py header_ocr_ds header_crops_ds header_tiles 2>&1 | tail -2 || fail tiles
step "OCR tiles"; $HERE/ocr_dir.sh header_tiles header_tiles_ocr | tail -1
step "merge tiles"; py $HERE/merge_tiles.py header_tiles_ocr header_tiles/meta.json header_ocr_tbl 2>&1 | tail -2 || fail merge
step "read A"; TBL_DIR="$PWD/header_ocr_tbl" py $HERE/logread2.py header_ocr_ds $S/readA.csv 2>&1 | tail -2 || fail readA
mkdir -p header_regions header_strips
step "regions+strips"; py $HERE/region.py $S/readA.csv header_regions 2>&1 | tail -2; py $HERE/strips.py $S/readA.csv header_strips 2>&1 | tail -2
step "OCR strips+regions"; $HERE/ocr_dir.sh header_strips header_strips_ocr | tail -1; $HERE/ocr_dir.sh header_regions header_regions_ocr | tail -1
step "read B + strips"
TBL_DIR="$PWD/header_ocr_tbl" REG_DIR="$PWD/header_regions_ocr" py $HERE/logread2.py header_ocr_ds $S/readB.csv 2>&1 | tail -2 || fail readB
py $HERE/stripread.py $S/stripfill.csv 2>&1 | tail -2 || fail stripread
py - "$S" <<'PY'
import csv, sys
S = sys.argv[1]
rows = list(csv.DictReader(open(S + '/readB.csv')))
fill = {(r['log'], r['field']): r for r in csv.DictReader(open(S + '/stripfill.csv'))}
n = 0
for r in rows:
    r['STRIP'] = ''
    for f in ('BLI', 'CIRC', 'TEMP'):
        x = fill.get((r['log'], f))
        if x and not r[f]:
            r[f] = x['value']; r[f + '_votes'] = x['votes']; r['STRIP'] += f + ';'; n += 1
with open(S + '/readC.csv', 'w', newline='') as w:
    cw = csv.DictWriter(w, fieldnames=list(rows[0].keys())); cw.writeheader(); cw.writerows(rows)
print('strip fills applied:', n, 'logs:', len(rows))
PY
mkdir -p temp_strips
step "temp strips"; py $HERE/tempstrips.py temp_strips 2>&1 | tail -2
step "OCR temp strips"; $HERE/ocr_dir.sh temp_strips temp_strips_ocr | tail -1
step "temp + BHT read"; py $HERE/tempread.py $S/tempfill.csv 2>&1 | tail -2; py $HERE/bhtread.py $S/tempfill.csv $S/bhtfill.csv 2>&1 | tail -2
py - "$S" <<'PY'
import csv, sys
S = sys.argv[1]
rows = list(csv.DictReader(open(S + '/readC.csv')))
tf = {r['log']: r for r in csv.DictReader(open(S + '/tempfill.csv'))}
bf = {r['log']: r for r in csv.DictReader(open(S + '/bhtfill.csv'))}
n1 = n2 = 0
for r in rows:
    r['TEMP_SRC'] = ''
    cur = r['TEMP']
    if cur and 120 <= int(cur) <= 350: continue
    if r['log'] in tf:
        x = tf[r['log']]; r['TEMP'] = x['value']; r['TEMP_votes'] = x['votes']; r['TEMP_SRC'] = 'label'; n1 += 1
    elif r['log'] in bf:
        x = bf[r['log']]; r['TEMP'] = x['value']; r['TEMP_votes'] = x['votes']; r['TEMP_SRC'] = 'Rm@BHT'; n2 += 1
with open(S + '/readD.csv', 'w', newline='') as w:
    cw = csv.DictWriter(w, fieldnames=list(rows[0].keys())); cw.writeheader(); cw.writerows(rows)
print('temp from label strips', n1, 'from Rm@BHT', n2)
PY
step "combine"
cp $S/orient.csv header_orientation_vendor.csv; cp $S/readC.csv header_read_raw.csv
py $HERE/combine.py "$DBF" $S/readD.csv "$WELLCSV" $S/orient.csv header_readings.auto.csv | tail -4 || fail combine
wc -l header_readings.auto.csv
echo "ALLDONE"
