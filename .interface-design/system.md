# Field-work CRM interface system

Applies to Odoo Community 18, module `field_work_photos`. Extend native views and controls; do not patch Odoo core or replace its save/access/workflow mechanisms.

## People and direction

Operations managers work between customer calls, scheduling and report review. Contractors use a phone on site. Prioritize the next task, readable evidence and an explicit saved/submitted/approved state. The product should feel like a well-organized field-work card on a service desk.

Domain: inquiry, site address, contractor, appointment, before/after evidence, execution approval, receipt and outstanding balance. Color world: water teal, blue ink, steel labels, white ceramic, amber inspection, green approval and red repair/loss.

Signature: the same work identity and next action recur in the dashboard queues, work header, stage indicator, task-to-work link, contractor report steps and payment summaries. Replace generic KPI decoration with actionable queues; replace an endless form with business tabs/steps; replace sparse sidebars with contextual help beside the task.

## Shared tokens and measurements

Source tokens: `static/src/scss/field_interface.scss`. Shared layout: `field_crm.scss`.

| Role | Token/value |
| --- | --- |
| Paper / desk | `--work-paper: #fff`; `--work-desk: #f3f6f7` |
| Main / secondary / caption | `--work-ink: #183044`; `--work-steel: #465d70`; `--work-caption: #5a6d7c` |
| Action / hover / tint | `--work-water: #086b74`; `#07545c`; `#edf6f6` |
| Input / border | `--work-input: #f6f8fa`; `--work-line: #dce4e9` |
| Inspection / approved / repair | `#7b5100`; `#216545`; `#9b2634` |
| Typography | Local OFL Heebo; body 16/400, label 14/500, section 20/600, title 28/600 (24 mobile), key amount 28/600 |
| Rhythm | 4px unit; 8px label gap, 16px component padding/gap, 24px section gap/padding |
| Buttons/fields | Minimum 44px height; 8px radius; primary water fill, secondary outlined/text |
| Surfaces | Thin borders, 12px panel radius, no decorative shadows; dialogs keep native layering |
| Focus | 3px water outline, 3px offset; use `:focus-visible`, preserve native focus management |

Keep readonly labels at full contrast. Readonly and disabled are different states. Numbers use tabular figures and LTR isolation while their blocks align beneath the Hebrew label. Badge text must carry status without color.

## Component intent checkpoints

All components use the palette/type/spacing above. Their depth is one bordered paper layer on the desk; popovers/dialogs inherit native Odoo layers.

| Component | Person, action and focal point | Structure |
| --- | --- | --- |
| Work hub | Operations chooses the next queue; review is first in reading order | Six counted queue buttons; one new-inquiry primary action; owner-only actual outstanding balances with scope note |
| Work card | Manager advances this job; title/state/next action lead | Business tabs; compact 7-stage progress; inline missing-data guidance; optional arrival/internal details collapsed |
| Client directory | Manager finds a customer/contact and their jobs | Native searchable list/kanban + short form; billing/contact address distinguished from job site |
| Task schedule | Manager locates a dispatched job or appointment | Native list/calendar + readonly evidence form; scoped event popover opens the task and offers no deletion; primary task action returns to the governed work card |
| Rates | Owner edits one contractor's three percentages | One tier per card, explicit boundaries and percent suffix; explain whole-amount tiers and frozen assignments |
| Contractor report | Phone user reports, attaches evidence, checks and submits | Three steps with Back/Continue, retained DOM values/files, partial draft save, focused linked error summary and inline errors |
| Money / dialogs | Operations records actual receipts; owner records payouts | Distinguish net forecast from gross payment; no formula changes; retain confirmation/audit/cancellation controls |
| Guide | User understands current workflow/integration limits | Plain Hebrew steps, role explanation, manual vs unverified API status; no active-integration claims from a simulation |

## RTL and interaction rules

- Keep native toolbar direction under Odoo control. Explicit RTL on custom content must use `/*rtl:ignore*/` so RTL asset compilation does not mirror it twice.
- Use logical inline/block spacing. Isolate phones, IDs, percentages and amounts with `bdi`/LTR containers. Prefer locale-aware native date/number widgets.
- Reuse native Odoo notebooks, lists, calendars, fields, dialogs and object actions. Use real buttons/links/labels; no clickable div replacements.
- Business stages stay server validated. Back/Continue saves through native mechanisms; a missing-field hint never substitutes for a server check.
- On phone, one primary action per current step; optional actions are secondary. Respect safe-area padding and visible focused fields; avoid covering fields with sticky footers.
- Empty states explain the next action. Loading/submission sets busy text; success distinguishes draft save, report submission and execution approval. Errors explain repair and retain existing server data.
- New client records remain discoverable before their first job. Search/filter/pagination and native access rules remain in force.
- No animation is required for repeated actions; honor reduced-motion. Do not add decoration-only motion or external font requests.

## Verification contract

For each affected screen record source review, modification, browser verification, viewport and role separately in `docs/crm-ux-coverage.md`. Shared CSS is not proof of per-screen coverage. Use disposable fixtures, wait for dynamic Odoo data/network to settle, inspect DOM before acting, test keyboard/error/empty states, retain screenshots and console errors. Review at 390/768/1024/1440px where applicable.

Skills loaded from upstream source for this work: Interface Design (primary), Vercel Web Design Guidelines (implementation review), Anthropic Webapp Testing (Playwright discipline), UI/UX Pro Max quick-reference (supplemental accessibility/form guidance). They are not installed as global personal skills; no Pro Max search database or Odoo-specific stack recommendation is claimed.


## Clarity refinement — 31 October 2026

Base: upstream `main` at `02d74f2`; this pass preserves the palette, Heebo, native controls and all business transitions.

- **Hub:** action records precede counters. Show pending reports first, then dispatched work scheduled before the end of the viewer's local day (including overdue work). State the inclusion rule and total; at most six previews, with an explicit full-list action. Never invent urgency for undated inquiries. Empty queues remain reachable but lose their filled surface and explanatory paragraph. Keep finance summaries owner-only.
- **Work card:** compact title/current stage and one next-step sentence. Missing-data checklist is a 44px native disclosure; field-level repair hints remain visible. Move the full stage map below the working tabs. Quote and scheduling inputs lead in their respective stages, while customer details remain editable below. Header 22px phone/24px desktop, 12px separation; do not add a second hero box.
- **Portal:** show job/customer/date/address and a 140-character description preview; provide clearly labelled full description/access details and a reporting anchor. Keep Call/Navigate visible. Reporting steps keep DOM inputs and File objects through Back/Continue. Optional notes use native details. No fixed action bar covers inputs. State invalid upload on the visible picker button, as well as the original input.
- **Schedule:** local-day agenda is the quick entry; time, customer, address and performer appear together. Each card opens the governed work card directly. Full task evidence, searchable list and calendar remain available. Appointment boundaries use the viewer's time zone and UTC storage; no invented end time.
- **Rates:** use compact border-bottom rows/columns rather than nested panels. Display an illustrative 1,000 ILS middle-tier calculation using the currently edited contractor rate and ILS rounding. Label it before VAT; distinguish it from frozen rates on dispatched jobs.
- **Shared chrome:** while a custom field-work view is active, the native navbar uses the same water action color; other Odoo apps keep their own theme. Native direction and icon fonts stay under Odoo control.
- **Brand:** keep any configured real logo/company identity. On field-portal routes only, replace Odoo's default logo with the company name, or the truthful application name “עבודות שטח” if the name is still “My Company”. Do not rename a real company or infer legal identity from unrelated work. The pilot bootstrap may name only the known default company “עבודות שטח — פיילוט”; existing custom names must remain untouched.

Terminology: “כרטיס העבודה” is the operational source for assignment, approval and collection; “משימה” is the dispatched evidence record; “שמירה והמשך מאוחר יותר” saves a draft; “שליחת דיווח לבדיקה” locks and submits for review, not approval.

Native Kanban integration: the hub's registered relational widget and today's registered renderer preserve Enter activation on nested work-card buttons. Do not apply a global Kanban patch. Outline action hover/focus/active use water fill + white text with the shared visible focus ring.

## Contractor statement — monthly reconciliation

Intent: the owner checks what is owed for a contractor and period, explains the arithmetic and opens original records. Signature: work identity recurs in dated movements with running balance and source links. Domain: eligibility, paid closure, gross approval, advance, cancellation, opening and closing balance. Preserve the water/ink/steel/white/amber world; no decorative KPI panels or charts.

- Native full-page transient form: company/contractor and month/range, **הצגת דוח** primary, **הפקת PDF** secondary after generation. Filter edits invalidate results. Retain the separately named per-job payment list.
- Closing balance leads at 28px/600; other amounts 20px, labels 14px, report heading 24px. Unboxed arithmetic strip, 16/24px gaps, thin separators, shared 4px rhythm and paper surfaces, no shadows. Dedicated report aliases use the existing palette and Qt print fallbacks.
- Dated ledger: work/source links, signed gross movement and running balance. Missing approval is text, never a silent zero. Approved zero is explicit in both card and report. Current estimates are separately labelled and never mixed into dated balances.
- Phone: cells stack with persistent labels at 767px; retain table headings for assistive technology. No horizontal page overflow or sticky overlay; 44px links/controls. Native date/autocomplete keyboard behavior stays intact.
- LTR-isolated numbers inside Hebrew RTL. Screen/PDF share one body and generation snapshot. A static 400-weight OFL Heebo instance is loaded through web.report_assets_common for Qt. A4 uses table layout, repeated headings, page-safe rows and page numbers.
- Show generation time, Israel timezone, arithmetic and legacy/late-entry limitations. Do not present effective-date reporting as a certified historic month-end snapshot. Current follow-up state is not historical evidence.

Sources: unclecatvn Odoo 18, Interface Design, Impeccable clarify/distill/adapt/craft floor and Anthropic Webapp Testing. Impeccable launcher was unavailable; its binary/detector did not run. Verification boundaries: docs/contractor-statement.md.

Print verification: Qt may apply phone screen media rules at A4 width. The report-only class explicitly restores table/header/body/row/cell display and hides mobile pseudo-labels. Keep data 14px and supporting print text 12px; preserve the 22/38/20/20 column split. Actual wkhtmltopdf output was inspected across a one-page example and four-page long-reference fixture. Native report actions use config=False for this internal layout, avoiding an unrelated company-branding wizard.


## Privacy and authorization in UI components

Sensitive financial/correction dialogs belong to their creator and allowed company; create a new dialog instead of opening someone else's transient draft. Disabled/hidden actions never replace server authorization. Portal lists/details and private statement HTML/PDF use no-store responses; a downloaded file cannot be revoked. New photo processing removes metadata and preserves orientation; copy must not promise an archival original. Do not expose protected values in errors, summaries, exports, DOM attributes or UI evidence. Keep test captures synthetic.
