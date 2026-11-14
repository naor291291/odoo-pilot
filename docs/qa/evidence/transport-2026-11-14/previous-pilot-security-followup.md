# Closed pilot dependency follow-up — 2026-11-14

Measured commit: `0bb562c19cb15d793448fcc2e6be8764e99569fe`. Inventory: security run 43607849090. Original 146 records / 94 canonical advisories are preserved; this document concerns the 50 follow-up rows. The latest selected-library audit contains 76 raw records, including duplicates and distro-backported findings; it is not a count of exploitable endpoints.

31 Pillow findings now use the upstream fixed release 13.0.0. The bundled libjpeg-turbo is 3.2.0: previous reasoning based on absence of libjpeg-turbo 3 is obsolete. Fixed-release evidence replaces that reasoning.

| Advisory / CVE | Severity | Impact / prerequisites | Current disposition |
|---|---|---|---|
| GHSA-5x8w-8jj5-q52h / CVE-2026-112398 | CRITICAL | Pillow: Heap buffer overflow in FlashPix (FPX) JPEG decoding leads to code execution | Fixed: Pillow 13.0.0; inventory run 43607849090 has no Pillow advisory records; compatibility run 43607849101 |
| GHSA-w889-685w-c8fh / CVE-2026-112900 | CRITICAL | Pillow: Argument Injection in Ghostscript call, potentially leading into RCE | Fixed: Pillow 13.0.0; inventory run 43607849090 has no Pillow advisory records; compatibility run 43607849101 |
| GHSA-332p-7hrc-92wf / CVE-2026-112393 | CRITICAL | Pillow: Heap buffer overflow in _tiffWriteProc when saving TIFF to BytesIO | Fixed: Pillow 13.0.0; inventory run 43607849090 has no Pillow advisory records; compatibility run 43607849101 |
| GHSA-3ww4-gg4f-jr7f / CVE-2023-50782 | HIGH | Python Cryptography package vulnerable to Bleichenbacher timing oracle attack | Open: compatibility or exact native/deployment path unresolved |
| GHSA-m959-cc7f-wv43 / CVE-2026-34073 | LOW | cryptography has incomplete DNS name constraint enforcement on peer names | Open: compatibility or exact native/deployment path unresolved |
| GHSA-vp96-hxj8-p424 / CVE-2026-27448 | LOW | pyOpenSSL allows TLS connection bypass via unhandled callback exception in set_tlsext_servername_callback | Open: compatibility or exact native/deployment path unresolved |
| GHSA-5pwr-322w-8jr4 / CVE-2026-27459 | HIGH | pyOpenSSL DTLS cookie callback buffer overflow | Open: compatibility or exact native/deployment path unresolved |
| GHSA-9wx4-h78v-vm56 / CVE-2024-35195 | MODERATE | Requests `Session` object does not verify requests after making first request with verify=False | Open: compatibility or exact native/deployment path unresolved |
| GHSA-8988-9cw3-xx77 / CVE-2026-97687 | HIGH | urllib3: HTTPS proxy TLS configuration may be ignored or overridden | Open: compatibility or exact native/deployment path unresolved |
| GHSA-jjg7-2v4v-x38h / CVE-2024-3651 | MODERATE | Internationalized Domain Names in Applications (IDNA) vulnerable to denial of service from specially crafted inputs to idna.encode | Open: compatibility or exact native/deployment path unresolved |
| GHSA-65pc-fj4g-8rjx / CVE-2026-45409 | MODERATE | Internationalized Domain Names in Applications (IDNA): Specially crafted inputs to idna.encode() can bypass CVE-2024-3651 fix | Open: compatibility or exact native/deployment path unresolved |
| GHSA-4cc2-g9w2-fhf6 / CVE-2026-58501 | MODERATE | Zeep: Server-Side Request Forgery (SSRF) | Open: compatibility or exact native/deployment path unresolved |

Residual unresolved: **0 critical, 3 high, 4 moderate, 2 low**. This is a review count, not nine demonstrated exploits. The three High prerequisites are RSA key exchange/timing exposure, a pyOpenSSL DTLS cookie callback returning more than 256 bytes, and an HTTPS proxy with mixed TLS policies. Intended ingress terminates at Caddy, Odoo has only HTTP on an internal network, and proxy settings are emptied. These are intended configuration restrictions, not sufficient runtime/native-call proof to close the three findings.

The measured Ubuntu package revisions are recorded in `evidence/pilot-2026-11-14/runtime-inventory.json`. Vendor changelogs for cryptography and urllib3 were checked; neither inspected changelog explicitly establishes a fix for these specific remaining High findings. A blanket pip upgrade of cryptography would require a compatible pyOpenSSL pair and could activate previously inapplicable advisory ranges. No such unvalidated upgrade was made.

Before GO: verify the complete native-call/transport exposure in a running isolated pilot configuration, or apply compatible targeted fixes and regressions. Before exposing any host, test private ingress and no-egress enforcement, TLS and actual account roles. Do not enable passkeys/extra modules or live transports without reassessing the dependency/module inventory.
