# Contractor statement — Odoo Community 18

Base: upstream `main` `c3960c7613eb74675114ccf86b48209959e409ae` (PR #13 merged). Every tracked base blob was checked against GitHub's tree; the existing local checkout and other worktrees were preserved. Branch: `feature/contractor-monthly-statement`. No Morning dependency, merge or deployment.

## Confirmed business decisions

The owner explicitly chose both rules during implementation:

1. Eligibility requires execution approval, full customer collection and explicit closure to **טופל ושולם**. Execution approval alone is insufficient.
2. The entitlement is the **gross amount explicitly approved by the owner**, not an automatic VAT uplift of a pricing estimate.

The second condition can be satisfied before closure. If approval is later, the entitlement date is the date both conditions first hold: the later approval date. This avoids retroactively creating financial movements. Gross zero can be explicitly approved; an unapproved zero or positive input is **missing approval**, never silently assumed to be an approved liability. Existing amounts are not auto-approved on upgrade. Operational closure, collection, advance registration and payout caps retain their existing rules.

## Arithmetic and dates

`closing = opening + new credits - payouts + signed adjustments`

- Opening includes all entitlement events before the first date, less contractor payments dated before that date, plus cancellations effective before that date.
- Entitlement credits are immutable signed movements with gross amount, contractor/company, owner approval identity/time, closure time, historical net estimate, sale amount and applied percentage. The pricing module still freezes assignment rates; the report never recalculates old credits from a current contractor profile.
- Changing the agreed gross amount invalidates approval and reverses an existing live credit. Reapproval creates a new credit. The existing rule preventing a gross total below posted payouts is retained; this feature does not introduce cash refunds. Reopening a closed job reverses its credit; later valid closure credits it again. Reversals retain the original snapshot and link to it. A credit can be reversed once. Historical contractor/company identities cannot be reassigned after a credit, even after reversal.
- Contractor payment entries are already immutable. Include the original payment even when its current state is cancelled; add the reversal at `cancelled_at`. A September payment cancelled in October still reduces September's balance and increases October's balance through an adjustment. Cancellation is an accounting registration correction, not a cash refund.
- A payment may relate to a job from any month. Advances are supported by the existing per-job gross cap, even before eligibility. A negative balance is shown explicitly; it is not clamped to zero.
- Customer receipts never reduce contractor balances. Their only link is the existing full-collection condition for job closure.
- Dates are inclusive. Stored UTC timestamps for eligibility/cancellation are converted using **Asia/Jerusalem**, including DST. Payment dates remain the user-entered calendar dates. A cancellation cannot become effective before that payment's date if users entered it from another timezone.
- Within a date, entitlement entries precede payments, with numeric source IDs and an original payment before its same-day cancellation. This is a stable ledger order, not a reconstruction of payment times (payments store dates only).
- Every amount is rounded with Odoo's ILS currency precision. Signed movements and running balances are rounded to agorot. Net estimates and approved gross amounts are labelled separately. No tax rate or contractor tax status is invented.

## Historical limits and reproducibility

`field_work_photos.statement_history_start` is initialized once on installation/upgrade, without inferring old entitlements. Existing closed jobs need owner approval; approval today creates a movement today. Earlier reopening, former gross amounts and former approval decisions cannot be recovered reliably from current rows. The report labels this limitation, including the history-start timestamp, and warns about closed jobs awaiting approval.

This is an **effective-date ledger based on information known at generation**, not a reconstruction of exactly what was known at a historical month end. A payment newly entered with an old payment date changes a newly generated historical statement. Later cancellations do not erase original payments. Cancelled legacy payments without a cancellation timestamp are explicitly counted as incomplete and excluded rather than assigned an invented date.

Each transient report stores a server-generated snapshot. Its automatic-vacuum age threshold is 24 hours, not a guaranteed expiration time; the pilot disables cron, so cleanup may occur later. Screen and PDF render the same shared QWeb body from that snapshot; printing does not recalculate. Editing any filter clears the old result. Users must explicitly regenerate to include newer movements. It is not a permanent archive or accounting/fiscal document. Generation writes only temporary report results, never jobs, entitlement events, payments or Morning documents.

The current follow-up section is explicitly **current information**, not historical job state. It includes unfinished jobs and jobs awaiting amount approval for this contractor/company; up to 100 previews are shown with the full count and source links. All ledger movements and totals remain uncapped. Archived jobs remain included.

## Interface and access

Navigation: **עבודות שטח → גבייה ותשלומים → התחשבנות קבלנים**. The old per-job payout list remains **תשלומי קבלנים לפי עבודה**. Select company, contractor and month or inclusive date range, then **הצגת דוח**. **הפקת PDF** prints the snapshot using Odoo's native `ir.actions.report`/QWeb/wkhtmltopdf pipeline, A4 with a locally hosted static Heebo instance, repeated table headings and page numbers. Printing uses `report_action(config=False)` because this internal layout must not open the company-branding configuration wizard. Qt can apply narrow screen media rules to A4; the PDF class explicitly restores table/header/cell layout, with 14px data and 12px supporting text.

Summary: opening, credits, payments, adjustments and closing. Dated rows include references, original work links, immutable movement/payment links and running balance. Opening drill-down links expose original entitlement and payment records, including cancellation metadata. Phone layouts stack table cells with their persistent labels; numbers remain LTR inside Hebrew RTL.

Only `group_field_finance` can create/read statements, read entitlement events, approve amounts or print PDF. Record rules restrict active allowed companies; an explicit creator rule isolates report snapshots between users. The installed Odoo 18 source treats transient access like ordinary ACL/record rules, so implicit creator isolation is not assumed. Report calculation and the report provider also check access, including direct RPC/HTML/PDF calls. No report query uses `sudo`. Narrow private event creation uses elevated access so operations can close/reopen a job without gaining access to private amounts or ledger output. The only reporting elevation reads the static history-start configuration value.

## Example to verify

An August credit of ₪700, August payout of ₪100 and September payout of ₪250 produce September opening **₪600**, new credits **₪0**, payouts **₪250**, adjustments **₪0**, closing **₪350**. Cancel the September payout in October: September remains ₪350; October opening is ₪350, adjustment +₪250, closing ₪600.

The browser fixture is deliberately independent of historical event import: prior-month advance ₪100, current-month credit ₪700 and current-month payout ₪250 give opening **−₪100**, credits **₪700**, payouts **₪250**, closing **₪350**. The customer receipt of ₪1,180 is excluded from the contractor movement list.

## Verification and skill use

- Read the current original specification PDF, pricing/collection/dispatch/review models, views, access rules and `.interface-design/system.md`.
- Read upstream **unclecatvn Odoo 18** SKILL, API highlights and relevant model, development, report, security, performance and testing guides. Checked Odoo 18 source for report rendering, layouts and access APIs; native `<list>`, direct modifier expressions, `check_access`, batch ORM and private mutation methods are used.
- Read upstream **Interface Design** and applied existing water/ink/steel tokens, Heebo, 4px rhythm and native Odoo controls. No new design language.
- Read current **Impeccable 4.8.0**, clarify/distill/adapt and craft floor. Its context launcher is not installed (exit 127); PRODUCT.md/DESIGN.md do not exist. Existing project context was read directly. No claim that its binary or detector ran.
- Read **Anthropic Webapp Testing** and ran the available `with_server.py --help`. The project already owns its Odoo/PostgreSQL lifecycle, so the helper was not used to launch a second server. Added native Python Playwright reconnaissance/waits, keyboard, required-field, source-link, empty/error, viewport and console checks.
- Local final Odoo/PostgreSQL suite: **169 executed, 0 failures/errors, no skips**. PDF action authorization is tested in the transaction suite; actual wkhtmltopdf is mandatory in the separate HTTP/browser suite with a running asset server. An initial local run had skipped the real-PDF case; attempting it inside an isolated transaction is not a substitute for HTTP-backed PDF verification. All 152 existing tests still pass. New cases cover same/prior month, opening/partial/advance, later/same-period cancellation, reopening/reclosure, amount correction/reapproval, frozen rates, missing vs zero, late approval, month/DST/cents, roles/companies/contractors, immutable output, HTML parity and read-only behavior.
- Representative synthetic ledger: 1,001 dated movements across 1,001 source jobs, verified totals, under 100 SQL queries and under 10 seconds enforced by integration test. Profiling identified repeated ILS lookups in the existing pricing computes; these are now batched without changing the formulas. This measures calculation, not production load or concurrent users.
- Final exact-code verification: commit `4395e00a7b35e6e6d4c4b7b6ffeb90b4041f6b66`, [CI run 41226165102](https://github.com/naor291291/odoo-pilot/actions/runs/41226165102), all steps passed. All 169 integration cases executed with no failures/errors/skips. Startup and restart smoke passed; three real headless Chrome suites passed with zero uncaught page errors.
- [Evidence archive](https://github.com/naor291291/odoo-pilot/actions/runs/41226165102/artifacts/13052275621): **81 PNGs** (25 existing core workflow, 41 CRM, 15 new statement captures), coverage JSON, existing annotated CRM HTML and **two actual Odoo QWeb/wkhtmltopdf PDFs**. The example is one A4 page; the long fixture is four pages, including a 145-character unbroken reference. Balance is ₪350 in the example, ₪326 after 24 additional ₪1 payments.
- PDF checks: downloaded through the real **הפקת PDF** UI button; compared snapshot amounts/text with `pypdf`; rendered all five output pages with Poppler `pdftoppm`; visually inspected Hebrew, dates, currencies, long references, repeated headers, row/page boundaries and footers. `pdffonts` confirms embedded Unicode **Heebo-Regular**. No overlaps or clipped content were observed. The first visual pass exposed Qt applying the phone layout in PDF; the final explicit table styles reduce the same long fixture from ten pages to four.
- New Chrome coverage: owner amount approval and confirmation; required contractor; month/range selection; summary/movements at 1440/1024/768/390px; keyboard Enter opening a native new-tab entitlement source; work-card source; opening payment list; entitlement form at 1440/390px with Hebrew labels; empty and invalid-range states; real PDF download; multi-page output; denied contractor RPC/PDF. These are emulated viewports on Linux Chrome, not physical phones.
- Commands: `python3 scripts/pilot.py test`, `python3 scripts/pilot.py smoke`, `scripts/check_contractor_statement_ui.py`, `scripts/check_field_ui.py`, `scripts/check_crm_ui.py`, native QWeb/wkhtmltopdf, `pypdf`, `pdftoppm`, `pdffonts`, Python compilation and `git diff --check`. The local targeted statement suite also passed after numeric-order and print-action changes. The last commit after this verification only updates documentation; executable source remains byte-identical to the tested commit.


Remaining limits: no recovery of pre-feature entitlement history, no permanent report archive, no standalone/unassigned contractor advance (existing payments require a job), no automatic VAT calculation, no sending to contractors, no contractor access expansion, no live Morning, no physical-device/screen-reader/production-concurrency verification.
