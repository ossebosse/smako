"""Write smako-recipe-authoring-v1 files for the varied proteins batch (2026-11-26)."""
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dsl import pack  # noqa: E402

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
for cuisine in sys.argv[2:]:
    module = importlib.import_module(cuisine)
    data = pack(f"smako-varied-proteins-{cuisine}-20261126", module.RECIPES)
    (out / f"{cuisine}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(cuisine, len(module.RECIPES))
