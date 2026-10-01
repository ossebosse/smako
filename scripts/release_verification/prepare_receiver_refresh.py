"""One ordinary due-only refresh of isolated test data, with real serving reload.

Run the immutable release image with only the test /work mount and its own
env file. No scheduler is started. The Windows task is not involved.
"""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import uvicorn
from app.main import app

from deploy.scripts import run_daily_refresh as runner

root = Path("/work")
assert os.environ["GROCERY_DATABASE_URL"] == "sqlite:////work/grocery.sqlite"
assert os.environ["INTERNAL_APP_BASE_URL"] == "http://127.0.0.1:8000"
assert os.environ["DEMAND_REFRESH_ENABLED"] == "true"
assert os.environ["WILLYS_COLLECTION_LOCATION"] == "LOCAL_RELAY"


def save(name, value):
    (root / (name + ".json")).write_text(json.dumps(value, default=str, indent=2) + "\n")


subprocess.run([sys.executable, "/probe/ops_preflight.py"], check=True)
plan = runner.demand_refresh_plan(now=datetime.now(UTC))
save("oct01-demand-before", plan)
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning"))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
deadline = time.monotonic() + 600
while not server.started:
    if not thread.is_alive() or time.monotonic() > deadline:
        raise RuntimeError("isolated serving startup failed")
    time.sleep(0.2)
try:
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
        save("oct01-serving-before", client.get("/api/price-universe/status").json())
        code = runner.main()
        save(
            "oct01-refresh",
            {
                "exit": code,
                "finished_utc": datetime.now(UTC),
                "network": "real due-only retailer requests; isolated data",
                "runner": json.loads((root / "runner.json").read_bytes()),
            },
        )
        save("oct01-serving-after", client.get("/api/price-universe/status").json())
        save("oct01-demand-after", runner.demand_refresh_plan(now=datetime.now(UTC)))
        subprocess.run([sys.executable, "/probe/ops_preflight.py"], check=True)
        print(
            json.dumps({"exit": code, "ready_http": client.get("/ready").status_code}), flush=True
        )
finally:
    server.should_exit = True
    thread.join(60)
