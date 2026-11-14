# Closed synthetic pilot — pre-deployment assessment

2026-11-14. Scope: 3–5 named testers, synthetic data only. **NO-GO until the security and host acceptance gates below are closed.** No merge, deployment, purchase, live integration, real financial document, customer data or data deletion occurred.

## Source of truth

Tested executable: `0bb562c19cb15d793448fcc2e6be8764e99569fe`, branch `qa/pre-deployment-review`, draft [PR #20](https://github.com/naor291291/odoo-pilot/pull/20). [Integration run 43607849101](https://github.com/naor291291/odoo-pilot/actions/runs/43607849101); [security run 43607849090](https://github.com/naor291291/odoo-pilot/actions/runs/43607849090). The final report commit changes documentation/evidence only and intentionally skips duplicate CI. Previous results are retained in `evidence/pre-deployment-report-2026-11-07.md`.

No AGENTS.md was found. Work began from existing QA reports and the seven already-closed application bug families. Baseline was not rediscovered. Full CI was necessary because the shared Pillow runtime changed, affecting native Odoo images, uploads and rendered documents.

## Changes actually made

- Hash-pinned Pillow **13.0.0** for Python 3.12 in the shared Docker runtime, including architecture-specific hashes. This deliberately overrides Odoo's older pin and requires compatibility evidence; no vendor certification is claimed. Both native and custom image paths use the selected version.
- Added two native image HTTP/encoder regression cases and Odoo's existing TestImage suite. Native WebP behavior remains unchanged; TIFF encoding is checked in a separate process, without expanding Odoo's server format registry.
- Extended the existing runtime journey with distinct, visibly synthetic quote/invoice PDFs, byte-for-byte open/download checks and rejection of closure before execution approval even after payment. Contractor assignment/photos, approval, payments and closure keep their existing checks. Separate browser suites exercise contractor-role actions.
- Added a closed-pilot Compose override, internal-CA Caddy/private source-IP ingress, disabled integrations/proxy settings, persistent volumes and bounded logs. Added resolved-configuration assertions and Caddy validation. See `deploy/PILOT.md` for a no-new-hosting-subscription path using an existing Linux computer and private LAN/VPN. No server was created.

## Executed verification

Both Actions workflows completed successfully. CI merge checkout: `e6dc727b0a2eca6e46b39aa7c5e801f1d3ba667c`.

| Verification group | Result |
|---|---|
| Odoo integration / permissions / business rules | **207 passed**, 0 failures/errors (205 retained + 2 new) |
| Upstream native Odoo TestImage | **15 passed** |
| Transport mocks / PDF EOF / HTML sanitizer | **6 / 2 / 4 passed** |
| Runtime security and synthetic PDF lifecycle | **7 passed** |
| Chrome suites | **4 passed**, including 14 journey assertions; no captured JS/console/network errors |
| RTL / responsive / axe | **44/44 passed**, 375/390/768/1440px; zero automated violations, overflow, execution errors or failed requests; all RTL |
| Separate PostgreSQL + filestore restore | **PASS**, 48 attachment checksums; PostgreSQL client/server major 16 |
| Local mocked backup failure controls | **7 passed** |
| Resolved Compose assertion groups | **7 passed**; Caddy validation also passed |
| Startup / role login / preserved restart state | **PASS** |

UI artifact has **154 PNGs**. The 390px contractor draft screenshot was visually inspected; the rest of this round's UI evidence is automated. No phone hardware or manual full accessibility certification is implied. [UI artifact](https://github.com/naor291291/odoo-pilot/actions/runs/43607849101/artifacts/14119592365) and [runtime/restore artifact](https://github.com/naor291291/odoo-pilot/actions/runs/43607849101/artifacts/14119542581) expire 2026-11-28. Compact JSON evidence is committed under `evidence/pilot-2026-11-14/`.

The first new integration run 43607495983 passed the original 205 Odoo tests but failed two newly added test assumptions: native Odoo intentionally leaves WebP unresized and restricts Pillow's plugin registry. Tests were corrected to match the documented behavior and run TIFF in a separate process. No product behavior was weakened to satisfy the tests. No manual browser session on the user's existing pilot or physical phone was performed in this round.

## Security disposition

All 50 historical follow-up rows remain in `dependency-followup.csv`. **35 fixed** (4 retained previous fixes + 31 Pillow fixes), 2 false positives, 1 previously verified native vendor fix, 3 inactive-module conditions, and **9 unresolved**. Remaining severity: **0 critical, 3 high, 4 moderate, 2 low**. These are unresolved advisories, not nine confirmed exploitable CRM endpoints. Updated image audit has 76 raw records; it is not an exploitable-vulnerability count. All three original Critical Pillow findings now use the fixed release.

See `pilot-security-followup.md` for CVE/GHSA, impact and evidence. Residual High paths concern cryptography RSA key exchange, pyOpenSSL DTLS cookie callbacks and urllib3 HTTPS-proxy TLS policies. The intended private/no-egress configuration reduces exposure, but resolved YAML is not proof that all runtime/native attack paths are absent. They remain open; no blanket crypto upgrade was made without compatibility validation.

Customer-facing application bugs open at start: **0**; new reproduced application bugs: **0**; previously fixed families retained: **7**. New test-harness errors corrected: **2**. Security fixes in this round: **31 canonical advisories**. No unrelated cosmetic redesign/refactoring was performed.

## Requirements and scope boundaries

The 39-row specification matrix remains **23 verified, 9 partial, 6 external-blocked, 1 not yet tested**: 23/33 = 69.7% of requirements excluding external dependencies (23/39 = 59.0% overall). The extra image and document regressions strengthen existing evidence but do not complete every edge case of a partial requirement. Closed synthetic pilot scope excludes live Morning/Gmail/WhatsApp, actual payments and real-customer documents; it does not waive authorization or data integrity checks.

Physical camera/home-screen installation, Firefox/WebKit, full screen-reader/manual keyboard acceptance, comprehensive two-tab/offline/session-expiry behavior and actual host load/monitoring are not newly verified. No claim of complete specification or production readiness is made.

## Remaining release gates, in order

1. Resolve or demonstrate non-reachability of the **three High** dependency paths in a running, attested closed-pilot configuration; retain each advisory's evidence. Remaining lower-severity findings need explicit disposition. Configuration validation alone is insufficient.
2. Select an existing suitable host/private network (or approve another solution separately), pin the reviewed runtime and other image digests, configure secrets and named synthetic tester accounts. Test actual HTTPS/source-IP denial, no-egress, private ports and persistence. No deployment is authorized by this task.
3. Configure a durable external backup destination and verify real database+filestore restore and operator recovery on the chosen host. CI synthetic restore and mocked failure controls do not certify an external backup service.
4. Run the host smoke list in `deploy/PILOT.md` before inviting testers, including the synthetic lifecycle and role/document isolation. Keep providers off. Production with real customers remains **NO-GO**.
