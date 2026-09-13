"""Ordinary production API probe; report actual freshness, never freeze live time."""

import json
from datetime import UTC, datetime
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

BASE = "https://beta.smako.nu"
opener = build_opener(HTTPCookieProcessor(CookieJar()))


def call(path, data=None):
    request = Request(
        BASE + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Origin": BASE, "Content-Type": "application/json"},
    )
    try:
        with opener.open(request, timeout=180) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


_, health = call("/health")
_, ready = call("/ready")
_, state = call("/api/personal/state")
root = Path("reports/fishfree-20260913")
request = json.loads((root / "acceptance.json").read_bytes())["request"]
request["personal"]["pantry_revision"] = state["revision"]
status, result = call("/api/plans", request)
output = {
    "observed_at": datetime.now(UTC).isoformat(),
    "health": health,
    "ready": ready,
    "http_status": status,
    "request": request,
    "plan" if status == 201 else "error": result["plan"] if status == 201 else result,
}
if status == 201:
    from backend.scripts.fishfree_acceptance import validate

    validate(result["plan"])
    _, saved = call("/api/plans/" + result["plan_id"])
    assert saved["plan"] == result["plan"]
    output["saved_reload"] = True
(root / "https-final.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2), encoding="utf8"
)
print(json.dumps({k: v for k, v in output.items() if k not in ("request", "plan")}, ensure_ascii=False))
