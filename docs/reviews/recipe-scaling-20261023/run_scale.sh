#!/usr/bin/env bash
# Scaling lane for one city: <city> <label-suffix> <extra matrix args...>
# Runs every library size, per-pack and merged search, repeat 2 (cold, warm).
set -u
ROOT=/c/Users/ossia/projects/smako
PY=$ROOT/.venv/Scripts/python.exe
WORK=$ROOT/.local/scaling-20261022
city=$1; suffix=$2; shift 2
OUT=$WORK/scale-$city; mkdir -p "$OUT"
for lib in 738 1738 4738; do
  wt=$WORK/lib-$lib; w=$(cygpath -w "$wt")
  for mode in ${MODES:-perpack merged}; do
    extra=(); [ $mode = merged ] && extra=(--merge-generations)
    label=L$lib-$mode$suffix
    echo "START $city $label $(date -u +%H:%M:%S)"
    ( cd "$wt/backend" && PYTHONPATH="$w;$w\\backend" "$PY" -X utf8 -m backend.scripts.planner_acceptance_matrix \
        --inputs "$(cygpath -w $ROOT/.local/fixes-review-20261018/data/$city)" --output "$(cygpath -w $OUT)" \
        --label $label --matrix-case standard --repeat 2 "${extra[@]}" "$@" ) > "$OUT/$label.log" 2>&1
    echo "END $city $label rc=$? $(date -u +%H:%M:%S) $(tail -n 2 $OUT/$label.log | tr '\n' ' ')"
  done
done
echo "SCALE DONE $city"
