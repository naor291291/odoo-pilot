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
