# Northflank Sandbox fit — 2026-11-14

**Decision: NO-GO for a verified free, no-card deployment.** This is a documentation-based feasibility assessment, not an account entitlement check or deployed test. No account, service, card, purchase or deployment was created. Scope remains 3–5 users and synthetic data only.

| Requirement | Documented platform support | Fit / unresolved gate |
|---|---|---|
| Free without a card | Pricing advertises Sandbox with no card, two services, two jobs, one database and up to $20/month of resources [1]. The billing guide still requires a payment method for resource creation on every plan [2]. | **Conflicting official sources.** Confirm the actual account's entitlement without entering a card; stop if a card is requested. No unconditional promise of free/no-card availability. |
| PostgreSQL persistence | Managed PostgreSQL 16 is supported [3]. | Use the single addon privately with persistent storage; verify exact free compute/storage quota and data retention. No addon was provisioned. |
| Odoo filestore persistence | Service volumes persist across restarts. Single Read/Write attaches to one pod and implies stop-before-start redeployments [4]. | A separate service volume must mount at `/var/lib/odoo` for filestore and sessions. Free volume entitlement/capacity is unverified. Ephemeral storage is unacceptable. Validate upload → restart/redeploy → checksum. |
| HTTPS | Managed ingress supports HTTP/WebSockets, TLS at the edge and HTTP→HTTPS redirect on supplied `code.run` domains [5]. | Platform capability confirmed in documentation, not tested. Preserve Odoo proxy settings, websocket routing and restricted DB manager; restrict access to the test group. Do not put the LAN-only Caddy internal-CA configuration unchanged behind managed ingress. |
| Database / ingress separation | Services support private ports and public ingress access policies [5]. | PostgreSQL must have no public endpoint. Use IP restrictions or an additional authentication policy for the application. Confirm Sandbox entitlement and actual denial behavior. |
| Deny-by-default egress | Network-policy documentation explicitly scopes allow/deny ingress/egress rules to BYOC clusters [6]. | **Managed free-Sandbox no-egress enforcement is not established.** Private database connectivity is not egress isolation. BYOC requires a separately supplied cloud, so it cannot be assumed to satisfy zero cost. Do not substitute empty proxy variables or disabled messaging for a firewall. |
| External backup | Global backup/custom destination documentation is enterprise-scoped [7]. | Do not count it as a free external backup. A separately controlled encrypted backup destination or offline retained export is required. No destination/credentials/restore evidence exists. |
| Capacity / cost | Published illustrative compute: 0.5 vCPU/1 GB $12/month; 1 vCPU/2 GB $24/month; persistent disk and egress are separately metered [1]. | The current Odoo config has two workers plus cron and per-worker limits; do not assert it fits a small free service. A 2 GB listed plan alone exceeds the advertised $20 resource allowance before PostgreSQL/storage. A smaller setup needs memory/PDF load measurements and confirmed plan quotas; no performance test on Northflank was performed. |

## Mapping if the unresolved gates are later cleared

One reviewed Odoo image with baked-in custom addons (the local Compose bind mount is not a cloud artifact), one private PostgreSQL 16 addon, a persistent Odoo volume, managed ingress, and at most a separate gateway service if needed. Pin the approved image digest. Keep email, WhatsApp, automatic stages and Morning off. No template is offered as deployment-ready because entitlement and networking/backup design are not verified.

The existing `deploy/backup.sh` depends on a Docker Compose host, stops Odoo writers, then captures a PostgreSQL dump and the matching filestore before uploading to Restic. It cannot be run unchanged as a Northflank job. A portable alternative must quiesce all writers, export the paired DB/filestore using an allowed container-access mechanism, encrypt and transfer to a separately controlled destination, then restore into isolated storage and compare attachment checksums. Single-pod volumes must not be concurrently attached to a backup job. A managed database backup alone omits Odoo attachments. A local/offline encrypted copy could avoid buying storage if the user already has durable storage, but retrieval/access and recovery must be tested; it is not an implemented automated backup.

## Acceptance gates before any user invitation

1. Resolve the no-card documentation contradiction against actual account eligibility; confirm hard resource limits and persistence without authorizing payment.
2. Confirm free service-volume and PostgreSQL allocations, and measure the intended worker configuration with synthetic PDF/photo workloads within those limits.
3. Demonstrate deny-by-default app egress and permitted private DB access on managed Sandbox, or record that the required isolation is unavailable. Keep this gate open until proved.
4. After separately authorized deployment only: test HTTPS/access denial, roles, restart persistence and a complete external paired backup/restore. No such host test is claimed here.

## Official sources checked

1. https://northflank.com/pricing
2. https://northflank.com/docs/v1/application/billing/pricing-on-northflank
3. https://northflank.com/docs/v1/application/databases-and-persistence/deploy-a-database
4. https://northflank.com/docs/v1/application/databases-and-persistence/add-a-volume
5. https://northflank.com/docs/v1/application/network/networking-on-northflank
6. https://northflank.com/docs/v1/application/network/configure-network-policies
7. https://northflank.com/docs/v1/application/databases-and-persistence/global-backup

Source disagreements and plan limitations are retained explicitly. Public documentation verifies capability descriptions, not availability or successful operation in this user's account.
