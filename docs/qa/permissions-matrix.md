# Permission verification matrix

These are executed model/HTTP results from the 205-test Odoo suite, not UI-menu observations. Owner = finance group; operations = dispatcher; contractor = restricted portal role. Native Project Manager is a different role and must not be assigned as a shortcut.

| Resource/action | Owner | Operations | Assigned contractor | Other contractor / guest | Executed evidence |
|---|---|---|---|---|---|
| Work detail and report | Internal company scope | Internal company scope | Assigned portal scope only | Denied | `test_foreign_detail_photo_and_post_return_404`, reassignment test |
| Customer quote/invoice PDF preview/download | Company scope | Company scope | Denied | Denied | `test_preview_and_download_require_internal_company_access` |
| Report photo and native binary URL | Internal scope | Internal scope | Assigned only | Denied, including guessed photo ID | `test_private_native_binary_routes_and_logout`, `test_extra_photo_id_and_generic_routes_remain_scoped` |
| Financial ledger and payout dialog | Allowed governed actions | Customer collection only; contractor payout denied | Denied | Denied | `test_operations_cannot_access_or_spoof_payouts`, `test_portal_and_non_dispatcher_have_no_ledger_or_dialog_access` |
| Statement HTML/PDF/attachment | Owner scope | Denied | Denied | Denied | `test_direct_statement_html_pdf_and_attachment_authorization` |
| Financial values via read/search/group/export | Authorized role only | Private values denied | Denied | Denied | `test_private_fields_deny_read_search_aggregation_and_export` |
| Audit/ledger direct edit/delete | Immutable, even owner | Denied | Denied | Denied | `test_ledger_immutable_and_audit_cannot_be_forged`, statement ledger tests |
| Foreign-company dialogs/statements | Denied on company switch | Denied | Denied | Denied | `test_company_switch_revokes_dialog_and_statement` |
| Private ORM methods via RPC | Not public RPC | Not public RPC | Denied | Denied | `test_direct_rpc_actions_and_private_methods_are_denied` |
| Portal write without CSRF | Token required | No role shortcut | Token required | Denied | `test_csrf_and_non_contractor_access` |
| Portal injected HTML text | Escaped output | Escaped output | Escaped output | No authorized access | `test_portal_text_is_escaped_and_pages_are_not_cached` |

No claim of exhaustive penetration testing. Actual hosting headers, production identities, every native Odoo menu, dependency exploitability, and real identity-provider/session-expiry behavior remain outside this verified matrix.
