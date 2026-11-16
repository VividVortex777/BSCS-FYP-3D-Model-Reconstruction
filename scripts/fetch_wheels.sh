#!/bin/bash
# Resumable, SHA-256-verified download of every wheel the backend venv needs.
#
# Why: on a slow or unreliable network, pip throws away partial downloads
# when it is interrupted (the torch + CUDA wheels are ~3 GB). This script
# keeps partial files as *.part and resumes them on the next run, so it
# survives disconnects and shutdowns. Install offline afterwards.
#
# Usage (from anywhere; needs the project venv to exist for its pip):
#   bash scripts/fetch_wheels.sh                    # uses backend/requirements.lock.txt
#   bash scripts/fetch_wheels.sh path/to/reqs.txt   # other requirements file
#   # detached, so it keeps running if the terminal closes:
#   setsid nohup bash scripts/fetch_wheels.sh >> ~/FYP-data/wheels/fetch.log 2>&1 < /dev/null &
# Then:
#   venv/bin/pip install --no-index --find-links ~/FYP-data/wheels -r backend/requirements.lock.txt
#
# Environment overrides:
#   WHEELS_DIR  where wheels are stored   (default ~/FYP-data/wheels, outside Git)
#   PARALLEL    simultaneous downloads    (default 4)
#   SEED_DIR    folder of partial wheels to resume from (optional)
#
# Files written to WHEELS_DIR:
#   resolve_report.json  pip's resolution of the requirements (metadata only)
#   urls.tsv             name, version, url, sha256 for every wheel
#   sizes.txt            size and filename, used to fetch small files first
#   *.whl                verified wheels;  *.whl.part  partial downloads
# Delete urls.tsv to force re-resolution after changing the requirements.

FYP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQ="$(realpath "${1:-$FYP_ROOT/backend/requirements.lock.txt}")"
WHEELS_DIR="${WHEELS_DIR:-$HOME/FYP-data/wheels}"
PARALLEL="${PARALLEL:-4}"
SEED_DIR="${SEED_DIR:-}"
PY="$FYP_ROOT/venv/bin/python"

[ -f "$REQ" ] || { echo "requirements file not found: $REQ"; exit 1; }
[ -x "$PY" ] || { echo "project venv missing: run 'python3 -m venv venv' in $FYP_ROOT first"; exit 1; }
mkdir -p "$WHEELS_DIR" && cd "$WHEELS_DIR" || exit 1

# 1. Resolve the full dependency set once (downloads metadata, not wheels).
if [ ! -s urls.tsv ] || [ "$REQ" -nt urls.tsv ]; then
    echo "=== resolving $REQ"
    "$PY" -m pip install --dry-run --ignore-installed --quiet \
        --only-binary=:all: --report resolve_report.json -r "$REQ" || exit 1
    "$PY" - <<'EOF' || exit 1
import json
report = json.load(open("resolve_report.json"))
with open("urls.tsv", "w") as out:
    for item in report["install"]:
        info = item["download_info"]
        sha = info["archive_info"]["hashes"]["sha256"]
        meta = item["metadata"]
        out.write(f'{meta["name"]}\t{meta["version"]}\t{info["url"]}\t{sha}\n')
EOF
    : > sizes.txt
    cut -f3 urls.tsv | while read -r url; do
        size=$(curl -sIL "$url" | tr -d '\r' | awk 'tolower($1)=="content-length:"{s=$2} END{print s+0}')
        echo "$size $(basename "$url")" >> sizes.txt
    done
    echo "=== $(wc -l < urls.tsv) wheels, $(awk '{s+=$1} END{printf "%.0f", s/1048576}' sizes.txt) MiB total"
fi

fetch_one() {
    url="$1"; sha="$2"
    file="$(basename "$url")"
    if [ -f "$file" ]; then
        echo "$sha  $file" | sha256sum -c --status - && { echo "SKIP  $file"; return 0; }
        mv "$file" "$file.part"    # wrong hash: treat as partial, resume/redo
    fi
    if [ ! -f "$file.part" ] && [ -n "$SEED_DIR" ] && [ -f "$SEED_DIR/$file" ]; then
        cp "$SEED_DIR/$file" "$file.part"
    fi
    for attempt in 1 2 3 4 5 6 7 8 9 10; do
        curl -fL -C - --retry 20 --retry-delay 5 --retry-all-errors \
             --speed-limit 1024 --speed-time 60 -sS -o "$file.part" "$url"
        if echo "$sha  $file.part" | sha256sum -c --status -; then
            mv "$file.part" "$file"; echo "OK    $file"; return 0
        fi
        size_now=$(stat -c %s "$file.part" 2>/dev/null || echo 0)
        echo "RETRY $file (attempt $attempt, $size_now bytes)"
        # After 3 failed attempts assume the partial file is corrupt; restart it.
        [ "$attempt" -ge 3 ] && rm -f "$file.part"
        sleep 5
    done
    echo "FAIL  $file"; return 1
}
export -f fetch_one
export SEED_DIR

# 2. Download: smallest first so most packages finish early.
echo "=== start $(date '+%F %T')"
cut -f3,4 urls.tsv \
  | while IFS=$'\t' read -r url sha; do
        size=$(grep -F " $(basename "$url")" sizes.txt 2>/dev/null | cut -d' ' -f1)
        echo "${size:-0} $url $sha"
    done \
  | sort -n | cut -d' ' -f2- \
  | xargs -P "$PARALLEL" -L 1 bash -c 'fetch_one "$0" "$1"'

ok=0
while IFS=$'\t' read -r _ _ url _; do
    [ -f "$(basename "$url")" ] && ok=$((ok + 1))
done < urls.tsv
total=$(wc -l < urls.tsv)
echo "=== done $(date '+%F %T'): $ok of $total wheels verified"
[ "$ok" -eq "$total" ] && echo "ALL-WHEELS-READY"
