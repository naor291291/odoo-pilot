# Pre-deployment QA report — in progress

Date: 2026-11-07. **Current decision: No-Go for real customer deployment.** No merge, deployment, provider send or real financial document was performed.

## Actual execution

- Clean isolated checkout from `main` `e274e5c`; retained the older dirty local checkout and existing pilot data unchanged.
- Existing Codespace observed on PR #17 branch, login screen present. It stopped on inactivity; restart reached GitHub sign-in. Its runtime commit cannot be certified as current main.
- Local isolated Odoo 18 source `976ab650ce1b5fa27e666b4e8641a8184655c322`, Python 3.12, PostgreSQL 16.2, source addon version 18.0.17.0.0. This is NOT the exact deployment image. `psycopg2-binary` substituted for source-built psycopg2; LDAP is not installed/used; optional pg_trgm and wkhtmltopdf unavailable.
- Baseline: **203/203 native Odoo tests passed, 0 failed, 0 errors**. These cover model and HTTP flows across dispatch, photos/visits, pricing, collections, statements, documents, metrics, portal and security. They do not represent 203 manual browser journeys.
- Additional unchanged-code prepaid-order test: **1 passed**.
- Malformed signed webhook reproduction: **1 failed as expected (500 vs 400)**. **Post-fix: 205/205 tests passed, 0 failures/errors**, including six malformed payload cases and valid intake.
- Browser execution locally attempted with Python and Node Playwright, Chromium failed at process singleton socket creation (`Operation not permitted`). No new authenticated screenshots, visual approval, Firefox/WebKit result or axe success is claimed.

- Additional pure adapter tests: **6/6 passed** with every SMTP/HTTP transport mocked; exact attachment bytes, Hebrew body, TLS before authentication, rejection redaction and upload-before-send verified.
- Current CI dependency audit: **146 advisory records across 13 packages**; advisory job is allowed to pass despite findings. Source/history checks passed. Do not equate green job status with resolved dependencies.

## Reproducible coverage added

Project-local instructions installed for interface-design, web-design-guidelines and playwright-cli. Microsoft CLI 0.1.23 installed; its browser download failed (invalid downloaded archive). Official Odoo 18 `TransactionCase`/`HttpCase` source read; no assumed SavepointCase/JS framework introduced. Current Vercel rules and existing design system read.

`npm ci --prefix scripts/qa && CHROME_BIN=/path/to/chrome npm --prefix scripts/qa run audit` audits only loopback disposable pilot credentials. It captures 375/390/768/1440 screenshots, WCAG axe findings/incomplete checks, overflow, RTL direction, observed load duration and same-origin HTTP failures. It fails on serious/critical axe violations, overflow or execution errors. Full existing browser journeys remain separate and were expanded to 375px. Results go to the existing CI artifact; no credentials/payload bodies are logged.

## Release gate

| Gate | Current state |
|---|---|
| No reproduced open P0/P1 application bugs | No new P0/P1 reproduced; bounded test result, not full assurance |
| Full critical backend regression | 205/205 post-fix native tests passed |
| Critical rendered workflows + UI/RTL | Pending CI; cannot approve from source |
| Private documents + actual PDF rendering | HTTP authorization passed; real renderer pending |
| Physical device acceptance | Deferred by user until after deployment; remains an explicit limitation |
| Live SMTP/Meta | External setup pending; no real customer messages |
| Dependencies, host, HTTPS, external restore | Unresolved release blockers |

Requirement-level status is in `requirements-coverage.md`; reproduced defects in `bug-report.md`. Complete functional build is not the same as validated operational readiness. Do not declare the whole original specification complete while these gates remain unresolved.
