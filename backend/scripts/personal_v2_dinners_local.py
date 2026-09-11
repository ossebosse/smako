"""Isolated actual ASGI/UI with frozen public facts and no retailer network."""

import os
import socket
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import uvicorn

from backend.scripts.personal_v2_dinners_browser import check
from backend.scripts.personal_v2_dinners_probe import fixture


def main():
    with tempfile.TemporaryDirectory(prefix="smako-dinner-ui-", ignore_cleanup_errors=True) as temp:
        root = Path(temp)
        os.environ.update(
            PLAN_STORE_PATH=str(root / "plans.sqlite"),
            PRICE_PROVIDER="mock",
            GROCERY_DATABASE_URL=f"sqlite+pysqlite:///{root.as_posix()}/grocery.sqlite",
        )
        from app.main import app
        from app.services.plan_store import PlanStore
        from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES

        from grocery_data.app.storage import (
            create_database_engine,
            create_schema,
            create_session_factory,
        )

        engine = create_database_engine(os.environ["GROCERY_DATABASE_URL"])
        create_schema(engine)
        app.state.community_session_factory = create_session_factory(engine)
        app.state.plan_store = PlanStore(root / "plans.sqlite")
        prepared, facts = fixture()
        GLOBAL_PREPARED_PRICE_UNIVERSES.activate(prepared)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                lifespan="off",
                log_level="error",
                access_log=False,
            )
        )
        thread = threading.Thread(target=server.run, daemon=True)
        with patch("app.services.personal_source_facts.load_retained_facts", return_value=facts):
            thread.start()
            while not server.started:
                time.sleep(0.05)
            try:
                check(f"http://127.0.0.1:{port}", Path("reports/personal-v2-dinners/local-browser"))
            finally:
                server.should_exit = True
                thread.join(timeout=5)
                engine.dispose()


if __name__ == "__main__":
    main()
