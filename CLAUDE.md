# Smako

@AGENTS.md

## Cloud sessions (Claude Code on the web/projects)

- The Windows paths and `.venv\Scripts\python.exe` commands in AGENTS.md apply to
  the owner's workstation. In a cloud clone use Linux equivalents:
  `python3.12 -m venv ../venv && ../venv/bin/pip install -r requirements-dev.txt`,
  then `../venv/bin/python -m pytest ...`.
- Clones are shallow. Tests that read old commits (for example
  `test_request_parity_against_pre_change_frontend`) need
  `git fetch --depth=2000 origin main` first.
- Browser tests use the preinstalled browsers in `$PLAYWRIGHT_BROWSERS_PATH`. If
  the pinned Playwright cannot find them, install the matching Playwright version
  into the venv for the test run only; do not change the lock file for it.
- Testing (see docs/TESTING.md): while working, run only the test files the change
  touches. Before opening a PR, run `-m "not live and not slow" -n auto --dist loadfile`
  over the affected suite. Leave the full suite, including `slow`, to CI; run it
  locally only when a change is broad (shared planner, conftest, data model).
- Work on a branch and open a pull request against `main`. Never activate beta,
  change production or run live collection from a cloud session.
