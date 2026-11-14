# Focused Staxa validation — 2026-11-14

Decision: **NO-GO for Staxa Free deployment**; preparatory code is reviewable. No existing runtime/app/database changes, Staxa resources, purchases, card entry or real data.

Tested commit: `a74d9206cbc77fe1e3eb8f0b184ced0f70246344`.
[Focused CI run 43615820586](https://github.com/naor291291/odoo-pilot/actions/runs/43615820586) passed. [Measurement artifact](https://github.com/naor291291/odoo-pilot/actions/runs/43615820586/artifacts/14122356471) expires 2026-11-28; its result is preserved in `probe-result.json`.

| Check | Result |
|---|---|
| 14 deployment contract/configuration tests | PASS locally and in CI |
| Exact derivation from existing runtime stage | PASS; generator drift check |
| Actual Docker build, root context | PASS; `docker build -f deploy/staxa/Dockerfile ... .` |
| Custom module installation | PASS; database query confirms `field_work_photos` is installed |
| New synthetic DB initialization, 512MiB / no swap / 0.5 CPU | PASS, exit 0 |
| `/web/login` HTML response under same ceiling | PASS |
| Sampled cgroup peak, initialization | 143,728,640 bytes (~137.1 MiB) |
| Sampled cgroup peak, login | 135,639,040 bytes (~129.4 MiB) |
| Actual Staxa Free storage, ingress/egress and TLS | NOT TESTED; no account/resource created |
| Persistent volume across Staxa redeploy | BLOCKED: free app-volume capability unverified |
| External paired PostgreSQL/filestore backup + restore | BLOCKED: export/access/destination unverified |
| Concurrent users, image uploads, full assets and PDF generation at 512MiB | NOT TESTED; no capacity GO |

Only new deployment code was tested; the existing 207 Odoo tests were not rerun. Existing module/security tests remain at their previously validated state. The probe database/container/volume names are unique, local to the disposable CI runner, and cleaned up; no hosted pilot is updated. The workflow is preparation/testing, not a Staxa deployment workflow.

The first run 43615492748 built successfully and initialized Odoo, but failed with a `CalledProcessError` before completing login. The harness used host-port lookup on an internal network; it was replaced with an in-container loopback HTTP check. Exact original Docker stderr was not retained, so no stronger root-cause claim is made. The final probe also verifies module installation rather than relying on process exit alone. Current run has no failed check. Configuration rejects padded/newline secrets rather than allowing INI parsing to silently change credentials.

Peak samples are lower bounds on the maximum over the whole lifetime (the final initialization instant can be missed), not promises about future workloads. The container was constrained to 512MiB, but Staxa documents only 64Mi guaranteed RAM with a 512Mi burst ceiling. A login page does not fetch all browser assets or render wkhtmltopdf. The separate PostgreSQL container is not included in application memory figures. Odoo's threaded profile intentionally has no cron/background execution and does not assert worker memory limits enforce the cgroup ceiling.

The final documentation-only commit is marked `[skip ci]` before opening the PR to avoid triggering the unrelated full PR workflow. No skipped test is represented as passing. Review README for official source links and explicit acceptance gates.
