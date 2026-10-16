"""Start an isolated local UI/API with mock prices and a migrated empty database."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def environment():
    runtime = ROOT / ".local/dev"
    runtime.mkdir(parents=True, exist_ok=True)
    return {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(ROOT / "backend"), str(ROOT))),
        "PYTHON_DOTENV_DISABLED": "1",
        "APP_ENV": "development",
        "PRICE_PROVIDER": "mock",
        "PRICE_UNIVERSE_REQUIRED": "false",
        "PRICE_UNIVERSE_PREWARM_ENABLED": "false",
        "COMPLETE_RECIPES_ENABLED": "false",
        "OPENAI_API_KEY": "",
        "PRIMAT_API_KEY": "",
        "OWN_GROCERY_BASE_URL": "",
        "FIELD_MODE_ENABLED": "false",
        "PLAN_STORE_PATH": str(runtime / "plans.sqlite3"),
        "GROCERY_DATABASE_URL": "sqlite+pysqlite:///" + (runtime / "grocery.sqlite").as_posix(),
        "GROCERY_RAW_SNAPSHOT_ROOT": str(runtime / "raw_snapshots"),
        "PRICE_UNIVERSE_CACHE_ROOT": str(runtime / "price_universes"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--check", action="store_true", help="Migrate and check import, then exit")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    env = environment()
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "grocery_data/alembic.ini", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        check=True,
    )
    if args.check:
        subprocess.run(
            [sys.executable, "-c", 'from app.main import app; print("Local app import OK")'],
            cwd=ROOT,
            env=env,
            check=True,
        )
        return
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
    ]
    if args.reload:
        command.append("--reload")
    subprocess.run(command, cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    main()
