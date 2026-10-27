"""Contractor rates and private, currency-rounded gross margin estimates."""
import math

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

FINANCE_GROUP = 'field_work_photos.group_field_finance'
RATE_FIELDS = ('field_rate_small', 'field_rate_medium', 'field_rate_large')
SNAPSHOT_FIELDS = {'field_rates_frozen', 'field_rate_small_snapshot',
                   'field_rate_medium_snapshot', 'field_rate_large_snapshot'}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    field_rate_small = fields.Float(string='אחוז קבלן — עד 500', default=70, groups=FINANCE_GROUP)
    field_rate_medium = fields.Float(string='אחוז קבלן — מעל 500 ועד 1,250', default=65, groups=FINANCE_GROUP)
    field_rate_large = fields.Float(string='אחוז קבלן — מעל 1,250', default=50, groups=FINANCE_GROUP)

    @api.constrains(*RATE_FIELDS)
    def _check_field_rates(self):
        for partner in self:
            if any(not math.isfinite(partner.sudo()[name]) or not 0 <= partner.sudo()[name] <= 100 for name in RATE_FIELDS):
                raise ValidationError('אחוז קבלן חייב להיות בין 0 ל־100.')


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    field_pricing_currency_id = fields.Many2one('res.currency', compute='_compute_field_pricing_currency', string='מטבע תמחור')

    def _compute_field_pricing_currency(self):
        for lead in self:
            lead.field_pricing_currency_id = self.env.ref('base.ILS')

    field_sale_amount = fields.Monetary(string='סכום עסקה לפני מע״מ', currency_field='field_pricing_currency_id', copy=False)
    field_material_cost = fields.Monetary(string='עלות חומרים לפני מע״מ', currency_field='field_pricing_currency_id', copy=False, groups=FINANCE_GROUP)
    field_rates_frozen = fields.Boolean(copy=False, groups=FINANCE_GROUP)
    field_rate_small_snapshot = fields.Float(copy=False, groups=FINANCE_GROUP)
    field_rate_medium_snapshot = fields.Float(copy=False, groups=FINANCE_GROUP)
    field_rate_large_snapshot = fields.Float(copy=False, groups=FINANCE_GROUP)
    field_applied_rate = fields.Float(string='אחוז קבלן מחושב', compute='_compute_field_pricing', compute_sudo=True, groups=FINANCE_GROUP)
    field_contractor_cost = fields.Monetary(string='תשלום צפוי לקבלן', currency_field='field_pricing_currency_id', compute='_compute_field_pricing', compute_sudo=True, groups=FINANCE_GROUP)
    field_gross_profit = fields.Monetary(string='רווח גולמי צפוי', currency_field='field_pricing_currency_id', compute='_compute_field_pricing', compute_sudo=True, groups=FINANCE_GROUP)
    field_gross_margin = fields.Float(string='שיעור רווח גולמי (%)', compute='_compute_field_pricing', compute_sudo=True, groups=FINANCE_GROUP)
    field_low_margin = fields.Boolean(compute='_compute_field_pricing', compute_sudo=True, groups=FINANCE_GROUP)

    @api.depends('field_sale_amount', 'field_material_cost', 'field_execution_type', 'field_pricing_currency_id',
                 'field_contractor_id.partner_id.field_rate_small',
                 'field_contractor_id.partner_id.field_rate_medium',
                 'field_contractor_id.partner_id.field_rate_large',
                 'field_rates_frozen', 'field_rate_small_snapshot',
                 'field_rate_medium_snapshot', 'field_rate_large_snapshot')
    def _compute_field_pricing(self):
        for lead in self:
            currency = lead.field_pricing_currency_id
            sale = currency.round(lead.field_sale_amount)
            rate = 0
            if lead.field_execution_type == 'subcontractor' and lead.field_contractor_id:
                tier = 'small' if sale <= 500 else 'medium' if sale <= 1250 else 'large'
                rate = (lead['field_rate_' + tier + '_snapshot'] if lead.field_rates_frozen
                        else lead.field_contractor_id.partner_id['field_rate_' + tier])
            cost = currency.round(sale * rate / 100)
            profit = currency.round(sale - cost - lead.field_material_cost)
            lead.field_applied_rate = rate
            lead.field_contractor_cost = cost
            lead.field_gross_profit = profit
            lead.field_gross_margin = profit / sale * 100 if sale > 0 else 0
            # Compare rounded currency amounts, avoiding floating-point noise at 35%.
            lead.field_low_margin = sale > 0 and currency.compare_amounts(profit * 100, sale * 35) < 0

    def _field_progress_missing(self, target_code):
        missing = super()._field_progress_missing(target_code)
        if target_code in ('sent', 'schedule', 'field', 'completed') and self.field_sale_amount <= 0:
            missing.append('סכום עסקה חיובי לפני מע״מ')
        return missing

    @api.constrains('field_sale_amount', 'field_material_cost')
    def _check_field_amounts(self):
        for lead in self:
            # Costs are private; sudo only for this invariant, never for user output.
            record = lead.sudo()
            for name in ('field_sale_amount', 'field_material_cost'):
                if not math.isfinite(record[name]) or record[name] < 0:
                    raise ValidationError('סכום העסקה ועלות החומרים חייבים להיות מספרים לא שליליים.')
            if record.is_field_service and record.field_dispatch_code in ('sent', 'schedule', 'field', 'completed') and record.field_sale_amount <= 0:
                raise ValidationError('יש להזין סכום עסקה חיובי לפני מע״מ לפני המשך הטיפול.')

    @api.model_create_multi
    def create(self, vals_list):
        if any(SNAPSHOT_FIELDS.intersection(vals) for vals in vals_list):
            raise AccessError('מחירון העבודה נשמר אוטומטית בעת השיבוץ.')
        return super().create(vals_list)

    def write(self, vals):
        if SNAPSHOT_FIELDS.intersection(vals):
            raise AccessError('לא ניתן לשנות את מחירון העבודה השמור באופן ישיר.')
        assignments = {}
        if {'field_contractor_id', 'field_execution_type'}.intersection(vals):
            service = self.filtered('is_field_service')
            if service:
                self.env.cr.execute('SELECT id FROM crm_lead WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(service.ids)])
                service.invalidate_recordset()
            assignments = {lead.id: (lead.field_contractor_id.id, lead.field_execution_type) for lead in service}
        if {'field_sale_amount', 'field_material_cost'}.intersection(vals):
            # Use the same lock order as dispatch/photo submission to prevent edits
            # racing with a review or approval.
            service = self.filtered('is_field_service')
            if service:
                self.env.cr.execute('SELECT id FROM crm_lead WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(service.ids)])
                service.invalidate_recordset()
                service.field_task_ids._lock_dispatch_work()
            if any(task.field_review_state in ('pending', 'approved') for task in service.field_task_ids):
                raise ValidationError('יש להחזיר את העבודה לתיקון לפני שינוי סכומים.')
        result = super().write(vals)
        # Preserve the contractor's rates at dispatch, including legitimate
        # reassignment while a task is in draft/correction. Later profile changes
        # affect future jobs only. This private super call bypasses only the
        # public snapshot-write guard and field restrictions for these four values.
        if {'stage_id', 'field_contractor_id', 'field_execution_type'}.intersection(vals):
            for lead in self.filtered(lambda item: item.is_field_service and item.field_dispatch_code == 'field'):
                record = lead.sudo()
                if not record.field_rates_frozen or (lead.id in assignments and assignments[lead.id] != (lead.field_contractor_id.id, lead.field_execution_type)):
                    partner = record.field_contractor_id.partner_id
                    snapshot = {'field_rates_frozen': True}
                    snapshot.update({name + '_snapshot': partner[name] if partner else 0 for name in RATE_FIELDS})
                    super(CrmLead, record).write(snapshot)
        return result
