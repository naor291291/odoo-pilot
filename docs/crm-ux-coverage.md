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
| P2 | Clients / Contacts | No short project-specific entry; native generic contact surface has unrelated fields | Scoped directory, short form, client-to-work action, discoverable pre-job clients |
| P2 | Tasks / Project | Native task has many project controls; unclear path back to governed work flow | Readonly task evidence view + schedule; explicit work-card action |
| P2 | Shared CSS / portal | Focus target/footer overlap, non-semantic dates, image dimensions, unclear unsaved photos | Shared focus/scroll rules, static report action area, native dates, sized lazy thumbnails |
| P2 | Settings/integration | Manual/expected/API capabilities can be mistaken for active automation | Plain-language guide explicitly distinguishes manual work, unverified API and simulation |
| P2 | Test script | Operations screenshot captured while Odoo was still updating | Attempt network idle, then wait for rendered content, unblocked UI, fonts and layout frames when Odoo’s persistent bus prevents idle |

## Coverage matrix

Status legend: source-reviewed is distinct from browser-verified. The CI evidence section below is the authority for completed checks; planned checks are not reported as passed.

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
| Appointment calendar | Native calendar interaction | Dedicated date-start/action | Open calendar and event, phone/desktop |
| Native Project/CRM surfaces | Upstream XML and installed actions | No core changes | Read-only smoke entry and screenshot where available |
| Native Odoo settings/users | Upstream XML and installed actions | No core changes or permission edits | Owner-only read-only smoke entry where available; not an exhaustive admin workflow audit |
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

Pending final CI and visual review. Before images: supplied screenshots and PR #11 CI artifacts (rates/portal/work cards). New hub/client/task screens have no equivalent custom before screen. After screenshots and a machine-readable screen checklist are generated in `.local-data/ui-checks/` by `scripts/check_field_ui.py` and `scripts/check_crm_ui.py`. Replace this paragraph with exact final run/results after verification.
