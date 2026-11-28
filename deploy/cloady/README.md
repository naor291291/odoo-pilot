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

The existing account on 2026-11-28 showed $11.70 invoiced this period, $0 outstanding,
$12.25 at renewal; resource subtotal $11.25 (2.5 vCPU, 5 GB RAM, 8 GB SSD).
The $1 discrepancy is unresolved. Idle apps retain subscribed capacity.
The authenticated Git preview recognizes compose.yaml, two services, 1 vCPU,
2 GB RAM, two 1 GB volumes and Odoo port 8069. It quotes $3.89/month for the app
but $11.25/month workspace total, inconsistent with existing renewal. Immediate
proration and final post-cleanup bill remain UNVERIFIED. No Deploy was clicked.
Public pricing gives Small (1 vCPU / 2 GB) at $5/month; this is an estimate for
one remaining app, not an account-specific confirmed renewal quote.

## Startup contract

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
CI also validates compose and builds the image; existing application CI remains intact.
Production migration, storage persistence, HTTPS and authenticated acceptance are
pending the paid-resource approval and actual migration, not claimed complete.
