# QA defect register

Baseline `e274e5c`, 2026-11-07. Severity: P0 catastrophic, P1 blocks a core workflow or exposes private information, P2 recoverable functional/reliability problem, P3 minor polish. Missing evidence and external setup are tracked separately from reproducible product bugs.

## QA-001 — P2 — malformed signed WhatsApp payload returns HTTP 500

- Screen/process: incoming webhook, `controllers/field_whatsapp.py`.
- Reproduce only on isolated synthetic Odoo: configure the test database/company and fixture app secret; POST correctly signed JSON with `object=whatsapp_business_account` and `entry` containing a string/null rather than event objects. No Meta request is made.
- Expected: HTTP 400, no partial intake; valid signed events still work.
- Actual baseline: HTTP 500 (`AssertionError: 500 != 400`) in `TestFieldWhatsAppWebhook.test_signed_malformed_event_structure_is_rejected`.
- Cause: signature verification authenticated the bytes, but nested arrays/objects were not validated before `.get()` calls. Valid signatures do not guarantee valid structure.
- Fix: validate the entire batch's entries/changes/value/metadata/statuses/messages/text before any mutation. Keep HMAC, size, company and phone guards unchanged. No private payload included in the response.
- Regression: six malformed structures plus existing signed/unsigned/duplicate tests. **Post-fix full suite: 205/205 passed, 0 failures/errors. QA-001 fixed and verified.**
- Evidence: `docs/qa/evidence/test-summary.txt` (sanitized test results). No screenshot applies to this HTTP-only error.

## QA-H01 — not a defect — approval arrives after payment and invoice

A suspected ordering gap was tested on unchanged production code. `test_prepaid_invoice_closes_when_execution_is_approved_last` passed: no premature closure before approval, then one queued invoice and paid closure after approval. No business logic changed. Retained as regression coverage.

## Open acceptance/evidence gaps (not counted as newly reproduced bugs)

- P1 release gate: unresolved upstream/deployment dependency advisory triage, see `docs/security/findings.md` D-001. No new exploit asserted.
- Browser/RTL/axe/actual PDF checks require executable browser environment. Local Chromium exits with forbidden socket creation; Codespace restart requires GitHub sign-in. CI results must replace this pending status before approval.
- Mobile physical tests, live provider configuration, hosting/TLS/external restore pending; no real customer action permitted in this review.
- Original spec red warning below 35% vs current amber warning documented in coverage; needs acceptance decision.
