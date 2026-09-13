"""Run in the preserved prior image; check exact new saved payload compatibility."""

import argparse
import json
from pathlib import Path

from app.models import PlanRequest, PlanResponse

root = Path("/output")
parser = argparse.ArgumentParser()
parser.add_argument("--label", default="after")
parser.add_argument("--image", default="personal-v2-combined-403020-20260913b")
parser.add_argument("--output", default="rollback.json")
args = parser.parse_args()
request = json.loads((root / f"{args.label}.json").read_bytes())["request"]
PlanRequest.model_validate(request)
paths = list(root.glob(f"{args.label}-[123]-plan.json"))
assert len(paths) == 3
for path in paths:
    raw = json.loads(path.read_bytes())
    assert PlanResponse.model_validate(raw).model_dump(mode="json") == raw
(root / args.output).write_text(
    json.dumps(
        {
            "status": "PASS",
            "image": args.image,
            "new_payloads_exactly_readable": True,
            "database_restore": False,
        },
        indent=2,
    ),
    encoding="utf8",
)
print("Prior image reads all three new saved plan payloads exactly; no database restore")
