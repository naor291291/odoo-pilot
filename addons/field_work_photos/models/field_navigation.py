"""Native, permission-aware entry points for the field-work application."""
from datetime import datetime, time, timedelta
import pytz

from odoo import api, fields, models
from odoo.exceptions import AccessError

OPS = 'field_work_photos.group_field_dispatcher'
FINANCE = 'field_work_photos.group_field_finance'


class FieldWorkDashboard(models.TransientModel):
    _name = 'field.work.dashboard'
    _description = 'מרכז עבודות השטח'

    name = fields.Char(default='מרכז העבודה', readonly=True)
    new_count = fields.Integer(compute='_compute_counts')
    quote_count = fields.Integer(compute='_compute_counts')
    schedule_count = fields.Integer(compute='_compute_counts')
    review_count = fields.Integer(compute='_compute_counts')
    active_count = fields.Integer(compute='_compute_counts')
    collection_count = fields.Integer(compute='_compute_counts')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.ref('base.ILS'), readonly=True)
    collection_balance = fields.Monetary(compute='_compute_finance', currency_field='currency_id', groups=FINANCE)
    contractor_balance = fields.Monetary(compute='_compute_finance', currency_field='currency_id', groups=FINANCE)

    attention_ids = fields.Many2many('crm.lead', compute='_compute_attention')
    attention_count = fields.Integer(compute='_compute_attention')

    @api.model
    def _today_bounds(self):
        # Dates are the viewer's local day; stored appointments remain UTC.
        zone = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        day = fields.Date.context_today(self)
        start = zone.localize(datetime.combine(day, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        end = zone.localize(datetime.combine(day + timedelta(days=1), time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        return start, end

    def _attention_domain(self):
        _, end = self._today_bounds()
        return [('is_field_service', '=', True), '|',
                ('field_task_ids.field_review_state', '=', 'pending'), '&',
                ('field_dispatch_code', '=', 'field'), ('field_visit_at', '<', end)]

    @api.depends_context('uid', 'allowed_company_ids', 'tz')
    def _compute_attention(self):
        self._require_ops()
        Lead = self.env['crm.lead']
        domain = self._attention_domain()
        # Review first, then the oldest scheduled work. No sudo/finance fields.
        pending = Lead.search([('is_field_service', '=', True),
                               ('field_task_ids.field_review_state', '=', 'pending')],
                              order='field_visit_at, id', limit=6)
        remaining = Lead.search(domain + [('id', 'not in', pending.ids)],
                                order='field_visit_at, id', limit=max(1, 6 - len(pending))) if len(pending) < 6 else Lead.browse()
        for dashboard in self:
            dashboard.attention_ids = pending | remaining
            dashboard.attention_count = Lead.search_count(domain)

    def action_attention(self):
        return self._leads(self._attention_domain())

    def action_today(self):
        self._require_ops()
        start, end = self._today_bounds()
        action = self.env['ir.actions.actions']._for_xml_id('field_work_photos.action_field_tasks')
        action.update(name='העבודות להיום', view_mode='kanban,calendar,list,form',
                      views=[(self.env.ref('field_work_photos.view_field_task_agenda').id, 'kanban'),
                             (self.env.ref('field_work_photos.view_field_task_calendar').id, 'calendar'),
                             (self.env.ref('field_work_photos.view_field_task_list').id, 'list'),
                             (self.env.ref('field_work_photos.view_field_task_form').id, 'form')], domain=[('field_service_lead_id', '!=', False),
                      ('state', '!=', '1_canceled'), ('field_visit_at', '>=', start), ('field_visit_at', '<', end)])
        return action

    def _require_ops(self):
        if not self.env.user.has_group(OPS):
            raise AccessError('מרכז העבודה זמין לצוות התפעול ולבעלים בלבד.')

    @api.depends_context('uid', 'allowed_company_ids')
    def _compute_counts(self):
        self._require_ops()
        Lead = self.env['crm.lead']
        base = [('is_field_service', '=', True)]
        domains = {
            'new_count': [('field_dispatch_code', '=', 'new')],
            'quote_count': [('field_dispatch_code', 'in', ['quote', 'sent'])],
            'schedule_count': [('field_dispatch_code', '=', 'schedule')],
            'review_count': [('field_task_ids.field_review_state', '=', 'pending')],
            'active_count': [('field_dispatch_code', '=', 'field')],
            'collection_count': [('field_dispatch_code', '=', 'completed')],
        }
        values = {name: Lead.search_count(base + domain) for name, domain in domains.items()}
        for dashboard in self:
            for name, value in values.items():
                dashboard[name] = value

    @api.depends_context('uid', 'allowed_company_ids')
    def _compute_finance(self):
        self._require_ops()
        if not self.env.user.has_group(FINANCE):
            raise AccessError('סיכומים כספיים כלליים זמינים לבעלים בלבד.')
        leads = self.env['crm.lead'].search([('is_field_service', '=', True)])
        customer = sum(leads.mapped('field_customer_balance'))
        contractor = sum(leads.mapped('field_contractor_balance'))
        for dashboard in self:
            dashboard.collection_balance = customer
            dashboard.contractor_balance = contractor

    @api.model
    def action_open(self):
        self._require_ops()
        record = self.create({})
        return {'type': 'ir.actions.act_window', 'name': 'מרכז העבודה', 'res_model': self._name,
                'res_id': record.id, 'views': [(self.env.ref('field_work_photos.view_field_dashboard').id, 'form')], 'target': 'current'}

    def _leads(self, domain):
        self._require_ops()
        action = self.env['ir.actions.actions']._for_xml_id('field_work_photos.action_field_service_leads')
        action['domain'] = [('is_field_service', '=', True)] + domain
        action['views'] = [(self.env.ref('field_work_photos.view_field_lead_list').id, 'list'),
                           (self.env.ref('field_work_photos.view_field_lead_form').id, 'form')]
        return action

    def action_new_work(self):
        action = self._leads([])
        action.update(res_id=False, views=[(self.env.ref('field_work_photos.view_field_lead_form').id, 'form')])
        return action

    def action_new_queue(self):
        return self._leads([('field_dispatch_code', '=', 'new')])

    def action_quote_queue(self):
        return self._leads([('field_dispatch_code', 'in', ['quote', 'sent'])])

    def action_schedule_queue(self):
        return self._leads([('field_dispatch_code', '=', 'schedule')])

    def action_review_queue(self):
        return self._leads([('field_task_ids.field_review_state', '=', 'pending')])

    def action_active_queue(self):
        return self._leads([('field_dispatch_code', '=', 'field')])

    def action_collection_queue(self):
        self._require_ops()
        return self.env['ir.actions.actions']._for_xml_id('field_work_photos.action_field_collections')

    def action_clients(self):
        self._require_ops()
        partners = self.env['crm.lead'].search([('is_field_service', '=', True)]).mapped('partner_id')
        action = self.env['ir.actions.actions']._for_xml_id('field_work_photos.action_field_clients')
        action['domain'] = ['|', ('field_crm_client', '=', True), ('id', 'in', partners.ids)]
        return action


class ResPartner(models.Model):
    _inherit = 'res.partner'

    field_crm_client = fields.Boolean(string='לקוח עבודות שטח', groups=OPS, copy=False)

    def action_open_field_client_work(self):
        self.ensure_one()
        self.check_access('read')
        dashboard = self.env['field.work.dashboard']
        return dashboard._leads([('partner_id', '=', self.id)])


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def action_open_field_work_card(self):
        self.ensure_one()
        self.check_access('read')
        return self.field_service_lead_id.action_open_field_workspace()
