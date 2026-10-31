# CRM clarity refinement — 31 October 2026

Method: dual-agent (A: design_assessment · B: implementation_assessment). Assessment A completed before B findings entered synthesis. No Impeccable detector result is claimed: the launcher and a real `detect --json` attempt both exited 127 because its engine binary is unavailable. No overlay was injected. The five requested Impeccable playbooks were read directly and applied to existing Odoo components; this is not a claim that their CLI commands ran successfully.

## Current baseline and product context

GitHub was read afresh. PRs #10/#11/#12 were already merged. Base is upstream `main`, `02d74f2126cddfc47ed9ea0d2aadd0012ee4b5b0`, not the remembered PR head. All tracked base bytes were checked against GitHub blob SHAs; existing worktrees were left untouched. Separate branch: `feature/crm-clarity-pass`. Morning #9 remains open/separate. No merge or production deployment is part of this pass.

Read the original three-page `מסמך8.pdf`, README, `.interface-design/system.md`, prior `crm-ux-coverage.md`, custom models/views/assets/security and native Odoo portal/calendar components. Audience: first-time nontechnical Hebrew project manager, returning manager, distracted phone contractor. Goal: know current location/state, identify the next real task, correct a mistake and finish without redundant navigation.

## Evidence before implementation

The PR #12 archive supplies historical before captures. Their UI structures and all affected baseline source match current main (differences in the old local copy were terminal whitespace, with a later devcontainer auto-start change). They are not fresh browser observations. In particular, static screenshots do not establish keyboard, latency, assistive-technology or save behavior.

| ID / severity | Screen / named visual evidence | Source corroboration and user impact | Change |
|---|---|---|---|
| F01 · 3 major · Nielsen #6/#8, Tog anticipation | `crm/hub-owner-1440.png`, `hub-owner-390.png`: accented review count 0, six equivalent tiles, no jobs | `field_navigation_views.xml` and dashboard model: manager must open a queue before identifying work | Pending/due records first with reason and direct workspace action; quieter counters including empty queues |
| F02 · 3 major · B&S workload, Content #1/#9 | `mobile-quote.png`: fields below viewport; `portal-step-error-mobile.png`: reporting follows full metadata block | Interface and portal templates duplicate identity, next-step and full summaries before inputs | Compact identity/one next step, collapsed full checklist/stage map, stage-specific input priority, compact portal brief with full details available |
| F03 · 2 minor · Nielsen #6/#7, G-P #3 | `crm/tasks-list-desktop.png`, `task-detail-mobile.png`: no address in list, extra evidence screen before treatment | Navigation model/views: all-task list is the only schedule entry | Time-zone-aware today agenda with client/address/performer and direct work-card action; calendar/evidence retained |
| F04 · 2 minor · Nielsen #8, G-P #7 | `crm/contractor-rate-form-mobile.png`: stacked large tier boxes; no worked example | Workspace rate form and pricing model | Flat compact tiers, dynamic illustrative calculation from this contractor's percentage; frozen-job warning preserved |
| F05 · 1 cosmetic · Nielsen #4, Content #7 | Portal/header/footer and hub: “Your logo” and “My Company” | Native portal chrome; real business identity not established in repo | Scoped textual fallback for default portal branding; preserve actual configured identity |

Source-only additional findings: visible upload picker lacked its error association; fixed `aria-describedby`/`aria-invalid`. Wizard wrote a step hash without restoring it; removed that misleading URL state while preserving DOM back/forward retention. Disabled submission remains existing guarded behavior; Continue exposes linked inline errors and server validation remains authoritative. It was a source risk, not a reproduced stuck state, and is not reported as fixed.

Positive patterns preserved: explicit submission-versus-approval distinction; useful inline error text and draft/correction flow; shared Heebo/water/steel palette, native controls, numeric isolation and permission boundaries.

Provisional BEFORE heuristic scores (0–4, expert judgment from screenshots/source; not measured user performance): status 3, real-world language 3, control 3, consistency 3, prevention 3, recognition 2, efficiency 2, minimalism 2, recovery 3, help 3: **27/40**. No invented after score or task-completion-time gain. Hub/entry cognitive load is moderate to high because queues/instructions compete; phone contractor loses vertical space to repeated metadata. First-time manager and distracted contractor are the primary personas. Keyboard checks require rendered verification.

## Skill provenance

- [UX Audit](https://github.com/EliaAlberti/ux-audit-skill/blob/main/SKILL.md): screenshot goal walk, severity/heuristic citations and evidence discipline. Intake was already answered by the user's brief; historical screenshots were available, so no blocking questions. Code/runtime findings are separately labelled. Annotation and visual comparison evidence are attached to CI when available.
- [Impeccable](https://github.com/pbakaus/impeccable/blob/main/.claude/skills/impeccable/SKILL.md): current critique, distill, clarify, adapt, polish, Operate and craft-floor references. Used independent A/B assessments as requested by critique. CLI context/detector unavailable as stated above; no detector counts, trend or stored CLI critique claimed.
- [Interface Design](https://github.com/Dammyjay93/interface-design/blob/main/.claude/skills/interface-design/SKILL.md): incumbent system retained and updated in the repo.
- [Vercel](https://github.com/vercel-labs/agent-skills/blob/main/skills/web-design-guidelines/SKILL.md) and its [current rules](https://github.com/vercel-labs/web-interface-guidelines/blob/main/command.md): source and rendered compliance review.
- [Anthropic Webapp Testing](https://github.com/anthropics/skills/blob/main/skills/webapp-testing/SKILL.md): helper `--help` ran; existing Odoo/PostgreSQL lifecycle retained. Real headless Chrome suites use DOM inspection/meaningful waits, with rendered content fallback for Odoo's persistent bus.

Questions skipped: the user has authorized the refinements and specified audience, scope and platforms.

## Validation and coverage

Final implementation verification: [CI run 41217828468](https://github.com/naor291291/odoo-pilot/actions/runs/41217828468), code commit `67c856313b3a62c04d1e2d71be29900ed7cbbe46`. All 152 Odoo/PostgreSQL integration tests, startup/restart smoke, both headless Chrome suites and visual evidence generation passed. Python/JavaScript/XML syntax, shared SCSS compilation and whitespace checks passed. Final follow-up updates documentation only; no unverified UI fix is included after this run.

| Surface | Reviewed/changed | Required verification |
|---|---|---|
| Hub | Real pending/due work, first six previews, counts/all-list, quieter empty queues | Owner/operations, 390/768/1024/1440px, per-job action, empty state, keyboard |
| Work card | Compact identity/checklist, stage-specific form order, field hints | New/quote/schedule, required fields and stage retention, desktop/phone/keyboard/long text |
| Portal | Compact essential brief, full details disclosure, notes disclosure, visible upload errors, removed non-restorable step hash | Back/Continue, draft/reopen, multi-photo/error/remove, submit, correction, foreign task access, desktop/phone |
| Today agenda/task list | Local-day query, ordered agenda, address, direct work-card button | Boundary tests incl. adjacent days, phone/intermediate/desktop, calendar retained |
| Contractor rates | Compact tiers/live example | Invalid percentage, save/recompute, frozen dispatched rates unchanged, operations denied |
| Branding | Default-only field-route fallback | Default/custom company conditions; no legal business name guessed |
| Native Odoo/finance | Existing regressions retained | Approval, collection, payout, cancellation, role separation; no core redesign claim |

No pricing formulas, snapshot rules, approval/collection transitions, photo caps, ACLs or existing records are migrated by these UI changes. Dashboard queries use normal requesting-user record rules without sudo. Today previews do not imply that a report is overdue merely because it is pending.

Remaining limits: no live Codespaces session or live Morning API; no physical iPhone/Android camera, Safari/WebKit, actual screen reader or interrupted cellular upload. API-dependent/automatic document delivery and monthly/conversion reporting remain prior specification gaps. General Odoo company chrome retains a genuinely configured business name; actual business identity must be configured by its owner.


## Keyboard defect found during verification

A later, explicit Enter test reproduced a real issue in the embedded hub cards: Odoo's native KanbanRenderer registers a card-level Enter hotkey that consumes Enter on a nested action button without activating it. A scoped registered renderer/relational field now handles Enter on our hub/agenda action buttons (and on the card's direct-action entry), leaving unrelated kanbans and native arrow navigation untouched. The focused outline button also inherited an unreadable purple background; scoped focus/active colors now use the shared water/white pair. This was browser-reproduced behavior, not inferred from a screenshot or a source-only risk. Final validation must include these keyboard cases.


## Final verified evidence

[66 PNGs, coverage JSON and self-contained annotated before/after HTML](https://github.com/naor291291/odoo-pilot/actions/runs/41217828468/artifacts/13048069104): 25 core workflow captures plus 41 CRM captures, zero uncaught JavaScript errors. Actual Chrome on Linux, synthetic disposable data; no live customer or Morning account used.

- 390/768/1024/1440px hub and core-form layouts; 390/768/1440px today agenda; per-screen desktop/phone entries in `crm/coverage.json`.
- **Hub keyboard behavior reproduced and fixed:** Enter on the actual per-job button opens its governed execution work card. Odoo prioritizes the closest registered hotkey area; the new renderer scopes its registration to the focused control/card, instead of sharing the native renderer area. The same Enter path passes from the phone agenda. Existing queue Enter navigation still passes.
- Native full-details disclosure opens/closes with Enter and preserves phone/contact context. Optional notes remain accessible. Three-step reporting retains text/files across Back/Continue; partial save/reopen, invalid file/limits/remove/replace, zoom/Escape, submission, incomplete visits, correction/resubmission and approval pass.
- Required work/quote fields, valid amount saves, negative profitability, partial receipts, paid closure, payout, cancellation, role restrictions and foreign-contractor access pass. Rate edits recompute the live 1,000 ILS example (66% → 660.00) without changing frozen prior assignment pricing.
- Owner and operations hub views, client/task/calendar/guide entries and native read-only surfaces pass. Native Odoo settings/CRM/Project reference entries are smoke coverage, not an exhaustive core redesign.
- Visually inspected final hub, quote phone, phone agenda, compact rate form/example, incomplete and error portal states, direct-work actions, desktop portal/focus and calendar imagery. Full job names and addresses wrap; idle ghost cards no longer leave empty lines. Annotate.py from UX Audit was run on two before captures and the annotation positions viewed; the standalone HTML uses equivalent labelled overlay boxes with approximate regions.

Additional source-only findings remain distinct from screenshot findings:

| ID / severity | Screen and source evidence | Impact and response |
|---|---|---|
| S01 · 2 minor | Portal photo picker, `static/src/js/field_portal.js`: original input becomes hidden but its error is not associated with the visible picker | Keyboard/assistive navigation loses the association. Fixed visible `aria-describedby`/`aria-invalid`, including after wizard error cleanup; invalid-file feedback exercised in Chrome. Actual screen-reader speech remains untested. |
| S02 · 2 minor | Portal step URL: old code writes `#report-step-N` but always initializes step 1 | Refresh suggests a restore guarantee that does not exist for unsaved uploads. Removed misleading step hash; Back/Continue still retains DOM data and saved drafts reopen from the server. No unsaved-refresh persistence is promised. |
| S03 · 2 minor, source risk only | Final submit is disabled while mandatory data/photos are absent | Could obscure recovery if reached without context. No stuck final-review state was reproduced. Existing Continue exposes linked field/photo errors and the guarded submit behavior is retained; this is not claimed as a newly fixed defect. |

During this pass two early Chrome failures came from a locator assuming form-field `name` attributes on native kanban-rendered dates; the actual date was visible. Corrected to the existing agenda-time semantic element. Later Enter failures were genuine behavior and were repaired in the scoped renderer. The final successful run includes the corrected assertions and actual keyboard paths. Local integration passed; a local restart smoke hit the host PID-namespace limitation, so the normal Docker CI startup/restart pass is the authoritative lifecycle evidence.

No physical camera, Safari/WebKit, screen reader, interrupted cellular upload, production concurrency or live Morning connection has been verified. These remain explicit limits. No merge or deployment was performed.
