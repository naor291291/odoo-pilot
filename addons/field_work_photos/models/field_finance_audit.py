"""Record financial edit events in existing chatter without leaking private amounts."""
from odoo import models
from .field_entitlement import SHEET_FIELDS
from .field_pricing import RATE_FIELDS

LEAD_FIELDS = {'field_sale_amount', 'field_material_cost', 'field_contractor_due', *SHEET_FIELDS}


def snapshot(records, values, names):
    fields = sorted(set(values).intersection(names))
    return {record.id: {name: record[name] for name in fields} for record in records} if fields else {}


def log_changes(records, before):
    for record in records:
        changed = [name for name, value in before.get(record.id, {}).items() if record[name] != value]
        if changed:
            # Keep amounts out of shared chatter, tracking_value_ids and email.
            # Existing ledgers retain immutable payment/entitlement amounts.
            record._message_log(
                body='עדכון כספי: ' + ', '.join(record._fields[name].string for name in changed))


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def write(self, values):
        before = snapshot(self.filtered('is_field_service'), values, LEAD_FIELDS)
        result = super().write(values)
        log_changes(self, before)
        return result


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def write(self, values):
        before = snapshot(self, values, RATE_FIELDS)
        result = super().write(values)
        log_changes(self, before)
        return result
