# Kobi temporary business access — prepared, not applied

PR #22 retains the six pilot fixes. Target module version: `18.0.17.0.2`.
Candidate login from prior instructions: `kobiabudi`; **live identity is not verified**.
There is no connected/authenticated pilot tab in this session. No live role, module,
record, deployment or credentials were changed.

## Scope

Use existing `field_work_photos.group_field_finance`, which implies Dispatcher.
It supports permitted business edits, customer receipts, contractor payouts/rates,
statements and owner metrics. It does not permit editing immutable ledger entries,
bypassing approval/collection rules, foreign-company access, or managing users.
Creating a **portal login** for a new contractor still requires an administrator;
editing an existing contractor's business/rate data does not. Computed reports
remain computed. No Finance Viewer or Administrator group is added.

Financial pricing/rate/sheet edits now record actor, time and submitted financial field names
in existing chatter, including when tracking_disable is supplied. Successful same-value saves are also logged to avoid missing concurrent updates. Private amounts
and before/after values are intentionally absent from shared chatter. Existing
payment and entitlement ledgers retain their amount/audit records. This is an edit
event trail, not a new private historical-value ledger.

## Update sequence — requires separate approval before execution

1. Read-only: confirm the actual Cloady instance/database/image and the account's
   exact login, UID, displayed name, active/internal status and company assignment.
   Reject duplicates, wrong UID, inactive/portal users, or existing user/settings
   administration roles. Do not infer identity from display name alone.
2. Back up PostgreSQL **and** filestore and record the previous image/module version;
   verify the existing restore route. Validate in a disposable clone first.
3. After merge/release/deployment approval, use the reviewed PR image/commit.
   In a maintenance window, stop competing application processes and run a single
   `field_work_photos` module upgrade using the instance's existing secret config.
   Do not initialize a new DB, overwrite credentials or run `-u all`.
4. Verify installed version `18.0.17.0.2`, field views and filename columns. Keep the
   existing identity/companies unchanged. On failure, restore the paired backup
   with its matching old image; do not simply run old code over new schema.
5. Only after explicit permission-change approval, use the helper below, retain the
   receipt privately, and commit only after successful post-checks.
6. In a fresh Kobi session verify menus, PDF access and permitted save/actions on
   synthetic records in the clone; confirm user/settings administration is denied.
   Check real pilot pages read-only. No customer data is changed merely for testing.

## Operator helper (Odoo shell; do not execute without approval)

```python
from odoo.addons.field_work_photos.models import pilot_access
info = pilot_access.preflight(env, 'kobiabudi')  # read-only; verify human identity
# Then, only after approval and verification of the actual UID:
receipt = pilot_access.enable(env, 'kobiabudi', expected_uid=VERIFIED_UID)
# Retain receipt (including added_finance) in a private operator record.
# env.cr.commit() only after reviewing the post-checks; rollback on any exception.
```

To finish the pilot, an authorized administrator calls
`pilot_access.restore(env, receipt)` and reviews the result before committing.
It removes only Finance introduced by this operation, leaves Dispatcher and other
pre-existing groups/companies intact, and preserves Finance if it existed before.
Refresh/re-authenticate Kobi and verify finance writes are denied. A changed account
identity/company assignment or inherited role preventing removal is a stop condition,
not permission to overwrite all groups. Keep the original receipt across repeated
calls; do not replace it with a later no-op enable receipt.

## Evidence

Focused permission/audit CI: **9 passed, 0 failed, 0 errors** on tested commit
`f8082faf72ae8de6f109aec433822bfdc2c5da64`: [run 44525065568](https://github.com/naor291291/odoo-pilot/actions/runs/44525065568).
The isolated Odoo database exercised reversible Finance membership, financial edits
and audit events, business view compilation/model access, payment actions, closure
guards, denial of user administration and cross-company writes. These are backend
and compiled-view checks, not browser acceptance.

 Initial run 44521577758 was blocked before tests by Ubuntu HTTP package-download timeouts while installing unused development tools. The focused Compose override now uses the unchanged reviewed runtime stage; no deployment/runtime dependency is removed. Run 44524534178 built runtime successfully but stopped on an unsupported Compose run flag; the flag was removed before retry. Previous six-fix evidence remains in PR #22;
no rerun of its 91 passing tests or the historical 207-test suite is planned.
UI login to each live business screen and the real account role change remain
unperformed. No production-access claim follows from synthetic role tests.
