> **Latest follow-up:** 40 open canonical advisories, 138 raw scanner records. Four new fixes verified in CI 42406366976; see the follow-up section and dependency-followup.csv. Earlier counts below are preserved baseline history.

# Dependency triage — actual CI image, 2026-11-07

Decision: **No-Go for real customer data**. Classification is complete for the 146 scanner rows; remediation/compatibility validation and native-path review are not complete. No exploit payload was executed. A high upstream score is not proof of an exploitable CRM route, and a restricted custom route is not proof that native Odoo is safe.

## Evidence and counting

Input: Security Actions run `42401972238`, artifact `13585966292`, `runtime-inventory.json` and `dependency-audit.json`. Odoo `18.0-20261102`, Python `3.12.3`, Linux Ubuntu Noble-derived image. Base image from integration build: `odoo:18.0@sha256:f61d3e36eb699e63557bbcdf4d7bd659e51418c326009e6574565d87e1d9026d`.

All advisory metadata was fetched from the OSV API, using the linked GitHub-reviewed advisory severity and upstream descriptions, on 2026-11-07. No inferred CVSS score was substituted. `dependency-alert-mapping.csv` preserves every original row/ID; `dependency-triage.csv` records 94 canonical advisories with conditions, relevance, patch evidence and unresolved questions. There are 95 distinct original scanner IDs, but two map to the same canonical advisory.

| Upstream severity | Raw scanner records | Canonical advisories |
|---|---:|---:|
| Critical | 4 | 4 |
| High | 73 | 48 |
| Moderate | 65 | 40 |
| Low | 4 | 2 |
| Total | 146 | 94 |

Seven canonical advisories require Windows-only paths and do not apply to this Linux runtime. **34 have verified vendor fixes**, compared against the expanded inventory from run `42404096013` / artifact `13586339334`. Three additional advisories have a required codec/wheel condition absent from that measured image. The remaining **50 stay open for patch/native-path evaluation**, with explicit custom-route mitigations and prerequisites in the CSV. They are not 50 demonstrated exploits. No conclusion about in-the-wild exploitation or KEV membership is made.

## Highest-priority decisions

1. **PDF parser: relevant authenticated upload surface.** Quote/invoice validation invokes Odoo `PdfReaderBase` on an uploaded file; Odoo deliberately prefers PyPDF2 2.x on Noble. Installed PyPDF2 2.12.1 is flagged by CVE-2023-36464. An 8MB limit does not impose a CPU deadline. Review a supported patched parser/backport or bounded parsing process before customer data. Merely installing `pypdf` does not switch Odoo's selected implementation. Source: `models/field_documents.py`, Odoo `odoo/tools/pdf/__init__.py`, [upstream advisory](https://github.com/py-pdf/pypdf/security/advisories/GHSA-4vvm-4w3v-6mr8). Reachability of the parser is verified by code and passing PDF tests; the malicious hang was not executed.
2. **HTML cleaner: relevant native surface.** Odoo's `html_sanitize` subclasses Cleaner; native rich text/chatter needs version-specific validation for the four cleaner advisories. Portal text escaping tests passed but do not certify every native rich-text path.
3. **Image libraries: patch the supported image and verify codec linkage.** The custom route restricts formats to JPEG/PNG/WebP, checks dimensions/frames, applies `ImageOps.exif_transpose` before resizing and writes a fresh metadata-free image. These controls reduce several prerequisites. Native Odoo image handling uses a broader `Image.open` and must be evaluated independently. Do not suppress all Pillow alerts.
4. **HTTP/crypto/authentication:** Meta uses a fixed HTTPS host, normal certificate verification and redirects disabled. This reduces redirect/URL conditions. Native external URL clients, proxy configuration, certificate APIs and optional passkey/CBOR routes still need evaluation. The inventory does not establish which optional modules are enabled.

## Four critical advisories

| Advisory | Required path | Pilot assessment |
|---|---|---|
| CVE-2026-112398 / GHSA-5x8w-8jj5-q52h | FlashPix JPEG decode | FPX excluded from custom allowlist. Native generic image callers remain unverified. |
| CVE-2026-112403 / GHSA-8g5g-8vmr-9782 | Lossless SOF3 JPEG, libjpeg-turbo 3.x, scaled draft/thumbnail | Ordinary JPEG allowlisting alone is insufficient. Custom exif-transpose/load precedes thumbnail; the measured Pillow codec is libjpeg-turbo **2.1.5**, which rejects the SOF3 prerequisite according to the upstream/Ubuntu description. Re-evaluate if codec/image changes. Ubuntu package-wide status remains vulnerable. |
| CVE-2026-112900 / GHSA-w889-685w-c8fh | EPS/Ghostscript with attacker-controlled special filename and argument file | Custom route accepts neither EPS nor a filesystem filename. Native/optional EPS processing still requires review. Ubuntu lists Noble as vulnerable. |
| CVE-2026-112393 / GHSA-332p-7hrc-92wf | TIFF encoding to BytesIO | Custom output preserves only accepted JPEG/PNG/WebP formats. Native TIFF export/callers remain unverified. |

Sources: [JPEG Ubuntu status](https://ubuntu.com/security/CVE-2026-112403), [EPS Ubuntu status](https://ubuntu.com/security/CVE-2026-112900), corresponding upstream advisories linked in the CSV. Ubuntu priority and upstream CVSS severity are distinct; the table above retains upstream severity.

## Backports and a confirmed patch gap

- **CVE-2024-49767**: installed `python3-werkzeug 3.0.1-3ubuntu0.2` includes [USN-7093-1](https://ubuntu.com/security/notices/USN-7093-1). Do not count its unchanged Python version as an unpatched multipart issue.
- **CVE-2026-59198**: installed `python3-pil 10.2.0-1ubuntu1.3` includes [USN-8690-1](https://ubuntu.com/security/notices/USN-8690-1).
- **Pillow patch applied in this PR build:** [USN-8999-1](https://ubuntu.com/security/notices/USN-8999-1), published 4 November, lists eleven CVEs across releases; ten apply to Noble and are fixed in `10.2.0-1ubuntu1.4`. Baseline image had `.3`; the rebuilt CI image now has `.4`. The EPS-only eleventh CVE affects 26.04, not this Noble image. Updating to `.4` does not resolve every later Pillow advisory or prove the four critical conditions absent.
- Canonical Ubuntu OSV records were fetched for 91 of the 92 CVEs. Installed full Debian versions were compared using `dpkg --compare-versions` against explicit fixed intervals; compact evidence is retained in `evidence/dependency-vendor-evidence.json`. Missing/no-fixed-range metadata remains open; absence of a record is not treated as safety. lxml CVE-2026-49825 is resolved through the installed lxml link-attribute backport even though the scanner reports lxml-html-clean. The two wheel-specific crypto advisories do not match the distribution build using system OpenSSL; other crypto issues remain separate. No ignore list or scanner suppression was added. No arbitrary pip upgrade replaced distribution-managed Odoo dependencies.

Before release, rebuild an approved image with supported fixes, capture the exact deployed digest and native codec/OpenSSL linkage, repeat the affected PDF/image/HTML/transport tests, then update each open triage row with evidence. Hosting, TLS and external restore remain separate gates.

## Reconciliation after the supported Pillow refresh

| Disposition | Canonical advisories |
|---|---:|
| Vendor fix verified in measured installed packages | 34 |
| Windows-only, not applicable to Linux | 7 |
| Required codec/wheel condition absent in measured image | 3 |
| Open: patch/path evaluation still required | 50 |

The raw pip audit still has 146 records because distribution backports generally retain upstream Python versions. This PR newly applies the ten Noble Pillow fixes; the other verified fixes were already supplied by the base image and are not claimed as new application repairs. No scanner finding is suppressed. This is the rebuilt development/CI image, **not an updated existing Codespace or a deployed production image**.

The 50 still-open advisories have upstream severities **3 critical, 25 high, 20 moderate and 2 low**. The three critical ones are FPX decode, EPS/Ghostscript and TIFF encode; the custom portal excludes their formats, but native Odoo exposure has not been ruled out. This distinction prevents both overstating 146 exploitable holes and incorrectly declaring the whole server safe.

## Follow-up: current disposition supersedes the 50-open baseline above

Measured follow-up executable revision: `cdea42a081d5750660d463d0b4fe3d011ee60b44`; Security run `42406366952`, artifact `13586953190`. `dependency-followup.csv` reviews **each of the 50 previously open advisories** with package presence, affected path, available candidate and compatibility decision. No deployment image exists; runtime claims refer to the measured CI image and its shared release stage.

- **Two scanner false positives:** GHSA-jwv3-5hgf-82ww begins at cryptography 42.0.0, GHSA-m2h6-j472-rp4c at 45.0.0. Installed 41.0.7 is below both ranges, and the measured verification PolicyBuilder API is absent. No suppression added; re-evaluate when upgrading crypto.
- **One targeted backport:** the upstream PyPDF2 EOF-loop workaround is applied in the runtime stage and runtime inventory confirms the guard. The bounded baseline reproduction failed, two local regressions pass. Native full-image/PDF verification passed in run 42406366976.
- **Three targeted upstream fixes:** lxml-html-clean 0.4.6 replaces 0.1.1 through an isolated, hash-pinned no-dependencies install. Odoo's official 18.0 requirements intentionally leave this package unpinned for security patches. Four Odoo sanitizer tests pass locally and in final run 42406366976. The fourth historical cleaner advisory had already been classified as vendor-fixed, so it is not double-counted as a new fix.
- **40 remain unresolved:** 3 critical, 21 high, 14 moderate, 2 low. All have a recorded compatibility/path decision. Thirty-one are Pillow advisories with upstream 13.0.0 fixes; Odoo on Python 3.12 pins 10.2.0. A major image-library migration and every native parser/encoder are not certified by passing custom portal tests. Crypto pairs, optional CBOR/SOAP and outbound/proxy paths likewise need version-specific testing or exact-host/module evidence.

The new raw scanner count is **138**, down from 146 after the cleaner update. Backports and false positives remain visible. The original 146-row mapping/94-row canonical baseline are retained for audit history; do not compare raw scanner rows directly to canonical open counts. Raw 138 is not the number of exploitable vulnerabilities.

Source candidates were checked against PyPI metadata on 2026-11-07 (`evidence/dependency-candidates.json`). Upstream fix availability is not a compatibility approval. `evidence/followup-runtime-inventory.json` records actual selected packages, native linkage and PDF guard. A source search found no custom/native Odoo call to the two pyOpenSSL callback APIs, but those advisories remain conservatively open pending exact deployment attestation. No arbitrary package suppression or global upgrade was used.

Additional native-library resolution: CVE-2024-0727 / GHSA-9v9h-cgj8-h64p is fixed in OpenSSL 3.0.13 according to the [official OpenSSL affected-version table](https://openssl-library.org/news/vulnerabilities-3.0/index.html). The cryptography backend in the measured image links exactly that fixed branch (Ubuntu .16 package). This is one newly verified existing vendor fix, not a code repair. Thus 50 = 4 newly fixed + 2 false positives + 1 additional vendor fix verified + 3 inactive-module conditions + 40 open.

Runtime module evidence also reports `auth_passkey`, `account`, `base_vat` and `certificate` uninstalled. All inspected Odoo CBOR imports are inside auth_passkey, with none in the custom addon. The three CBOR advisories are therefore classified as **not reachable in the measured pilot configuration**, not patched and not globally safe. Re-open them before enabling passkeys and verify module state again on any deployment. SOAP risk remains open because native wrappers also exist outside these optional modules.
