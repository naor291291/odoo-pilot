# Git-managed Cloady deployment

Target: main containing PR #23, module 18.0.18.0.0. Root compose.yaml builds
`deploy/cloady/Dockerfile` from the repository root, including the shared runtime
security patches and all addons. The old Upload application cannot change source.
The one-time transfer requires a new Git application; future releases use that same
Git application and its named database/filestore volumes.

## Release gate

No paid resource may be created before the user approves the displayed immediate
charge and monthly increment. No old application or volume may be deleted before
successful authenticated acceptance and separate deletion approval.

On 2026-11-28 PR #24 merged as `898d5d8`. The existing Upload application
was Running and had no Git deployment trigger. Its data and volumes remain intact.
The authenticated quote was $7.36/month before, $11.25/month after, a $3.89/month
increment. Creation of `odoo-crm-git` was submitted within the user's $4 immediate
and $4 monthly cap. Exact charged proration still requires invoice verification.
The Git app tracks `naor291291/odoo-pilot`, `main`; automatic deploy-on-push and
preview branches are disabled. Two dedicated 1 GB volumes were created.

PR #25 merged as `e3ad711` after all three CI workflows passed. Cloady built and
started this revision in the same Git app (deployment `24b65de1`), with the explicit
maintenance responder and PostgreSQL 16.16. This resolved initial rollout; the
maintenance HTTP response is not a working CRM.

Both the initial backup and the final snapshot `20261128T153648Z` were restored
into the dedicated target database while no Odoo process was running. Validation
passed for all 310 table counts, 58 file-backed attachments, and hashes of all
users/passwords and group memberships. Private encrypted independent backup copies
were verified by decryption. No credentials or customer backups belong in Git.

The source changed after the first snapshot. A final paired snapshot was captured
under bounded table locks (90-second hard deadline, automatic rollback); after its
private download and checksum verification, the old Upload app was stopped through
Cloady before the bounded write hold expired. Its volumes remain intact. The final
snapshot was restored and verified again before launching the managed upgrade.
The managed upgrade completed: SQL verified `18.0.18.0.0`, state `installed`.

### Real same-app Redeploy proof — 2026-11-28

All three PR #26 workflows passed before merge `c2dd232d0c6629c28787df64513ddd7aad5d9619`.
In `odoo-crm-git` (USE1), both services were stopped, then Settings → Deployments →
Deploy now built deployment `2d28ac15`. The app remained stopped after the build;
Overview → Start activated the new image. Runtime logs showed
`Release supervisor revision: git-redeploy-proof-20261128` and successful registry/HTTP startup.
Image digest: `sha256:77f0c43ed175ce116596518a97613331e13f60417c96aa06a23ab649be651c94`.

Before/after read-only SQL and file checks passed:
- Module remains `18.0.18.0.0`, installed.
- Exact fingerprints of 16 business/attachment tables are unchanged.
- All 58 file references remain; each file matches its database SHA-1 checksum.
- User/login/password/active/company/share fingerprint and group membership fingerprint are unchanged.
- The pre-Redeploy baseline persisted on the existing filestore volume.
- Managed migration backup count remains 1: no repeated migration on the same version.
- Both existing named 1 GB volumes and services remain; no resources or billing settings were changed.

Live URL: https://odoo-crm-git-vyvsw7k6-silver-maple-6.cloady.io/
HTTPS login was subsequently completed by the user as `kobiabudi`; the authenticated
preferences dialog confirmed the existing account, Hebrew and Asia/Jerusalem.
Read-only browser smoke checks passed for the work dashboard, jobs Kanban, central
work card, pending collections, completed/paid collections, contractor rate list,
and settlement report form (discarded without saving). An existing quote PDF also
opened and rendered successfully under that authenticated session. Financial fields
and actions were visible to Kobi. No business records or credentials were changed.
These checks do not claim payment/write execution, a separate Naor login, or new
negative permission tests. Old applications/volumes were not deleted.

Observed UI follow-ups: two finance menu headings have the same label; a few labels
remain English. Reopening the nested work-card URL directly showed the older form
layout, while opening via the Kanban action showed the new central card. The sample
PDF in the legacy quote slot is a transaction-account document; its business
classification was not changed or treated as a verified receivable. These issues
were observed during smoke testing and are not claimed resolved by this redeploy.

Screenshots were captured privately. They are not published in this repository.

## Future update procedure

1. Merge a reviewed change to `main` after CI passes. Increment the addon manifest
   only when addon code changes; the supervisor reads that version dynamically.
2. Verify an accessible paired backup and previous release reference. Arrange a
   maintenance window. In the **same Git application**, stop it and wait for both
   services to show Stopped; never change/delete its named volumes.
3. After both services stop, use Settings → Deployments → Deploy now and verify
   the expected main commit in build history. After the build, use Overview → Start
   if the app remains stopped. Start alone is not proof that new Git code was built.
   Keep deploy-on-push disabled to avoid rolling writers.
4. Startup checks the installed version, holds its database lease, backs up before
   a necessary upgrade, and starts HTTP only after successful version verification.
5. Verify the installed version, users, documents and business screens before
   reopening usage. A same-version redeploy must not rerun migrations.
6. On a failed/interrupted migration, keep the app stopped. Preserve attempt.json
   and logs; inspect the database before deciding whether to acknowledge a completed
   migration or restore the paired snapshot with its matching previous image.
   Switching an image alone is not a database rollback. Never delete the old app
   without separate approval.

The harmless startup log marker `git-redeploy-proof-20261128` is used for the live
Git update acceptance check; it does not change addon fingerprints or business data.

## Startup contract

* For the initial restore, set `ODOO_MAINTENANCE=1` before deployment. Only a static
  maintenance HTTP responder runs; it does not import Odoo, connect to PostgreSQL,
  start cron, initialize a database or run migrations. HTTP 200 in this mode is a
  platform health response, **not** a successful Odoo acceptance test. Use the same
  existing service/volumes for restoration, then verify the paired restore and set
  `ODOO_PREVIOUS_RELEASE` before switching maintenance to 0 and redeploying.
* Import an existing PostgreSQL database and its matching filestore first. No empty
  database initialization, user creation or password reset occurs in this image.
* Target version comes from the addon manifest; installed version from PostgreSQL.
* A session advisory lease is held across backup, upgrade and the serving lifetime.
  Competing managed instances stop. Other database clients also block startup.
  This is a fail-safe, not permission to use a rolling deployment: stop old Odoo
  before updating. Legacy servers do not cooperate with this lease.
* Before an upgrade, record the immutable previous image/deploy in
  ODOO_PREVIOUS_RELEASE. A private local DB+filestore pair is checked, then an
  exclusive persistent attempt file is fsynced before the upgrade command.
* Only `-u field_work_photos --stop-after-init --no-http --max-cron-threads=0`
  runs. HTTP starts only after version verification. Cron/external delivery remain
  disabled for the pilot; enabling them is a separate configuration review.
* Failed/interrupted attempts remain blocked across restarts, including a crash
  after database commit but before final completion metadata. Do not automatically
  delete the attempt marker. An operator must inspect version, schema, logs and
  paired backup; successful commit can be acknowledged only after verification.
* Downgrade images are refused; rolling back an image does not roll back a database.
* Local backup hashes, attachment consistency and pg_restore list are not proof of
  an off-host restorable backup. Do not claim recovery verified from these alone.

## One-time transfer (after quote approval)

1. Verify the Git preview recognizes root compose, exact branch/commit, build context,
   8069 HTTPS, no public PostgreSQL port, both named persistent mounts, resource caps,
   and all prices. Disable automatic deploy-on-push until controlled stop/start is
   validated. Do not edit the old application's resources or source.
2. Save old immutable image, compose/config, secret settings and addon versions in
   private storage. Preserve existing DB/master secrets; never put them in Git/logs.
3. Arrange maintenance; stop old Odoo, prove no remaining DB clients/cron/writers.
   Take PostgreSQL custom-format dump and matching filestore with attachment hashes.
   Keep an independently accessible encrypted copy outside the affected volumes.
4. Restore to the new private PostgreSQL and filestore while new Odoo remains stopped
   or fail-closed. No public DB exposure, no sending integrations. Preserve database
   name field_crm, users/password hashes/groups, document rows and attachment paths.
   Restore database using original dedicated role; set filestore ownership to image
   Odoo UID. Validate table counts, attachment SHA1 and document hashes after restore.
5. Start the managed image once; verify target module version and migration logs,
   login as existing Naor/Kobi, financial/contractor isolation, PDFs, receipt-required
   closing and the 700−273 at 65% = 277.55 example using synthetic records only.
6. Switch the public entry point only after validation; verify HTTPS/session/login.
   Keep the old app stopped and intact. Report both URLs, costs and acceptance results.
7. Propose old app deletions only after independent recovery copy is retained and
   confirm exact resources are dedicated. Stopping alone does not reduce subscription.

## Every later release

Require successful CI, a module version bump for addon changes, tested migration,
immutable previous deployment and a recovery copy. Use the supported Git application's
same source and named volumes. Stop the old deployment before redeploying the approved
main commit, then let startup upgrade once before HTTP. Verify before reopening access.
Cloady's stop/redeploy behavior and volume preservation must be demonstrated on the
new app before enabling automatic CI-triggered production deployment. No unattended
production deployment workflow is enabled by this PR.

## Failure and rollback

On failure keep service unavailable; retain attempt marker and logs. Do not loop
restarts or run old code against a newer schema. Before cutover the original app is
an intact fallback only if no new-system writes were accepted and its original
code/schema still match. After any accepted new writes, rollback needs a reviewed
maintenance recovery from a matching DB+filestore pair; never automatically restore
or discard writes. No deletion/reset is scripted.

## Validation

`python3 deploy/cloady/test_startup.py` tests safety decisions, restart blocking,
termination, lease loss and disk headroom. `test_postgres.py` uses disposable CI
PostgreSQL 16 to verify exclusion and actual dump/restore+attachment correspondence.
CI also builds the image and exercises an actual 18.0.17.0.2 to 18.0.18.0.0 upgrade, HTTP readiness, password-hash preservation, competing-server refusal and restart without repeated migration. Existing application CI remains intact.
Production migration, same-app Git Redeploy, storage persistence and HTTPS were
verified as recorded above. Authenticated read-only business-screen smoke checks
passed as Kobi; the exact limits and UI follow-ups are recorded above.
