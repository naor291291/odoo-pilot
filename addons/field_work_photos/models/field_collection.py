"""Manual operational receipts and contractor payouts; never issues fiscal documents."""
import math
import uuid

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

OPS = 'field_work_photos.group_field_dispatcher'
OWNER = 'field_work_photos.group_field_finance'
KINDS = [('customer', 'תקבול מלקוח'), ('contractor', 'תשלום לקבלן')]
METHODS = [('transfer', 'העברה בנקאית'), ('card', 'כרטיס אשראי'),
           ('cash', 'מזומן'), ('check', 'המחאה'), ('other', 'אחר')]
STATUS = [('unset', 'נדרש סכום כולל'), ('unpaid', 'טרם שולם'),
          ('partial', 'שולם חלקית'), ('paid', 'שולם במלואו')]
SUMMARY_FIELDS = {'field_customer_paid', 'field_customer_balance', 'field_collection_status',
                  'field_contractor_paid', 'field_contractor_balance', 'field_payout_status',
                  'field_payment_ids', 'field_payout_ids', 'field_closed_at', 'field_closed_by'}


def _money(value, currency):
    if not math.isfinite(value) or value < 0:
        raise ValidationError('יש להזין סכום תקין ולא שלילי.')
    return currency.round(value)


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    field_customer_due = fields.Monetary(
        string='סכום לגבייה כולל מע״מ', currency_field='field_pricing_currency_id',
        copy=False, groups=OPS, tracking=True)
    field_payment_ids = fields.One2many('field.work.payment', 'lead_id',
        domain=[('kind', '=', 'customer')], string='תקבולים מהלקוח', copy=False, groups=OPS)
    field_customer_paid = fields.Monetary(string='התקבל מהלקוח',
        currency_field='field_pricing_currency_id', compute='_compute_collection', store=True, groups=OPS)
    field_customer_balance = fields.Monetary(string='יתרה לגבייה',
        currency_field='field_pricing_currency_id', compute='_compute_collection', store=True, groups=OPS)
    field_collection_status = fields.Selection(STATUS, string='מצב גבייה',
        compute='_compute_collection', store=True, groups=OPS)
    field_contractor_due = fields.Monetary(
        string='סכום לתשלום לקבלן כולל מע״מ', currency_field='field_pricing_currency_id',
        copy=False, groups=OWNER)
    field_payout_ids = fields.One2many('field.work.payment', 'lead_id',
        domain=[('kind', '=', 'contractor')], string='תשלומים לקבלן', copy=False, groups=OWNER)
    field_contractor_paid = fields.Monetary(string='שולם לקבלן',
        currency_field='field_pricing_currency_id', compute='_compute_payout', store=True, groups=OWNER)
    field_contractor_balance = fields.Monetary(string='יתרה לקבלן',
        currency_field='field_pricing_currency_id', compute='_compute_payout', store=True, groups=OWNER)
    field_payout_status = fields.Selection(STATUS, string='מצב התחשבנות',
        compute='_compute_payout', store=True, groups=OWNER)
    field_closed_at = fields.Datetime(string='מועד סגירה', readonly=True, copy=False, groups=OPS)
    field_closed_by = fields.Many2one('res.users', string='נסגרה על ידי', readonly=True, copy=False, groups=OPS)

    def _collection_totals(self, kind, due):
        self.ensure_one()
        currency = self.env.ref('base.ILS')
        # The caller computes a field restricted to the appropriate group. Never
        # mix customer receipts with owner-only payouts in either aggregate.
        payments = self.env['field.work.payment'].sudo().search([
            ('lead_id', '=', self.id), ('kind', '=', kind), ('state', '=', 'posted')]) if self.id else self.env['field.work.payment']
        paid = currency.round(sum(payments.mapped('amount')))
        balance = currency.round(due - paid)
        status = 'unset' if due <= 0 else 'paid' if currency.is_zero(balance) else 'partial' if paid else 'unpaid'
        return paid, balance, status

    @api.depends('field_customer_due', 'field_payment_ids.amount', 'field_payment_ids.state', 'field_payment_ids.kind')
    def _compute_collection(self):
        for lead in self:
            lead.field_customer_paid, lead.field_customer_balance, lead.field_collection_status = lead._collection_totals('customer', lead.field_customer_due)

    @api.depends('field_contractor_due', 'field_payout_ids.amount', 'field_payout_ids.state', 'field_payout_ids.kind')
    def _compute_payout(self):
        for lead in self:
            lead.field_contractor_paid, lead.field_contractor_balance, lead.field_payout_status = lead._collection_totals('contractor', lead.field_contractor_due)

    def _lock_collection(self):
        self._require_dispatcher()
        self.check_access('write')
        if any(not lead.is_field_service or not lead.active or not lead.company_id or
               lead.company_id not in self.env.companies for lead in self):
            raise ValidationError('הפעולה זמינה לעבודת שטח פעילה בחברה המורשית בלבד.')
        if self:
            self.env.cr.execute('SELECT id FROM crm_lead WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(self.ids)])
            self.invalidate_recordset()
            self.field_task_ids._lock_dispatch_work()

    def _check_collection_kind(self, kind):
        if kind not in dict(KINDS):
            raise ValidationError('יש לבחור סוג תשלום תקין.')
        self._require_dispatcher()
        if kind == 'contractor' and not (self.env.su or self.env.user.has_group(OWNER)):
            raise AccessError('התחשבנות עם קבלנים זמינה לבעלים בלבד.')

    @api.constrains('field_customer_due', 'field_contractor_due', 'stage_id', 'field_payment_ids', 'field_payout_ids')
    def _check_collection_amounts(self):
        for lead in self.sudo():
            for kind, due in [('customer', lead.field_customer_due), ('contractor', lead.field_contractor_due)]:
                _money(due, self.env.ref('base.ILS'))
                paid, balance, status = lead._collection_totals(kind, due)
                if balance < 0:
                    raise ValidationError('הסכום הכולל אינו יכול להיות קטן מהתשלומים הרשומים. יש לבדוק או לבטל רישום שגוי תחילה.')
            if lead.field_dispatch_code == 'paid' and (
                not lead.is_field_service or lead._collection_totals('customer', lead.field_customer_due)[2] != 'paid' or
                not lead.field_task_ids or any(t.field_review_state != 'approved' for t in lead.field_task_ids)):
                raise ValidationError('סגירת עבודה מחייבת אישור ביצוע וגבייה מלאה של הסכום הכולל.')

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        # RPC/import context defaults must not inject stored computed balances
        # or a pre-filled receipt relation after our public create guard ran.
        return {name: value for name, value in defaults.items() if name not in SUMMARY_FIELDS}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if SUMMARY_FIELDS.intersection(vals):
                raise AccessError('תשלומים, יתרות ופרטי סגירה מתעדכנים באמצעות הפעולות הייעודיות בלבד.')
            for name in ('field_customer_due', 'field_contractor_due'):
                if name in vals:
                    vals[name] = _money(vals[name], self.env.ref('base.ILS'))
        return super().create(vals_list)

    def write(self, vals):
        if SUMMARY_FIELDS.intersection(vals):
            raise AccessError('תשלומים, יתרות ופרטי סגירה מתעדכנים באמצעות הפעולות הייעודיות בלבד.')
        service = self.filtered('is_field_service')
        sensitive = {'field_customer_due', 'field_contractor_due', 'partner_id', 'company_id',
                     'field_contractor_id', 'field_execution_type', 'is_field_service'}
        if service and sensitive.intersection(vals):
            service._lock_collection()
            for name in ('field_customer_due', 'field_contractor_due'):
                if name in vals:
                    vals[name] = _money(vals[name], self.env.ref('base.ILS'))
            for lead in service:
                # Include cancelled records: their historical party/company must
                # never silently change after a mistaken registration is voided.
                ledger = self.env['field.work.payment'].sudo().search([('lead_id', '=', lead.id)])
                for name in ('partner_id', 'company_id'):
                    if ledger and name in vals and vals[name] != lead[name].id:
                        raise ValidationError('לא ניתן להחליף לקוח או חברה בעבודה שיש בה רישומי תשלום.')
                if ledger.filtered(lambda p: p.kind == 'contractor') and (
                    ('field_contractor_id' in vals and vals['field_contractor_id'] != lead.field_contractor_id.id) or
                    ('field_execution_type' in vals and vals['field_execution_type'] != lead.field_execution_type)):
                    raise ValidationError('לא ניתן להחליף קבלן או סוג ביצוע לאחר רישום תשלום לקבלן. יש לפתוח עבודה נפרדת.')
                if lead.field_dispatch_code == 'paid' and 'field_customer_due' in vals and vals['field_customer_due'] != lead.field_customer_due:
                    raise ValidationError('יש לפתוח את העבודה מחדש לפני שינוי הסכום לגבייה.')
        return super().write(vals)

    def _payment_dialog(self, kind):
        self.ensure_one()
        self._check_collection_kind(kind)
        self._lock_collection()
        if kind == 'customer' and (not self.partner_id or self.field_customer_due <= 0):
            raise ValidationError('יש לבחור לקוח ולהזין סכום לגבייה כולל מע״מ לפני רישום תשלום.')
        if kind == 'contractor' and (self.field_execution_type != 'subcontractor' or not self.field_contractor_id or self.field_contractor_due <= 0):
            raise ValidationError('יש לבחור קבלן ולהזין סכום לתשלום לקבלן כולל מע״מ.')
        return {'type': 'ir.actions.act_window', 'res_model': 'field.work.payment.register',
                'views': [(False, 'form')], 'target': 'new',
                'context': {'default_lead_id': self.id, 'default_kind': kind}}

    def action_register_customer_payment(self):
        return self._payment_dialog('customer')

    def action_register_contractor_payment(self):
        return self._payment_dialog('contractor')

    def action_close_field_work(self):
        self.ensure_one()
        self._lock_collection()
        if self.field_dispatch_code != 'completed' or self.field_collection_status != 'paid':
            raise ValidationError('אפשר לסגור רק עבודה שביצועה אושר ושיתרת הלקוח שלה אפס לאחר גבייה מלאה.')
        self._set_field_review_stage('paid')
        super().write({'field_closed_at': fields.Datetime.now(), 'field_closed_by': self.env.uid})
        self.message_post(body='העבודה נסגרה כטופל ושולם לאחר אישור הביצוע והשלמת הגבייה.')
        return True

    def _set_field_review_stage(self, code):
        # Review/cancellation can reopen a paid job; the receipt ledger survives.
        was_paid = self.filtered(lambda lead: lead.field_dispatch_code == 'paid')
        result = super()._set_field_review_stage(code)
        if code != 'paid' and was_paid:
            super(CrmLead, was_paid).write({'field_closed_at': False, 'field_closed_by': False})
            for lead in was_paid:
                lead.message_post(body='העבודה נפתחה מחדש. רישומי התשלום נשמרו ויש לבדוק את מצב הביצוע והגבייה.')
        return result

    def unlink(self):
        if self.env['field.work.payment'].sudo().search_count([('lead_id', 'in', self.ids)]):
            raise ValidationError('לא ניתן למחוק עבודה עם רישומי תשלום. ניתן לארכב אותה.')
        return super().unlink()


class FieldWorkPayment(models.Model):
    _name = 'field.work.payment'
    _description = 'רישום תשלום לעבודת שטח'
    _order = 'payment_date desc, id desc'
    _rec_name = 'reference'

    lead_id = fields.Many2one('crm.lead', string='עבודה', required=True, ondelete='restrict', index=True)
    kind = fields.Selection(KINDS, string='סוג רישום', required=True, default='customer', index=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, index=True)
    partner_id = fields.Many2one('res.partner', string='לקוח / קבלן', required=True, readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True, required=True)
    amount = fields.Monetary(string='סכום כולל מע״מ', required=True)
    payment_date = fields.Date(string='תאריך תשלום', required=True, default=fields.Date.context_today)
    method = fields.Selection(METHODS, string='אמצעי תשלום', required=True, default='transfer')
    reference = fields.Char(string='אסמכתה / מספר קבלה', required=True)
    note = fields.Text(string='הערה פנימית')
    state = fields.Selection([('posted', 'נרשם'), ('cancelled', 'בוטל')], string='מצב', required=True, default='posted', readonly=True)
    request_key = fields.Char(required=True, default=lambda self: str(uuid.uuid4()), readonly=True, copy=False)
    reference_key = fields.Char(readonly=True, copy=False)
    cancelled_by = fields.Many2one('res.users', string='בוטל על ידי', readonly=True, copy=False)
    cancelled_at = fields.Datetime(string='מועד ביטול', readonly=True, copy=False)
    cancel_reason = fields.Text(string='סיבת ביטול', readonly=True, copy=False)

    _sql_constraints = [
        ('request_unique', 'unique(request_key)', 'התשלום כבר נרשם. יש לרענן את כרטיס העבודה.'),
        ('reference_unique', 'unique(lead_id, kind, reference_key)', 'האסמכתה כבר רשומה בסוג תשלום זה בעבודה.'),
        ('positive_amount', 'CHECK(amount > 0)', 'יש להזין סכום תשלום חיובי.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if {'company_id', 'partner_id', 'currency_id', 'state', 'reference_key',
                'cancelled_by', 'cancelled_at', 'cancel_reason', 'create_uid', 'create_date', 'write_uid', 'write_date'}.intersection(vals):
                raise AccessError('פרטי הבקרה נשמרים אוטומטית ואינם ניתנים להזנה ישירה.')
        leads = self.env['crm.lead'].browse(sorted({v.get('lead_id') for v in vals_list if v.get('lead_id')})).exists()
        leads._lock_collection()
        # Batches are processed incrementally under the parent lock so two items
        # in one request cannot both spend the same remaining balance.
        records = self.browse()
        for values in vals_list:
            vals = dict(values)
            lead = leads.filtered(lambda l: l.id == vals.get('lead_id'))
            if not lead:
                raise ValidationError('יש לבחור עבודת שטח קיימת.')
            kind = vals.get('kind', 'customer')
            lead._check_collection_kind(kind)
            if not lead.partner_id or (kind == 'customer' and lead.field_dispatch_code == 'paid'):
                raise ValidationError('לא ניתן לרשום תשלום ללא לקוח או בעבודה סגורה.')
            if kind == 'contractor' and (lead.field_execution_type != 'subcontractor' or not lead.field_contractor_id):
                raise ValidationError('תשלום לקבלן מחייב עבודה המשויכת לקבלן משנה.')
            currency = self.env.ref('base.ILS')
            amount = _money(vals.get('amount', 0), currency)
            due = lead.sudo().field_customer_due if kind == 'customer' else lead.sudo().field_contractor_due
            paid, balance, status = lead._collection_totals(kind, due)
            if amount <= 0 or due <= 0 or currency.compare_amounts(amount, balance) > 0:
                raise ValidationError('סכום התשלום חייב להיות חיובי ולא לעלות על היתרה. יש לבדוק את הסכום הכולל ואת התשלומים הקיימים.')
            reference = (vals.get('reference') or '').strip()
            date = fields.Date.to_date(vals.get('payment_date') or fields.Date.context_today(self))
            if not reference or len(reference) > 200 or date > fields.Date.context_today(self):
                raise ValidationError('יש להזין אסמכתה עד 200 תווים ותאריך תשלום שאינו בעתיד.')
            if self.search_count([('lead_id', '=', lead.id), ('kind', '=', kind), ('reference_key', '=', reference.casefold())]):
                raise ValidationError('האסמכתה כבר רשומה בסוג תשלום זה בעבודה. יש לבדוק את הרישומים הקיימים.')
            vals.update(amount=amount, kind=kind, state='posted', cancelled_by=False,
                        cancelled_at=False, cancel_reason=False,
                        reference=reference, reference_key=reference.casefold(),
                        payment_date=date, company_id=lead.company_id.id, currency_id=currency.id,
                        partner_id=(lead.partner_id if kind == 'customer' else lead.field_contractor_id.partner_id).id)
            records |= super().create([vals])
        return records

    def write(self, vals):
        raise AccessError('רישום תשלום אינו ניתן לעריכה. לביטול טעות יש להשתמש בביטול רישום ולפרט סיבה.')

    def unlink(self):
        raise AccessError('אין למחוק רישומי תשלום. יש לבטל רישום שגוי עם סיבה.')

    def copy(self, default=None):
        raise AccessError('אין לשכפל רישומי תשלום.')

    def action_cancel_registration(self):
        self.ensure_one()
        self.check_access('write')
        self.lead_id._check_collection_kind(self.kind)
        if self.state != 'posted':
            raise ValidationError('הרישום כבר בוטל.')
        return {'type': 'ir.actions.act_window', 'res_model': 'field.work.payment.cancel',
                'views': [(False, 'form')], 'target': 'new', 'context': {'default_payment_id': self.id}}

    def _cancel_registration(self, reason):
        self.ensure_one()
        self.check_access('write')
        lead = self.lead_id
        lead._check_collection_kind(self.kind)
        lead._lock_collection()
        self.invalidate_recordset()
        if self.state != 'posted' or not (reason or '').strip():
            raise ValidationError('ניתן לבטל רישום פעיל בלבד, בצירוף סיבה.')
        # Reopen BEFORE changing the ledger so the paid-stage invariant stays true.
        if self.kind == 'customer' and lead.field_dispatch_code == 'paid':
            lead._set_field_review_stage('completed')
        super().write({'state': 'cancelled', 'reference_key': False, 'cancel_reason': reason.strip(),
                       'cancelled_by': self.env.uid, 'cancelled_at': fields.Datetime.now()})
        # Owner-only payout details must never enter the shared CRM chatter.
        if self.kind == 'customer':
            lead.message_post(body='בוטל רישום תקבול מלקוח. הסיבה ופרטי הביטול שמורים ברשומת התשלום.')
        return lead._field_workspace_action(focus='collection' if self.kind == 'customer' else 'finance')


class FieldWorkPaymentRegister(models.TransientModel):
    _name = 'field.work.payment.register'
    _description = 'רישום תקבול או תשלום לקבלן'

    lead_id = fields.Many2one('crm.lead', string='עבודה', required=True, readonly=True)
    kind = fields.Selection(KINDS, string='סוג רישום', required=True, readonly=True, default='customer')
    amount = fields.Monetary(string='סכום כולל מע״מ', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.ref('base.ILS'), readonly=True)
    payment_date = fields.Date(string='תאריך תשלום', required=True, default=fields.Date.context_today)
    method = fields.Selection(METHODS, string='אמצעי תשלום', required=True, default='transfer')
    reference = fields.Char(string='אסמכתה / מספר קבלה', required=True)
    note = fields.Text(string='הערה פנימית')
    request_key = fields.Char(default=lambda self: str(uuid.uuid4()), required=True, readonly=True)

    def action_apply(self):
        self.ensure_one()
        self.lead_id._check_collection_kind(self.kind)
        self.lead_id._lock_collection()
        # A repeated click on the same dialog is idempotent, including after
        # another browser has cancelled its original entry.
        existing = self.env['field.work.payment'].search([('request_key', '=', self.request_key)], limit=1)
        if not existing:
            self.env['field.work.payment'].create({
                'lead_id': self.lead_id.id, 'kind': self.kind, 'amount': self.amount,
                'payment_date': self.payment_date, 'method': self.method,
                'reference': self.reference, 'note': self.note, 'request_key': self.request_key})
        elif existing.lead_id != self.lead_id or existing.kind != self.kind:
            raise ValidationError('חלונית התשלום אינה תואמת לעבודה. יש לפתוח אותה מחדש.')
        return self.lead_id._field_workspace_action(focus='collection' if self.kind == 'customer' else 'finance')


class FieldWorkPaymentCancel(models.TransientModel):
    _name = 'field.work.payment.cancel'
    _description = 'ביטול רישום תשלום שגוי'

    payment_id = fields.Many2one('field.work.payment', string='רישום תשלום', required=True, readonly=True)
    reason = fields.Text(string='סיבת הביטול', required=True)

    def action_apply(self):
        self.ensure_one()
        return self.payment_id._cancel_registration(self.reason)
