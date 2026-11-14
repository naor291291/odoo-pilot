# Pre-deployment QA report

Date: 2026-11-07. **Decision: No-Go for a real-customer pilot.** Application regressions pass, but unresolved dependency risk and operational prerequisites remain. No deployment, main merge, live provider send or financial document issuance was performed.

## Tested revision and Actions

Executable head: `4bd513f5249402c1a77fb1a2107d8aac3b7a475c`; GitHub PR merge checkout: `ae2d8a90919b40b1cfef7704278ab7f5f8d44124`. Draft [PR #20](https://github.com/naor291291/odoo-pilot/pull/20). A subsequent documentation/evidence-only commit uses `[skip ci]`; the executable tree is unchanged and the successful suites are not restarted just for reports.

- [Final integration run 42404096194](https://github.com/naor291291/odoo-pilot/actions/runs/42404096194): **success**, including native tests, runtime security, real Chrome journeys, axe, synthetic backup restore and visual report assembly.
- [Final security run 42404096013](https://github.com/naor291291/odoo-pilot/actions/runs/42404096013): source/history and inventory jobs succeeded. The advisory job reports findings without blocking CI; green does not mean vulnerability-free.
- Initial current-work run 42401972181 failed on accessibility; second run 42403194963 narrowed the failures to two rule categories. Final run fixed both. Successful baseline tests were retained; follow-up CI was necessary to verify changed templates/image.
- Runtime: Odoo `18.0-20261102`, Python 3.12.3, Ubuntu Noble-derived container, PostgreSQL 16, actual wkhtmltopdf. Existing stopped Codespace was older (PR #17); it was not modified or certified current. The older dirty local checkout and pilot data were preserved.

## What actually ran

**Eight business areas covered**, with bounded model/HTTP/browser evidence: clients/inquiries/dispatch; quote/invoice attachment flows; payments/closure; contractor reporting/photos; pricing/reconciliation; owner metrics; role/document isolation; mocked inbound/outbound integrations. Coverage per requirement is in `requirements-coverage.md`; this is not a claim that every requested edge case passed.

| Test set | Final result |
|---|---|
| Native Odoo model/HTTP regression | **205 passed, 0 failed, 0 errors** |
| Mocked SMTP/Meta transport tests | **6 passed, 0 failed** |
| Runtime security scenarios | **6 passed**: concurrent overpayment, duplicate submission, HTML escaping/cache, read-only report, actual private PDF, logout session replay |
| Existing Chrome suites | **4 passed**: statement/PDF, guided business flow, CRM screens/roles, owner/contractor journeys |
| Journey-specific assertions | **14 passed**, no captured JS/console/network errors |
| New accessibility/responsive audit | **44/44 states** (11 screens × 375/390/768/1440); zero axe violations, errors, document overflow or failed same-origin responses; all RTL |
| Synthetic backup restore | Passed into separate database; 46 attachment checksums verified, record counts matched |
| Source/history security scans | Passed; dependency findings remain separately open |

The backup fixture contained 8 leads, 7 tasks, 47 attachments, 33 payments and 2 entitlements. This proves the scripted synthetic restore, not external storage durability or production recovery. Statement rendering exercised one-page and four-page real Hebrew PDFs. Financial rules, partial/full payment, closure guards, duplicate/concurrent submissions and unauthorized document/contractor access were exercised with synthetic data. No real customer/provider messages or charges occurred.

**154 PNG screenshots** were captured in the final UI artifact. UI load observations on loopback CI: median 323ms, min 63ms, max 772ms across 44 states; this is not a production SLA or load test. The existing 1,001-movement calculation test passed. Manual screenshot review covered mobile work hub, contractor report, price list and desktop owner metrics; not every image/dialog received manual acceptance.

## Defects and fixes

**7 reproduced defect families; 7 fixed and verified: 6 P2, 1 P3.** Malformed signed WhatsApp input returned 500; document language was missing; controls lacked accessible names; native ARIA relationships were invalid; scroll areas were not keyboard-focusable; mobile zoom was disabled; owner metrics exposed a technical record title. See `bug-report.md` for reproduction, cause, fixes and retests. The suspected invoice/payment-before-approval ordering defect did not reproduce and is retained only as a regression test.

Supported Pillow package update from `10.2.0-1ubuntu1.3` to `.4` newly applies ten Noble security fixes in the rebuilt CI/development image. This is distinct from the seven application defects and does not update an existing Codespace or deployment.

## All 146 dependency records classified

146 records / 13 packages map to **94 canonical advisories** (95 original IDs with one alias duplication). Canonical upstream severity: 4 critical, 48 high, 40 moderate, 2 low. Each CSV row records prerequisites, affected paths, pilot relevance and evidence.

| Disposition | Canonical count |
|---|---:|
| Vendor fix verified against full installed package version | 34 |
| Windows-only, not applicable to measured Linux runtime | 7 |
| Required codec/wheel condition absent in measured image | 3 |
| Still open: patch or native-path evaluation required | 50 |

The remaining 50 comprise **3 critical, 25 high, 20 moderate, 2 low**; they are not 50 demonstrated exploits. Priorities: reachable PDF parser, native HTML sanitizer, broader native image paths. Custom JPEG/PNG/WebP restrictions reduce exposure to the three critical image findings but do not establish that all native Odoo paths are safe. No exploit payload was run, no finding suppressed, no blanket pip upgrades applied. `dependency-review.md`, the 94-row triage, the 146-row mapping and vendor evidence preserve the classification. Raw scanner count remains 146 because upstream Python versions do not reflect distro backports.

## Open gaps and deployment gate

- **Dependencies:** complete remediation/compatibility/native-path validation for the 50 open advisories; no known-exposure-free certification.
- **Infrastructure:** permanent host, HTTPS, external backups and a tested external restore are not configured. No deployment authorized in this task.
- **Integrations:** Gmail sender selected but SMTP credentials not configured; Meta permissions/templates and live tests pending; Morning real-account/API validation pending. Original scope uses externally issued PDFs uploaded to Odoo.
- **Acceptance:** actual phones/camera/home-screen shortcut are deferred by the user until deployment. Firefox/WebKit, screen reader, full manual keyboard/contrast checks, offline/mobile network interruption, session-expiry and two-tab conflicts remain incomplete. Axe reports manual-review items for contrast, bypass and ARIA; zero automated violations is not WCAG certification.
- **Product deviations:** amber below 35% margin vs original red; ambiguous original profitability wording; no interactive dashboard date filter. See coverage document. Not every native Project/CRM/settings dialog was tested.

No newly reproduced P0/P1 application bug remains in the tested scope. Nevertheless, **No-Go for real customer data** until dependency and operational gates are closed. Synthetic demonstrations/review can continue. The whole specification is not certified complete.

## Evidence and limitations

- `evidence/accessibility-before.json` / `accessibility-after.json`: machine-readable findings for all 44 states.
- `evidence/owner-dashboard-before.png` / `owner-dashboard-after.png`: actual screenshots showing corrected Hebrew title.
- `evidence/test-summary.txt`: sanitized server results; `permissions-matrix.md`: role boundaries; `evidence/formula-review.md`: original spreadsheet formulas compared to implementation/tests.
- Final full UI artifact: [13587106253](https://github.com/naor291291/odoo-pilot/actions/runs/42404096194/artifacts/13587106253), runtime artifact 13587315839. Actions artifacts expire 2026-11-21; compact evidence above is retained in git.
- Local Chromium execution failed due a socket restriction; all claimed rendered checks above came from actual CI Chrome. The stopped Codespace was not used as a substitute for current-code verification.
- Project-local Interface Design, Vercel Web Design Guidelines and Playwright CLI instructions were read/installed; official Odoo 18 testing source was used. Provenance is recorded in `tool-provenance.md`.

Requirement status totals (39 rows; verification scope bounded per row): Implemented & Verified: 23, Partially Implemented: 9, Blocked by External Dependency: 6, Not Yet Tested: 1.
