# Git-managed Cloady migration — preparation, not deployed

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

The first Git build produced the image successfully, but rollout failed and neither
service ran. The UI supplied no runtime log. A required Compose variable,
`ODOO_PREVIOUS_RELEASE`, was absent in the initial environment. Initial restoration
also needs an explicit maintenance process, because the supervisor deliberately
refuses an uninitialized database. Do not describe this launch as a working CRM.

A fresh source backup contains 310 tables and 58 file-backed attachment references.
The paired dump/archive hashes and all 58 file checksums were verified after private
S3 download. An independent encrypted copy was verified by decrypting in memory.
A full database restore has NOT yet been verified. No production migration or traffic
cutover has occurred. Live Redeploy/data-preservation acceptance remains pending.

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
Production migration, storage persistence, HTTPS and authenticated acceptance are
pending the paid-resource approval and actual migration, not claimed complete.
