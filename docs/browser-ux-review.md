# CRM browser journey review — October–November 2026

Method: dual-agent (A: `/root/ux_design_review` · B: `/root/ux_implementation_review`).

Base: `main` at `203911117d64de74e1020f2f7768e5e859a4da42`, after security PR #15 and contractor statement PR #14. Branch: `feature/crm-browser-ux`; PR #16. Existing work and Morning PR #9 are preserved. This is a refinement of the existing field-work UI, not a change to pricing, approvals, financial eligibility or access boundaries.

## Environment and evidence contract

- The shared Codespace was previously upgraded to this base; no test records or changes from this branch are deployed there in this pass.
- The browser inventory showed a newly opened Odoo tab. Automatic review denied reading it because the earlier access choice specified isolated CI. The denial remained after the later live-tab request was supplied. Manual use of the shared site remains unverified.
- Dynamic checks run in a **separate disposable GitHub Actions Odoo 18/PostgreSQL 16 environment**. Chromium interacts with `http://127.0.0.1:8069`; it does not visit the blocked forwarded address. This is actual automated browser interaction, not manual live-site operation or screenshot-only verification.
- Artificial names, addresses, photos, financial transactions and generated credentials only. No Morning, email, WhatsApp, live payment or customer service calls.
- Baseline audit head `7ac44f83b6feb493fce6ffd862933608315f92f8` ran at tested merge `28d0777d698ed10e9512cc5f5a88a0e4a1bad5ff`. It adds tests and workflow only. Production addon content matches `2039111`. The comparison checks the archive's tested commit and observation mode.
- RPC provisions test users and verifies persisted values. The new journey drives client and work entry, quote, assignment and contractor reporting through rendered controls. Older suites also use RPC fixtures for some business records. No applicable `AGENTS.md` was found in the checkout or its ancestors.

## Skills and provenance

Loaded: UX Audit instructions and severity/evidence rules; Interface Design; Impeccable `critique`, `distill`, `clarify`, `adapt`, `polish`, Operate context and craft floor; Vercel Web Design Guidelines (fresh upstream review rules); Anthropic Webapp Testing; Odoo 18 index, API highlights, view, controller/security and testing references as relevant. Existing `.interface-design/system.md`, specification, screen coverage, security documentation and project-native test lifecycle are authoritative.

The Impeccable context launcher and detector were each attempted; both exited 127 because the bundled executable is absent. Neither deterministic detector counts nor an injected overlay are claimed. Assessment A completed before Assessment B findings entered synthesis. The expert Nielsen score was 28/40, a prioritization aid, not a measured completion score. The Anthropic server helper is not used: the existing Odoo/PostgreSQL Compose workflow owns service startup. Playwright handles browser interaction. Physical iOS/Android devices, Safari and screen readers are outside the available environment.

## Findings and exact reproductions

The first baseline reproduced the observed portal issues before reaching its dialog-focus assertion. The second baseline stopped after Chromium cancelled an attempted reload and the harness waited for navigation. Both passed 187 Odoo tests, startup and the three existing Chromium suites. The screenshots and observations already collected remain valid for those states. The new regression run requires the complete journey.

| ID | Severity | Surface / reproduction | Current evidence | User impact / proposed repair |
| --- | --- | --- | --- | --- |
| BUX-01 | 2 | Save contractor draft, then edit the summary | Chromium `saved-then-edited-390.png` and save-state check | Saved confirmation remained after an edit. Show the unsaved state after an accepted change. |
| BUX-02 | 2 | Select two before photos, exceed capacity with another batch, remove a retained new photo | Chromium `capacity-recovered-390.png` and capacity check | Stale capacity error and empty placeholders competed with the selected photos. Clear capacity guidance after removal and hide placeholders when photos are selected. |
| BUX-03 | 2 | Open all three empty portal scopes with an unassigned contractor | Chromium `empty-*-390.png` and three scope checks | The generic copy mentioned assignments on submitted and completed tabs. Give each scope an explanation of what belongs there. |
| BUX-04 | 2 | Open photo step with five before and five after, including a marked replacement, at 390px | Chromium `ten-photos-390.png`, 2,078px measured panel height | Long thumbnail rows delayed the next action. Compact the grid while keeping saved, new and removed states, full image access and 44px controls. |
| BUX-05 | 1 | Open short description with no additional arrival details | Chromium `draft-*.png` at 390, 768 and 1440 | The disclosure repeated the description. Show it when it offers additional information. |
| BUX-06 | 2 | Enter additional notes and proceed to review | Chromium `review-notes-390.png` and notes check | Review omitted text that the form submits. Show the notes when supplied. |
| BUX-07 | 1 | Read hub and today's appointment values | Chromium `crm/today-agenda-390.png`, `crm/hub-owner-390.png` and native Odoo field source | Seconds cluttered the appointment. Show localized minutes and isolate the numeric run. |
| BUX-08 | 2 | Edit summary, submit an invalid image, then leave the returned error page | Source review of POST error rendering and dirty initialization. Baseline journey ended before this case | Preserve the unsaved warning for retained edits. Keep the draft clean if only the discarded file changed. |

Heuristic references: Nielsen #1 (BUX-01), #9 (BUX-02), #2/#10 (BUX-03), #7/#8 and Fitts's Law (BUX-04), #8/Content #9 (BUX-05/07), #6 (BUX-06). No severity 3/4 or data-loss finding is asserted from source or static images.

Keep: governed work-card actions, owner-only finance, explicit draft/submitted/approved states, native semantic controls, linked field errors, retained File objects across steps, no-JS multipart fallback and current server-side limits. Do not remove business data or bypass authorization to reduce friction.

## Screen and process coverage

The inventory below ran in the final CI. Shared CSS does not imply per-screen verification. The coverage JSON and screenshot names record which widths were exercised for each surface.

| Surface | Existing real Chromium journey | New focused journey / boundary |
| --- | --- | --- |
| Hub | Owner/operations, counts, direct work action, six queues, Enter activation; 390/768/1024/1440 | Rendered appointment text omits seconds and is LTR |
| Inquiries / work card | New partial draft, required-field dialog, stage progression, tab changes, amount save; desktop/phone | Owner creates a client and inquiry via rendered CRM at 1440. Required phone blocks the first attempt, Escape returns to entered values, and the corrected form advances |
| Clients | List/search/cards, new client, name validation, save, linked work, work-to-client dialog | Client creation is through UI; other test customers can be RPC fixtures |
| Assignment / tasks / today / calendar | Dispatch, task evidence, work link, agenda, event popover/dialog, desktop→phone resize | Owner enters the quote amount/reference, selects the contractor, enters an appointment and confirms dispatch in the rendered UI. The assigned contractor completes the report journey on that work |
| Rates | Invalid/valid percentages, example, frozen historical assignment; desktop/phone | No formula or historical amount changes |
| Contractor portal | Report requirements, photos, draft, correction/resubmission, incomplete visit, second-contractor denial | Rendered login, empty scopes, saved/unsaved transitions, real reload confirmation, file/error recovery, notes review, ten photos and image-dialog keyboard focus at 390/768/1440 |
| Approval | Completed/incomplete review, correction reason and approval | Existing full work journey rerun |
| Customer collections | Partial receipts, remainder, closure, cancellation/reopening, mobile dialog | Artificial financial transactions only |
| Contractor payments | Owner payout, operations exclusion | No new contractor financial access |
| Contractor statement / PDF | Filters, source links, empty result, mobile/desktop, actual Odoo PDF and multiple pages, role separation | Existing statement suite rerun; same source calculation retained |
| Guide / native references | Guide, native Contacts/Project/CRM/settings/users entry smoke | Entry smoke is not a full audit of Odoo administration |

## Results and limitations

Baseline runs [41234157921](https://github.com/naor291291/odoo-pilot/actions/runs/41234157921) and [41235252275](https://github.com/naor291291/odoo-pilot/actions/runs/41235252275) captured issues on unchanged product code. The [first baseline archive](https://github.com/naor291291/odoo-pilot/actions/runs/41234157921/artifacts/13055320087) contains the comparison screenshots.

The first repaired run verified all focused behaviors except the gallery height target. Its measured panel was 1,564px. The final patch puts the picker before the photos, combines the guidance and avoids duplicate picker labels. The independent review also narrowed the rejected-save state to cases where the returned report values differ from the saved record. The final test separately checks client rejection, server rejection with unchanged text, and server rejection with retained edits.

Final implementation head `b1b8a23eb8f1c7b60029f27732d3a6513a9b3af8` and tested merge `86ddbd1cbcaac69af2940b8b301c44a4bc477951`, module `18.0.14.0.0`. [Integration and Chromium run 42384661370](https://github.com/naor291291/odoo-pilot/actions/runs/42384661370) passed 187 Odoo cases, startup/restart, all four Chromium suites, runtime security checks and an isolated restore with 44 attachment checksums. The new suite passed all 14 named checks and recorded zero uncaught page errors, console errors or same-origin HTTP failures in its portal journey. The manager journey also records uncaught page errors. The role boundary checks cover owner, operations and separate contractor sessions. A one-page and a four-page contractor statement PDF were produced by Odoo.

At 390px the ten-photo panel measured **1,438px**, down from **2,078px** on the baseline, about **31%** shorter. Photo and removal controls measured at least 44×44px at 390, 768 and 1440. The native image dialog kept underlying controls out of the tab sequence and restored focus on Escape. Chromium temporarily reported `body` when focus traversed browser chrome. Evidence includes the measured result, the real `beforeunload` dialogs and retained values after a failed save.

[Final evidence archive](https://github.com/naor291291/odoo-pilot/actions/runs/42384661370/artifacts/13579287056) contains the 19 new journey captures, the 41 CRM screen captures, 15 statement captures, core workflow captures, PDFs and a before/after HTML with seven matched pairs. Selected portal, gallery and appointment screenshots were visually inspected. The [security run 42384661334](https://github.com/naor291291/odoo-pilot/actions/runs/42384661334) passed its source and history checks. Dependency inventory remains advisory.

Separate agents performed UX assessment, implementation review, frontend edits, browser regression authoring and independent follow-up review. Root coordinated the CI runs, completed the owner journey and verified the artifacts. The Impeccable launcher and detector were unavailable. Physical phone/camera, Safari, system zoom and assistive-technology behavior remain outside this run. The shared Codespace did not receive the branch.

The final visual review found two minor polish points. Agenda time is visually separated from the right-aligned card text, and the gallery help can wrap between `12` and `MB` on a phone. The verified draft retains those layouts.
