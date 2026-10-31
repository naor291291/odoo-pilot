# Security findings — public-safe review

Baseline `24d22c3034a1819c5b35667f60a4ef29296113ba`; synthetic pilot only. Severity reflects the intended application boundary if real data were present, not a claim that real data was exposed. No critical issue was verified. Confirmed application defects: **one high, two medium, one low**; caching is additional hardening. Dependency alerts and deployment gaps are tracked separately, not counted as verified exploits.

Detailed operational exploitation instructions and real identifiers/secrets do not belong in this public repository. Safe reproduction uses only the named synthetic tests in an isolated database; the baseline failures and post-fix results are recorded in `verification.md`.

## S-001 — High: financial draft confidentiality crossed the operations boundary

- **Location:** baseline `security/field_collection_security.xml:13` (dialog ACLs, no corresponding private rules); fixed rules at `security/field_collection_security.xml:5`, `:10`, `:15`. Action guards: `models/field_collection.py:317`, `:342`, and `models/field_workspace.py:121` (`action_apply`). All addon paths are under `addons/field_work_photos/`.
- **Prerequisites:** authenticated operations user; an owner-created payout dialog exists. No system/admin privilege or access to the actual payout model is needed.
- **Evidence/impact:** synthetic regression returned an owner-created payout dialog in another user's search and exposed its amount/reference. Ordinary transient ACLs in the inspected Odoo 18 build do not imply creator isolation. The ledger's existing owner-only check still prevented an unauthorized payout; this finding concerns private draft data, not proven money movement.
- **Fix:** global creator/active-company rules on registration, cancellation and correction dialogs; finance-kind restrictions on monetary dialogs; explicit action access checks. No broader finance access was granted.
- **Safe validation:** `TestSecurityHardening.test_financial_dialogs_are_private_to_creator`, `test_private_cancellation_and_correction_dialogs`, `test_operations_cannot_create_private_contractor_dialog`, `test_company_switch_revokes_dialog_and_statement`. Search/read/export/direct action must deny the other user; the creator can still register/cancel/correct and repeated registration stays idempotent.

## S-002 — Medium: protected workflow defaults bypassed explicit creation guards

- **Location:** baseline `models/project_task.py:117`, `models/field_dispatch.py:311`, `models/field_pricing.py:102`; fixes in each model's `default_get` (`project_task.py:84`, `field_dispatch.py:314`, `field_pricing.py:108`).
- **Prerequisites:** authenticated caller with the corresponding native create rights. This is not a portal privilege escalation.
- **Evidence/impact:** baseline fixtures could create pending/audit evidence, an improperly linked task, or a fabricated frozen pricing snapshot through default channels despite the explicit-value guards. Existing constraints did reject an inconsistent approved/in-progress combination; the final reproducer uses a valid pending state, rather than treating that rejection as a vulnerability.
- **Fix:** discard managed workflow/dispatch/pricing defaults and force initial review state to draft. Continue to reject explicit attempts. Ordinary user-entered business defaults remain available; historical prices and existing data are not rewritten.
- **Safe validation:** `test_review_defaults_do_not_create_approval_or_audit`, `test_dispatch_link_default_cannot_create_linked_task`, `test_pricing_defaults_do_not_freeze_fabricated_rates`. Legitimate dispatch still freezes the actual contractor rate and preserves the existing ₪650 estimate on a ₪1,000 fixture.

## S-003 — Medium: effective photo parent/default input escaped locking and count checks

- **Location:** baseline `models/field_visit.py:133`; fixes at `models/field_visit.py:133` and `models/project_task.py:148`.
- **Prerequisites:** native project/photo create rights and an accessible parent. Contractor model RPC access remains denied.
- **Evidence/impact:** default-parent creation added an extra image after report submission and beyond five per kind; a default image also bypassed the custom format check. The original explicit-parent path already enforced these controls.
- **Fix:** expand effective creation defaults before checking the parent, take the same locks/state checks, validate all image values, then verify final gallery counts. Use the normalized image for storage. Do not weaken parent record access checks.
- **Safe validation:** `test_photo_default_parent_cannot_bypass_review_lock`, `test_photo_default_parent_enforces_gallery_limit`, `test_photo_defaults_validate_file_content`; existing portal upload/removal/atomic-submission cases continue to run.

## S-004 — Low: small uploaded images retained private metadata

- **Location:** `models/project_task.py:109`, `models/field_visit.py:133/:146`; native source `odoo/tools/image.py:ImageProcess.image_quality` can return the original small image, and bypasses normal WebP processing.
- **Prerequisites:** valid metadata-bearing image uploaded by an authorized account, later downloaded by an authorized recipient. No anonymous disclosure was demonstrated.
- **Evidence/impact:** a synthetic small JPEG retained EXIF, including GPS metadata. Metadata adds privacy information beyond the displayed report; it is not needed for the defined before/after workflow.
- **Fix:** decode only JPEG/PNG/WebP, check bounds/one frame, apply orientation, resize to 1920 and re-encode without metadata/trailing content. Register only the supported additional WebP plugin; Odoo's minimal plugin preload otherwise prevents its normal use. JPEG/WebP output may be recompressed. Existing stored images are unchanged and need a separately planned review before real-data migration.
- **Safe validation:** `test_uploaded_images_drop_metadata_and_preserve_orientation`, `test_webp_resize_and_invalid_image_preserve_saved_data`; both main and extra images are checked. Invalid files preserve existing data.

## H-001 — Additional hardening: explicit private response caching

Portal detail/list HTML and statement HTML/PDF now send `Cache-Control: private, no-store` (`controllers/field_portal.py`, `controllers/contractor_statement.py:8`). Native report authentication/provider checks remain in place. Tests verify headers and session/guest denials; no browser-cache extraction attack was performed. This reduces future caching risk but cannot revoke files already downloaded or guarantee every browser's history behavior.

## D-001 — Open: dependency/image patch status needs triage

Local pip-audit 2.10.1 reported **137 advisory records, 90 distinct primary IDs, 13 packages** in the existing local Odoo Python environment. Counts contain repeated advisory records/aliases and are not counts of proven vulnerabilities. Examples include Pillow 10.2.0, Werkzeug 3.0.1, Jinja2 3.1.2 and requests 2.31.0. This local pip environment is not the Ubuntu/Docker deployment image.

Custom image upload reaches JPEG/PNG/WebP decoders; it does not accept a user font/PDF, use Pillow's platform image viewer or convert an arbitrary format. Advisories affecting those other paths are not established upload exploits. Native Odoo may use additional parsers outside this custom route. Ubuntu backports can also make a nominal package version insufficient evidence of vulnerability. No exploit payloads for dependency advisories were run.

CI inventories the actual rebuilt development image (Python and available distribution versions) and publishes an unsuppressed advisory report. The dependency step is deliberately **advisory**, with a visible warning on either findings or scan failure; source/history scans and functional authorization regressions fail the workflow. This does not authorize real-data use. Before production: establish exact image digests/SBOM, correlate vendor/backport status and reachable advisories, patch/rebuild supported Odoo/base/decoder/PDF components and rerun compatibility/security checks. No arbitrary mass upgrade or unreviewed ignore list was introduced.

## Deployment and operational gaps

These are not claims that Codespaces was deployed as production. No production server, TLS proxy, firewall or backup service was provided for verification.

1. **Before real data:** choose and verify supported hosting, TLS/proxy/header/cookie behavior, database role/network separation, worker/request/resource limits and PDF outbound network restrictions. The pilot's `workers=0`, disabled cron, floating images and generated test accounts are development choices.
2. **Before real data:** encrypted, access-controlled backups outside the Codespace; paired DB/filestore restore schedule; agreed RPO/RTO, retention/erasure and incident owner. Current local backup permissions are checked, but no off-site/encryption service is configured.
3. **Before real data:** remove pilot accounts/bootstrap password/role resets, enroll privileged users in supported Odoo TOTP with recovery procedures, verify deployed login cooldown/rate limits and review native internal groups. No credentials/MFA/access configuration was changed in this review.
4. **Before merging Morning:** rebase and independently review its secret storage, company isolation and import/report boundaries. Its `client_secret` is a protected DB field, not a claim of at-rest encryption; no live key, API or document was used here.

The full reachable Git history scan found no recognized secret. This is bounded detection, not proof that no secret has ever existed. The known Compose DB password is an explicit internal disposable-development value; no real key rotation is warranted from that value alone. No runtime credentials or DB dumps were included in the PR or artifacts.
