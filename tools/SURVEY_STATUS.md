# PRB map: directional-survey reconciliation — status and to-do

Last updated: Nov 1, 2026 (monthly update; Converse survey reading stopped after batch 6). Repo: https://github.com/BackwardsHAT123/PRB (map = `index.html`, path fixes = `data/overrides.json`).

## What this is
Wells on the map that only show a straight line from surface hole (SHL) to bottom hole (BHL) get a real lateral path
by reading the operator's filed directional survey from the WOGCC site (text files, or scanned PDFs read by OCR),
recomputing the path (minimum curvature) from the header surface location, and **accepting it only if it ends on the
header bottom hole**. Accepted paths are stored in `data/overrides.json` (fx 8) and drawn on the map.

Result codes from the reader (`survey_out*.jsonl`): `ok` (path accepted), `rejected` (recomputed path missed the header
bottom hole by too much), `none` (no survey on file), `unreadable` (OCR/text could not be read), `error`/`blocked` (site problem).
`ok` results are split again at apply time: **exact** (applied), **adjusted** (path had to be shifted a little to end on
the bottom hole, held back), **depth gap** (>1,200 ft gap in the survey inside the curve/lateral, held back).

## DONE

| Batch | Wells | Result | Applied to map | Commit |
|---|---|---|---|---|
| Campbell, first round (earlier session) | n/a (counts not kept in this session) | — | **51 paths** (fx 8) | `fbb94a9` |
| Campbell, second batch (`targets_chunk1.json`, 100 wells: 31 EOG, 24 Ballard, 24 Peak Powder River, 21 Devon) | 100 | 57 ok, 24 rejected, 12 none, 7 unreadable | **40 paths** (fx 8) | `a496d5f` |
| Campbell, third batch (`targets_chunk2.json`, 100 wells) | 100 | 64 ok, 21 rejected, 12 none, 3 unreadable | **46 paths** (fx 8) | `c69e54b` |
| Campbell, fourth batch (`targets_chunk3.json`, 100 wells; 4 first hit site errors and were retried) | 100 | 62 ok, 25 rejected, 5 none, 4 unreadable | **51 paths** (fx 8) | see git log |
| Campbell, fifth batch (`targets_chunk4.json`, 100 wells; 2 first hit site errors and were retried) | 100 | 64 ok, 24 rejected, 8 none, 4 unreadable | **44 paths** (fx 8) | see git log |
| Campbell, sixth batch (`targets_chunk5.json`, 64 wells, the last Campbell list; 6 first hit site errors and were retried) | 64 | 42 ok, 7 rejected, 7 none, 8 unreadable | **36 paths** (fx 8) | see git log |
| Groves Fed pad, Tom's request Oct 29 (`targets_groves.json`, 2 wells already drawn from the certification form, fx 7) | 2 | 2 ok (7.4 m and 53.4 m from the header bottom hole) | **2 paths** (fx 8) | see git log |
| Johnson, first batch (`targets_johnson1.json`, 100 wells of 106 straight-line targets; 4 first hit site errors and were retried) | 100 | 73 ok, 9 rejected, 12 none, 2 unreadable (62 exact, 13 adjusted, 2 depth-gap) | **62 paths** (fx 8) | see git log |
| Johnson, second batch (`targets_johnson2.json`, last 6 Johnson targets) | 6 | 5 ok (2 exact, 3 adjusted), 1 rejected | **2 paths** (fx 8) | see git log |
| Converse, batch 1 (`targets_converse1.json`, 100 wells: Continental 100) | 100 | 63 ok (52 exact, 7 adjusted, 4 depth-gap), 18 rejected, 7 none, 12 unreadable | **52 paths** (fx 8) | see git log |
| Converse, batch 2 (`targets_converse2.json`, 100 wells: Continental 100) | 100 | 68 ok (52 exact, 8 adjusted, 8 depth-gap), 18 rejected, 7 none, 7 unreadable | **52 paths** (fx 8) | see git log |
| Converse, batch 3 (`targets_converse3.json`, 100 wells: Continental 100) | 100 | 61 ok (45 exact, 11 adjusted, 5 depth-gap), 15 rejected, 6 none, 18 unreadable | **45 paths** (fx 8) | see git log |
| Converse, batch 4 (`targets_converse4.json`, 100 wells: Continental 100) | 100 | 64 ok (51 exact, 4 adjusted, 9 depth-gap), 22 rejected, 3 none, 11 unreadable | **51 paths** (fx 8) | see git log |
| Converse, batch 5 (`targets_converse5.json`, 100 wells: Continental 100) | 100 | 67 ok (52 exact, 10 adjusted, 5 depth-gap), 15 rejected, 9 none, 9 unreadable | **52 paths** (fx 8) | see git log |
| Converse, batch 6 (`targets_converse6.json`, 100 wells: Continental 100) | 100 | 71 ok (60 exact, 3 adjusted, 8 depth-gap), 18 rejected, 1 none, 10 unreadable | **60 paths** (fx 8) | see git log |
| Cadet wells, Johnson (`tools/survey_work/targets_cadet.json`, 7 straight-line producers added to the map Oct 27, 2026) | 7 | 7 ok (6 exact, 1 depth-gap) | **6 paths** (fx 8); `49-019-42247` held for a depth gap (`survey_held_cadet.json`) | see git log |
| Sister Fed, Tethys and Chaos Fed wells, Johnson (`tools/survey_work/targets_chs.json`, 12 straight-line wells at Tom's request, Oct 27, 2026) | 12 | 6 ok (all exact), 6 none (permits, spudded or abandoned wells with no survey) | **6 paths** (fx 8) | see git log |
| Anschutz Pokes Fed permits, Johnson (10 wells, T46N R77W sec 16 to 28; `tools/survey_work/pokes_apd.py`, results in `pokes_apd_plats.json`, Oct 27, 2026) | 10 | state GIS permit tracks ended about 9 km from the true bottom hole | **10 paths** (fx 6 with a note): surface hole, landing point and bottom hole from the survey plat on page 11 of each APD; `49-019-42214` surface hole moved 174 m to the plat | see git log |
| Converse T36N R71W (`targets_3671.json`, 156 wells) | 6 of 156 | 4 ok, 1 unreadable, 1 none | none yet | — |
| Monthly update 2026-11 (`tools/survey_work/survey_out_monthly.jsonl`, 100 newest untried Campbell/Johnson straight-line wells; Converse excluded) | 100 | 63 ok (49 exact, 6 adjusted, 8 depth-gap), 10 rejected, 19 none, 8 unreadable | **49 paths** (fx 8); held lists in `survey_held_2026-11.json` | see git log |
| Ballard re-check Nov 6, 2026 (6 unreadable/none wells re-run: same results) + Dilts Fed 34-17 PH `49-005-62754` from the operator design section details Tom supplied (KOP, LP, PBHL; 32 m from header BHL) | 6 | no change | **1 path** (fx 6 with note) | see git log |
| Ballard re-check 2 (Nov 6, 2026): 17 shifted + 15 rejected wells re-read | 32 | rejected ones unchanged (survey cut short, OCR gaps, or lateral-only survey) | **12 paths** (fx 9, shifted to header BHL); 3 depth-gap held (`61924`, `64952`, `67768`); 2 shifted wells stay straight (path is a straight line) | see git log |
| Shifted ("adjusted") paths, all operators, Nov 6, 2026 (Tom approved) | 137 | 92 applied; 35 held for depth gaps in the curve, 10 stay straight (path is a straight line) | **92 paths** (fx 9, shifted to header BHL) | see git log |
| Campbell never-read wells, Nov 6, 2026 (`targets_campbell_nov.json`, 188 wells: Citation 79, EMEP II 47, True 14, Denbury 10, others; 3 got stuck on large scans: 56127, 56628, 56631) | 185 | 116 ok (53 exact applied, 32 shifted held, 5 depth-gap held, 22 agree with a straight line, 4 failed length/end checks), 30 rejected, 19 unreadable, 20 none | **53 paths** (fx 8); held lists in `survey_held_campbell_nov.json` | see git log |
| Campbell never-read batch, shifted paths applied Nov 6, 2026 (Tom approved) | 32 | 16 applied; 15 stay straight (path is a straight line); 1 held for a depth gap | **16 paths** (fx 9) | see git log |
| Rejected wells whose survey starts deep (Tom approved, Nov 6, 2026): Anschutz `49-019-30004`, Combs `49-009-29936`, Spearhead `49-009-29921`: missing upper hole drawn as a straight run from the surface hole to the first station at the implied offset, azimuth within 20 degrees of the first station | 10 checked | 3 applied (fx 9); 7 not applied (path would be a 2 or 3-point dog-leg, no real shape) | **3 paths** | see git log |
| Held depth-gap wells with the gap only in the lateral hold (Nov 7, 2026; every gap has both ends at 80 degrees or more and under 25 ft of position ambiguity) | 78 held | 60 applied (34 exact, 26 shifted to header BHL, shifts 60-249 m); 15 held with a gap in the curve; 3 stay straight | **60 paths** (fx 8 / fx 9) | see git log |
| Curve-gap wells (Nov 7, 2026): 15 held; gaps where inclination and azimuth barely change are a straight tangent hold | 15 | 3 applied (fx 8: `49-005-62894`, `75671`, `78355`); 2 tangent-gap wells stay straight (`61924`, `62222`); 10 held because the gap spans a real build (about 20-50 degrees to 90 degrees over 1,600-3,800 ft: `61785`, `49-009-37297`, `29176`, `46703`, `29066`, `29440`, `49-005-78428`, `68638`, `67034`, `63829`) | **3 paths** | see git log |
| Permit plats (Nov 7, 2026): 47 active/proposed permits with no survey on file (Campbell 19, Johnson 9, Converse 19); APD plat read from the state APD (text layer, or OCR for image plats) | 47 | 23 applied (fx 6 with a note: surface hole, kick-off/landing point and bottom hole from the plat, NAD83); 1 corrected (fx 10, Lost Twin Lakes `49-009-33482`: APD puts it in Sec 31-T41N-R74W, 1.4 km from the map); 23 left as straight lines on purpose: their APD plats (Butch, Annie, Leavitt Trust, WRC, Sage Butte, 1876, Anadarko, Continental, Burch Fed, Howitzer) list only surface and bottom hole, and the APD page-4 coordinates match the map to within 6 m; Powell `49-009-50010` APD download is truncated | **24 wells** | see git log |
| Spudded wells with no survey (Nov 7, 2026): 134 straight-line spudded wells (Campbell 26, Johnson 7, Converse 101); latest APD read | 134 | 2 plat paths (fx 6, planned: Dawson Fed `49-009-49969`, `49971`); 4 locations fixed from the APD table (fx 10: Stig Fed `49-005-78217` was an 8 m line, Kringen `49-009-49922`/`49923`, Troy `49-009-50602`); 28 older APDs have no coordinate table; the rest already match the map. About 24 wells have an APD bottom hole 130-1,440 m from the map's header bottom hole with the same lateral length; **left as is** (permitted plan vs state header, which is right is unknown): Ballista `49-005-68756`, Walnut `78411`/`78412`, Tillard `49-009-29650`, Lame Deer Lake `31106`, James `49086`, Bucky `49573` and others | **6 wells** | see git log |
| Campbell/Johnson rejected + unreadable re-read (Nov 7, 2026): 102 Campbell wells (52 unreadable, 50 rejected under 1 km) and 11 Johnson wells | 113 | 2 ok (`49-005-62220` curve gap, held; `49-019-31667` applied, fx 8). The rejected wells' stations show the survey bearing matches the header bearing (within 6 degrees) with the end near the SHL-BHL line, and a length within 25% of the header's: the header bottom hole is a plan/projection, not the survey being wrong. Applied shifted to the header bottom hole (fx 9) where the survey ends in the lateral (inclination 80+), cross-track error is under 200 m, length ratio 0.75-1.25, miss under 1 km, and there is no curve gap | | **25 paths** (24 fx 9, 1 fx 8; shifts 256-681 m, larger than the 250 m of earlier fx 9 batches) | see git log |

Of the ok wells in the sixth batch (`targets_chunk5.json`): 36 applied, 4 held as "adjusted", 2 held for depth gaps (`49-005-61785`, `77703`); lists in `survey_held_chunk5.json`.

Of the 64 ok in the fifth batch (`targets_chunk4.json`): 44 applied, 9 held as "adjusted", 11 held for depth gaps (`49-005-61931`, `61703`, `67768`, `62116`, `64209`, `61924`, `61330`, `77279`, `73547`, `62232`, `77700`); lists in `survey_held_chunk4.json`.

Of the 62 ok in the fourth batch (`targets_chunk3.json`): 51 applied, 11 held as "adjusted", 4 held for depth gaps (`49-005-62364`, `62222`, `62667`, `78355`); lists in `survey_held_chunk3.json`.

Of the 64 ok in the third batch: 46 applied, 12 held as "adjusted" (72-238 m shifts), 6 held for depth gaps (`49-005-62391`, `64315`, `63494`, `62479`, `62402`, `64952`); lists in `survey_held_chunk2.json`. `49-005-62153` (held for a depth gap in the second batch) no longer trips the gap check but was left unapplied. The reader writes `survey_stations.jsonl` next to the scripts (not in `data/`).

Of the 57 ok in the second Campbell batch: 40 applied, 14 held as "adjusted", 3 held for depth gaps
(`49-005-62153`, `49-005-62714`, `49-005-77639`). Full lists are in `tools/survey_work/survey_held.json`.
Applied paths were checked: each starts exactly at the header SHL, ends within 58 m of the header BHL, and is 0.98–1.34x its straight-line length.

Johnson: 64 more paths from filed directional surveys (fx 8), all 106 Johnson targets run; depth-gap wells held: `49-019-29897`, `30388`; lists in `survey_held_johnson1.json`. The Johnson target lists are `targets_johnson1.json` (100) and `targets_johnson2.json` (6, done); results go to `survey_out_johnson.jsonl`.

Paths on the map now by source (Campbell): 437 from filed certification forms (fx 7), 321 from filed directional surveys (fx 8), 12 from operator design surveys (fx 6). Of 1,402 Campbell wells, about 524 still show a straight line (Nov 1, 2026).

## LEFT TO DO

1. **Campbell survey batches: all five target lists (`targets_chunk1.json` to `5`) are done.** The target lists only held wells with a straight line and a header bottom hole when they were made, so a new list could be built for any wells added or still unresolved — `tools/survey_work/targets_chunk2.json` … `targets_chunk5.json` ( operators Ballard, EOG, Devon, Peak Powder River; only wells that still had a straight line and a header bottom hole when the lists were made).
   The second batch (100 wells) took about 70 minutes, so each further 100 is roughly an hour to an hour and a half.
2. **Converse: survey reading stopped (decision Oct 26, 2026).** Batches 1 to 6 (600 Continental wells, `tools/survey_work/targets_converse1.json` to `6`) were read and 312 exact paths applied. The remaining Converse lists (`targets_converse7.json` to `18`, about 1,100 wells, plus T36N R71W `targets_3671.json`, 150 wells left) were not run and are not planned. The monthly update no longer reads Converse surveys; Converse wells still get new-well, state-track and production updates. The state site (pipeline.wyo.gov) blocked the reader after roughly 200 to 300 wells in a few hours, even at one request per 10 seconds; resting overnight cleared it. If this is revisited, run one chunk at a time with long rests.
3. **Decide on the held results from the second to sixth Campbell batches** (counts as of the last apply run): 74 "adjusted" paths (Campbell and Johnson, incl. 6 from the Nov 2026 monthly run) (shifted to end on the header BHL) and 34 depth-gap paths (incl. 8 from the Nov 2026 run). The first round also held its adjusted ones back. They can be applied with the "include adjusted" option (fx 9) if you want them.
4. **94 rejected + 18 unreadable wells from the second to sixth Campbell batches** have not been investigated (misread OCR, or the survey really does not match the header bottom hole). IDs are in `tools/survey_work/survey_out.jsonl` (status `rejected` / `unreadable`).
5. **Johnson wells outside the two target lists and Converse wells**: Johnson's 106 straight-line targets were read (64 paths applied). Wells with a multi-point state track already use it; wells with a straight state track show a straight line.
6. Optional: apply script `tools/apply_surveys.py` was written for the earlier session's folder layout (`prb/index.html`, `prb/data/overrides.json`) and for Campbell only. For the second batch I applied results with an inline script on a fresh clone of the repo (same rules: status ok, not adjusted, not depth-gap, well still a straight line, then write `ln`, `fx` 8 and `surv` into the page data and `data/overrides.json`). It would be worth tidying that into the tools folder, and making it work for Converse.

* **Tall strip scans** (about 725 x 7,300 pt, e.g. `49-005-56127`, `56628`, `56631`) crashed the OCR engine and hung the worker pool; `survey_pipeline.py` now reads pages in overlapping 1,800 px tiles. Those three wells read but stay rejected (misses of 1,398 and 612 m) or unreadable.
* **Permit plats:** `tools/survey_work/pokes_apd.py` (image plats, OCR), `plat_text.py` (text-layer plats: labeled NAD83 points, or NAD27/NAD83 pairs) and `page4.py` (surface and bottom hole table on APD page 4).

## How to run it again
Needs Python with `rapidocr-onnxruntime`, `numpy`, `pypdfium2` (the earlier session used a virtualenv at `.../scratchpad/ocrenv`, which lives in a temp folder and may disappear; rebuild with `python3 -m venv ocrenv && ocrenv/bin/pip install rapidocr-onnxruntime numpy pypdfium2`).
Keep `survey_pipeline.py` and `parse_ocr.py` in the same folder, then, from that folder:

    SURVEY_OUT=survey_out_3671.jsonl ocrenv/bin/python survey_pipeline.py targets_3671.json 4
    SURVEY_OUT=survey_out.jsonl      ocrenv/bin/python survey_pipeline.py targets_chunk2.json 4

(`4` = workers; requests are paced to one every 3 seconds in total. Create a file named `SURVEY_STOP` in that folder to stop a run cleanly. Network access to `pipeline.wyo.gov` is required.)

## Cautions
* The WOGCC site rate-limits. After heavy use (thousands of header-page requests plus a long survey run) the Data Explorer header pages started returning "Request Rejected" for a while. Space big runs out; do not hammer it.
* The reader's results are only as good as the header bottom hole: it accepts a path when it ends there. If a header bottom hole is wrong, a correct survey gets rejected (and a wrong one can never be accepted).
* Scratch folders under `/private/tmp/...` are temporary. The working files are saved in `tools/survey_work/` (and a copy in `PRB_survey_work/` on Tom's Mac).

* **Roush pad (Ballard, sec 25-43N-74W) and two Leavitt wells reconciled Oct 26, 2026** (`fx 17` = filed survey carried on to the header bottom hole). For `49-005-64209`, `64213`, `64217` and `64240` the header bottom hole is the operator's projection to bit; the reader's station list ended at the last MWD reading (216 to 365 ft short), so each path is the survey plus a straight run to the header bottom hole. For `49-005-64239` the header bottom hole (2,006 ft FWL) is about 600 ft east of the certified location (1,403 ft FWL); the map uses the survey's own bottom hole. `49-005-77981` and `49-005-78485` (Leavitt) now use their filed survey paths (fx 8), which bow off the straight heel-to-toe line mid-lateral.

## Other path/point fixes made this session (not from surveys, for context)
Stored in `data/overrides.json` with a note shown in the popup; fx codes: 10 surface hole moved to the footage location; 11 bottom hole from state track end; 12 bottom hole estimated from the stated section; 13 state track shifted to the header surface hole; 14 state track pinned to header SHL/BHL; 15 state track runs the wrong way (straight line shown); 16 bottom hole taken from the state's bottom-hole layer. Also existing: 1 stray track point removed, 2 manually corrected, 3 straight line because the state track is incomplete, 4 rescaled track, 6/7/8/9 as above.

## Files (this note is `tools/SURVEY_STATUS.md`; working data is in `tools/survey_work/`)
* `tools/SURVEY_STATUS.md` — this note
* `tools/survey_work/targets_chunk1..5.json` — Campbell target lists (chunk1 already run)
* `tools/survey_work/targets_3671.json` — Converse T36N R71W target list
* `tools/survey_work/survey_out.jsonl` — reader results, second Campbell batch; `tools/survey_work/survey_out_3671.jsonl` — T36N R71W so far
* `tools/survey_work/survey_stations.jsonl` — the survey stations the reader found (MD, inclination, azimuth)
* `tools/survey_work/survey_held.json` — held (adjusted, depth-gap) and rejected well lists
* `tools/survey_work/targets_valid.json`, `tools/survey_work/valid_out.jsonl` — the earlier validation run of the reader against known-good wells
* `tools/survey_work/bh_review.json` — the bottom-hole vs state-layer comparison
* the scripts themselves are in `tools/`
