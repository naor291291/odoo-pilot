"""Append-only contractor entitlements. Reporting never creates these entries."""
from datetime import timezone
from zoneinfo import ZoneInfo

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .field_collection import OWNER, _money

BUSINESS_TZ = 'Asia/Jerusalem'
APPROVAL_FIELDS = {'field_contractor_amount_approved', 'field_contractor_amount_approved_at',
                   'field_contractor_amount_approved_by'}
SHEET_CATEGORIES = [('regular', 'רגיל'), ('undocumented', 'ללא תיעוד'), ('easy_house', 'איזי האוס')]
SHEET_MONEY_FIELDS = ('field_sheet_customer_paid', 'field_sheet_contractor_expenses',
                      'field_sheet_business_expenses', 'field_sheet_cash')
SHEET_FIELDS = (*SHEET_MONEY_FIELDS, 'field_sheet_category', 'field_sheet_no_commission', 'field_sheet_complete')
SHEET_OUTPUT_FIELDS = {'field_sheet_profit', 'field_sheet_rate', 'field_sheet_amount'}


def sheet_amounts(paid, contractor_expenses, business_expenses, category, no_commission, currency):
    """Return the workbook's J, K and applicable L/M/N amount before VAT."""
    profit = currency.round(paid - contractor_expenses - business_expenses) if paid else 0.0
    if no_commission:
        return profit, 0, profit
    rate = 70 if profit <= 500 else 65 if profit <= 1250 else 50
    if not profit and category == 'regular':
        return profit, rate, 0.0
    return profit, rate, round(profit * rate / 100 + contractor_expenses, 4)


def business_date(value):
    return fields.Datetime.to_datetime(value).replace(tzinfo=timezone.utc).astimezone(ZoneInfo(BUSINESS_TZ)).date()


class FieldWorkEntitlement(models.Model):
    _name = 'field.work.entitlement'
    _description = 'תנועת זכאות לקבלן'
    _order = 'event_date, id'
    _rec_name = 'lead_id'

    lead_id = fields.Many2one('crm.lead', string='עבודה', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one('res.company', string='חברה', required=True, index=True)
    contractor_id = fields.Many2one('res.users', string='קבלן', required=True, ondelete='restrict', index=True)
    currency_id = fields.Many2one('res.currency', string='מטבע', required=True)
    kind = fields.Selection([('credit', 'זכאות מאושרת'), ('reversal', 'ביטול זכאות')], string='סוג תנועה', required=True)
    amount = fields.Monetary(string='תנועה כולל מע״מ', required=True)
    event_at = fields.Datetime(string='מועד התנועה', required=True)
    event_date = fields.Date(string='תאריך בישראל', required=True, index=True)
    reason = fields.Char(string='בסיס התנועה', required=True)
    recorded_by = fields.Many2one('res.users', string='מבצע הפעולה', required=True)
    reversal_of_id = fields.Many2one('field.work.entitlement', string='התנועה שבוטלה', ondelete='restrict', index=True)
    approved_by = fields.Many2one('res.users', string='הסכום אושר על ידי', required=True)
    approved_at = fields.Datetime(string='מועד אישור הסכום', required=True)
    closed_at = fields.Datetime(string='מועד סגירת העבודה', required=True)
    net_estimate = fields.Monetary(string='אומדן היסטורי לפני מע״מ', required=True)
    sale_net = fields.Monetary(string='עסקה היסטורית לפני מע״מ', required=True)
    applied_rate = fields.Float(string='אחוז היסטורי')
    sheet_category = fields.Selection(SHEET_CATEGORIES, string='קטגוריה לפי הגיליון')
    sheet_amount = fields.Float(string='תנועה לפי הגיליון לפני מע״מ', digits=(16, 4))
    sheet_cash = fields.Monetary(string='מזומן שהתקבל אצל הקבלן לפני מע״מ')

    _sql_constraints = [('one_reversal', 'unique(reversal_of_id)', 'תנועת הזכאות כבר בוטלה.')]

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError('זכאות נוצרת רק מסגירת עבודה ואישור סכום הקבלן.')

    def write(self, vals):
        raise AccessError('תנועת זכאות נשמרת ללא עריכה. תיקון מתועד בתנועה נפרדת.')

    @api.ondelete(at_uninstall=False)
    def _prevent_delete(self):
        raise AccessError('אין למחוק תנועות זכאות.')

    def copy(self, default=None):
        raise AccessError('אין לשכפל תנועות זכאות.')

    @api.model
    def _append(self, lead, reversal=False, reason=None):
        # Only governed work actions call this private method. Operations may
        # close/reopen jobs, but may never read the owner's private ledger.
        lead.check_access('write')
        lead._require_dispatcher()
        lead_sudo = lead.sudo()
        ledger_sudo = self.sudo()
        entries_sudo = ledger_sudo.search([('lead_id', '=', lead.id)])
        reversed_ids = set(entries_sudo.mapped('reversal_of_id').ids)
        live_sudo = entries_sudo.filtered(lambda row: row.kind == 'credit' and row.id not in reversed_ids)
        now = fields.Datetime.now()
        if reversal:
            values = [{
                'lead_id': row.lead_id.id, 'company_id': row.company_id.id,
                'contractor_id': row.contractor_id.id, 'currency_id': row.currency_id.id,
                'kind': 'reversal', 'amount': -row.amount, 'event_at': now,
                'event_date': business_date(now), 'reason': reason, 'recorded_by': self.env.uid,
                'reversal_of_id': row.id, 'approved_by': row.approved_by.id,
                'approved_at': row.approved_at, 'closed_at': row.closed_at,
                'net_estimate': row.net_estimate, 'sale_net': row.sale_net,
                'applied_rate': row.applied_rate,
                'sheet_category': row.sheet_category, 'sheet_amount': -row.sheet_amount,
                'sheet_cash': -row.sheet_cash,
            } for row in live_sudo]
        elif (not live_sudo and lead_sudo.field_dispatch_code == 'paid'
              and lead_sudo.field_execution_type == 'subcontractor'
              and lead_sudo.field_contractor_id and lead_sudo.field_contractor_amount_approved):
            values = [{
                'lead_id': lead.id, 'company_id': lead.company_id.id,
                'contractor_id': lead.field_contractor_id.id,
                'currency_id': self.env.ref('base.ILS').id, 'kind': 'credit',
                'amount': lead_sudo.field_contractor_due, 'event_at': now,
                'event_date': business_date(now),
                'reason': 'העבודה נסגרה ושולמה וסכום הקבלן אושר',
                'recorded_by': self.env.uid,
                'approved_by': lead_sudo.field_contractor_amount_approved_by.id,
                'approved_at': lead_sudo.field_contractor_amount_approved_at,
                'closed_at': lead.field_closed_at,
                'net_estimate': lead_sudo.field_contractor_cost,
                'sale_net': lead_sudo.field_sale_amount,
                'applied_rate': lead_sudo.field_applied_rate,
            }]
            if lead_sudo.field_sheet_category:
                values[0].update(sheet_category=lead_sudo.field_sheet_category,
                                 sheet_amount=lead_sudo.field_sheet_amount, sheet_cash=lead_sudo.field_sheet_cash)
        else:
            values = []
        if values:
            super(FieldWorkEntitlement, ledger_sudo).create(values)


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    field_contractor_amount_approved = fields.Boolean(string='סכום הקבלן אושר', readonly=True, copy=False, groups=OWNER)
    field_contractor_amount_approved_at = fields.Datetime(string='סכום הקבלן אושר במועד', readonly=True, copy=False, groups=OWNER)
    field_contractor_amount_approved_by = fields.Many2one('res.users', string='סכום הקבלן אושר על ידי', readonly=True, copy=False, groups=OWNER)
    field_sheet_category = fields.Selection(SHEET_CATEGORIES, string='קטגוריה לפי הגיליון', copy=False, groups=OWNER)
    field_sheet_customer_paid = fields.Monetary(string='שולם מהלקוח לפני מע״מ', currency_field='field_pricing_currency_id', copy=False, groups=OWNER)
    field_sheet_contractor_expenses = fields.Monetary(string='הוצאות הקבלן לפני מע״מ', currency_field='field_pricing_currency_id', copy=False, groups=OWNER)
    field_sheet_business_expenses = fields.Monetary(string='הוצאות העסק לפני מע״מ', currency_field='field_pricing_currency_id', copy=False, groups=OWNER)
    field_sheet_cash = fields.Monetary(string='מזומן אצל הקבלן לפני מע״מ', currency_field='field_pricing_currency_id', copy=False, groups=OWNER)
    field_sheet_no_commission = fields.Boolean(string='אחוז עמלה 0', copy=False, groups=OWNER)
    field_sheet_complete = fields.Boolean(string='נתוני הגיליון מלאים', copy=False, groups=OWNER)
    field_sheet_profit = fields.Monetary(string='רווח לחלוקה לפני מע״מ', currency_field='field_pricing_currency_id', compute='_compute_sheet_amounts', groups=OWNER)
    field_sheet_rate = fields.Float(string='אחוז לפי הגיליון', compute='_compute_sheet_amounts', groups=OWNER)
    field_sheet_amount = fields.Float(string='תשלום לפי הגיליון לפני מע״מ', digits=(16, 4), compute='_compute_sheet_amounts', groups=OWNER)

    @api.depends(*SHEET_FIELDS)
    def _compute_sheet_amounts(self):
        currency = self.env.ref('base.ILS')
        for lead in self:
            result = (0.0, 0, 0.0)
            if lead.field_sheet_category and lead.field_sheet_complete:
                result = sheet_amounts(lead.field_sheet_customer_paid, lead.field_sheet_contractor_expenses,
                                       lead.field_sheet_business_expenses, lead.field_sheet_category,
                                       lead.field_sheet_no_commission, currency)
            lead.field_sheet_profit, lead.field_sheet_rate, lead.field_sheet_amount = result

    @api.constrains(*SHEET_MONEY_FIELDS)
    def _check_sheet_money(self):
        currency = self.env.ref('base.ILS')
        for lead in self.sudo():
            for name in SHEET_MONEY_FIELDS:
                _money(lead[name], currency)

    @api.model
    def default_get(self, fields_list):
        protected = APPROVAL_FIELDS | SHEET_OUTPUT_FIELDS
        return {key: value for key, value in super().default_get(fields_list).items() if key not in protected}

    @api.model_create_multi
    def create(self, vals_list):
        if any(APPROVAL_FIELDS.intersection(vals) for vals in vals_list):
            raise AccessError('יש לאשר את סכום הקבלן בפעולה הייעודית.')
        if any(SHEET_OUTPUT_FIELDS.intersection(vals) for vals in vals_list):
            raise AccessError('תוצאות הגיליון מחושבות לפי הנתונים שהוזנו.')
        return super().create(vals_list)

    def write(self, vals):
        if APPROVAL_FIELDS.intersection(vals):
            raise AccessError('פרטי אישור סכום הקבלן נשמרים אוטומטית.')
        if SHEET_OUTPUT_FIELDS.intersection(vals):
            raise AccessError('תוצאות הגיליון מחושבות לפי הנתונים שהוזנו.')
        sensitive = {'field_contractor_due', 'field_contractor_id', 'field_execution_type', 'company_id'}
        sheet_inputs = tuple(name for name in SHEET_FIELDS if name in vals)
        old = {}
        if sensitive.intersection(vals) or sheet_inputs:
            service = self.filtered('is_field_service')
            service._lock_collection()
            entries_sudo = self.env['field.work.entitlement'].sudo().search([('lead_id', 'in', service.ids)])
            historic_ids = set(entries_sudo.mapped('lead_id').ids)
            for lead in service.sudo():
                old[lead.id] = (lead.field_contractor_due, lead.field_contractor_id.id, lead.field_execution_type,
                                lead.company_id.id, tuple(lead[name] for name in sheet_inputs))
                if lead.id in historic_ids and any(
                    key in vals and vals[key] != (lead[key].id if key.endswith('_id') else lead[key])
                    for key in ('field_contractor_id', 'field_execution_type', 'company_id')
                ):
                    raise ValidationError('אין לשנות קבלן, חברה או סוג ביצוע בעבודה עם היסטוריית זכאות. יש לפתוח עבודה נפרדת.')
        result = super().write(vals)
        for lead in self:
            if lead.id in old:
                lead_sudo = lead.sudo()
                current = (lead_sudo.field_contractor_due, lead.field_contractor_id.id, lead.field_execution_type,
                           lead.company_id.id, tuple(lead_sudo[name] for name in sheet_inputs))
                if old[lead.id] != current:
                    self.env['field.work.entitlement']._append(lead, reversal=True, reason='שינוי סכום או פרטי התחשבנות — נדרש אישור מחדש')
                    super(CrmLead, lead_sudo).write({
                        'field_contractor_amount_approved': False,
                        'field_contractor_amount_approved_at': False,
                        'field_contractor_amount_approved_by': False})
        return result

    def action_approve_contractor_amount(self):
        self.ensure_one()
        self._check_collection_kind('contractor')
        self._lock_collection()
        if self.field_execution_type != 'subcontractor' or not self.field_contractor_id:
            raise ValidationError('יש לבחור קבלן משנה לפני אישור הסכום.')
        if self.field_sheet_category and not self.field_sheet_complete:
            raise ValidationError('יש להשלים את נתוני הגיליון ולסמן שהם מלאים לפני אישור הסכום.')
        if not self.field_contractor_amount_approved:
            super().write({'field_contractor_amount_approved': True,
                           'field_contractor_amount_approved_at': fields.Datetime.now(),
                           'field_contractor_amount_approved_by': self.env.uid})
        self.env['field.work.entitlement']._append(self)
        return self._field_workspace_action(focus='finance')

    def action_close_field_work(self):
        result = super().action_close_field_work()
        for lead in self:
            self.env['field.work.entitlement']._append(lead)
        return result

    def _set_field_review_stage(self, code):
        was_paid = self.filtered(lambda lead: lead.field_dispatch_code == 'paid')
        result = super()._set_field_review_stage(code)
        if code != 'paid':
            for lead in was_paid:
                self.env['field.work.entitlement']._append(lead, reversal=True, reason='העבודה נפתחה מחדש — הזכאות בוטלה עד לסגירה חוזרת')
        return result
