"""Restricted recovery entrypoint: authenticated stored-plan reading, no pricing.

Run this entrypoint instead of app.main, with schedulers stopped and the latest
plan database. It deliberately never instantiates PlanStore or loads a universe.
"""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from app.api.account import install_account
from app.api.plan import _plan_actor_hash, _plan_read_forbidden
from app.config import get_settings
from app.services.beta_observability import BetaRequestMiddleware
from app.services.plan_store import PlanOwnerMismatchError, PlanReadOnlyError, PlanStore
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Smako: sparade planer i läsdrift", docs_url=None, redoc_url=None, openapi_url=None
)
app.add_middleware(BetaRequestMiddleware, settings_factory=get_settings)
install_account(app)


def checkpointed_connection():
    """Read a quiescent checkpointed store without creating WAL/SHM sidecars.

    Operators must stop all writers and checkpoint before mounting read-only.
    Refuse a nonempty WAL rather than silently omit its committed revisions.
    Keep writers stopped for the entire lifetime of this recovery service.
    """
    path = get_settings().plan_store_path.expanduser().resolve()
    wal = Path(str(path) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise sqlite3.OperationalError("recovery requires completed WAL checkpoint")
    return sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)


@app.middleware("http")
async def restrict_operations(request: Request, call_next):
    path = request.url.path
    authentication = path in {
        "/api/account/status",
        "/api/account/login",
        "/api/account/callback",
        "/api/account/logout",
    }
    plan_read = (
        request.method == "GET" and path.startswith("/api/plans/") and len(path.split("/")) == 4
    )
    public_read = request.method in {"GET", "HEAD"} and (
        path in {"/", "/personal", "/klassisk", "/health", "/ready", "/api/health"}
        or path.startswith("/static/")
    )
    if not (authentication or plan_read or public_read):
        return JSONResponse(
            status_code=503,
            content={
                "code": "recovery_read_only",
                "detail": "Sparade planer kan läsas. Nyplanering, omräkning och import är tillfälligt avstängda.",
            },
            headers={"X-Error-Code": "recovery_read_only", "Cache-Control": "no-store"},
        )
    return await call_next(request)


@app.get("/api/plans/{plan_id}")
def read_plan(plan_id: str, request: Request, revision: int | None = None):
    settings = get_settings()
    owner = _plan_actor_hash(request, settings)
    PlanStore._validate_owner_actor_hash(owner)
    try:
        with closing(checkpointed_connection()) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM consumer_plan_revisions WHERE plan_id=? AND (? IS NULL OR revision=?) ORDER BY revision DESC LIMIT 1",
                (plan_id, revision, revision),
            ).fetchone()
        if row is None:
            raise HTTPException(404, "plan not found")
        PlanStore._assert_owner(row["owner_actor_hash"], owner)
        result = {
            k: row[k]
            for k in (
                "plan_id",
                "revision",
                "parent_revision",
                "created_at",
                "operation",
                "app_version",
                "build_id",
                "price_universe_id",
            )
        }
        # Preserve the saved JSON verbatim semantically, including fields newer
        # than this reader. Never deserialize through a potentially older model.
        result.update(
            request=json.loads(row["request_json"]), plan=json.loads(row["response_json"])
        )
        return JSONResponse(
            result,
            headers={"Cache-Control": "private, no-store", "X-Smako-Mode": "recovery_read_only"},
        )
    except (PlanOwnerMismatchError, PlanReadOnlyError) as exc:
        raise _plan_read_forbidden(exc) from exc
    except (sqlite3.Error, ValueError, KeyError) as exc:
        raise HTTPException(
            503,
            "saved plan temporarily unavailable",
            headers={"X-Error-Code": "recovery_plan_unavailable"},
        ) from exc


@app.get("/health")
@app.get("/api/health")
@app.get("/ready")
def health():
    try:
        with closing(checkpointed_connection()) as db:
            db.execute(
                "SELECT plan_id, response_json, owner_actor_hash FROM consumer_plan_revisions LIMIT 1"
            ).fetchall()
    except sqlite3.Error as exc:
        raise HTTPException(503, "saved plan store unavailable") from exc
    return {"status": "ready", "mode": "recovery_read_only", "planning": False, "import": False}


static = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static), name="static")


@app.get("/")
@app.get("/personal")
@app.get("/klassisk")
def index():
    return FileResponse(
        static / "index.html",
        headers={"Cache-Control": "no-store", "X-Smako-Mode": "recovery_read_only"},
    )
