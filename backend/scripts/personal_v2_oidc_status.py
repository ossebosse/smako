"""Only presence flags; never emit configuration values or session material."""

import json
import os

keys = ("SMAKO_OIDC_ISSUER_URL", "SMAKO_OIDC_CLIENT_ID", "SMAKO_OIDC_CLIENT_SECRET")
print(
    json.dumps(
        {
            "required_present": {k: bool(os.environ.get(k, "").strip()) for k in keys},
            "public_base_url_is_beta": os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
            == "https://beta.smako.nu",
            "session_key_at_least_32": len(os.environ.get("SECRET_KEY", "")) >= 32,
        }
    )
)
