# GeoGraphix ASCII4 (.WB4) layout, as exported by Drillinginfo

Worked out from `Powder Test GeoGraphix ASCII4.WB4` (two wells: ROUSH 44-25 TH, 49-005-61788, and ROUSH FED 44-24-1X TH, 49-005-63118).
Not an official spec: field positions are inferred from two wells, so a field that was blank or always the same width in the sample may be
off for other wells. Columns are 1-based; "end" means right-aligned so the last character sits in that column.

## File
- ASCII, CRLF line ends, no tabs. A file ends with a CRLF.
- `##` lines are comments: three file header lines, then for every well `## ****************** NEW WELLHEADER ******************` and a
  `## <Name> Records (<TT>) for <UWI14> :` line before each record type, even when that type has no records.
- One record per line, fixed width. Columns 1-2 are the record type, columns 15-28 the 14-digit UWI (API digits plus `0000`).
- Per-well order: WH, B0, CP, FT, SD, ST, MC, PF, IT, IP, PT.

## Record types

| Type | Length | One per | Content |
|---|---|---|---|
| WH | 988 | well | header |
| B0 | 397 | well | legal location (section, township, range) |
| CP | 146 | completion | completion interval |
| FT | 678 | formation top | formation tops |
| SD | 327 | well | directional survey header |
| ST | 152 | survey station | MD, TVD, inclination, azimuth, offsets |
| MC | 417 | casing string | casing |
| PF | 448 | perforation interval | perforations |
| IT | 531 | treatment | IP treatment (fluid and proppant totals) |
| IP | 515 | test | initial potential |
| PT | 237 | month | monthly production |

## Fields the exporter writes

**WH**: UWI 15-28 · operator start 52 · well name end 128 · well number end 148 · latitude start 151 and longitude start 160 (6 decimals, no
separator) · status start 201 (`OIL+ACTIVE`) · fluid start 228 (`OIL`) · KB elevation end 246 · ground elevation end 262 · total depth (MD) end 294 ·
formation at TD start 309 · spud date start 363 and completion date start 373 (mm/dd/yyyy; a third date at 383 is probably the permit date) ·
field end 527 · state end 547 · county start 565 · country start 585 · temporary id end 617 (`TEMP` plus a number) · elevation reference `KB` start 628 ·
lease end 783 · 10-digit API start 907.

**B0**: `Congress` start 33 · section end 74 · township number end 80 · N/S at 84 · range number end 89 · E/W at 93.

**CP**: completion number at 44 · completion date start 57 · formation start 81 · top depth end 96 · bottom depth end 106 · formation start 121 and 141.

**SD**: `Default` start 54 · `Minimum Curvature` start 94 · bottom-hole latitude start 146, longitude start 156 (separated by a space).

**PT**: `Default` start 34 · formation start 67 · `Production` start 75 · oil (bbl) end 127 · gas (mcf) end 140 · water (bbl) end 153 ·
month `mm/01/yyyy` start 219 · `100` end 232 (probably the allocation percent) · days on production end 236.
Every month from first production to the last reported month has a row, including zero months.

**Seen in the sample but not written**: FT (formation tops), ST (survey stations), MC (casing; size in cols 32-50, depth 91-95, hole size 265-269),
PF (perforation intervals; sequence at 44-60, top end 80, bottom end 90), IT (fluid gal end 129, proppant lbs end 163, date at 282),
IP (test date 121, oil bbl end 162, gas mcf end 186, water bbl end 210).

## Checked against the sample
Exporting the same two wells from the PRB data reproduces the sample's section comments, the B0 lines and every oil, gas, water and date value in PT exactly.
Differences are source data only: the Drillinginfo file has its own surface and bottom-hole coordinates, elevations, total depth, a few dates and a top-perf depth.
Days on production are stored for the first 8 months only, so later months are blank.
