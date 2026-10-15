# Project rules

## Start recurring operations work here

- Read `docs/OPERATIONS.md`, then run
  `.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py status` from this root.
  This is a bounded read-only admin check, not collection or menu generation.
- Use `incidents` and `reproduce --snapshot-id ...` from that same entry point
  for current evidence. Do not begin by scanning all dated release archives.
- For consumer HTTP failures use `app-incident --request-id <actual reference>`.
  Status also reads recent app 5xx metrics. Keep client response time distinct
  from asynchronous metric persistence; unavailable exception evidence is unknown.
- Repairs require a current incident/signature, reviewed runtime, existing
  operation lease and explicit task authority. Preserve unknown/unreachable
  states and separate imported, published, loaded and receipted stages.

## Permanent repository and working discipline

- The permanent local development root is `D:\Projects\Smako`. This repository,
  with its own `.git` directory and intended main branch `master`, is authoritative
  for new development. Historical dated copies are preserved evidence, not new
  development workspaces. Do not create more standalone dated project copies.
- Before editing, inspect the working directory, `git rev-parse --show-toplevel`,
  the current branch and `git status --short`. Preserve existing user changes.
- Work on bounded branches and make small, traceable commits. Never force-push,
  rewrite history, reset or clean another task's work as routine preparation.
- One controlled writer owns each working copy. If concurrent work is needed,
  use explicitly created Git-worktrees of this same repository and integrate
  their branches deliberately. Check for other writers before backups/merges.
- Keep local data, secrets and environments outside the Git index. Follow
  `docs/DEVELOPMENT.md` for data restoration; ignored files are not automatically
  backed up. Review staged content, tracked sensitive paths and file sizes.
- Development, tests and local consolidation never authorize production
  activation, scheduler/Windows-task changes, live collection or profile changes.
- Read the current `docs/HANDOFF.md` and `docs/CONSOLIDATION.md` before continuing.
  Historical chats keep their old working directories; do not edit Codex databases.

## Application rules retained from the source projects

- Preserve the existing snapshot, source-strategy, promotion, PriceUniverse,
  GroceryContext, PhysicalStore, provider and CLI architecture. Do not create
  parallel pricing, promotion, assortment or refresh systems.
- PriceUniverse is shared and source-driven. Community evidence stays advisory,
  and `USER_SPECIFIC` offers must never enter the shared artifact.
- Keep product identity and price scope exact. Fuzzy names may suggest manual
  review but must never attach authoritative prices automatically.
- `own:coop:730400` is Coop Online Syd: `ONLINE_FULFILLMENT` with
  `online_price`. It is not a physical Lund shelf-price context. Keep Coop's
  physical offer feeds separate.
- Production Coop crawling is restricted to
  `COOP_ALLOW_FULL_CRAWL=true` and `COOP_ONLINE_CONTEXT_IDS=730400`. Never
  broaden this allowlist without separately verified source and scope evidence.
- Refreshes must retain valid LKG data on failure, validate candidates before
  atomic activation, report truthful source age, and use the shared operation
  lock. Never overlap a full refresh, source retry, backup or activation.
- Do not weaken freshness or quality gates to make status green. The default
  source states are FRESH under 36 h, AGING from 36 h, and STALE at 48 h.
  Per the user's 2026-10-15 price policy, these are observation-age warnings,
  not expiry dates for qualified ordinary prices. Retain base prices until a
  validated replacement; apply each campaign's actual validity dates for every
  chain. Missing/invalid provenance, source qualification and identity gates
  remain mandatory. Never renew timestamps when retaining prices.
- Never log, document or commit secrets, retailer credentials, raw receipt
  contents, cookies or browser/session identity. Do not implement challenge
  bypasses or undocumented retailer login automation.
- Preserve user work in this directory. Do not reset, clean, or remove data
  unless an exact disposable target has been verified first.
- Use Python 3.12. After relevant changes, run focused tests, Ruff and
  compileall; reuse unchanged, hash-stable verification instead of needlessly
  repeating expensive live collections.

- Permanent municipal acceptance: Coop, Stora Coop and X:-tra must use the same
  official municipality parameter through discovery, store-bound collection,
  validation, OWN, PriceUniverse and refresh selection. Verify Lund and another
  municipality with the same code; distinguish live network evidence from
  retained-data tests. X:-tra publications must come from each official store's
  current source links, never a fixed Skansvägen URL or saved Lund flyer.
  Preserve every discovered/unknown/failed store in coverage and report unknown
  PDF layouts explicitly. This never expands existing user area/store choices
  or authorizes production activation or changes to the pending ICA release.
