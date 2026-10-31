"""Read-only statement snapshots; one calculation and template for screen/PDF."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.misc import format_datetime

from .field_collection import OWNER
from .field_entitlement import BUSINESS_TZ, business_date

OUTPUT_FIELDS = {'payload', 'report_html', 'generated_at'}
FILTER_FIELDS = {'company_id', 'contractor_id', 'period_mode', 'month_date', 'date_from', 'date_to'}


def utc_boundary(day):
    return datetime.combine(day, time.min, ZoneInfo(BUSINESS_TZ)).astimezone(timezone.utc).replace(tzinfo=None)


class ContractorStatement(models.TransientModel):
    _name = 'field.contractor.statement'
    _description = 'התחשבנות קבלנים לתקופה'
    _rec_name = 'contractor_id'
    _transient_max_hours = 24

    company_id = fields.Many2one('res.company', string='חברה', required=True, default=lambda self: self.env.company)
    contractor_id = fields.Many2one('res.users', string='קבלן', required=True)
    period_mode = fields.Selection([('month', 'חודש'), ('range', 'טווח תאריכים')], string='בחירת תקופה', required=True, default='month')
    month_date = fields.Date(string='תאריך בחודש המבוקש', default=fields.Date.context_today)
    date_from = fields.Date(string='מתאריך', required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(string='עד תאריך', required=True, default=lambda self: fields.Date.end_of(fields.Date.context_today(self), 'month'))
    generated_at = fields.Datetime(string='מועד הפקה', readonly=True)
    payload = fields.Json(readonly=True)
    report_html = fields.Html(string='דוח התחשבנות', compute='_compute_report_html', sanitize=False)

    @api.onchange('period_mode', 'month_date')
    def _onchange_period(self):
        if self.period_mode == 'month' and self.month_date:
            self.date_from = self.month_date.replace(day=1)
            self.date_to = fields.Date.end_of(self.month_date, 'month')

    def _require_report_access(self):
        if not self.env.su and not self.env.user.has_group(OWNER):
            raise AccessError('דוח התחשבנות קבלנים זמין לבעל הרשאה כספית בלבד.')
        self.check_access('read')
        for report in self:
            if report.company_id not in self.env.companies:
                raise AccessError('יש לבחור חברה פעילה ומורשית במחליף החברות.')
            report.contractor_id.check_access('read')

    @api.depends('payload')
    def _compute_report_html(self):
        for report in self:
            report._require_report_access()
            report.report_html = self.env['ir.qweb']._render(
                'field_work_photos.contractor_statement_body', {'s': report.payload}) if report.payload else False

    @api.model
    def default_get(self, fields_list):
        return {key: value for key, value in super().default_get(fields_list).items() if key not in OUTPUT_FIELDS}

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user.has_group(OWNER):
            raise AccessError('אין הרשאה להפיק דוח התחשבנות.')
        if any(OUTPUT_FIELDS.intersection(vals) for vals in vals_list):
            raise AccessError('תוצאות הדוח נוצרות בחישוב בלבד.')
        records = super().create(vals_list)
        records._require_report_access()
        return records

    def write(self, vals):
        self._require_report_access()
        if OUTPUT_FIELDS.intersection(vals):
            raise AccessError('אין לערוך תוצאות דוח. יש לשנות מסננים ולהציג דוח חדש.')
        result = super().write(vals)
        self._require_report_access()
        if FILTER_FIELDS.intersection(vals):
            super().write({'payload': False, 'generated_at': False})
        return result

    def _period(self):
        self.ensure_one()
        start, end = self.date_from, self.date_to
        if self.period_mode == 'month':
            if not self.month_date:
                raise ValidationError('יש לבחור תאריך בחודש המבוקש.')
            start, end = self.month_date.replace(day=1), fields.Date.end_of(self.month_date, 'month')
        if not start or not end or start > end:
            raise ValidationError('יש לבחור טווח תקין: תאריך ההתחלה חייב להיות לפני תאריך הסיום או זהה לו.')
        return start, end

    def _domains(self):
        self.ensure_one()
        return (
            [('company_id', '=', self.company_id.id), ('contractor_id', '=', self.contractor_id.id)],
            [('company_id', '=', self.company_id.id), ('partner_id', '=', self.contractor_id.partner_id.id),
             ('lead_id.field_contractor_id', '=', self.contractor_id.id),
             ('kind', '=', 'contractor'), '|', ('state', '=', 'posted'), ('cancelled_at', '!=', False)],
        )

    def _build_statement(self):
        self.ensure_one()
        self._require_report_access()
        start, end = self._period()
        start_utc, end_utc = utc_boundary(start), utc_boundary(end + timedelta(days=1))
        generated_at = fields.Datetime.now()
        cutoff = min(end_utc, generated_at + timedelta(microseconds=1))
        currency = self.env.ref('base.ILS')
        ent_domain, pay_domain = self._domains()
        entitlements = self.env['field.work.entitlement']
        payments = self.env['field.work.payment']

        def aggregate(model, domain):
            return currency.round(model._read_group(domain, [], ['amount:sum'])[0][0] or 0)

        # Both independent date axes matter: user-entered payment date and
        # immutable cancellation timestamp. Never filter originals by posted state.
        opening_credit = aggregate(entitlements, ent_domain + [('event_date', '<', start)])
        opening_paid = aggregate(payments, pay_domain + [('payment_date', '<', start)])
        opening_void = aggregate(payments, pay_domain + [('cancelled_at', '<', start_utc), ('payment_date', '<', start)])
        opening = currency.round(opening_credit - opening_paid + opening_void)
        entries = entitlements.search_fetch(ent_domain + [('event_date', '>=', start), ('event_date', '<=', end)],
            ['lead_id', 'kind', 'amount', 'event_date', 'reason', 'net_estimate', 'applied_rate'])
        paid_entries = payments.search_fetch(pay_domain + [('payment_date', '>=', start), ('payment_date', '<=', end)],
            ['lead_id', 'amount', 'payment_date', 'reference', 'state', 'cancelled_at'])
        void_entries = payments.search_fetch(pay_domain + [('cancelled_at', '>=', start_utc), ('cancelled_at', '<', cutoff), ('payment_date', '<=', end)],
            ['lead_id', 'amount', 'payment_date', 'reference', 'cancelled_at', 'cancel_reason'])
        payout_action = self.env.ref('field_work_photos.action_field_payouts').id

        def work_link(lead):
            return f'/odoo/action-{payout_action}/{lead.id}'

        def row(day, kind, amount, lead, source, label, reference, **extra):
            return dict(date=str(day), type=label, kind=kind, amount=amount, work=lead.name,
                        work_url=work_link(lead), source_url=f'/odoo/{source._name}/{source.id}',
                        reference=reference, **extra)

        rows = []
        for entry in entries:
            rows.append(row(entry.event_date, entry.kind, entry.amount, entry.lead_id, entry,
                'זכאות מאושרת' if entry.kind == 'credit' else 'ביטול זכאות', entry.reason,
                net_estimate=entry.net_estimate, rate=entry.applied_rate))
        for payment in paid_entries:
            rows.append(row(payment.payment_date, 'payment', -payment.amount, payment.lead_id,
                payment, 'תשלום לקבלן / מקדמה', payment.reference))
        for payment in void_entries:
            # A date entered by a user in a different timezone can lie later
            # than the cancellation's Israeli date. Reverse no earlier than payment.
            day = max(payment.payment_date, business_date(payment.cancelled_at))
            if start <= day <= end:
                rows.append(row(day, 'payment_void', payment.amount, payment.lead_id, payment,
                    'ביטול רישום תשלום', f'{payment.reference} · {payment.cancel_reason}'))
        rows.sort(key=lambda item: (item['date'], item['source_url'], item['kind'] == 'payment_void'))
        credit = currency.round(sum(item['amount'] for item in rows if item['kind'] == 'credit'))
        paid = currency.round(-sum(item['amount'] for item in rows if item['kind'] == 'payment'))
        adjustments = currency.round(sum(item['amount'] for item in rows if item['kind'] in ('reversal', 'payment_void')))
        balance = opening
        for item in rows:
            balance = currency.round(balance + item['amount'])
            item['balance'] = balance

        # Current exceptions are explicitly separate from the dated ledger.
        # Including archived work avoids silently erasing a liability or advance.
        pending_domain = [('is_field_service', '=', True), ('company_id', '=', self.company_id.id),
            ('field_execution_type', '=', 'subcontractor'), ('field_contractor_id', '=', self.contractor_id.id),
            '|', ('field_dispatch_code', '!=', 'paid'), ('field_contractor_amount_approved', '=', False)]
        lead_model = self.env['crm.lead'].with_context(active_test=False)
        pending_count = lead_model.search_count(pending_domain)
        missing_closed_count = lead_model.search_count(pending_domain + [('field_dispatch_code', '=', 'paid'), ('field_contractor_amount_approved', '=', False)])
        pending = lead_model.search(pending_domain, limit=100, order='id')
        exceptions = [dict(work=lead.name, work_url=work_link(lead), estimate=lead.field_contractor_cost,
            gross=lead.field_contractor_due if lead.field_contractor_amount_approved else None,
            status=('ממתין לסגירת העבודה' if lead.field_contractor_amount_approved else
                    'סכום כולל לא אושר — אינו נכלל ביתרה'), frozen=lead.field_rates_frozen) for lead in pending]
        history_start = self.env['ir.config_parameter'].sudo().get_param('field_work_photos.statement_history_start')
        unknown_cancellations = payments.search_count([
            ('company_id', '=', self.company_id.id), ('partner_id', '=', self.contractor_id.partner_id.id),
            ('kind', '=', 'contractor'), ('state', '=', 'cancelled'), ('cancelled_at', '=', False), ('payment_date', '<=', end)])
        return dict(company=self.company_id.name, contractor=self.contractor_id.name,
            date_from=str(start), date_to=str(end), timezone=BUSINESS_TZ,
            generated_at=format_datetime(self.env, generated_at, tz=BUSINESS_TZ, dt_format='dd/MM/yyyy HH:mm:ss'),
            history_start=history_start, opening=opening, opening_credit=opening_credit,
            opening_paid=opening_paid, opening_void=opening_void, credit=credit, paid=paid, adjustments=adjustments,
            closing=balance, rows=rows, exceptions=exceptions, pending_count=pending_count,
            missing_closed_count=missing_closed_count,
            unknown_cancellations=unknown_cancellations,
            legacy_period=not history_start or start < business_date(history_start))

    def action_show_report(self):
        self.ensure_one()
        payload = self._build_statement()
        super().write({'payload': payload, 'generated_at': fields.Datetime.now()})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'views': [(self.env.ref('field_work_photos.view_contractor_statement_form').id, 'form')], 'target': 'current'}

    def action_print_pdf(self):
        self.ensure_one()
        self._require_report_access()
        if not self.payload:
            raise ValidationError('יש ללחוץ על הצגת דוח לפני הפקת PDF.')
        return self.env.ref('field_work_photos.action_report_contractor_statement').report_action(self)

    def action_open_opening(self):
        self.ensure_one()
        self._require_report_access()
        start, _end = self._period()
        ent_domain, _pay_domain = self._domains()
        return {'type': 'ir.actions.act_window', 'name': 'זכאויות לפני תחילת התקופה',
                'res_model': 'field.work.entitlement', 'view_mode': 'list,form',
                'domain': ent_domain + [('event_date', '<', start)], 'context': {'create': False}}

    def action_open_opening_payments(self):
        self.ensure_one()
        self._require_report_access()
        start, _end = self._period()
        _ent_domain, pay_domain = self._domains()
        return {'type': 'ir.actions.act_window', 'name': 'תשלומים לפני תחילת התקופה — כולל תיעוד ביטול',
                'res_model': 'field.work.payment', 'view_mode': 'list,form',
                'domain': pay_domain + [('payment_date', '<', start)], 'context': {'create': False}}


class ReportContractorStatement(models.AbstractModel):
    _name = 'report.field_work_photos.contractor_statement_pdf'
    _description = 'הפקת התחשבנות קבלנים'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['field.contractor.statement'].browse(docids)
        docs._require_report_access()
        if len(docs) != 1 or not docs.payload:
            raise ValidationError('יש להציג דוח אחד לפני הפקתו.')
        return {'doc_ids': docs.ids, 'doc_model': docs._name, 'docs': docs}
