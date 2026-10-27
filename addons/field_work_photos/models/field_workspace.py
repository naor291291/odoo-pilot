from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    field_workspace_task_id = fields.Many2one('project.task', compute='_compute_workspace_task')
    field_report_state = fields.Selection(related='field_workspace_task_id.field_review_state')
    field_report_before_image = fields.Image(related='field_workspace_task_id.field_before_image', readonly=False)
    field_report_after_image = fields.Image(related='field_workspace_task_id.field_after_image', readonly=False)
    field_report_note = fields.Text(related='field_workspace_task_id.field_review_note')
    field_report_submitted_at = fields.Datetime(related='field_workspace_task_id.field_submitted_at')
    field_report_approved_at = fields.Datetime(related='field_workspace_task_id.field_approved_at')
    field_report_can_review = fields.Boolean(compute='_compute_workspace_reviewer')
    field_attention_label = fields.Char(compute='_compute_field_attention')

    @api.depends('field_task_ids')
    def _compute_workspace_task(self):
        for lead in self:
            lead.field_workspace_task_id = lead.field_task_ids[:1]

    @api.depends_context('uid')
    def _compute_workspace_reviewer(self):
        allowed = self.env.su or self.env.user.has_group('field_work_photos.group_field_reviewer')
        for lead in self:
            lead.field_report_can_review = allowed

    @api.depends('field_missing_fields', 'field_dispatch_code', 'field_report_state')
    def _compute_field_attention(self):
        for lead in self:
            if lead.field_report_state == 'pending':
                label = 'ממתינה לבדיקת דיווח'
            elif lead.field_report_state == 'changes_requested':
                label = 'ממתינה לתיקון הדיווח'
            elif lead.field_dispatch_code == 'completed':
                label = 'הביצוע אושר'
            elif lead.field_missing_fields:
                label = 'להשלמה: ' + lead.field_missing_fields.splitlines()[0].lstrip('• ')
            else:
                label = {'new': 'אפשר להכין הצעת מחיר', 'quote': 'עדכון פרטי ההצעה',
                         'sent': 'ממתינה לאישור ההצעה', 'schedule': 'אפשר לשבץ לביצוע',
                         'field': 'ממתינה לדיווח מהשטח'}.get(lead.field_dispatch_code, '')
            lead.field_attention_label = label

    def _workspace_task(self):
        self.ensure_one()
        self._require_dispatcher()
        self.check_access('write')
        if not self.is_field_service or not self.field_task_ids:
            raise ValidationError('יש לשבץ את העבודה לפני דיווח מהשטח.')
        task = self.field_task_ids
        task.check_access('write')
        return task

    def _field_workspace_action(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'res_model': 'crm.lead',
                'res_id': self.id, 'views': [(self.env.ref('field_work_photos.view_field_lead_form').id, 'form')],
                'target': 'current'}

    def action_open_field_task(self):
        self._workspace_task()
        return self._field_workspace_action()

    def action_submit_field_report(self):
        self._workspace_task().action_finish_field_work()
        return True

    def action_approve_field_report(self):
        self._workspace_task().action_approve_field_work()
        return True

    def action_return_field_report(self):
        task = self._workspace_task()
        task._require_field_reviewer()
        if task.field_review_state not in ('pending', 'approved'):
            raise ValidationError('אפשר להחזיר לתיקון דיווח שהוגש או אושר בלבד.')
        return {'type': 'ir.actions.act_window', 'res_model': 'field.work.correction',
                'views': [(False, 'form')], 'target': 'new',
                'context': {'default_task_id': task.id}}

    @api.model_create_multi
    def create(self, vals_list):
        protected = {'field_workspace_task_id', 'field_report_state', 'field_report_note', 'field_report_submitted_at', 'field_report_approved_at'}
        if any(protected.intersection(vals) or vals.get('field_report_before_image') or vals.get('field_report_after_image') for vals in vals_list):
            raise AccessError('דיווח שטח ניתן לעדכן רק לאחר שיבוץ הפנייה.')
        return super().create(vals_list)

    def write(self, vals):
        if {'field_workspace_task_id', 'field_report_state', 'field_report_note', 'field_report_submitted_at', 'field_report_approved_at'}.intersection(vals):
            raise AccessError('מצב הדיווח ופרטי האישור מתעדכנים באמצעות פעולות התהליך בלבד.')
        if {'field_report_before_image', 'field_report_after_image'}.intersection(vals):
            for lead in self:
                lead._workspace_task()
        return super().write(vals)


class FieldWorkCorrection(models.TransientModel):
    _name = 'field.work.correction'
    _description = 'החזרת דיווח שטח לתיקון'

    task_id = fields.Many2one('project.task', required=True, readonly=True)
    reason = fields.Text(string='מה צריך לתקן?', required=True)

    def action_apply(self):
        self.ensure_one()
        task = self.task_id
        task._require_field_reviewer()
        task.check_access('write')
        if not (self.reason or '').strip():
            raise ValidationError('יש לפרט מה צריך לתקן בדיווח.')
        task.write({'field_review_note': self.reason.strip()})
        task.action_request_field_changes()
        lead = task.field_service_lead_id
        return lead._field_workspace_action() if lead else {'type': 'ir.actions.act_window_close'}
