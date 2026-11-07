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

## Follow-up starting state and dependency correction

At follow-up start, **zero application defects were open**: QA-001–QA-007 had already passed final run 42404096194. The request's phrase “seven awaiting retest” was stale. All seven remain in the regression scope after the runtime changes. No new application defect has been reproduced during this follow-up.

### SEC-F01 — upstream PDF EOF loop (dependency availability defect)

- Baseline: PyPDF2 2.12.1 `ContentStream.__parse_content_stream` loops after an unterminated comment at EOF. The previous report correctly identified the installed parser, but overstated direct quote/invoice exploitation: constructing a reader does not by itself execute content-stream parsing. Native PDF compression/extraction can invoke the affected routine.
- Safe reproduction: synthetic `%...` comment in a `BytesIO` subclass capped at 100 reads. Baseline hit the cap; no unbounded CPU loop or live worker was allowed.
- Root cause: loop stopped only for CR/LF, not EOF.
- Fix: upstream's documented one-line EOF guard, applied only to exact supported PyPDF2 2.12.1 and recognized source during image build. Unexpected versions/source stop the build for review.
- Local retest: two parser tests pass. Full image CI and browser/PDF retest results are recorded in the follow-up report. No screenshot applies to the bounded library-level reproduction.
- This is one confirmed dependency defect, not an additional claim of a reproduced customer-facing outage. It closes one canonical security advisory when final image verification passes.

### Targeted HTML cleaner update

Three remaining canonical cleaner advisories are addressed by a hash-pinned 0.4.6 override, a package Odoo deliberately leaves unpinned for future security patches. Four local native-cleaner tests passed. An initial test incorrectly required removing harmless empty SVG/Math containers; it was corrected to assert removal of executable content while preserving Hebrew formatting. No product behavior was weakened to satisfy a test. Final image validation passed in 42406366976; these three advisories are closed for the measured runtime.

### Final follow-up retest

Run **42406366976** on executable head `cdea42a081d5750660d463d0b4fe3d011ee60b44` passed. QA-001: native signed malformed-event tests passed; QA-002–QA-006: 44 axe states have zero violations at all four widths; QA-007: actual final owner-dashboard screenshot shows the Hebrew breadcrumb. Native/model/HTTP authorization and four browser suites remain green. Seven existing application defect families remain closed, zero newly reproduced open application defects. The two PDF and four HTML-cleaner tests pass in the actual rebuilt image, closing four canonical dependency advisories. Three CBOR advisories are inactive-module classifications, two crypto entries are false positives, and one further vendor fix was verified; **40 unresolved dependency advisories remain separate from the application defect count**.
