# Operational readiness — follow-up review

2026-11-07. No host selected or deployment executed. Compose and configuration were reviewed from source; actual network, volumes, credentials and TLS cannot be certified without a host.

| Concern | Evidence now | Remaining acceptance |
|---|---|---|
| Runtime parity | Development derives from the same `runtime` Docker stage containing the PDF backport, supported Pillow refresh and targeted HTML cleaner | Build/publish approved runtime, pin resulting digest; never substitute stock upstream image |
| Secrets | Examples contain placeholders, delivery modes/inbound/automation default off; source/history CI scans pass | Configure real secrets with restricted permissions; validate runtime without printing them |
| Exposure | Only Caddy exposes 80/443; database network internal; Odoo private; database management blocked | DNS, actual HTTPS/redirect/certificate, firewall and negative URL checks |
| Persistent files | Named DB and Odoo data volumes; Caddy data/config volumes | Recreate/restart on actual host and verify attachments |
| Consistent backup | Script quiesces Odoo, captures dump + filestore, restarts, uploads to approved off-site scheme | Provision Restic repository/credentials, schedule, retention and external restore |
| Backup failure handling | **7/7 local mocked tests passed**: success, dump/tar/upload failures, repository unavailable, app stopped, non-off-site rejection | Real provider failure drill remains external |
| Restore | Existing CI separate-database restore and 46 attachment checksum checks passed | Selected external snapshot, actual operator/RPO/RTO evidence |
| Logs/monitoring | Source config avoids verbose request logging; operator checklist added | Log rotation, capacity/HTTPS/backup/delivery alerts and notification test |
| Update/rollback | Matched commit/digest/snapshot procedure added; explicitly prohibits old code over migrated DB | Isolated host rehearsal and operator signoff |

Test command: `python scripts/qa/test_backup_control_flow.py`; Docker/Restic were fake executables in a temporary directory. No service was stopped and no repository contacted. `bash -n deploy/backup.sh deploy/init-db.sh` passed. These are meaningful control-flow checks, not a claim of infrastructure readiness.
