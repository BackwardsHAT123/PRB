#!/bin/zsh
# Headless-Chrome smoke test of the live page logic (compare panel, popups, GRID BHT option).
# usage: zsh tools/page_check.sh        (needs Google Chrome; starts a local server on a free port, then stops it)
cd "${0:A:h}/.." || exit 1
CHROME=${CHROME:-"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}
[ -x "$CHROME" ] || { echo "Chrome not found (set CHROME=...)"; exit 2; }
PORT=$((8800 + RANDOM % 200))
python3 -m http.server $PORT --bind 127.0.0.1 >/dev/null 2>&1 & SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
sleep 1
OUT=$("$CHROME" --headless=new --disable-gpu --no-sandbox --user-data-dir="${TMPDIR:-/tmp}/page_check_profile_$$" --virtual-time-budget=60000 --dump-dom "http://127.0.0.1:$PORT/tools/page_check.html" 2>/dev/null)
python3 -I -c "
import sys,re,json
t=sys.stdin.read();m=re.search(r'RESULT (\[.*\]) END',t,re.S)
if not m: print('no result from the page (did it load?)');sys.exit(2)
import html
r=json.loads(html.unescape(m.group(1)));bad=0
for ok,msg in r:
    print('ok  ' if ok else 'FAIL',msg);bad+=0 if ok else 1
print('all page checks passed' if not bad else str(bad)+' FAILED');sys.exit(1 if bad else 0)
" <<<"$OUT"
