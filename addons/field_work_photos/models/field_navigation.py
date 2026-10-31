"""Native, permission-aware entry points for the field-work application."""
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
