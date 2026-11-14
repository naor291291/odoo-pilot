# Staxa Free preparation — NO-GO

Checked 2026-11-14. Based on main after PR #20 (`1c1c4d7`). This directory prepares a separate image; it does not modify the existing Docker runtime, application modules, database or pilot. No Staxa resource, card, purchase or deployment was created.

**Do not invite testers or deploy this as a ready system.** Persistent application storage, private access, complete backup/restore and representative capacity are not verified. Platform namespace isolation alone does not close those gates.

## Image and build settings

- Dockerfile: `deploy/staxa/Dockerfile`
- Build context: repository root `.` (not `deploy/staxa`)
- Application port: **8069**, HTTP listen address `0.0.0.0`
- Image target: final `staxa` stage; non-root `odoo` user
- Root-context build command: `docker build -f deploy/staxa/Dockerfile -t staxa-odoo:probe .`
- `settings.example.json` maps the documented Staxa settings. It is an example, **not a deployment command**. Posting tenant/service creation to Staxa would immediately deploy; do not do so in this task.

Dockerfiles cannot import a stage from a separate Dockerfile. `generate_dockerfile.py` therefore copies the exact reviewed `runtime` stage from `.devcontainer/Dockerfile` into a standalone Dockerfile, then appends the Staxa stage. `--check` fails on drift. Regenerate after shared-runtime changes. This preserves the hash-pinned Pillow/crypto/HTTP/cleaner overrides, PDF EOF backport and shared PYTHONPATH. All `addons/` modules are baked into the image, without a host bind mount. No dependency versions are changed here. The Dockerfile-specific ignore file excludes unrelated context and local environment files.

Use a reviewed base-image digest through `ODOO_BASE_IMAGE` when producing a deployment artifact; the existing default remains the shared `odoo:18.0` tag. Record the final built image digest. This preparation does not claim a tag is immutable.

## Environment and module initialization

Staxa documents injected `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` and `DATABASE_URL` when PostgreSQL is selected. The adapter uses the complete five-field set first. If none is present, it accepts the URL, including encoded passwords/IPv6. Partial sets fail instead of mixing credentials. URL query support is deliberately limited to `sslmode`; unsupported options fail rather than silently weakening TLS.

Supply `ODOO_ADMIN_PASSWORD` privately (at least 32 characters); it is the database-management secret, **not an Odoo user's login password**. The configuration is written to a random mode-0600 temporary file. Secrets are not passed in command arguments or printed. Password/URL/master-secret variables are removed from the executed child's environment. Use Staxa's secret controls; do not paste credentials into GitHub or chat. `.env.example` contains no real values.

`DB_SSLMODE=require` is the default. Verify PostgreSQL TLS/CA support in the actual tenant. `verify-ca` / `verify-full` may additionally require CA provisioning. `disable` exists solely for the isolated synthetic CI database; it is not approval to disable TLS on a real host. A database username `postgres` is refused: request a dedicated role owning the pilot database. Do not assume provisioned credentials already meet that requirement.

- `STAXA_ODOO_MODE=serve` (default) starts an existing initialized database. It does not auto-install or upgrade modules.
- `STAXA_ODOO_MODE=init` explicitly installs `field_work_photos` and its manifest dependencies, excludes demo data, disables HTTP and exits. Run only as an operator-controlled one-off against a new synthetic database after authorization. Never point it at an existing pilot database.
- Prepare strong named Odoo administrator/operator/contractor accounts **before enabling ingress**; a new Odoo database must not be exposed with bootstrap/default user credentials.
- The normal server loads `base,web`, includes `/mnt/extra-addons`, fixes the database/filter, and disables database listing. App routing still requires a gateway rule to deny database-manager endpoints.
- Email, WhatsApp, inbound messaging and automatic business transitions are forced off. `workers=0`, `max_cron_threads=0` and `db_maxconn=8` reduce the process/connection footprint. Scheduled/background behavior is intentionally unavailable in this candidate profile.

## Free-plan fit

| Requirement | Official evidence | Decision |
|---|---|---|
| No card / free | Signup advertises no card; Free plan costs $0 [1,2]. | Advertised, not tested with this account. No signup/payment performed. Stop if a card or upgrade is requested. |
| 512MiB | Small guarantees only 64Mi RAM / 25m CPU, with burst ceilings 512Mi RAM / 500m CPU [3]. | **Not 512Mi guaranteed capacity.** A passing ceiling-limited CI probe does not certify performance under the guaranteed allocation. |
| Odoo volume | Reviewed setup/API exposes no confirmed persistent application-volume mount or free volume entitlement [4,5]. | **BLOCKED.** Need provider confirmation for `/var/lib/odoo`, capacity, ownership, persistence across redeploys/restarts and retention. The inherited Docker `VOLUME` is not a Staxa storage provisioner. |
| PostgreSQL | Managed PostgreSQL, including version 16, and injected credentials are documented [4]. | Retention, dump/export access, TLS, role privileges and restore guarantees remain unverified. A managed DB does not persist filestore attachments. |
| HTTPS | Platform provisions SSL for tenant endpoints [6]. | Documented only; validate certificate, redirect and proxy trust on the actual tenant. |
| Closed access / egress | Namespace isolation is included; Free has **0 network rules** [2]. API documents ingress/egress controls and restricted egress mode [5]. | Tenant separation does not prove tester-only HTTP ingress or deny-egress. Free access-control enforcement, private PostgreSQL and database-manager blocking are **unverified**; do not assume zero rules permits the required policy. |
| External paired backup | No documented free PostgreSQL+application-volume backup/export/restore path found in the reviewed setup/API [4,5]. | **BLOCKED** pending a viable external destination and a verified paired restore. |

## 512MiB validation boundary

`probe_memory.py` creates uniquely named disposable Docker containers/network/volume with synthetic data only. It bounds the application to 512MiB, no swap and 0.5 CPU, installs the custom module once, then requests `/web/login`. It records cgroup peak memory, exit/OOM state and results in `staxa-probe-result.json`. Only probe-owned resources are removed. The database is separate; this does not measure Staxa's database quota. No 207-test rerun is involved.

The focused GitHub workflow builds the actual standalone image and runs only the new deployment tests/probe. It runs on pushes to this branch. The final documentation-only commit uses `[skip ci]` before opening the PR, avoiding the repository's unconditional full Odoo PR workflow. Do not interpret skipped checks as executed tests.

**Probe results are in `validation.md`.** Even a successful init/login probe leaves Hebrew PDF/wkhtmltopdf, asset compilation, image uploads, sustained sessions and 3–5 simultaneous users unmeasured. With `workers=0`, Odoo's worker memory limits do not provide a reliable aggregate 512MiB cap; no misleading `limit_memory_hard` is set. The container/platform cgroup is the hard cap. Exceeding it can terminate the entire application. Do not approve capacity solely from idle login memory.

## Backup and acceptance requirements

The existing `deploy/backup.sh` assumes a Docker Compose host. It cannot be run unchanged inside Staxa. An acceptable path must:

1. Quiesce all app/cron writers and create a PostgreSQL dump plus the corresponding complete filestore; record the code/image and DB major version.
2. Transfer the pair, encrypted, to a separately controlled durable destination. Possible mechanisms are provider-supported container export or an in-tenant backup job with access to both data sources and an allowed destination; neither is verified on Free. PostgreSQL-only exports omit photos/PDFs. Odoo's web database manager should remain blocked and is not the proposed backup route.
3. Restore to a separate synthetic database and volume, compare attachment checksums, and test opening photos/PDFs. Do not overwrite the current pilot.
4. After separately authorized deployment: verify HTTPS/access denial, private DB, denied undesired egress, upload/restart/redeploy persistence and representative PDF/photo/concurrent-user memory behavior.

**Decision: NO-GO.** Provider storage/access/backup capabilities and host tests are missing. No existing environment was altered to work around these limitations.

## Official sources

[1] https://staxa.dev/signup
[2] https://staxa.dev/support/articles/plans-and-limits
[3] https://staxa.dev/support/articles/resource-sizes-health-checks
[4] https://staxa.dev/support/articles/first-deployment
[5] https://staxa.dev/docs
[6] https://staxa.dev/support/articles/platform-overview
