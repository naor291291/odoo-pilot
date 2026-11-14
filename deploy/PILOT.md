# Closed synthetic pilot — preparation only

Scope: 3–5 named testers, invented customers/photos/documents only. No real receipts, provider sends or Morning API. This document does not authorize deployment.

Zero hosting subscription is possible on an **existing, reliably powered Linux machine** with Docker, enough RAM/disk, and a private LAN or already managed VPN reachable by the testers. Hardware, electricity and operator effort still exist. No new free-cloud provider, credit card or uptime guarantee is assumed. A sleeping laptop, temporary Codespace or ephemeral disk is not an always-available pilot host. If no suitable existing machine/network is available, hosting remains a blocker; do not publish an unstable workaround.

## Prepare the machine after separate authorization

1. Use Docker Compose >=2.24.4. Record the reviewed git commit and pin the Odoo runtime, PostgreSQL 16 and Caddy images by digest. Build Odoo from the common `runtime` stage as described in README; never substitute stock `odoo:18.0` for the patched image. Do not upgrade PostgreSQL major versions with an existing data volume.
2. Copy `.env.example`, `delivery.env.example` and `odoo.conf.example` to the corresponding private files. Generate unique credentials on the host, restrict their permissions and keep them out of chat/git. Set `CRM_DOMAIN` to a private DNS/hosts name used by the testers, and `PILOT_ALLOWED_CIDRS` to their explicit LAN/VPN ranges. Never use `0.0.0.0/0` or `::/0`.
3. Always use both files: `docker compose --env-file .env -f compose.yaml -f compose.pilot.yaml …`. The override removes external routing from Odoo, clears proxy settings and forces integrations off. Caddy alone has edge access. Do not enable Marketplace/optional authentication/accounting modules during this reviewed pilot.
4. Initialize privately using the README steps, create named owner/operations/contractor accounts, replace bootstrap passwords and keep administrator access with the operator. Persistent named volumes hold PostgreSQL and the complete Odoo filestore; never run `down -v` on the pilot host.
5. Caddy uses an internal CA for private HTTPS. Install/trust only this controlled CA on the approved tester devices using the organization's normal procedure. Do not bypass certificate errors. Do not port-forward this stack to the public Internet. Existing VPN access must already be secured.
6. Take a database+filestore backup and rehearse restore into separate volumes before inviting testers. The standard backup script uses base Compose; its stop/start/run operations act on the same project and volumes. Supply the same Compose project name consistently. Verify the off-site Restic destination or explicitly keep the pilot blocked until a durable external copy is available.

## Mandatory host smoke checks (not yet executed)

- HTTPS accepted by approved clients; disallowed source IP gets 403; database manager gets 404; ports 5432/8069/8072 are not exposed.
- Confirm Odoo container cannot connect to an external address and has no proxy variables/delivery channels enabled. Container image audit alone does not prove host firewall behavior.
- Owner/operations/contractor logins and cross-user document/photo denial; complete one synthetic quote→assignment→photos→approval→invoice→payment→closure.
- Restart the application and confirm the same customer, PDF and image remain; restore backup into isolated volumes and compare counts/checksums.
- Verify bounded logs, disk capacity and backup failure notifications. Record who operates the host and receives incidents.

Rollback: retain failed volumes, restore the paired pre-update database+filestore with the recorded code/image, keep integrations off, then repeat smoke checks. Never downgrade code over a migrated database. Full procedure: README.

Until these host checks pass, a passing CI run is **code readiness only**, not approval of an actual deployment.
