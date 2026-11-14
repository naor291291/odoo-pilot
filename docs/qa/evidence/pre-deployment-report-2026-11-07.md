# QA follow-up — final pre-deployment assessment

Date: 2026-11-07. **NO-GO for a real-customer deployment.** No main merge, deployment, live message, financial issuance, data reset or credential disclosure occurred. Draft [PR #20](https://github.com/naor291291/odoo-pilot/pull/20) contains the changes and evidence.

## Verified state, not assumed history

Remote main remains `e274e5c`; the follow-up started at `1f62897`, a report-only commit after executable `4bd513f`. Its completed Actions runs were checked and were green. The seven previous application defect families were already fixed and verified; they were **not seven open bugs**. There were 50 unresolved canonical dependency advisories. No AGENTS.md was found in the workspace/repository; existing specification, design, coverage and deployment documents were used. The older dirty checkout and existing pilot data were preserved.

Latest tested executable: **`cdea42a081d5750660d463d0b4fe3d011ee60b44`**, CI merge checkout `2831af23a15080dc459c871b6b80e514b5f6ec49`. [Integration run 42406366976](https://github.com/naor291291/odoo-pilot/actions/runs/42406366976) and [Security run 42406366952](https://github.com/naor291291/odoo-pilot/actions/runs/42406366952) both completed successfully. The preceding PDF-only run 42406149600 also passed. A final documentation/test-harness-only commit uses `[skip ci]`: production/runtime files remain exactly those tested; the added backup harness and adjusted ordinary PDF fixture were checked locally.

A full compatibility run was justified because the common image parser/sanitizer changed. Prior successful evidence was retained rather than discarding it or restarting baseline discovery. Tests ran on an isolated synthetic CI pilot, **not an updated existing Codespace or deployment**.

## Actual fixes and verification

1. Reproduced PyPDF2's unterminated-comment EOF loop using a 100-read bounded stream. Applied the upstream one-line EOF guard at image-build time, requiring exact PyPDF2 version/source. Two regressions pass. The previous report overstated direct custom PDF-route exploitation: PdfReader construction alone is not content-stream parsing; native PDF operations can invoke the vulnerable routine.
2. Updated only `lxml-html-clean` to hash-pinned **0.4.6**, with no dependency replacement. Odoo explicitly leaves this package unpinned for security fixes. Four tests verify selected version, base-tag rejection, escaped CSS import rejection and Hebrew/native rich-text sanitization. Three previously unresolved advisories are fixed.
3. Factored a shared Docker `runtime` stage so the reviewed Pillow refresh, PDF guard and cleaner override also have a defined release build path. Development derives from it. Deployment must pin the resulting approved image digest, not a stock Odoo digest. No image was deployed/published.
4. Added and ran seven mocked backup control-flow tests, plus matched-code/database/filestore rollback and monitoring/operator instructions. Real host setup remains external.

| Test group | Result |
|---|---|
| Native Odoo model/HTTP regression | **205 passed, 0 failed, 0 errors** |
| SMTP/Meta transport mocks | **6 passed**; no live sends |
| PDF EOF-backport regression | **2 passed**, including bounded baseline failure then fixed behavior |
| Native HTML-cleaner regression | **4 passed** locally and in actual image |
| Runtime security scenarios | **6 passed**: concurrent overpayment/idempotency, escaping/cache, read-only report, real PDF, logout replay |
| Existing Chrome suites | **4 passed**, including 14 journey-specific assertions; no captured JS/console/network errors |
| Axe/RTL/responsive states | **44/44 passed**, 11 screens × 375/390/768/1440; zero violations, execution errors, document overflow or failed same-origin responses; all RTL |
| Synthetic separate-database restore | Passed, **46 attachment checksums** verified |
| Backup failure-control harness | **7 passed locally**, fake Docker/Restic only |
| Source/history scans | Passed; advisory scan is informational and not a release gate by itself |

Final UI artifact contains **154 PNGs**. Manual screenshot inspection verified owner metrics at 1440px and contractor report at 390px; the broader four-suite browser actions remain automated. All seven previous defect families remain verified. PDFs were rendered with actual wkhtmltopdf, including multipage statements. Role/document isolation, collection/closure rules, contractor photos and ledger formulas retain their model/HTTP/browser evidence. Eight business areas are covered; see requirement-level boundaries rather than treating test counts as manual end-to-end process counts.

UI observations in loopback CI: median **373ms**, range **80–909ms**, across 44 states. These are navigation observations, not production load/SLA measurements. The existing 1,001-movement calculation test passes. No large-scale concurrent-user benchmark was performed.

## All 50 previously open dependency advisories reviewed

See `dependency-followup.csv` for **50 individual rows**, installed version/presence, candidate version, affected path, exploit prerequisites, compatibility decision and evidence. The original 146-row / 94-canonical mapping remains preserved. Updated raw scanner output has **138 records**, not 138 proven vulnerabilities.

| Follow-up disposition | Count |
|---|---:|
| Newly fixed and verified (PDF backport + cleaner update) | 4 |
| False positives: cryptography below affected introduced versions, required API absent | 2 |
| Existing native OpenSSL fix newly verified | 1 |
| Not reachable in measured configuration: auth_passkey/CBOR module uninstalled | 3 |
| Still unresolved: compatibility or exact native/deployment path | **40** |

Open severity: **3 critical, 21 high, 14 moderate, 2 low**. This is upstream advisory severity, not proof of an exploitable CRM endpoint. Thirty-one open advisories concern Pillow; 13.0.0 fixes exist, but Odoo/Python 3.12 pins 10.2.0 and a broad native image compatibility review has not been completed. Custom allowlisting is not blanket proof of safety for native Odoo. Crypto pairing, native HTTP/proxy/IDNA and SOAP paths also remain documented decisions. CBOR must be reassessed before activating passkeys or certifying a deployed module inventory. All packages are present in the CI image; no actual deployment image/host exists to inspect.

**Counts:** application bugs open at start: **0**; prior families reverified: **7**; new customer-facing application bugs reproduced/fixed: **0**; one library-level failure reproduced and corrected, and **4 canonical security advisories newly fixed**; currently open reproduced application bugs: **0**. Residual potential security findings: **40**, with the severity breakdown above. Exact exploitable-endpoint count is not established, so it must not be reported as zero or forty proven exploits.

## Specification coverage

39 requirements mapped: **23 verified, 9 partial, 6 external-blocked, 1 not yet tested**. Verified coverage is **23/33 = 69.7%** excluding the six externally blocked requirements, or **23/39 = 59.0%** of the full matrix. This is not 100% end-to-end certification; evidence scope is explicit per row. No requirement is classified wholly Not Implemented, but partial rows contain remaining implementation/acceptance work.

Verified areas include customer/dispatch models, document separation/access, payment and approval-before-closure, contractor isolation/photos, spreadsheet-based rates/reconciliation, owner metric calculations and signed webhook behavior. Partial coverage remains for exhaustive search/filter/two-tab/offline states, every native Project/CRM/settings dialog, full manual accessibility and broader performance. Live Morning/Gmail/WhatsApp are not tested; original customer PDFs are issued externally and uploaded, not legal financial issuance by this QA.

## Status and remaining work

| Area | Status | Remaining |
|---|---|---|
| Specification | Partially verified | 9 partial, 6 external, 1 not-yet-tested rows |
| Business workflows | Critical tested scope passes | Offline/two-tab/session-expiry edge cases and live providers |
| UI/UX | Seven previous fixes remain verified | Complete manual keyboard/screen-reader/contrast acceptance; native dialogs |
| Mobile/RTL | Four viewport widths pass | Physical iPhone/Android camera/home-screen/network checks, deferred by user |
| Security | Improved; release blocked | 40 unresolved advisories, exact host/module attestation |
| PDFs | Parser fix, real rendering and access pass | Live Morning issuance/import remains separate |
| Permissions | Tested role/company/document boundaries pass | Actual deployment users/groups/MFA acceptance |
| Performance | Bounded calculation and CI timings pass | Actual host sizing and representative concurrent load |
| Operations | Scripts/config reviewed, synthetic restore and mocked failures pass | Host, TLS, off-site provider/restore, logging/alerts and rollout rehearsal |

No current executed regression remains failed. The initial bounded PDF reproduction failed as intended and passes after the fix. An initial local cleaner test incorrectly rejected harmless empty SVG/Math containers and was corrected to assert removal of executable content; no application behavior was weakened. Firefox/WebKit, screen reader/full manual contrast, physical device/offline/network interruption and actual external backup/monitoring/provider acceptance were **not performed**. Axe still lists manual-review items; zero automated violations is not accessibility certification.

## Ordered closure plan — NO-GO

1. **Security release gate:** resolve the three critical Pillow/native-format findings and remaining high-priority open paths with supported backports or an isolated, tested compatibility upgrade. Record each row's resolution; preserve PDF/image/rich-text/transport regressions. Recheck measured module state on the eventual deployment image.
2. **Runtime and infrastructure gate:** build/pin the approved runtime image, select the host/domain, configure secrets/private ingress/HTTPS, off-site backup and a real matched database/filestore restore. Rehearse update/rollback; verify log rotation and alerts. This task authorizes preparation, not execution of deployment.
3. **Scope/integration gate:** configure controlled Gmail/Meta recipients and account permissions, then test real provider acceptance only with separate authorization. Keep missing channels disabled and explicitly excluded until accepted. Morning API remains a separate external dependency; manual externally issued PDFs stay supported.
4. **Acceptance gate:** complete physical-device checks when the user-authorized deployed test environment exists; finish keyboard/screen-reader/contrast and failure/recovery edge cases with synthetic data. Resolve documented product deviations such as amber vs red margin warning rather than silently changing business rules.

See `operational-readiness.md`, `requirements-coverage.md`, `bug-report.md`, and `dependency-review.md`. Final [UI artifact 13588260430](https://github.com/naor291291/odoo-pilot/actions/runs/42406366976/artifacts/13588260430) expires 2026-11-21. Compact scan results, runtime inventory, affected-range evidence and sanitized CI summary are committed under `evidence/`; original before/after screenshots remain available there. The previous assessment is retained as `evidence/previous-pre-deployment-report.md`.
