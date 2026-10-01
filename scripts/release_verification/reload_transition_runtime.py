"""Use the normal authenticated internal reload route inside the isolated network."""

import json

from deploy.scripts.run_daily_refresh import _reload_runtime

print(json.dumps(_reload_runtime()))
