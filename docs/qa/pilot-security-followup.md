# Targeted High closure and Northflank gate — 2026-11-14

Scope: only the three High blockers from `f3f0cea10ee20dd644745de0bf78b87e2056c565`, required compatibility dependencies, and a free/no-card Northflank feasibility review. No merge, deployment, purchase, live provider, real data or new feature. This report supersedes the earlier three-High-open disposition, preserved in `evidence/transport-2026-11-14/previous-pilot-security-followup.md`.

## Changes

Tested code candidate: `5417c0c196898a152f8e918bd775ecf8e595f820`. Cryptography 50.0.2 and pyOpenSSL 26.4.0 are a compatible dependency pair; urllib3 is 2.8.0. Required cffi 2.0.0 and typing_extensions 4.15.0 are explicitly pinned. All wheels have SHA256 locks; installation keeps `--no-deps` and isolates overrides in the existing shared runtime directory. No unrelated dependency bundle was updated. These are intentional Odoo pin exceptions, not upstream Odoo certification.

| Advisory | Previous version | Fix / evidence | Disposition |
|---|---|---|---|
| GHSA-3ww4-gg4f-jr7f / CVE-2023-50782 | cryptography 41.0.7 | 50.0.2 wheel; actual image links OpenSSL 4.0.3. Regression verifies implicit RSA rejection support plus valid RSA PKCS#1 v1.5 round-trip. | Fixed upstream release; not dismissed because TLS ingress happens elsewhere. |
| GHSA-5pwr-322w-8jr4 / CVE-2026-27459 | pyOpenSSL 23.2.0 | 26.4.0; direct native callback rejects a 257-byte DTLS cookie without writing to output or length; valid short-cookie control succeeds. | Fixed. Bounded old-version reproduction fails the rejection assertion; new version passes. |
| GHSA-8988-9cw3-xx77 / CVE-2026-97687 | urllib3 2.0.7 | 2.8.0; forwarding and CONNECT paths preserve the proxy's certificate policy and do not pass target client keys, hostname or fingerprint to the proxy. | Fixed. Both old-version policy checks fail; new version passes. |

The callback baseline allocates a deliberately oversized 1024-byte buffer, avoiding an actual native out-of-bounds write. Proxy tests inspect the parameters passed at the TLS wrapper boundary using mocks; they do not claim a live remote TLS attack demonstration. The RSA check is backend-feature and patched-version evidence, not a statistical timing-attack experiment. No external server was contacted by these tests.

## Verification

Seven focused tests passed locally on Python 3.12.14 with the exact reviewed package pins. Three bounded negative controls against old pyOpenSSL/urllib3 versions failed as expected. [Security run 43610750093](https://github.com/naor291291/odoo-pilot/actions/runs/43610750093) passed: actual Docker inventory selects the three patched versions and the advisory audit returns **zero findings for each of those three packages**. The full selected-library audit still contains 44 raw records; they must not be treated as 44 proven exploits or ignored because the workflow succeeded.

[Integration run 43610750108](https://github.com/naor291291/odoo-pilot/actions/runs/43610750108) completed successfully on the patched runtime:

- **207 Odoo tests**, 0 failures/errors; **15 native image tests**.
- **7 new transport-security regressions** in the actual Docker image; 6 existing transport mocks, 2 PDF and 4 HTML regressions.
- 7 runtime lifecycle/security scenarios; 4 Chrome suites, including 14 browser-journey assertions.
- **44/44 RTL/axe viewport states** at 375/390/768/1440px, no violations, document overflow or failed requests. No captured JS/console errors in the browser journey results.
- Separate synthetic PostgreSQL+filestore restore: **48 attachment checksums verified**. This is not an external-host backup certification.
- Startup/restart/role smoke, 7 resolved Compose assertion groups and Caddy validation passed.

[Browser artifact 14120327005](https://github.com/naor291291/odoo-pilot/actions/runs/43610750108/artifacts/14120327005) and [runtime/restore artifact 14120391927](https://github.com/naor291291/odoo-pilot/actions/runs/43610750108/artifacts/14120391927) expire 2026-11-28. Compact evidence is committed here. Final documentation-only commit skips duplicate CI; runtime remains the tested `5417c0c` tree. No unresolved test failure remains; the three old-version failures were intentional negative controls.

Full CI is justified specifically by changing Odoo's shared crypto/TLS/HTTP runtime and native CFFI dependencies. No new baseline review or unrelated test suite was introduced. Existing Pillow/PDF/sanitizer fixes remain intact. Optional modules outside the synthetic pilot remain outside compatibility acceptance; ARM64 wheel hashes are supplied but this CI runner validates x86_64 only.

## Remaining findings and gate

The original 50 follow-up rows are retained. Five previously open findings are resolved by this change: the three requested High findings plus two Low findings in the same upgraded crypto/TLS packages. Three earlier crypto dispositions based on old-package affected ranges/native backend are updated to patched-release evidence, because the backend and available APIs changed. Totals: **43 fixed, 3 inactive-module conditions, 4 still open (all Moderate)**. Thus the reviewed follow-up has **0 Critical / 0 High / 4 Moderate / 0 Low unresolved**. This is not a blanket whole-image or live-host certification. The four remaining Moderate rows concern Requests, IDNA (two) and Zeep; they were not expanded into unrelated upgrades in this scoped task.

**Northflank free/no-card hosting remains NO-GO.** See [Northflank fit](northflank-sandbox-fit.md): official billing and pricing statements conflict on card requirements; free persistent volume entitlement is unverified; network-policy docs explicitly describe BYOC rather than proving managed Sandbox deny-egress; enterprise global backups cannot be assumed free. HTTPS and persistent storage are documented capabilities, not tested account entitlements or working infrastructure.

No host TLS/access/no-egress, persistent restart/redeploy or external paired PostgreSQL+filestore restore was performed. Those mandatory external checks still block inviting users. No service was provisioned to bypass this task's deployment prohibition. Code security closure does not grant deployment approval.

Evidence: `evidence/transport-2026-11-14/`, existing synthetic CI artifacts, and `dependency-followup.csv`. Official release metadata: https://pypi.org/pypi/cryptography/50.0.2/json ; https://pypi.org/pypi/pyOpenSSL/26.4.0/json ; https://pypi.org/pypi/urllib3/2.8.0/json . Advisory definitions: https://osv.dev/vulnerability/GHSA-3ww4-gg4f-jr7f ; https://osv.dev/vulnerability/GHSA-5pwr-322w-8jr4 ; https://osv.dev/vulnerability/GHSA-8988-9cw3-xx77 .
