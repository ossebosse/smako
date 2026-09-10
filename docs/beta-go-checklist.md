# Lund beta GO checklist

This checklist separates code/configuration evidence from facts that can only
be established on the eventual public host. Completing local checks does not
mean the application is publicly deployed.

## 1. Local release/configuration gate

- Full Python, frontend, Ruff, compileall and production-build verification is
  green on one stable source tree.
- `docker compose ... config --quiet` succeeds with a private production env.
- Only approved Lund source/context allowlists are present.
- The active PriceUniverse manifest and artifact hash validate.
- A scratch restore reports `semantic_and_file_hash` for grocery data, plans
  and PriceUniverse. Original source timestamps and LKG links remain unchanged.
- Application rollback and PriceUniverse rollback have been rehearsed
  independently.
- The short beta-tester workflow remains current in
  [beta-testpaket-sv.md](beta-testpaket-sv.md).

## 2. Production smoke command

Run from an operator machine outside the server after DNS and ACME TLS work:

```bash
python deploy/scripts/production_smoke.py \
  --base-url https://beta.example.se \
  --timeout-seconds 45 \
  --request-cold-target-seconds 10 \
  --output reports/public-beta/production-smoke.json
```

The command rejects HTTP, credentials in the URL, redirects and malformed
responses. It verifies `/health`, `/ready`, the PWA manifest and one real
22350/5-meal/4-serving/BALANCED/max-2 request. The plan must contain five
recipes, at most two contexts, positive reconciled basket economics,
`BasketAuditor=PASS`, complete PriceUniverse provenance and zero live provider
calls. It then reloads the saved plan and proves its PriceUniverse ID and total
were not silently repriced.

A local rehearsal may add `--allow-http`, but that result is not production TLS
evidence. Exit 2 means the functional smoke passed but the request-cold target
was missed; do not hide that distinction.

## 3. External host/TLS gate

- The hostname resolves publicly to the intended host.
- Caddy obtained a normal ACME certificate; no browser exception is used.
- Only 80/443 are public; backend port 8000 is private.
- `/health` and `/ready` pass from a separate network.
- Response security headers and certificate chain are inspected externally.
- Production secrets are unique, private and not equal to their templates.
- An encrypted off-host backup exists and a scratch restore has passed.

## 4. Real-phone acceptance

Use at least one current iPhone/Safari or Android/Chrome over mobile data, not a
desktop fake-camera flag:

1. Open the real HTTPS hostname without a certificate warning.
2. Complete onboarding and create the standard plan.
3. Open two complete recipes and the grouped shopping list.
4. Confirm the context count, total and online-price wording are readable.
5. Reload/close/reopen and verify the saved plan is unchanged.
6. Deny camera permission once and verify a useful recovery message.
7. Allow camera permission, scan a known physical EAN-13 and verify the exact
   local product result.
8. Scan a valid unknown EAN and verify the missing-product report flow.
9. Submit a real issue only if one exists; otherwise use general feedback.
10. Exercise PWA installation and one offline shell load, then reconnect.

Record device, OS/browser versions, hostname, certificate issuer, build ID,
PriceUniverse ID, time and pass/fail. Never capture cookies, tokens or a raw
receipt in the acceptance report.

## 5. Rollback drill

Application release rollback and PriceUniverse rollback are intentionally
separate:

1. Retain the previous immutable application image and previous active
   PriceUniverse bundle.
2. Revert `APP_VERSION`/image with `up -d --no-build`; verify health/readiness
   and run the production smoke.
3. Separately stop scheduler, restore `--only-price-universe`, restart app and
   confirm the expected old universe ID/source ages.
4. Confirm database/community rows did not change during price-only rollback.
5. Roll forward again and repeat readiness/smoke.

Exact commands and privacy-erasure handling are in
[public-beta-deployment.md](public-beta-deployment.md) and
[production-backup-restore.md](production-backup-restore.md).

## 6. Invitation gate

Before sending the first tester link, an operator must explicitly sign off:

- **CODE:** stable full verification and production smoke pass;
- **CONFIGURATION:** source allowlists, schedule, secrets and freshness limits;
- **INFRASTRUCTURE:** public host, DNS, ACME TLS, persistent volumes and off-host
  backup;
- **MANUAL ACCEPTANCE:** real-phone camera/EAN and PWA checklist;
- **LEGAL/OPERATOR:** named contact, privacy/terms review and incident owner.

Any missing infrastructure/manual/legal fact stays a release blocker, not a
code failure and not something the repository may fabricate.
