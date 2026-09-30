"""Write secret-bearing test environment only in /work; never print values."""

import argparse
import json
import secrets
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--policy", choices=["original", "five"], required=True)
args = parser.parse_args()
root = Path("/work")
from rollback_http import ORIGINAL

private_path = root / "ops-private.json"
if private_path.exists():
    private = json.loads(private_path.read_bytes())
else:
    private = {"key": secrets.token_hex(32), "admin": secrets.token_hex(32)}
    private_path.write_text(json.dumps(private))
    private_path.chmod(0o600)
env = {
    "APP_ENV": "development",
    "PYTHON_DOTENV_DISABLED": "1",
    "SECRET_KEY": private["key"],
    "BETA_ADMIN_TOKEN": private["admin"],
    "PUBLIC_BASE_URL": "http://127.0.0.1:8000",
    "INTERNAL_APP_BASE_URL": "http://127.0.0.1:8000",
    "GROCERY_DATABASE_URL": "sqlite:////work/grocery.sqlite",
    "GROCERY_RAW_SNAPSHOT_ROOT": "/work/raw",
    "PLAN_STORE_PATH": "/work/plans.sqlite",
    "PRICE_UNIVERSE_CACHE_ROOT": "/work/price-universes",
    "PRICE_UNIVERSE_REQUIRED": "true",
    "PRICE_UNIVERSE_PREWARM_ENABLED": "false",
    "PLAN_PREWARM_ENABLED": "false",
    "OWN_SOURCES_ONLY": "false" if args.policy == "original" else "true",
    "PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS": ORIGINAL
    if args.policy == "original"
    else ",".join(json.loads((root / "policy.json").read_bytes())["required_context_ids"]),
    "MAX_PRICE_AGE_HOURS": "48",
    "PRICE_AGE_WARNING_HOURS": "36",
    "REFRESH_CITY": "Lund",
    "REFRESH_POSTAL_CODE": "22350",
    "REFRESH_REPORT_DIR": "/work/reports",
    "REFRESH_RUNNER_STATUS_PATH": "/work/runner.json",
    "DEMAND_REFRESH_STATE_PATH": "/work/demand.json",
    "DEMAND_REFRESH_ENABLED": "false",
    "SOURCE_RELAY_INBOX": "/work/raw/source-inbox/willys",
    "WILLYS_COLLECTION_LOCATION": "LOCAL_RELAY",
    "COOP_ALLOW_FULL_CRAWL": "true",
    "COOP_ONLINE_CONTEXT_IDS": "730400",
    "ALLOW_PROVIDER_FALLBACK": "false",
    "ALLOW_MOCK_FALLBACK": "false",
}
if args.policy == "five":
    env.update(WILLYS_MUNICIPAL_CONFIG="/work/willys-config.json", REFRESH_MUNICIPALITY_CODE="1281")
    for prefix, directory in [
        ("COOP", "coop-municipal"),
        ("HEMKOP", "hemkop-municipal"),
        ("LIDL", "lidl-municipal"),
        ("CITYGROSS", "citygross-municipal"),
    ]:
        env[prefix + "_MUNICIPAL_ROOT"] = "/work/" + directory
        env[prefix + "_MUNICIPAL_OFFERS_ROOT"] = "/work/" + directory
        env[prefix + "_MUNICIPALITY_CODE"] = "1281"
        env[prefix + "_MUNICIPAL_ENABLED"] = "true"
        env[prefix + "_MUNICIPAL_OFFERS_ENABLED"] = "true"
    env.update(
        COOP_XTRA_OFFERS_ENABLED="true",
        ICA_STRUCTURED_OFFERS_ENABLED="true",
        ICA_STRUCTURED_OFFERS_ROOT="/work/ica-structured",
        WILLYS_FLYER_ENABLED="true",
        WILLYS_FLYER_MUNICIPALITY_CODE="1281",
        WILLYS_FLYER_ROOT="/work/willys-flyer",
    )
path = root / "ops.env"
path.write_text("".join(f"{k}={v}\n" for k, v in env.items()))
path.chmod(0o600)
print("Private test environment prepared; no production config or credentials copied.")
