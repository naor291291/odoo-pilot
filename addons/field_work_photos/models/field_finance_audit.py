"""Record financial edit events in existing chatter without leaking private amounts."""
from odoo import models
from .field_entitlement import SHEET_FIELDS
from .field_pricing import RATE_FIELDS

LEAD_FIELDS = {'field_sale_amount', 'field_material_cost', 'field_customer_due', 'field_contractor_due', *SHEET_FIELDS, 'field_expenses_approved', 'field_commission_formula'}


def log_updates(records, names):
    if not names:
        return
    for record in records:
        # Log every successful financial write, even a same-value save. Comparing
        # values before the model's locks could miss a concurrent update/revert.
        # Never put amounts in shared chatter, tracking values or notifications.
        record._message_log(
            body='עדכון כספי: ' + ', '.join(record._fields[name].string for name in names))


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def write(self, values):
        names = sorted(set(values).intersection(LEAD_FIELDS))
        result = super().write(values)
        if names:
            log_updates(self.filtered('is_field_service'), names)
        return result


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def write(self, values):
        names = sorted(set(values).intersection(RATE_FIELDS))
        result = super().write(values)
        log_updates(self, names)
        return result
