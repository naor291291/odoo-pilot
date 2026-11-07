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
