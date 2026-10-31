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
