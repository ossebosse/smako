#!/usr/bin/env bash
# One measurement lane per city; runs sequentially so a city's versions share conditions.
# Usage: run_lane.sh <city> <plan...> where plan items are VERSION:CASE
set -u
ROOT=/c/Users/ossia/projects/smako
PY=$ROOT/.venv/Scripts/python.exe
city=$1; shift
OUT=$ROOT/.local/recipes-20261022/$city
mkdir -p "$OUT"
for item in "$@"; do
  v=${item%%:*}; case=${item#*:}
  if [ "$v" = C ]; then src=$ROOT; else src=$ROOT/.local/wt/$v; fi
  echo "START $city $v $case $(date -u +%H:%M:%S)"
  w=$(cygpath -w "$src")
  ( cd "$src/backend" && PYTHONPATH="$w;$w\\backend" "$PY" -X utf8 -m backend.scripts.planner_acceptance_matrix \
      --inputs "$(cygpath -w "$ROOT/.local/fixes-review-20261018/data/$city")" --output "$(cygpath -w "$OUT")" \
      --label "$v" --matrix-case "$case" --repeat 3 ) > "$OUT/$v-$case.log" 2>&1
  echo "END $city $v $case rc=$? $(date -u +%H:%M:%S) $(grep -c wall_seconds "$OUT/$v-$case.log") iterations"
done
echo "LANE DONE $city"
