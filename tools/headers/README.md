# Induction-log header readers

Reads the header of scanned induction-log TIFs (Wyoming oil and gas conservation commission "induction log" scans) with
macOS Vision OCR and extracts, per log: **KB elevation**, **bottom logged interval**, **time since circulated** and
**max recorded temperature**. Output goes to `header_readings.auto.csv` (one row per log).

Your TIFs and the readings stay on your machine: nothing in this folder reads or writes inside the repo, and the
`PRB_work` workspace folders are not part of it. Do not commit TIFs, crops, OCR output or readings.

## One-time setup
- macOS with Xcode command line tools (for `swiftc`), Python 3 with Pillow and numpy.
- `zsh tools/headers/build_ocr.sh` compiles the Vision helper to `tools/headers/ocr` (git-ignored).
  Run the pipeline in a shell that allows Vision (a sandbox that blocks it will fail at the OCR stages).

## Run
```
zsh tools/headers/run_headers.sh WORKDIR TIF_DIR WELL_CSV STATE_DBF [COUNTY]
```
- `WORKDIR`   output/scratch folder for one batch (any location outside the repo)
- `TIF_DIR`   folder of `<API>_<logID>.tif`
- `WELL_CSV`  well list with columns `API`, `Well Name`, `Operator`, `Spud Year`, `TD_ft`
- `STATE_DBF` the state well-header DBF (used to cross-check KB / ground elevation)
- `COUNTY`    optional filter for the DBF (e.g. `CAMPBELL`)

Every stage skips finished work, so the command can be re-run after an interruption. Progress is printed with
`[HH:MM]` stamps. It ends with `ALLDONE`.

## Stages
prep crops -> OCR -> orientation/vendor guess -> deskew -> OCR -> table tiles -> merge -> read A (row geometry) ->
regions and strips -> OCR -> read B -> strip fills -> temperature strips and Rm@BHT -> combine.

## Outputs (in WORKDIR)
- `header_readings.auto.csv`: the combined result (never overwrites an existing `header_readings.csv`)
- `header_read_raw.csv`, `header_orientation_vendor.csv`: raw per-field votes and orientation/vendor guess
- `_work/`: intermediate CSVs; `header_*` folders: crops and OCR text

## Known limits
- On logs with more than one run the reader can take a later run's bottom logged / temperature. The earlier
  review pass fixed temperatures to run 1 (nearest the label); bottom logged and circulation time are still on the
  to-do list.
- `priority.py` ranks wells for manual review; it expects a `header_readings.csv` in WORKDIR (copy or merge the
  `.auto` file first). `validate.py` compares readings with the state header.
