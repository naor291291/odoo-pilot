# CRM-wide UI/UX review and coverage

Scope: the custom field-work CRM and the native Contacts/Project/CRM/settings surfaces it uses, Odoo Community 18. Baseline: PR #11, commit `7ee73940b2c31b23091adf3fece143e45a83579b`. Separate branch `feature/crm-wide-ux`; no merge or production deployment.

## Sources and limits

Read the original three-page `מסמך8.pdf` (22 October 2026), all module models/controllers/views/security/assets, README and previous UI audit, native Odoo view/compiler/control-panel sources, and the four requested skill instructions. No repository AGENTS.md or pre-existing system.md was found. The source specification includes capabilities beyond the current pilot. Its older payment/automatic-document descriptions are not silently substituted for the currently tested approval/receipt/closure rules.

Skill sources: [Interface Design](https://github.com/Dammyjay93/interface-design/blob/main/.claude/skills/interface-design/SKILL.md), [Vercel guidelines skill](https://github.com/vercel-labs/agent-skills/blob/main/skills/web-design-guidelines/SKILL.md), [fresh review rules](https://github.com/vercel-labs/web-interface-guidelines/blob/main/command.md), [Anthropic testing](https://github.com/anthropics/skills/blob/main/skills/webapp-testing/SKILL.md), [Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/main/.claude/skills/ui-ux-pro-max/SKILL.md). Loaded as source resources, not globally installed. Pro Max's static quick-reference supplements forms/accessibility; the existing palette/font remain authoritative. The Anthropic server helper was loaded and its `--help` run; the existing Odoo/PostgreSQL lifecycle is retained because CI already manages these services. Chrome verification runs in GitHub Actions; local execution supports actual Odoo integration tests, not a local Chrome installation.

## Audit before implementation

| Priority | Location | Finding and impact | Implementation |
| --- | --- | --- | --- |
| P1 | Navigation / root menu | Opens a work queue without explaining the operating picture; clients/tasks are reached indirectly | Native operational hub, explicit clients/tasks/guide entries |
| P1 | `views/field_workspace_views.xml` | Contractor tiers are long table labels and a flat form; boundaries/whole-amount pricing hard to scan | Three tier cards, percent suffix, frozen-rate explanation |
| P1 | `views/field_portal_templates.xml` | One long report/photo form; missing requirements mostly disable submission | Three report steps, retained values/files, linked error summary + inline repair guidance, draft save |
| P1 | `static/src/js/field_portal.js` | Newly chosen files may be lost by navigation without warning | Dirty-form navigation warning; current step never submits automatically |
| P1 | Work planning | Missing data listed away from its field; progress hidden in expanded status list | Inline missing-data guidance and compact stage indicator, same server validation |
| P1 | Calendar event popover | Native Edit/Delete labels suggested changing a governed assignment from the schedule | Scoped calendar renderer/popover: open readonly task, no deletion, native dialogs and accessible close button |
| P1 | Calendar at the phone breakpoint | The open desktop sidebar survives a resize and hides the native mobile calendar | Scoped controller collapses the sidebar on entry to phone layout; mobile filters remain available |
| P2 | Calendar appointment details | Only a start is stored, while the native popup invents an end and a one-hour duration | Show the actual localized start/date, with an explicit Hebrew label and LTR isolation |
| P2 | Clients / Contacts | No short project-specific entry; native generic contact surface has unrelated fields | Scoped directory, short form, client-to-work action, discoverable pre-job clients |
| P2 | Tasks / Project | Native task has many project controls; unclear path back to governed work flow | Readonly task evidence view + schedule; explicit work-card action |
| P2 | Shared icon buttons / mobile dialogs | A shared text font replaced native icon fonts, and the event header truncated the work identity | Preserve native FA/OI fonts; wrap the scoped mobile event header |
| P2 | Shared CSS / portal | Focus target/footer overlap, non-semantic dates, image dimensions, unclear unsaved photos | Shared focus/scroll rules, static report action area, native dates, sized lazy thumbnails |
| P2 | Settings/integration | Manual/expected/API capabilities can be mistaken for active automation | Plain-language guide explicitly distinguishes manual work, unverified API and simulation |
| P2 | Test script | Operations screenshot captured while Odoo was still updating | Attempt network idle, then wait for rendered content, unblocked UI, fonts and layout frames when Odoo’s persistent bus prevents idle |

## Coverage matrix

Status legend: source-reviewed is distinct from browser-verified. The completed CI evidence section below and its machine-readable checklist identify the actual checks; shared CSS is not treated as per-screen verification.

| Screen / state | Source review | Change | Browser scenarios |
| --- | --- | --- | --- |
| Operational hub (new) | Model/menu/security mapped | Counts, queue links, owner-only balances, new inquiry | Owner/operations, four widths, keyboard queue activation, scope/count assertions |
| Field inquiries Kanban | Existing view/action + native renderer | Shared readability retained | Board, long names, native list switch |
| Inquiries list/search | Native filters/stage domains | Shared readability retained | Name search and selected job |
| Work planning/quote/assignment | All stage rules and inherited view tree | Compact progress, field-level guidance | Missing required fields, Continue/Back, quote, dispatch, values retained |
| Work execution/approval/correction | Models + all evidence widgets | Existing unified work area retained | Submit, correction, resubmit, approve, incomplete visit |
| Customer collection | Payment models/ledgers/dialogs | Existing UI retained | Partial receipts, mobile dialog, cancellation and reopening |
| Contractor payout | Owner fields/security | Existing UI retained | Owner payout and operations exclusion |
| Contractor rates list/form | Model constraints, native edit | Three-tier form | List captions, form percentages, mobile/desktop, range validation |
| Client list/search/kanban (new scoped views) | Partner ACLs/native Contacts | Directory/actions | Search/switch/open, new client remains listed |
| Client form (new scoped view) | Partner/native labels/widgets | Short contact/address groups | Required name, edit/save, phone/email, return to related jobs |
| Tasks list/detail (new scoped views) | Task/Project/review security | Readonly evidence + work-card link | Dispatched job, details, return to current work stage |
| Appointment calendar | Native calendar interaction and popover | Dedicated date-start/action, scoped open-task popover, no deletion | Open calendar and event, phone/desktop |
| Native Project/CRM surfaces | Upstream XML and installed actions | No core changes | Read-only smoke entry and screenshot |
| Native Odoo settings/users | Upstream XML and installed actions | No core changes or permission edits | Owner-only read-only smoke entry; not an exhaustive admin workflow audit |
| Guide (new) | Current pilot vs specification compared | Workflow/role/integration help | Desktop/phone, actual visible manual/unverified status |
| Portal home/list/scopes/empty | Routes/domains/pager | Skip/navigation/readability | Assigned work, scopes, empty, contractor separation |
| Portal report step 1 | Report fields and submission constraints | Required-field hints/errors | Empty summary, incomplete reason, keyboard focus, Back retention |
| Portal photos step 2 | Multipart/atomic/file limits | Step layout and upload feedback retained | Multiple images, limits, remove/replace, zoom/Escape, no viewport overflow |
| Portal review step 3 / receipt | Existing save/submit endpoint | Explicit review and status | Save draft, reopen, send, pending/approved lock, correction loop |
| Payment/correction dialogs | Existing server validation/audit | Native focus/controls retained | Mandatory reason, mobile bounds, confirm/cancel |

## Preserved behavior

No pricing formulas, tier boundaries, frozen assignment rates, approval/paid transitions or ledger audit rules change. Dashboard sums existing operational balances in ILS under the requesting user's normal record rules; it does not derive revenue, profit or conversion metrics. Contractors gain no native CRM/Project access. Finance fields remain protected in the ORM and view groups. New navigation performs normal reads and uses native object actions.

## Specification gaps / blockers

- Morning read-only integration remains separate in PR #9; live account/API verification depends on credentials/Best access. No live API call or document delivery is claimed here.
- Invoice/PDF workflow, automatic WhatsApp/email delivery, monthly contractor statement/Pivot and owner revenue/profit/conversion dashboard with 50% target are not complete in the current pilot. The new operational hub does not pretend to implement them.
- General Odoo administration, every third-party/native module and production deployment are outside an exhaustive UI redesign of this custom CRM. Native surfaces are separately identified rather than counted from shared CSS.
- Browser automation is Chrome on Linux with simulated viewport/touch context. Physical iPhone/Android camera, actual mobile screen reader, interrupted cellular upload and production concurrency require device/environment verification.

## Evidence

Implementation verified at commit `196032d4d67d8ccad1e1ea0c6610b61d9e9e23ec` in [CI run 41210874114](https://github.com/naor291291/odoo-pilot/actions/runs/41210874114). All integration, restart/smoke, both Chrome suites, evidence generation and screenshot upload steps passed.

| Verification | Completed result |
| --- | --- |
| Actual Odoo/PostgreSQL integration suite | 148 tests, 0 failures, 0 errors; also passed locally |
| Startup and restart smoke | Hebrew, existing data/admin ownership, generated contractor and reviewer/owner roles |
| Main Chrome workflow | Missing required fields, Continue/Back, saved amounts, negative profitability, photos/limits/remove/replace/zoom/focus, drafts, correction/resubmission, incomplete visit, approval, partial receipts, paid closure, payout, cancellation and queues |
| Additional CRM Chrome suite | 36 successful captures, 0 uncaught page errors; dashboard, board/search, client directory/form/cards/required-name/new-client persistence, task detail/work-card/customer dialog, calendar event/readonly dialog/phone resize, rate validation and saved edit with frozen prior assignment, guide, operations and contractor separation |
| Responsive widths | 390/768/1024/1440px for the hub and core pricing checks; selected additional screens at desktop/390px, as recorded individually in `coverage.json` |
| Roles | Owner, operations, and two separate contractors; foreign contractor job returns 404, operations has no owner finance fields |
| Native unchanged surfaces | Client/task reference forms plus Project, CRM, general settings and users: read-only entry/screenshot smoke; no admin-setting mutation or exhaustive native workflow claim |
| Visual evidence | 25 main-flow + 36 additional CRM PNGs, `crm/coverage.json`, self-contained `crm-ui-before-after.html`; baseline PR #11 screenshots loaded successfully |

[Download the evidence archive](https://github.com/naor291291/odoo-pilot/actions/runs/41210874114/artifacts/13046347621). All screenshots use disposable synthetic data. Before images are PR #11 (`7ee7394`) rates/portal/work cards; native client/task references are explicitly identified as unchanged original screens captured in the same run. New hub/client/task views are not presented as if an equivalent custom before screen existed.

Selected screenshots were visually inspected for work/financial forms, owner and operations hubs, client/task phone layouts, rate cards and native validation, calendar phone/popup/dialog, guide, contractor report/review and empty states. The review caught and corrected the missing mobile primary action, oversized portal buttons, hidden native customer arrow, empty mobile calendar/sidebar, icon-font replacement, clipped mobile event title and invented appointment duration. Exact per-capture widths and files remain in the machine-readable checklist; shared CSS is not counted as independent coverage of unvisited screens.


## Subsequent clarity refinement

The 31 October 2026 follow-up starts from merged upstream `main` (`02d74f2`). See [the separate clarity audit](crm-clarity-audit.md) for current findings, affected screens, skill provenance and new verification results. Historical results above belong to PR #12; they are not evidence that this follow-up passed.

Follow-up evidence: [CI 41217828468](https://github.com/naor291291/odoo-pilot/actions/runs/41217828468) passed all 152 tests, startup/restart and both Chrome suites, including the scoped Enter fix. The follow-up generated 66 screenshots (25 core + 41 CRM) and an annotated before/after HTML. Full results, exact tested implementation commit, evidence provenance and remaining device/API limits are in `crm-clarity-audit.md`.
