from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    leads = env['crm.lead'].search([('is_field_service', '=', True)])
    for lead in leads:
        if lead.field_dispatch_code not in ('completed', 'paid') and not env['field.work.entitlement'].search_count([('lead_id', '=', lead.id)]):
            lead._migrate_commission_formula('net')
        # Do not manufacture receipt numbers, totals or financial documents.
        lead._archive_legacy_documents(update_debt=False)
