# Pre-deployment requirement traceability

Review date: 2026-11-07. Baseline: `e274e5c9d46f360b72ec7789b16b30780a52088b` (merged PRs 14–19). No AGENTS.md exists in this checkout or its workspace ancestors. One custom addon: `field_work_photos`, version `18.0.17.0.0`, on Odoo Community 18; native dependencies Project, CRM and Portal.

Sources actually read: original three-page `מסמך8.pdf` dated 2026-10-22 (Library `libfile_e513f9d4e00081918b56eb31c70c0660`), README, `.interface-design/system.md`, previous UI coverage/review documents, contractor statement rules, security permissions/findings and deployment guide. The newer user decisions retain execution approval + full collection for closure, separate quote/invoice PDFs, and free hosting as the current deployment preference.

Status vocabulary: **Implemented & Verified**, **Implemented but Failed**, **Partially Implemented**, **Not Implemented**, **Blocked by External Dependency**, **Not Yet Tested**. Verification is bounded to the evidence column: passing ORM/HTTP tests does not establish browser, real-device or deployed-provider correctness. Tests below are in `addons/field_work_photos/tests/` unless specified otherwise.

| ID | Requirement / source | Implementation and screen | Status | Evidence / boundary |
|---|---|---|---|---|
| R01 | Community 18 / spec §1 | manifest; CRM/Project/Portal | Implemented & Verified | Real Odoo 18 initialization and 203 baseline tests |
| R02 | Client creation/update / §2 | `field_navigation.py`; clients | Implemented & Verified | `test_field_workspace.py`, rendered client save journey passed in final CI |
| R03 | Manual inquiry and governed stages / §2 | `field_dispatch.py`; work card | Implemented & Verified | `test_field_dispatch.py`: required values and illegal transitions |
| R04 | Assignment creates one task / §2 | `field_dispatch.py`; scheduling | Implemented & Verified | Dispatch tests, idempotence and reassignment |
| R05 | Preserve values and drafts on reload | work form, portal JS | Partially Implemented | Browser journey coverage: saved/edited draft, reload guard, rejected file recovery passed in run 42401972181; not all two-tab states |
| R06 | Search/filter/sort/client discoverability | clients/queues/native search | Partially Implemented | CRM Chrome suite passed; search/filter/sort exhaustive permutations not completed |
| R07 | Quote number and separate PDF / §3 | `field_documents.py`; planning tab | Implemented & Verified | `test_field_documents.py` model/HTTP attachment checks |
| R08 | Invoice number and separate PDF / §3 | `field_documents.py`; collection tab | Implemented & Verified | Separate content, numbers, validity and size tests |
| R09 | Private PDF viewing/download / §3,6 | document controller and attachment guards | Implemented & Verified | HTTP authorization and real statement PDF authorization passed; customer quote/invoice PDF browser preview not separately captured |
| R10 | Generate customer PDFs in Morning / §3 | External Morning then upload | Blocked by External Dependency | Original scope is external generation + upload; no real financial document issued |
| R11 | Automatic quote transition / §2–3 | document delivery model | Implemented & Verified | `test_field_pilot_metrics.py`: number/PDF, complete fields, queue idempotence |
| R12 | Explicit quote approval / §2 | next-stage action | Implemented & Verified | Dispatch suite |
| R13 | Partial/full payment, balance, cancellation | `field_collection.py`; collection | Implemented & Verified | `test_field_collection.py`, zero/negative/overpayment/duplicate reference |
| R14 | Execution approval + full collection required | collection and task actions | Implemented & Verified | Collection tests, direct writes/defaults blocked; additional prepaid-order regression passes |
| R15 | Double submission/concurrent payment | payment locks and dialog idempotence | Implemented & Verified | Two simultaneous payment attempts and same-dialog duplicate submissions passed runtime security check in 42401972181 |
| R16 | Contractor user and restricted mobile role / §6 | groups, portal controllers | Implemented & Verified | `test_field_portal.py`, `test_security_hardening.py`; native internal field-manager role is not equivalent |
| R17 | Contractor sees only assigned work / §6 | portal, record rules | Implemented & Verified | HTTP IDOR, reassignment, guest and native binary-route denial tests |
| R18 | Required before/after photos / §5 | visit/task models and portal | Implemented & Verified | Completion/submission tests, atomic failure and review lock |
| R19 | Multiple photos and file limits / §5 | `field_visit.py`, normalized images | Implemented & Verified | Up to five per kind, format/bytes/pixels/count and metadata tests |
| R20 | Direct/contractor pricing and tiers / §4 | pricing model/rates | Implemented & Verified | `test_field_pricing.py`: boundaries, zero/negative outcomes, frozen rates |
| R21 | Monthly contractor reconciliation / §5 | statement wizard and ledger | Implemented & Verified | `test_contractor_statement.py`: periods, opening balance, adjustments, cancellations, rounding |
| R22 | Match original Google Sheet formulas | spreadsheet settlement extensions | Implemented & Verified | Original XLSX export formulas J/K/L/M/N checked against implementation and passing boundary/special-case native tests; see evidence/formula-review.md. Currency precision and approved-ledger scope differ deliberately. |
| R23 | Statement HTML/PDF parity / §5 | native QWeb report | Implemented & Verified | Real wkhtmltopdf and rendered statement checks passed in 42401972181, including multipage PDF |
| R24 | Owner income/profit/conversion charts / §3 | dashboard model/QWeb | Implemented & Verified | Metrics tests match source records and company; rendered chart audit passed in final CI; values independently tested at model level |
| R25 | Empty dashboard and period explanation | dashboard + six-month charts | Partially Implemented | Source reviewed, no interactive period filter; browser empty state pending |
| R26 | Owner/operations financial separation / §6 | field groups/ACL/rules | Implemented & Verified | Security/pricing/payment/statement/metrics tests; operations cannot access finance |
| R27 | Email PDF automation / §3 | SMTP adapter + delivery queue | Blocked by External Dependency | Mocked delivery only; chosen Gmail sender not configured; no real messages sent |
| R28 | WhatsApp PDF automation / §3 | Meta Cloud API adapter | Blocked by External Dependency | Mocked delivery/consent/test-recipient checks; API account/templates pending |
| R29 | Signed incoming WhatsApp + deduplication / §2 | public HMAC webhook | Implemented & Verified | Valid/invalid signature and duplicate-event HTTP tests; malformed-shape fix verified by six HTTP 400 cases |
| R30 | Delivery success/failure/retry history / §3 | delivery attempt log | Partially Implemented | Queue/retry tests; provider callbacks and worker interruption not fully exercised live |
| R31 | Hebrew/RTL in every requested viewport / §1 | shared SCSS and native widgets | Partially Implemented | 44 audited viewport states rendered in CI, all RTL/no document overflow; 154 screenshots total. Final 44 states have zero axe violations; physical devices not covered |
| R32 | Keyboard/focus/errors/accessibility | native controls, portal JS | Partially Implemented | 44 final axe scans have zero violations after repairs; incomplete manual checks remain (contrast/bypass/ARIA); no compliance claim |
| R33 | All native Project/CRM/settings screens | native Odoo surfaces | Not Yet Tested | Existing smoke suite does not cover every state/dialog |
| R34 | Offline/session-expiry/two-tabs/back | native web client/portal | Partially Implemented | Draft reload/navigation guards passed; offline/session-expiry/two-tab edits not exhaustively exercised. Logout session replay was rejected in runtime security check |
| R35 | Large data and latency | statement calculation/browser timings | Partially Implemented | Existing 1,001-movement performance test passed; concurrency checks passed; 44 loopback UI observations: median 323ms, range 63–772ms, not a production load benchmark |
| R36 | Mobile home-screen shortcut/camera / §1 | responsive portal | Blocked by External Dependency | User explicitly deferred physical-device acceptance until deployment |
| R37 | Permanent host, HTTPS / §1 | deploy Compose/Caddy | Blocked by External Dependency | No deployment authorized; free host not provisioned |
| R38 | External backup and real restore | deploy backup script | Blocked by External Dependency | No external destination; CI synthetic database restore passed with 46 attachment checksums; not an external infrastructure restore |
| R39 | Secrets and dependency readiness / §6 | source/history scans + inventory | Partially Implemented | Source/history scans passed; 146 rows mapped to 94 advisories in dependency-review.md. Unresolved dependency/native-path risk blocks release |

## Product deviations that must remain explicit

- The original wording tying closure to an invoice number was superseded by the user's execution-approval and full-collection requirement. Do not remove those checks.
- Margin is profit / sale, not markup; the original document's “100–200% profitability” is ambiguous. The existing implementation documents a net-of-VAT margin and does not manufacture values above 100%.
- Positive margins below 35% currently use amber, losses red; the original spec requests red below 35%. Treat as an acceptance deviation, not silently alter the established design during QA.
- Customer invoice/quote PDFs are uploaded from Morning, not legally issued by Odoo. API import is a separate, unmerged integration path.
- The implementation uses native/custom Odoo components and official Meta Cloud API rather than the example marketplace/Green-API products. Functional acceptance must not be inferred from a vendor name.
