"""Keep the test process independent from a developer's repository dotenv.

``grocery_data.app.main`` exposes a module-level production app. Importing it
creates the default database factory, whose documented startup path loads the
repository ``.env``. Without this collection-time guard, a local field-server
setting such as ``FIELD_MODE_ENABLED=true`` can therefore change later
dependency-injected TestClient apps into the restricted field deployment.

Individual dotenv-loader tests deliberately remove this flag with
``monkeypatch`` and pass their own temporary dotenv path.
"""

from __future__ import annotations

import os

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
