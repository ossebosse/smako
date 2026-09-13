"""Use the existing backup/lock/rollback routine, with this immutable release."""

from pathlib import Path

import combined_profile_activate as operation

operation.BUILD = "personal-v2-fast-403020-20260913c"
operation.ROLLBACK = "personal-v2-fast-403020-20260913a"
operation.STATE = Path("/opt/smako/evidence") / f"{operation.BUILD}-rollback-private.json"
operation.ENV_BACKUP = Path("/opt/smako") / f"production.before-{operation.BUILD}.env"

if __name__ == "__main__":
    operation.main()
