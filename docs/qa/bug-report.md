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

- P1 release gate: unresolved upstream/deployment dependency remediation (triage completed), see `docs/security/findings.md` D-001. No new exploit asserted.
- Chrome/RTL/axe/actual PDF checks passed in CI run 42404096194. Physical devices, Firefox/WebKit and full manual screen-reader/keyboard acceptance remain unverified.
- Mobile physical tests, live provider configuration, hosting/TLS/external restore pending; no real customer action permitted in this review.
- Original spec red warning below 35% vs current amber warning documented in coverage; needs acceptance decision.

## QA-002 — P2 — rendered pages lack document language

- Reproduction: authenticate on the synthetic pilot or open login/contractor portal; inspect `html` at any audited width.
- Expected: a language matching the request locale. Actual: no `lang`, axe `html-has-lang` serious finding on all 44 states.
- Cause: native shared `web.layout` has no default language attribute.
- Fix: inherited server QWeb template sets request language with BCP-47 hyphenation. Verified in final run 42404096194: 44/44 states, no axe violations.

## QA-003 — P2 — icon controls and list selection lack accessible names

- Reproduction: use mobile search/view/actions menus, task completion, optional columns or list row selection with accessible-name inspection.
- Expected: meaningful accessible names. Actual: unnamed buttons/links/checkboxes (`button-name`, `link-name`, `label`, `role-img-alt`).
- Cause: native templates rely on icons/tooltips or an empty checkbox label.
- Fix: inherited OWL templates provide Hebrew control names, row/all-selection labels and hide decorative search icon from accessibility tree. Verified in final run 42404096194: 44/44 states, no axe violations.

## QA-004 — P2 — invalid native navigation/search ARIA structure

- Reproduction: axe scan of native desktop/mobile shell.
- Expected: valid role relationships and attributes. Actual: `aria-required-children`, `aria-required-parent`, `aria-allowed-attr`.
- Cause: systray is marked as menu despite containing independent widgets; app brand is a menuitem outside menu; search container has input-only autocomplete attribute.
- Fix: name/group systray, link semantics for brand, menuitem semantics for section controls, remove invalid search attribute. Verified in final run 42404096194: 44/44 states, no axe violations.

## QA-005 — P2 — scrollable content not keyboard reachable

- Reproduction: open narrow contractor price list; inspect keyboard access to horizontally scrollable renderer. Also detected on a content region.
- Expected: region can receive keyboard focus. Actual: axe `scrollable-region-focusable` serious failure.
- Cause: native renderer root has `tabindex=-1`; content wrapper not focusable.
- Fix: make list/content regions keyboard-focusable, retaining native cell/selection behavior. Verified in final run 42404096194: 44/44 states, no axe violations.

## QA-006 — P2 — mobile webclient disables zoom

- Reproduction: read native webclient viewport meta at mobile width.
- Expected: user can zoom text. Actual: `user-scalable=no`, axe `meta-viewport` moderate failure.
- Cause: native bootstrap viewport setting.
- Fix: inherited template preserves device width/initial scale and removes zoom prohibition. Verified in final run 42404096194: 44/44 states, no axe violations.

## QA-007 — P3 — owner dashboard exposes a technical record title

- Reproduction: open owner dashboard at 1440px. Breadcrumb displays `field.work.owner.dashboard,5` instead of a Hebrew title.
- Expected: meaningful title for a nontechnical user.
- Cause: transient model has no record-name field.
- Fix: readonly default Hebrew `name` on dashboard record. Verified by final rendered screenshot: Hebrew breadcrumb “מדדי בעלים”; see evidence/owner-dashboard-after.png.
- Before evidence: first-run `pre-deployment/action_field_owner_dashboard-1440.png`.

All rendered findings above were observed in artifact `13586141245`, run `42401972181`. The initial 44 axe scans are retained in `evidence/accessibility-before.json`. Severity here is application triage, distinct from axe's rule impact. These are six additional defect families, not one defect per repeated viewport/node.

## Final disposition

**7 defect families found; all 7 fixed and verified (6 P2, 1 P3).** No newly reproduced P0/P1 application defect remains. This does not close the dependency release gate or the acceptance gaps above. QA-003 and QA-004 required a second patch for copied Form/List cog templates and the tablet More menu; the intermediate failure is retained in Actions run 42403194963. Final run 42404096194 passed all browser regressions and 44 axe states. Before/after JSON and owner-dashboard screenshots are retained under evidence/.
