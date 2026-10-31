# Verification record

Baseline: `24d22c3034a1819c5b35667f60a4ef29296113ba`. Code is on `feature/security-hardening`; module `18.0.13.0.0`. All fixtures are synthetic. No shared Codespace or third-party service was attacked, upgraded or reconfigured.

## Actual local checks

- Real Odoo Community 18/PostgreSQL integration: **187 test methods, zero failures/errors**, including all 169 baseline methods and 18 new methods. Output explicitly confirmed `Verified 187 Odoo integration tests`. No new skip or expected-failure marker was used. Test counting now derives the expected number from source rather than silently excluding newly named suites.
- Baseline reproduction: eight focused regression methods against unchanged application code produced **nine failed assertions, zero errors** (two users in a subtest). They covered private draft access, review/audit defaults, task-link defaults, frozen pricing defaults, photo parent lock/count/format defaults and metadata retention. An earlier fixture used an inconsistent state and hit an existing constraint; it was corrected before recording this clean reproduction.
- Targeted fixed suite: **13 methods, zero failures/errors**. The full 187-method suite then passed, including five new real HTTP cases. Core pricing, receipt cancellation, approval, immutable events, historical statements, company/contractor isolation and report parity remain in the suite.
- Two real authenticated sessions against the isolated pilot: one of two simultaneous overpayments succeeds; repeated concurrent use of one payment dialog creates one additional receipt; stored totals are correct. HTML escaping/no-store, read-only report rendering and replay after logout are checked. Local PDF rendering was explicitly not executed because wkhtmltopdf is absent; CI runs the helper without the local `--skip-pdf` flag.
- Paired offline DB/filestore restore into a new database: counts and attachment checksum verification passed; source database remained separate and private backup stayed under ignored `.local-data/`. Connections are closed before deleting only the drill-created database. This is not an interactive restored-site or encrypted/off-site backup claim.
- Gitleaks **8.30.1**, official release SHA256 verified: **103 reachable commits, all available branches**, approximately 1.17MB scanned, zero recognized leaks, no allowlist added. Redaction enabled. This does not inspect old deleted/unreachable refs, private external artifacts or hidden/live runtime secrets.
- Bandit **1.9.4**: addon production Python, **1,904 source lines, zero findings** at all severities. Tests excluded. Bandit has no Odoo-specific ACL understanding, so native regression tests/manual tracing remain essential.
- pip-audit **2.10.1**: local installed Odoo Python packages; 137 raw advisory records/90 distinct primary IDs across 13 packages. Not treated as 137 verified exploits. No automated fixes or ignored advisory IDs. Docker distribution/backport triage is a separate CI inventory.
- Python compilation, `git diff --check`, full Git history/blame for the changed guards, caller tracing and manual review of Python/JS/QWeb/security/config/CI paths. There are no custom npm packages to audit. No Semgrep/Trivy/DAST campaign or OS exploit testing was run locally.

The local launcher uses a wrapper for the test namespace and a separate PostgreSQL data directory/port. Its stock restart smoke cannot reliably identify wrapped processes by the installed `odoo` executable name; that local attempt failed and was not reported as passing. The managed local lifecycle then verified the HTTP/runtime cases. Official-image startup/restart, real PDF and desktop/mobile Chrome are required separately in GitHub CI.

## Scenario coverage

| Required scenario | Evidence |
|---|---|
| Foreign contractor job/photo/document | Existing scoped portal tests plus new native binary/attachment/extra-photo ID HTTP cases |
| Old contractor after reassignment | Existing detail/main/extra-photo revocation tests |
| Forged task/company/contractor/file IDs | ORM locked assignment/party/company tests; default-link/photo-parent regressions; foreign removal HTTP case |
| Operations financial read/search/group/export | New `test_private_fields_deny_read_search_aggregation_and_export`; export permission deliberately granted to fixture to test deeper protection |
| Private transient records | New search/read/export/action/creator/company/kind tests |
| Guest/logged-out direct URL/PDF | New real HTTP redirects/attachment denials and runtime session replay; not just hidden buttons |
| Direct public action/private method RPC | New contractor RPC cases; existing business action authorization cases |
| Locked approved amounts/reports/photos | Existing pricing/dispatch/review/collection cases plus default-parent lock regression |
| XSS/escaping/CSRF | Existing CSRF denial; new literal script-text HTTP report input and report-reference escaping checks |
| Image type/size/count/metadata/resize/error | Existing invalid/file/count limits plus explicit/default image and EXIF/GPS/orientation/WebP regressions |
| Parallel/repeated money requests | New two-session runtime fixture; existing batch, uniqueness and wizard-idempotency suite |
| Statement/source/PDF parity and arithmetic | Existing statement suite; new direct provider HTTP/role cases; mandatory real PDF runtime/Chrome in CI |
| Backup and restore | New offline separate-DB drill with DB table counts and every referenced attachment checksum |

Two concurrent requests are a controlled correctness check, not a production load/concurrency benchmark. No sustained availability test, real phone, screen reader, complete 50MP memory profile, all native token paths, full Odoo core/JS/OS CVE review, proxy TLS/MFA setup or live Morning integration was verified.

## Skills and source use

Read upstream SKILL instructions for OpenAI Security Threat Model/Best Practices, Trail of Bits Differential Review and unclecatvn Odoo 18. Read the threat output contract, differential methodology/adversarial/reporting resources and relevant Odoo security/controller/model/report/testing/API-highlight guidance; inspected browser-JS security guidance for the custom DOM code. No matching Python/Odoo guide exists in OpenAI Best Practices; Odoo-specific conclusions use official/local framework source instead of Django/Flask assumptions. Third-party skill scripts were not executed.

Source checks included Odoo 18 `models.py` default injection/field access/transient behavior, `ir_binary.py`, native binary/report controllers, image processing, session and login cooldown code. Official deployment/update/security documentation was consulted. Native source/runtime behavior takes precedence over guide examples. No external scanners were given credentials or customer data.

## CI and release evidence

CI runs the same full suite and official-image startup/restart smoke, mandatory real PDF/runtime checks, the three existing headless Chrome suites, and the restore drill. Source/history scans fail closed; dependency inventory is visibly advisory pending reviewed vendor/path triage. Results and exact executable commit/run references are added after the PR's checks finish. A prepared workflow or a previous PR's screenshots are not evidence that the new branch passed.


### Exact source and scanner evidence

Remote executable head: `10ae02c153e8a2e2af6f0dab70b2a104cb3bfb34`; source tree `9a7ffeb2be00bd7b9f18ff40b00285f343b0f78b`, byte-identical to local tested commit `2c77c614907347b875ed869f1c69e5adf4607be8`. GitHub tested its generated PR merge `28fadd734ade3b8882e1fbf8d6d4267afbdc19f8` into unchanged base `24d22c3`. No repository history was force-pushed or overwritten.

[Security workflow 41231106608](https://github.com/naor291291/odoo-pilot/actions/runs/41231106608): source/history passed, **104 commits** scanned with no recognized leak; Bandit passed. [Source results](https://github.com/naor291291/odoo-pilot/actions/runs/41231106608/artifacts/13053816878). Dependency inventory completed, audit emitted its documented warning: **146 raw / 95 distinct primary IDs / 13 packages**; [inventory/advisory artifact](https://github.com/naor291291/odoo-pilot/actions/runs/41231106608/artifacts/13053263894) was downloaded and inspected, including distribution versions and PDF engine. This workflow success does **not** mean the dependency audit is clean.

Final local restore included 4 jobs, 2 tasks, 9 payments, 1 entitlement and 25 attachment rows; all 24 filestore-backed attachment checksums matched. The separate test DB was cleaned up successfully. Local source scan excluded tests and found no issues at any severity.

CI text/artifact inspection: Gitleaks also scanned the downloaded source/dependency job logs and dependency metadata. It flagged two AWS-pattern matches in the third-party PyPDF2 advisory text (`PYSEC-2026-1835`), not repository/runtime credentials: a published presigned example URL dated June 2023 with a 300-second lifetime. These were triaged as expired third-party advisory content, not silently ignored or treated as an active project secret. No service key was tested or rotated. UI archive membership/text and the completed integration log are reviewed separately; no exhaustive screenshot OCR or scan of every historical CI run is claimed.


### First official-image integration run and recovery correction

[Integration run 41231106604](https://github.com/naor291291/odoo-pilot/actions/runs/41231106604) at the head above passed all 187 native methods, startup/restart, the mandatory two-session/real-PDF runtime checks and all three Chrome suites. Its **restore step failed**, so the overall run was not successful: the image-selected PostgreSQL client emitted `SET transaction_timeout`, unsupported by the configured PostgreSQL 16 server. This was a compatibility failure in recovery tooling, not a successful restore claim. The local client/server were both 16, explaining why the local drill did not reveal it.

Correction: install `postgresql-client-16` alongside the image default, choose dump/restore binaries matching the queried server major, and fail before backup if a matching client is absent. Report the selected major in restore evidence and both default/matching client versions in the image inventory. This avoids ignoring restore errors or editing a dump to hide them. The corrected official-image run is required below. No business database was overwritten.


### Final official-image verification — passed

Executable commit **`9adc18ccf89c1ecda7594689335b821d51b246e3`**, source tree `34052e14ad70f09a1a894432c07dd383a822ec3c` (identical to local `26d5a54`), tested through generated PR merge `ac401ffe32b4878c6627869ef41dd9e097bd4a0f` into `24d22c3`. [Integration workflow 41232041040](https://github.com/naor291291/odoo-pilot/actions/runs/41232041040) completed **successfully**, including all 187 test methods with zero failures/errors, official-image startup/restart, two-session overpayment/idempotency, real HTML/PDF escaping/no-store/read-only checks, logout replay, all three actual Chrome suites, and the corrected restore drill.

Restore evidence: 7 job rows, 6 task rows, 33 payments, 2 entitlements, 45 attachment rows; **all 44 filestore-backed attachment checksums matched** in a separate restored DB, private backup verified and PostgreSQL client/server major **16**. [Runtime/restore result artifact](https://github.com/naor291291/odoo-pilot/actions/runs/41232041040/artifacts/13054645605) was downloaded and its two JSON members inspected: no DB dump, filestore or credentials are uploaded.

[Final security workflow 41232040829](https://github.com/naor291291/odoo-pilot/actions/runs/41232040829) completed: source/history passed (**105 commits**, no recognized repository secret), Bandit passed. Dependency audit remains **advisory with 146 raw records / 95 distinct IDs / 13 packages**, not a clean result. [Final source results](https://github.com/naor291291/odoo-pilot/actions/runs/41232040829/artifacts/13054141093); [final inventory/advisories](https://github.com/naor291291/odoo-pilot/actions/runs/41232040829/artifacts/13053544536). Inventory confirms default client 18.6 and the explicitly selected PostgreSQL 16.15 client required by the configured server.

[Final browser evidence](https://github.com/naor291291/odoo-pilot/actions/runs/41232041040/artifacts/13053889116) contains the three suite results and screenshots/PDFs. The first executable run's archive was downloaded and checked: **81 PNGs, two PDFs and coverage JSON; no unexpected file types** (41 CRM / 15 statement captures, plus 25 core workflow captures). Application code is identical across the recovery-only image/tool correction; the final CI reran every suite. No new layout changes or screenshot-OCR security guarantee is claimed.

Completed integration logs and downloaded textual UI coverage were included in the redacted Gitleaks text scan. The only two matches remained the previously described expired third-party URL inside advisory text; none came from integration logs, UI text or source. Public artifacts remain synthetic.

Any later commit for this review updates Markdown documentation only; the executable tree above is the tested version. No merge, live upgrade, port/access change or key rotation was performed.
