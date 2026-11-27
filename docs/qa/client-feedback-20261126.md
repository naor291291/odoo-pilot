# Client feedback 26 November 2026 — acceptance map

Target module: `18.0.18.0.0`. Base: `693156a`. PR: #23.
No deployment, live document delivery, production data edits or cloud resources are included.

| Requirement | Implementation | Automated evidence |
| --- | --- | --- |
| Setup followed by one editable workcard; retain internal lifecycle | `view_field_setup`, `view_field_workcard`, workspace actions | `test_two_screens_and_shared_stage`, `check_workcard_ui.py` |
| Customer first on Kanban | `view_field_kanban_customer_first` | XML inheritance and browser board audit |
| 700 − 273 = 427; 65% = 277.55 | Net pricing formula and frozen contractor rates | `test_acceptance_700_273_65`, `test_rate_snapshot_and_cost_updates`, browser calculation |
| Deduct expenses once; reimburse approved contractor expenses | Separate materials/other-business expense inputs and reimbursement approval | `test_expenses_deducted_once_and_reimbursement_approved`, zero-rate case |
| Negative base remains visible and blocks payout | Dialog, approval and direct payment-create checks; no automatic zeroing or override | `test_negative_base_is_visible_and_payout_blocked`, direct-payment and legacy-formula bypass cases |
| Early billing, partial payments, no double debt | Append-only document register updates one work debt, never sums invoices and proformas | `test_proforma_and_invoice_one_debt_partial_payment`, browser documents and payment dialog |
| Full payment plus receipt required for closure | Backend stage/action guard and safe automated closure gate | `test_full_payment_requires_receipt_then_closes`, `test_receipt_does_not_fake_payment`, updated delivery regressions |
| Preserve all documents and PDFs | Immutable records, PDF validation, original-file attachment allowed once | Document history/duplicate/invalid-PDF/legacy archive tests; authenticated browser PDF download |
| Paid and pending collection shortcuts | Complementary action domains; dashboard queue count includes early bills | `test_paid_and_outstanding_actions_are_disjoint`, browser paid filter |
| Finance + Dispatcher may create contacts/enrol contractors without Settings | Verified partner action grants only contractor portal group; duplicate/internal/cross-company identities rejected | Enrolment/idempotency/access-denial tests and existing pilot-access regressions |
| Contractor isolation | Existing task/photo rules retained; document register has company rule and no portal ACL | Existing portal regression suite plus contractor document-denial tests |
| Hebrew, RTL, ILS and mobile | Existing Hebrew/ILS assets; native responsive workcard; explicit labels | Browser 375/390/768/1440 checks; axe audit includes setup and central card |
| Safe upgrade | Pre/post migration retains historical formula for completed/paid, amount-approved or ledger-backed works; archives old files without changing debt or inventing receipts | `test_upgrade_preserves_historical_formula_and_documents` |

## Business decisions and limits

- Negative commission: show the negative value and block payment until a business decision. No manual bypass was added.
- Pricing retains the existing **before-VAT** convention. Billing and payment amounts are entered explicitly **including VAT**; no VAT rate is inferred and no currency conversion is performed.
- Other business expenses explicitly exclude separately entered materials. Existing expense allocations must be checked before a production upgrade; numeric equality alone cannot identify duplicated real expenses.
- Historical approved/closed calculations and immutable entitlement entries retain their previous formula. New work uses net commission; open work without an approved amount or entitlement is converted by migration.
- Portal enrolment does not send email, set a public password or grant system administration. Password setup remains through an authenticated administrator in a secure channel.
- Roy and Yaron: live identities and activation were **not verified**. The available browser is at the sign-in screen; no live user was changed.
- Physical phones, assistive technology and live integrations are outside the synthetic CI verification.

## Verification

Python/XML syntax and whitespace checks passed locally. Real Odoo, browser, security and backup checks run in the PR's existing GitHub Actions workflows; a draft PR is not a claim that those checks passed. Final results and links are recorded in the PR description after completion.

The acceptance browser journey replaces the obsolete seven-stage journey in CI; contractor portal, reports, CRM/native screens and accessibility suites remain enabled. The old `check_field_ui.py` remains a historical baseline utility and is not acceptance for the new workcard.
