from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

from .field_collection import OWNER
from .contractor_statement import utc_boundary
from .field_entitlement import business_date


ACCEPTED_STAGES = ('schedule', 'field', 'completed', 'paid')
QUOTED_STAGES = ('sent', *ACCEPTED_STAGES)


class FieldWorkOwnerDashboard(models.TransientModel):
    _name = 'field.work.owner.dashboard'
    _description = 'מדדי עבודות שטח לבעלים'

    name = fields.Char(default='מדדי בעלים', readonly=True)

    company_id = fields.Many2one('res.company', compute='_compute_metrics', string='חברה')
    currency_id = fields.Many2one('res.currency', compute='_compute_metrics')
    sale_total = fields.Monetary(compute='_compute_metrics', string='עסקאות שאושרו לפני מע״מ')
    receipt_total = fields.Monetary(compute='_compute_metrics', string='גבייה בפועל כולל מע״מ')
    estimated_profit = fields.Monetary(compute='_compute_metrics', string='רווח גולמי צפוי לפני מע״מ')
    estimated_margin = fields.Float(compute='_compute_metrics', string='שיעור רווח משוקלל', digits=(16, 2))
    profit_count = fields.Integer(compute='_compute_metrics')
    unpriced_count = fields.Integer(compute='_compute_metrics')
    quoted_count = fields.Integer(compute='_compute_metrics', string='הצעות שנשלחו')
    accepted_count = fields.Integer(compute='_compute_metrics', string='הצעות שאושרו')
    conversion = fields.Float(compute='_compute_metrics', string='שיעור המרה', digits=(16, 2))
    trends = fields.Html(compute='_compute_trends', sanitize=False, string='מגמות חצי שנתיות')

    def _require_owner(self):
        if not self.env.user.has_group(OWNER):
            raise AccessError('מדדי החברה זמינים לבעלים בלבד.')

    @api.depends_context('uid', 'company')
    def _compute_trends(self):
        self._require_owner()
        current_month = business_date(fields.Datetime.now()).replace(day=1)
        start = current_month - relativedelta(months=5)
        months = {
            start + relativedelta(months=offset): dict(receipts=0, profit=0, quoted=0, accepted=0, priced=0)
            for offset in range(6)
        }
        company = self.env.company
        leads = self.env['crm.lead'].with_context(active_test=False).search([
            ('is_field_service', '=', True), ('company_id', '=', company.id),
            ('field_dispatch_code', 'in', QUOTED_STAGES), ('create_date', '>=', utc_boundary(start)),
            ('create_date', '<', utc_boundary(current_month + relativedelta(months=1))),
        ])
        for lead in leads:
            month = months[business_date(lead.create_date).replace(day=1)]
            month['quoted'] += 1
            if lead.field_dispatch_code in ACCEPTED_STAGES:
                month['accepted'] += 1
                if lead.field_sale_amount > 0 and (lead.field_execution_type == 'direct' or lead.field_contractor_id):
                    month['profit'] += lead.field_gross_profit
                    month['priced'] += 1
        receipt_groups = self.env['field.work.payment'].with_context(active_test=False)._read_group([
            ('company_id', '=', company.id), ('kind', '=', 'customer'), ('state', '=', 'posted'),
            ('lead_id.is_field_service', '=', True), ('lead_id.company_id', '=', company.id),
            ('payment_date', '>=', start), ('payment_date', '<', current_month + relativedelta(months=1)),
        ], groupby=['payment_date:month'], aggregates=['amount:sum'])
        for day, total in receipt_groups:
            months[fields.Date.to_date(day)]['receipts'] = total
        data = []
        currency = self.env.ref('base.ILS')
        for day, month in months.items():
            data.append(dict(label=day.strftime('%m/%Y'), receipts=currency.round(month['receipts']),
                             profit=currency.round(month['profit']) if month['priced'] else None,
                             conversion=month['accepted'] / month['quoted'] * 100 if month['quoted'] else None))
        charts = [
            ('הכנסות לפי גבייה', 'תקבולים כולל מע״מ לפי חודש התשלום.', 'receipts', '₪'),
            ('רווח גולמי צפוי', 'לפני מע״מ, לפי חודש פתיחת העבודות המאושרות עם תמחור מלא.', 'profit', '₪'),
            ('המרת הצעות', 'לפי חודש פתיחת העבודה והשלב הנוכחי. יעד 50%.', 'conversion', '%'),
        ]
        for dashboard in self:
            dashboard.trends = self.env['ir.qweb']._render(
                'field_work_photos.field_owner_trends', {'months': data, 'charts': charts})

    @api.depends_context('uid', 'company')
    def _compute_metrics(self):
        self._require_owner()
        company = self.env.company
        currency = self.env.ref('base.ILS')
        leads = self.env['crm.lead'].with_context(active_test=False)
        scope = [('is_field_service', '=', True), ('company_id', '=', company.id)]
        quoted_count = leads.search_count(scope + [('field_dispatch_code', 'in', QUOTED_STAGES)])
        accepted = leads.search(scope + [('field_dispatch_code', 'in', ACCEPTED_STAGES)])
        priced = accepted.filtered(lambda lead: lead.field_sale_amount > 0 and (
            lead.field_execution_type == 'direct' or lead.field_contractor_id))
        sale_total = currency.round(sum(accepted.mapped('field_sale_amount')))
        priced_sale = currency.round(sum(priced.mapped('field_sale_amount')))
        profit = currency.round(sum(priced.mapped('field_gross_profit')))
        payments = self.env['field.work.payment'].with_context(active_test=False)
        [(receipt_total,)] = payments._read_group([
            ('company_id', '=', company.id), ('kind', '=', 'customer'), ('state', '=', 'posted'),
            ('lead_id.is_field_service', '=', True), ('lead_id.company_id', '=', company.id),
        ], aggregates=['amount:sum'])
        for dashboard in self:
            dashboard.update({
                'company_id': company, 'currency_id': currency, 'sale_total': sale_total,
                'receipt_total': currency.round(receipt_total or 0), 'estimated_profit': profit,
                'estimated_margin': profit / priced_sale * 100 if priced_sale else 0,
                'profit_count': len(priced), 'unpriced_count': len(accepted - priced),
                'quoted_count': quoted_count, 'accepted_count': len(accepted),
                'conversion': len(accepted) / quoted_count * 100 if quoted_count else 0,
            })

    @api.model
    def action_open(self):
        self._require_owner()
        dashboard = self.create({})
        return {
            'type': 'ir.actions.act_window', 'name': 'מדדי בעלים',
            'res_model': self._name, 'res_id': dashboard.id,
            'views': [(self.env.ref('field_work_photos.view_field_owner_dashboard').id, 'form')],
        }
