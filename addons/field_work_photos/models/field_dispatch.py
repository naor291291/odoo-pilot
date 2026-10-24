from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


STAGES = [
    ('new', 'לקוח חדש / פנייה'), ('quote', 'ממתין להצעת מחיר'),
    ('sent', 'הצעה נשלחה'), ('schedule', 'ממתין לתיאום'),
    ('field', 'בביצוע בשטח'), ('completed', 'הושלם וממתין לתשלום'),
]
DISPATCH_FIELDS = {
    'field_contractor_id', 'field_visit_at', 'field_site_address',
    'field_work_description', 'partner_id', 'contact_name', 'phone', 'name',
}


class CrmStage(models.Model):
    _inherit = 'crm.stage'

    field_dispatch_code = fields.Selection(STAGES, copy=False, index=True)


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    is_field_service = fields.Boolean(string='פניית עבודת שטח', copy=True, index=True)
    field_contractor_id = fields.Many2one(
        'res.users', string='קבלן מבצע', copy=False, tracking=True,
        domain=lambda self: [("share", "=", True), ("active", "=", True), ("groups_id", "in", self.env.ref("field_work_photos.group_field_contractor").ids)],
    )
    field_visit_at = fields.Datetime(string='מועד ביצוע', copy=False, tracking=True)
    field_site_address = fields.Char(string='כתובת ביצוע', tracking=True)
    field_work_description = fields.Text(string='תיאור העבודה לקבלן', tracking=True)
    field_quote_number = fields.Char(string='מספר הצעת מחיר ממורנינג', copy=False, tracking=True)
    field_task_ids = fields.One2many('project.task', 'field_service_lead_id', string='משימת שטח', copy=False)
    field_task_count = fields.Integer(compute='_compute_field_task_count')
    field_dispatch_code = fields.Selection(related='stage_id.field_dispatch_code')

    def _compute_field_task_count(self):
        for lead in self:
            lead.field_task_count = len(lead.field_task_ids)

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        if self.env.context.get('field_service_pipeline'):
            return stages.search([('field_dispatch_code', '!=', False)], order='sequence, id')
        return super()._read_group_stage_ids(stages, domain)

    def _require_dispatcher(self):
        if not self.env.su and not self.env.user.has_group('field_work_photos.group_field_dispatcher'):
            raise AccessError('רק מנהלת תפעול או בעל הרשאת שיבוץ יכולים לעדכן עבודות שטח.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_field_service', self.env.context.get('default_is_field_service')):
                self._require_dispatcher()
                vals.setdefault('team_id', self.env.ref('field_work_photos.team_field_service').id)
                vals.setdefault('stage_id', self.env.ref('field_work_photos.stage_field_new').id)
                vals.setdefault('type', 'opportunity')
                stage = self.env['crm.stage'].browse(vals['stage_id'])
                if vals.get('field_quote_number') and stage.field_dispatch_code in ('new', 'quote'):
                    vals['stage_id'] = self.env.ref('field_work_photos.stage_field_sent').id
            if vals.get('field_task_ids'):
                raise AccessError('משימת שטח נוצרת באמצעות תהליך השיבוץ בלבד.')
        leads = super().create(vals_list)
        leads.filtered(lambda l: l.is_field_service and l.field_dispatch_code == 'field')._ensure_field_task()
        return leads

    def write(self, vals):
        service = self.filtered('is_field_service')
        if service or vals.get('is_field_service'):
            self._require_dispatcher()
        if service and vals.get('is_field_service') is False:
            raise ValidationError('לא ניתן להסיר את סוג פניית השטח לאחר יצירתה.')
        if 'field_task_ids' in vals:
            raise AccessError('משימת שטח נוצרת באמצעות תהליך השיבוץ בלבד.')
        # Serialize dispatch and reassignment; the task also has a unique lead key.
        if service:
            self.env.cr.execute('SELECT id FROM crm_lead WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(service.ids)])
            service.invalidate_recordset()
            service.field_task_ids._lock_dispatch_work()
        if DISPATCH_FIELDS.intersection(vals):
            if any(t.field_review_state in ('pending', 'approved') for t in service.field_task_ids):
                raise ValidationError('יש להחזיר את העבודה לתיקון לפני שינוי פרטי העבודה או השיבוץ.')
        result = super().write(vals)
        if vals.get('field_quote_number'):
            service.filtered(lambda l: l.field_dispatch_code in ('new', 'quote')).write({
                'stage_id': self.env.ref('field_work_photos.stage_field_sent').id,
            })
        service.filtered(lambda l: l.field_dispatch_code == 'field')._ensure_field_task()
        if DISPATCH_FIELDS.intersection(vals):
            for lead in service:
                lead.field_task_ids._write_dispatch_details(lead._field_task_values())
        return result

    @api.constrains('is_field_service', 'stage_id', 'field_contractor_id', 'field_visit_at',
                    'field_site_address', 'field_work_description', 'partner_id', 'contact_name',
                    'phone', 'field_quote_number', 'company_id', 'name')
    def _check_field_dispatch(self):
        for lead in self.filtered('is_field_service'):
            code = lead.field_dispatch_code
            if not code:
                raise ValidationError('יש לבחור שלב מתוך מסלול עבודות השטח.')
            if code in ('sent', 'schedule', 'field', 'completed') and not (lead.field_quote_number or '').strip():
                raise ValidationError('יש להזין מספר הצעת מחיר ממורנינג לפני המשך הטיפול.')
            if lead.field_task_ids and code not in ('field', 'completed'):
                raise ValidationError('לא ניתן להחזיר פנייה ששובצה לשלב טרום ביצוע.')
            if code == 'field' and any(t.field_review_state == 'approved' for t in lead.field_task_ids):
                raise ValidationError('פתיחה מחדש של עבודה מאושרת מחייבת החזרה לתיקון מתוך המשימה.')
            if code == 'completed' and not (lead.field_task_ids and all(t.field_review_state == 'approved' for t in lead.field_task_ids)):
                raise ValidationError('הפנייה תושלם רק לאחר אישור דיווח השטח.')
            if code in ('field', 'completed'):
                contractor = lead.field_contractor_id
                existing_assignment = bool(lead.field_task_ids and lead.field_task_ids.field_contractor_id == contractor)
                if not contractor or (not existing_assignment and (not contractor.active or not contractor.share or not contractor.has_group('field_work_photos.group_field_contractor'))):
                    raise ValidationError('יש לבחור קבלן פעיל בעל הרשאת פורטל קבלנים.')
                if not lead.field_visit_at or not (lead.field_site_address or '').strip() or not (lead.field_work_description or '').strip():
                    raise ValidationError('יש להזין מועד ביצוע, כתובת ותיאור עבודה לפני השיבוץ.')
                if not lead.partner_id:
                    raise ValidationError('יש לבחור לקוח לפני השיבוץ.')
                project = lead.env.ref('field_work_photos.project_field_dispatch')
                if project.company_id and lead.company_id != project.company_id:
                    raise ValidationError('פרויקט הפיילוט מיועד לחברה הראשית בלבד.')

    def _field_task_values(self):
        self.ensure_one()
        return {
            'name': self.name,
            'field_contractor_id': self.field_contractor_id.id,
            'field_visit_at': self.field_visit_at,
            'field_site_address': self.field_site_address,
            'field_work_description': self.field_work_description,
            'field_customer_name': self.contact_name or self.partner_id.name,
            'field_customer_phone': self.phone or self.partner_id.phone or self.partner_id.mobile,
        }

    def _ensure_field_task(self):
        for lead in self:
            if not lead.field_task_ids:
                self.env['project.task']._create_dispatched_task({
                    **lead._field_task_values(), 'name': lead.name,
                    'project_id': self.env.ref('field_work_photos.project_field_dispatch').id,
                    'field_service_lead_id': lead.id, 'field_report_required': True,
                    'company_id': lead.company_id.id, 'user_ids': [(5, 0, 0)],
                })

    def action_dispatch_field_work(self):
        self.ensure_one()
        self._require_dispatcher()
        if not self.is_field_service or self.field_dispatch_code not in ('schedule', 'field'):
            raise ValidationError('יש להעביר את הפנייה לממתין לתיאום לפני השיבוץ.')
        self.write({'stage_id': self.env.ref('field_work_photos.stage_field_field').id})
        return self.action_open_field_task()

    def action_open_field_task(self):
        self.ensure_one()
        self.check_access('read')
        if not self.field_task_ids:
            raise ValidationError('עדיין לא נוצרה משימת שטח לפנייה.')
        return {'type': 'ir.actions.act_window', 'res_model': 'project.task', 'res_id': self.field_task_ids.id, 'view_mode': 'form'}

    def unlink(self):
        if self.field_task_ids:
            raise ValidationError('לא ניתן למחוק פנייה עם משימת שטח. ניתן לארכב אותה.')
        return super().unlink()


class ProjectTask(models.Model):
    _inherit = 'project.task'

    field_service_lead_id = fields.Many2one('crm.lead', string='פנייה מקורית', readonly=True, copy=False, index=True, ondelete='restrict', groups='base.group_user')
    field_contractor_id = fields.Many2one('res.users', string='קבלן מבצע', readonly=True, copy=False, index=True)
    field_visit_at = fields.Datetime(string='מועד ביצוע', readonly=True, copy=False)
    field_site_address = fields.Char(string='כתובת ביצוע', readonly=True, copy=False)
    field_work_description = fields.Text(string='תיאור העבודה לקבלן', readonly=True, copy=False)
    field_customer_name = fields.Char(string='שם לקוח', readonly=True, copy=False)
    field_customer_phone = fields.Char(string='טלפון לקוח', readonly=True, copy=False)

    _sql_constraints = [('field_service_lead_unique', 'unique(field_service_lead_id)', 'לפנייה כבר קיימת משימת שטח.')]

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('field_service_lead_id') for vals in vals_list):
            raise AccessError('משימה מקושרת נוצרת מתוך הפנייה בלבד.')
        return super().create(vals_list)

    @api.model
    def _create_dispatched_task(self, vals):
        return super().create([vals])

    def _lock_dispatch_work(self):
        self.check_access('write')
        leads = self.mapped('field_service_lead_id')
        if leads:
            # Every dispatched write takes locks in the same lead -> task order,
            # so a concurrent photo submission cannot race with reassignment.
            self.env.cr.execute('SELECT id FROM crm_lead WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(leads.ids)])
            self.env.cr.execute('SELECT id FROM project_task WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(self.ids)])
            self.invalidate_recordset()
            leads.invalidate_recordset()

    def _write_dispatch_details(self, vals):
        self._lock_dispatch_work()
        if any(t.field_review_state in ('pending', 'approved') for t in self):
            raise ValidationError('יש להחזיר את העבודה לתיקון לפני שינוי השיבוץ.')
        return super().write(vals)

    def write(self, vals):
        protected = DISPATCH_FIELDS | {'field_service_lead_id', 'field_customer_name', 'field_customer_phone', 'project_id', 'company_id', 'user_ids', 'name', 'active'}
        if 'field_service_lead_id' in vals or (protected.intersection(vals) and self.filtered('field_service_lead_id')):
            raise AccessError('יש לעדכן פרטי עבודה ושיבוץ דרך הפנייה המקורית.')
        self._lock_dispatch_work()
        return super().write(vals)

    def action_finish_field_work(self):
        self._lock_dispatch_work()
        return super().action_finish_field_work()

    def action_approve_field_work(self):
        self._lock_dispatch_work()
        result = super().action_approve_field_work()
        leads = self.mapped('field_service_lead_id')
        if leads:
            leads.write({'stage_id': self.env.ref('field_work_photos.stage_field_completed').id})
        return result

    def action_request_field_changes(self):
        self._lock_dispatch_work()
        result = super().action_request_field_changes()
        leads = self.mapped('field_service_lead_id')
        if leads:
            leads.write({'stage_id': self.env.ref('field_work_photos.stage_field_field').id})
        return result

    def unlink(self):
        if self.filtered('field_service_lead_id'):
            raise ValidationError('לא ניתן למחוק משימת שטח מקושרת.')
        return super().unlink()
