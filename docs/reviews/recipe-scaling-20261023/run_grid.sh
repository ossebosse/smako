#!/usr/bin/env bash
# Grid lane: <city> <case> then lines "LIB LABEL ARGS..." on stdin.
set -u
ROOT=/c/Users/ossia/projects/smako
PY=$ROOT/.venv/Scripts/python.exe
WORK=$ROOT/.local/scaling-20261022
city=$1; case=$2
OUT=$WORK/grid-$city-$case; mkdir -p "$OUT"
while read -r lib label args; do
  [ -z "$lib" ] && continue
  if [ "$lib" = 262 ]; then wt=$ROOT; else wt=$WORK/lib-$lib; fi; w=$(cygpath -w "$wt")
  ( cd "$wt/backend" && PYTHONPATH="$w;$w\\backend" "$PY" -X utf8 -m backend.scripts.planner_acceptance_matrix \
      --inputs "$(cygpath -w $ROOT/.local/fixes-review-20261018/data/$city)" --output "$(cygpath -w $OUT)" \
      --label L$lib-$label --matrix-case $case --repeat ${REPEAT:-2} $args ) > "$OUT/L$lib-$label.log" 2>&1
  echo "END $city $case L$lib-$label rc=$? $(date -u +%H:%M:%S) $(tail -n 1 $OUT/L$lib-$label.log)"
done
echo "GRID DONE $city $case"
