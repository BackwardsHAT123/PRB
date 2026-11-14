#!/bin/zsh
# usage: ocr_dir.sh SRC_DIR OUT_DIR   (resumable: skips files already OCR'd; prints DONE at the end)
# HDR_OCR = path to the compiled ocr binary (default: ./ocr next to this script; build it with build_ocr.sh)
OCR=${HDR_OCR:-${0:A:h}/ocr}
[ -x "$OCR" ] || { echo "ocr binary not found at $OCR (run build_ocr.sh)"; exit 1; }
mkdir -p "$2"
n=0
for f in "$1"/*.png; do b=$(basename "$f" .png); [ -s "$2/$b.tsv" ] || { $OCR "$f" > "$2/$b.tsv.part" 2>/dev/null && mv "$2/$b.tsv.part" "$2/$b.tsv"; }; n=$((n+1)); [ $((n % 100)) -eq 0 ] && echo "$n files checked, $(ls "$2" | grep -c tsv$) OCR'd"; done
echo "DONE $(ls "$2" | grep -c 'tsv$') OCR'd"
