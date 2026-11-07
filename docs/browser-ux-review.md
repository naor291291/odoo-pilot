# CRM browser journey review — 31 October 2026

Method: dual-agent (A: `/root/ux_design_review` · B: `/root/ux_implementation_review`).

Base: `main` at `203911117d64de74e1020f2f7768e5e859a4da42`, after security PR #15 and contractor statement PR #14. Branch: `feature/crm-browser-ux`; PR #16. Existing work and Morning PR #9 are preserved. This is a refinement of the existing field-work UI, not a change to pricing, approvals, financial eligibility or access boundaries.

## Environment and evidence contract

- The shared Codespace was previously upgraded to this base; no test records or changes from this branch are deployed there in this pass.
- A new cloud-browser access attempt was rejected by URL policy before page observation. No alternate URL, proxy, port exposure or browser workaround was attempted. Manual use of the shared live site remains unverified in this pass.
- Dynamic checks run in a **separate disposable GitHub Actions Odoo 18/PostgreSQL 16 environment**. Chromium interacts with `http://127.0.0.1:8069`; it does not visit the blocked forwarded address. This is actual automated browser interaction, not manual live-site operation or screenshot-only verification.
- Artificial names, addresses, photos, financial transactions and generated credentials only. No Morning, email, WhatsApp, live payment or customer service calls.
- Baseline audit commit `7ac44f83b6feb493fce6ffd862933608315f92f8` adds tests/workflow only; production addon content is identical to `2039111`. `--observe` records defects without hiding them. Normal regression mode must assert the repaired behavior.
- RPC is used to set up independent fixtures and assert persisted business data. Login/edit/selection/save/review/reload/photo/keyboard paths explicitly attributed to UI are driven through rendered Chromium controls. The pre-existing field-work suite uses some RPC setup/edits; it is not represented as entirely manual UI data entry.

## Skills and provenance

Loaded: UX Audit instructions and severity/evidence rules; Interface Design; Impeccable `critique`, `distill`, `clarify`, `adapt`, `polish`, Operate context and craft floor; Vercel Web Design Guidelines (fresh upstream review rules); Anthropic Webapp Testing; Odoo 18 index, API highlights, view, controller/security and testing references as relevant. Existing `.interface-design/system.md`, specification, screen coverage, security documentation and project-native test lifecycle are authoritative.

The Impeccable context launcher and detector were each attempted; both exited 127 because the bundled executable is absent. Neither deterministic detector counts nor an injected overlay are claimed. Assessment A completed before Assessment B findings entered synthesis. The expert Nielsen score was 28/40, a prioritization aid, not a measured completion score. The Anthropic server helper is not used: the existing Odoo/PostgreSQL Compose workflow owns service startup. Playwright handles browser interaction. Physical iOS/Android devices, Safari and screen readers are outside the available environment.

## Findings and exact reproductions

Status below is deliberately separated into source candidate, prior screenshot and newly executed browser evidence. Final run references and before/after captures will be recorded after execution.

| ID | Severity | Surface / reproduction | Current evidence | User impact / proposed repair |
| --- | --- | --- | --- | --- |
| BUX-01 | 2 | Save contractor draft, then edit summary or choose another image | Source: `field_portal.py` saved notice + `field_portal.js` dirty handlers; runtime pending | Old “saved” confirmation can misrepresent new unsaved edits. Replace it with explicit unsaved state after mutation; retain native unload protection. |
| BUX-02 | 2 | Select two before photos, exceed capacity with another batch, remove a retained new photo | Source: gallery error/removal lifecycle; runtime pending | Capacity instruction can remain after correction. Recompute capacity errors on add/remove without silently clearing format/size rejection. |
| BUX-03 | 2 | Open all three empty portal scopes with an unassigned contractor | Source: single generic empty block; runtime pending | Submitted/completed lists incorrectly explain new assignment. Give each scope a truthful heading and next-step explanation. |
| BUX-04 | 2 | Open photo step with five before/five after, including a marked replacement, at 390px | Source + prior CI screenshot, new metric pending | Repeated per-image text and framing increase scrolling. Compact thumbnails/status/actions while preserving full images, distinct states, removal and 44px targets. |
| BUX-05 | 1 | Open short description with no additional arrival details | Source: unconditional description disclosure; runtime pending | Repeats the same description under another control. Render extra details only when they add information. |
| BUX-06 | 2 | Enter additional notes, proceed to review, compare with eventual submitted form | Source: review excludes submitted notes; runtime pending | User cannot verify all submitted text. Show nonempty notes in review with a clear label. |
| BUX-07 | 1 | Read hub/today appointment values containing nonzero seconds | Source + prior screenshots; new browser evidence pending | Seconds add noise to operational scheduling. Retain native localized date/time and timezone; omit seconds, isolate numeric run. |

Heuristic references: Nielsen #1 (BUX-01), #9 (BUX-02), #2/#10 (BUX-03), #7/#8 and Fitts's Law (BUX-04), #8/Content #9 (BUX-05/07), #6 (BUX-06). No severity 3/4 or data-loss finding is asserted from source or static images.

Keep: governed work-card actions, owner-only finance, explicit draft/submitted/approved states, native semantic controls, linked field errors, retained File objects across steps, no-JS multipart fallback and current server-side limits. Do not remove business data or bypass authorization to reduce friction.

## Screen and process coverage

The following is the test inventory, **not yet a claim that the new run passed**. The final evidence table records executed results. Shared CSS does not imply per-screen verification.

| Surface | Existing real Chromium journey | New focused journey / boundary |
| --- | --- | --- |
| Hub | Owner/operations, counts, direct work action, six queues, Enter activation; 390/768/1024/1440 | Verify localized appointment display after refinement |
| Inquiries / work card | New partial draft, required-field dialog, stage progression, tab changes, amount save; desktop/phone | Values and business rules remain under existing regression suite |
| Clients | List/search/cards, new client, name validation, save, linked work, work-to-client dialog | Client creation is through UI; other test customers can be RPC fixtures |
| Assignment / tasks / today / calendar | Dispatch, task evidence, work link, agenda, event popover/dialog, desktop→phone resize | No native calendar/global navigation replacement |
| Rates | Invalid/valid percentages, example, frozen historical assignment; desktop/phone | No formula or historical amount changes |
| Contractor portal | Report requirements, photos, draft, correction/resubmission, incomplete visit, second-contractor denial | Rendered login, empty scopes, saved/unsaved transitions, real reload confirmation, file/error recovery, notes review, ten photos and image-dialog keyboard focus at 390/768/1440 |
| Approval | Completed/incomplete review, correction reason and approval | Existing full work journey rerun |
| Customer collections | Partial receipts, remainder, closure, cancellation/reopening, mobile dialog | Artificial financial transactions only |
| Contractor payments | Owner payout, operations exclusion | No new contractor financial access |
| Contractor statement / PDF | Filters, source links, empty result, mobile/desktop, actual Odoo PDF and multiple pages, role separation | Existing statement suite rerun; same source calculation retained |
| Guide / native references | Guide, native Contacts/Project/CRM/settings/users entry smoke | Entry smoke is not a full audit of Odoo administration |

## Results and limitations

Baseline and repaired runs: pending. No passing claim until the actual logs, coverage JSON and captures have been inspected. Console/page/network output in the focused journey is collected separately from business validation dialogs; environment failures must not be mislabeled as product defects.
