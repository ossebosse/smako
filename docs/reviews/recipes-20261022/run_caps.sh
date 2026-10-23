#!/usr/bin/env bash
# Caps check for version C: uncapped reference, then capped run validated against it.
# Usage: run_caps.sh <city> <case...>
set -u
ROOT=/c/Users/ossia/projects/smako
PY=$ROOT/.venv/Scripts/python.exe
city=$1; shift
OUT=$ROOT/.local/recipes-20261022/caps-$city
mkdir -p "$OUT"
w=$(cygpath -w "$ROOT"); in=$(cygpath -w "$ROOT/.local/fixes-review-20261018/data/$city"); o=$(cygpath -w "$OUT")
run() { ( cd "$ROOT/backend" && PYTHONPATH="$w;$w\\backend" "$PY" -X utf8 -m backend.scripts.planner_acceptance_matrix \
          --inputs "$in" --output "$o" --repeat 1 "$@" ); }
for case in "$@"; do
  echo "START $city $case uncapped $(date -u +%H:%M:%S)"
  run --label Cu --matrix-case "$case" --uncapped > "$OUT/Cu-$case.log" 2>&1
  echo "END $city $case uncapped rc=$? $(date -u +%H:%M:%S)"
  run --label Ccap --matrix-case "$case" --uncapped-reference "$o\\Cu-$case.json" > "$OUT/Ccap-$case.log" 2>&1
  echo "END $city $case capped-vs-uncapped rc=$? $(date -u +%H:%M:%S)"
done
echo "CAPS DONE $city"
