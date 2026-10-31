# Pilot operation, deployment gates and recovery

This review targets a synthetic pilot. Keep `.local-data/`, generated credentials, real documents and backups out of Git/CI artifacts. `scripts/pilot.py` creates/updates test users and passwords and grants the pilot admin finance access on initialization: do not use this bootstrap for production. Parent directory permissions are 0700 and generated credential/config files 0600; anyone with host/workspace access is still trusted.

## Reviewed configuration

`.devcontainer/compose.yaml` publishes no PostgreSQL host port; application forwarding is a separate Codespaces control. No port visibility, sharing, firewall, auth or live Codespace setting was changed in this review. Actual external availability/exposure was not tested. The configured DB name/filter and `list_db=False` are retained. Do not expose database-management screens or a filestore directory through a production proxy.

Development `odoo:18.0` and `postgres:16` tags float; they are not immutable production artifacts. Capture their resolved digest plus OS/Python/PDF versions, apply vendor security updates and run the suite on every approved rebuild. `scripts/security_inventory.py` reports selected parsers/network/crypto libraries and distribution metadata without reading environment secrets. `--requirements` is the same selected Python scope; it is not a complete OS/JavaScript SBOM. Native Odoo JavaScript/PDF/OS components still need vendor/image-level advisory review. There are no custom npm dependencies or external font/CDN scripts in the addon.

For production, obtain an actual deployment plan and verify TLS termination, trusted proxy boundaries, secure session cookie behavior, DB credentials/least privilege/private network, worker memory/CPU/time limits, request body/rate limits, PDF egress and session/logout behavior through that proxy. Native Odoo's login cooldown (inspected source defaults: five failures, sixty seconds) and optional `auth_totp` exist; deployed values/enrollment were not changed or exhaustively probed. Do not infer production MFA or brute-force protection from a mocked HttpCase login.

## Safe backup/restore drill

Only run these commands in the disposable synthetic test environment. The drill is not a general-purpose production backup/restore tool and does not accept a business database name.

1. Stop the pilot runner/service using the environment's normal service controls. The drill acquires the same `runner.lock` and refuses an active launcher. Native Odoo instances started outside that launcher must also be stopped by the operator.
2. From the repository, with the existing internal PostgreSQL connection environment, run `python3 scripts/check_backup_restore.py`.
3. It writes a mode-0700 folder under ignored `.local-data/security-backups/`, containing a custom-format `pg_dump`, a matching filestore copy and a non-secret result JSON. Main/extra photo fields live in PostgreSQL and are included in the dump; ordinary attachment files need the filestore copy.
4. It creates a new random `odoo_pilot_restore_*` DB, restores without replacing an existing DB, compares job/task/attachment/payment/entitlement counts and every referenced file checksum. Connections close before cleanup; only the DB actually created by that invocation is dropped. The backup remains private for inspection. Restore verification here is SQL/filestore integrity, not a complete interactive restored-site acceptance test.
5. A real recovery process must also copy the paired filestore to the restored database's Odoo data directory, deploy matching addon/config versions and verify attachment reads and key business flows before switching traffic. Store backup encryption keys separately, test restore access, and agree RPO/RTO/retention with the business. This review does not assign legal retention periods.

Do not upload the backup folder to GitHub artifacts. CI uploads only `result.json` and synthetic runtime result flags; never the database dump, filestore, configuration or credentials.

## Logging and privacy

Payments retain creator/date and cancellation actor/time/reason; entitlement events retain actor, approval identity and historical amount/rate. Customer-facing report actions are read-only with respect to those ledgers. Private contractor payouts are not posted in shared CRM chatter. Native job/report tracking can contain customer/site/free-text data; log/chatter retention and access must be part of the business policy.

Scanner output is redacted; runtime test helpers log test names/summary flags, not session cookies or credentials. `pilot.py status` intentionally displays local test credentials for the operator and is currently invoked on attach; keep terminal/screenshots private and never run it in CI logs or for production credential distribution. Public UI evidence must stay synthetic. Downloaded PDFs/images cannot be remotely revoked; authorization and no-store apply to subsequent requests.

## Release boundary

Review the PR and its exact commit/check results. No merge, deployment, public-port change, account expansion or secret rotation is authorized by this security implementation request. After a separate merge/deployment instruction, back up the target and use a controlled upgrade; do not copy synthetic financial test records into a business database.
