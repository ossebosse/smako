# Smako — current state, 10 September 2026, 17:17 UTC

Beta live; VPS runtime release `automation-ica-20260909` unchanged.

- **Unattended Willys VERIFIED:** task `Smako Willys Local Relay`, ossia / Limited
  / **S4U**, daily **01:30 Europe/Stockholm**. No interactive desktop required.
  Actual session-0 filesystem/DNS/HTTPS/SSH/inbox probes passed with agent disabled.
- One completed new collection passed: 35m41s, 1,246 HTTP 200 responses, 883/883
  categories, 18,409 raw rows, 200 out-of-stock exclusions. **18,209 FRESH indexed
  Willys rows**, OWN / LOCAL_RELAY, observed 10 September 16:28:57–16:57:12 UTC.
  Artifact `90a8dd67cd5845ffb8618080048d80eb`, hash prefix `aacae3a19673`.
- Task result **0**, last start **10 September 18:28:16 Stockholm**, next
  **11 September 01:30**. Normal import/activation/search reload passed; workflow
  46m33s. Four beta searches and all planner modes passed, zero provider calls.
- Cancellation defect fixed: launcher job now terminates local Python/SSH children.
  Initial partial attempt was aborted without an artifact; old artifact hash intact.
  Actual cancellation probe and 30 focused relay tests passed; lint/compile/parser pass.
- **Next operator action:** tomorrow morning run from the repository:
  `pwsh -NoProfile -NonInteractive -File .\deploy\scripts\inspect_willys_relay.ps1`.
  Check last result/actual run, successful observation, VPS freshness and next run.
  **MULTI_DAY_RELIABILITY = UNOBSERVED** until actual scheduled nights are observed.
- WakeToRun/StartWhenAvailable true. Power plan unchanged: AC important wake timers
  only, battery timers disabled; actual sleep wake unverified. Powered-off PC can
  miss runs. VPS backup/refresh/Coop retry stay 02:47/03:17/06:17; all locks retained.
- ICA unchanged: 1,880 rows; no normalization/policy changes or ICA live requests.
  [Deferred ICA OWN research](sources/ica-own-deferred-research.md) preserves the
  requested future hypotheses and constraints. **Do not execute it without a new
  scoped milestone. Primat remains production.**

[Verification report](../reports/smako-willys-unattended-verification-20260910.md) ·
[Aggregate evidence](../reports/smako-willys-unattended-verification-20260910.json) ·
[Runbook](willys-local-relay.md) ·
[Prior HANDOFF preserved](../reports/handoff-before-unattended-verification-20260910.md).
Private evidence: `D:\smako-unattended-verify-20260910`; relay: `D:\smako-local-relay`.
