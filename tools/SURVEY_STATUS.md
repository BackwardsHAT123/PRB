# PRB map: directional-survey reconciliation — status and to-do

Last updated: Oct 24, 2026 (after the third Campbell batch). Repo: https://github.com/BackwardsHAT123/PRB (map = `index.html`, path fixes = `data/overrides.json`).

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
| Johnson, first batch (`targets_johnson1.json`, 100 wells of 106 straight-line targets; 4 first hit site errors and were retried) | 100 | 73 ok, 9 rejected, 12 none, 2 unreadable (62 exact, 13 adjusted, 2 depth-gap) | **62 paths** (fx 8) | see git log |
| Johnson, second batch (`targets_johnson2.json`, last 6 Johnson targets) | 6 | 5 ok (2 exact, 3 adjusted), 1 rejected | **2 paths** (fx 8) | see git log |
| Converse, batch 1 (`targets_converse1.json`, 100 wells: Continental 100) | 100 | 63 ok (52 exact, 7 adjusted, 4 depth-gap), 18 rejected, 7 none, 12 unreadable | **52 paths** (fx 8) | see git log |
| Converse T36N R71W (`targets_3671.json`, 156 wells) | 6 of 156 | 4 ok, 1 unreadable, 1 none | none yet | — |

Of the ok wells in the sixth batch (`targets_chunk5.json`): 36 applied, 4 held as "adjusted", 2 held for depth gaps (`49-005-61785`, `77703`); lists in `survey_held_chunk5.json`.

Of the 64 ok in the fifth batch (`targets_chunk4.json`): 44 applied, 9 held as "adjusted", 11 held for depth gaps (`49-005-61931`, `61703`, `67768`, `62116`, `64209`, `61924`, `61330`, `77279`, `73547`, `62232`, `77700`); lists in `survey_held_chunk4.json`.

Of the 62 ok in the fourth batch (`targets_chunk3.json`): 51 applied, 11 held as "adjusted", 4 held for depth gaps (`49-005-62364`, `62222`, `62667`, `78355`); lists in `survey_held_chunk3.json`.

Of the 64 ok in the third batch: 46 applied, 12 held as "adjusted" (72-238 m shifts), 6 held for depth gaps (`49-005-62391`, `64315`, `63494`, `62479`, `62402`, `64952`); lists in `survey_held_chunk2.json`. `49-005-62153` (held for a depth gap in the second batch) no longer trips the gap check but was left unapplied. The reader writes `survey_stations.jsonl` next to the scripts (not in `data/`).

Of the 57 ok in the second Campbell batch: 40 applied, 14 held as "adjusted", 3 held for depth gaps
(`49-005-62153`, `49-005-62714`, `49-005-77639`). Full lists are in `tools/survey_work/survey_held.json`.
Applied paths were checked: each starts exactly at the header SHL, ends within 58 m of the header BHL, and is 0.98–1.34x its straight-line length.

Johnson: 64 more paths from filed directional surveys (fx 8), all 106 Johnson targets run; depth-gap wells held: `49-019-29897`, `30388`; lists in `survey_held_johnson1.json`. The Johnson target lists are `targets_johnson1.json` (100) and `targets_johnson2.json` (6, done); results go to `survey_out_johnson.jsonl`.

Paths on the map now by source (Campbell): 441 from filed certification forms (fx 7), 268 from filed directional surveys (fx 8), 12 from operator design surveys (fx 6). Of 1,406 Campbell wells, about 553 still show a straight line.

## LEFT TO DO

1. **Campbell survey batches: all five target lists (`targets_chunk1.json` to `5`) are done.** The target lists only held wells with a straight line and a header bottom hole when they were made, so a new list could be built for any wells added or still unresolved — `tools/survey_work/targets_chunk2.json` … `targets_chunk5.json` ( operators Ballard, EOG, Devon, Peak Powder River; only wells that still had a straight line and a header bottom hole when the lists were made).
   The second batch (100 wells) took about 70 minutes, so each further 100 is roughly an hour to an hour and a half.
2. **Converse T36N R71W: 150 wells left** in `tools/survey_work/targets_3671.json` (153 of the 156 are Anschutz). Four of these (`49-009-31444` Dolly Fed, `34261` Rags Fed, `34300` Bucky Fed, `49038` Toughy Fed) have a bottom hole I estimated earlier (fx 12), so the reader will likely "reject" them; check by hand whether the survey's own end point falls in the stated bottom-hole section — it may give the true bottom hole.
   The run was stopped when a session ended; it resumes where it left off (finished wells are skipped).
3. **Decide on the held results from the second to sixth Campbell batches** (counts as of the last apply run): 68 "adjusted" paths (Campbell and Johnson) (shifted to end on the header BHL) and 26 depth-gap paths. The first round also held its adjusted ones back. They can be applied with the "include adjusted" option (fx 9) if you want them.
4. **94 rejected + 18 unreadable wells from the second to sixth Campbell batches** have not been investigated (misread OCR, or the survey really does not match the header bottom hole). IDs are in `tools/survey_work/survey_out.jsonl` (status `rejected` / `unreadable`).
5. **Converse and Johnson wells outside T36N R71W**: no survey reading has been done anywhere else. Wells with a multi-point state track already use it; wells with a straight state track show a straight line.
6. Optional: apply script `tools/apply_surveys.py` was written for the earlier session's folder layout (`prb/index.html`, `prb/data/overrides.json`) and for Campbell only. For the second batch I applied results with an inline script on a fresh clone of the repo (same rules: status ok, not adjusted, not depth-gap, well still a straight line, then write `ln`, `fx` 8 and `surv` into the page data and `data/overrides.json`). It would be worth tidying that into the tools folder, and making it work for Converse.

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
