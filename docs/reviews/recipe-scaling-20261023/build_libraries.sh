#!/usr/bin/env bash
# Synthetic scaling libraries in isolated worktrees (never in the main checkout).
# Total sizes = current library + synthetic recipes, imported in packs of 500.
set -eu
ROOT=/c/Users/ossia/projects/smako
PY=$ROOT/.venv/Scripts/python.exe
WORK=$ROOT/.local/scaling-20261022
cd "$ROOT"
"$PY" -X utf8 reports/recipe-scaling-20261019/generate_library.py --recipes 4738 --output "$(cygpath -w $WORK/drafts-4738.json)"
for extra in 738 1738 4738; do
  wt=$WORK/lib-$extra
  [ -d "$wt" ] || git worktree add -q --detach "$wt" HEAD
  w=$(cygpath -w "$wt")
  start=0
  while [ $start -lt $extra ]; do
    end=$(( start + 500 < extra ? start + 500 : extra ))
    part=$WORK/lib-$extra-part-$start.json
    "$PY" -X utf8 -I -c "
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8')); a,b=int(sys.argv[2]),int(sys.argv[3])
d['recipes']=d['recipes'][a:b]; d['pack_id']=f\"{d['pack_id']}-{a}-{b}\"
json.dump(d,open(sys.argv[4],'w',encoding='utf-8'),ensure_ascii=False)" "$(cygpath -w $WORK/drafts-4738.json)" $start $end "$(cygpath -w $part)"
    ( cd "$wt/backend" && RECIPE_PREPARATION_CACHE_ROOT="$(cygpath -w $WORK/prep-cache-build)" PYTHONPATH="$w;$w\\backend" "$PY" -X utf8 -m app.services.meal_library_cli author \
        "$(cygpath -w $part)" --output "$(cygpath -w $part.pack.json)" --report "$(cygpath -w $part.report.json)" --import ) | tail -1
    start=$end
  done
  echo "BUILT lib-$extra $(ls $wt/backend/app/data/recipes/meal-pack-*.json | wc -l) packs"
done
echo BUILD DONE
