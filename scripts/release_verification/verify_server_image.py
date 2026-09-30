"""Compare the packaged server source to the image and launch offline Chromium."""

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    archive = Path("/release.zip")
    root = Path("/srv/app")
    with zipfile.ZipFile(archive) as package:
        manifest = json.loads(package.read("RELEASE.json"))
    if manifest["kind"] != "server":
        raise ValueError("Not a server package")
    checked = []
    missing = []
    mismatch = []
    for name, expected in manifest["files"].items():
        if not name.startswith(("backend/", "grocery_data/", "deploy/")) and name != "pyproject.toml":
            continue
        target = root / name
        if not target.is_file():
            missing.append(name)
        elif hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            mismatch.append(name)
        else:
            checked.append(name)
    # Intentionally excluded from Docker by .dockerignore. They remain in the
    # source package as operator examples and must never become runtime config.
    allowed_missing = {"deploy/.env.production.example"}
    if mismatch or set(missing) - allowed_missing:
        raise AssertionError({
            "missing": missing[:8], "missing_count": len(missing),
            "mismatch": mismatch[:8], "mismatch_count": len(mismatch),
        })
    pip = subprocess.run(
        ["python", "-m", "pip", "check"], capture_output=True, text=True, check=False
    )
    if pip.returncode:
        raise AssertionError(pip.stdout)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto("about:blank")
            assert page.title() == ""
        finally:
            browser.close()
    result = {
        "commit": manifest["commit"],
        "package_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "checked_runtime_files": len(checked),
        "allowed_missing": missing,
        "mismatch": mismatch,
        "pip_check": "PASS",
        "chromium_offline_launch": "PASS",
        "network": "none",
    }
    (Path("/work") / f"image-verification-{manifest['commit'][:12]}.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
