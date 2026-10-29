from functools import partial

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.osv import expression


VISIT_FIELDS = {'field_visit_result', 'field_visit_summary', 'field_visit_reason', 'field_visit_notes'}


class ProjectTask(models.Model):
    _inherit = 'project.task'

    field_visit_result = fields.Selection([
        ('completed', 'הושלם'), ('followup', 'נדרש המשך'), ('not_done', 'לא בוצע'),
    ], string='תוצאת הביקור', default='completed', copy=False, tracking=True)
    field_visit_summary = fields.Text(string='מה בוצע בפועל?', copy=False, tracking=True)
    field_visit_reason = fields.Text(string='מה מנע השלמה ומה נדרש להמשך?', copy=False, tracking=True)
    field_visit_notes = fields.Text(string='הערות נוספות', copy=False, tracking=True)
    # The existing images remain the first photo in each gallery. No migration
    # or copying of historical photos is needed; up to four extras follow each.
    field_extra_photo_ids = fields.One2many('field.work.photo', 'task_id', string='תמונות נוספות', copy=False)

    def _check_visit_editable(self):
        self.check_access('write')
        self._lock_dispatch_work()
        standalone = self.filtered(lambda t: not t.field_service_lead_id)
        if standalone:
            self.env.cr.execute('SELECT id FROM project_task WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(standalone.ids)])
            standalone.invalidate_recordset()
        if any(t.field_review_state not in ('draft', 'changes_requested') or t.state == '1_canceled' for t in self):
            raise ValidationError('הדיווח והתמונות נעולים בזמן הבדיקה ולאחר אישור.')

    def write(self, vals):
        if VISIT_FIELDS.intersection(vals) or 'field_extra_photo_ids' in vals:
            self._check_visit_editable()
        for name in VISIT_FIELDS.intersection(vals):
            if vals[name] and len(vals[name]) > 4000:
                raise ValidationError('אורך שדה דיווח מרבי הוא 4,000 תווים.')
        result = super().write(vals)
        if {'field_before_image', 'field_after_image', 'field_extra_photo_ids'}.intersection(vals):
            self._check_gallery_limits()
        return result

    def _check_gallery_limits(self):
        for task in self:
            for kind in ('before', 'after'):
                extras = task.field_extra_photo_ids.filtered(lambda p: p.kind == kind)
                if len(extras) > 4:
                    raise ValidationError('אפשר לשמור עד 5 תמונות בכל אזור: לפני ואחרי ביצוע.')
                if extras and not task['field_%s_image' % kind]:
                    raise ValidationError('יש לשמור תמונה ראשונה לפני הוספת תמונות נוספות.')

    def _field_gallery(self, kind):
        self.ensure_one()
        items = [{'key': '%s:0' % kind, 'id': 0}] if self['field_%s_image' % kind] else []
        return items + [{'key': '%s:%s' % (kind, p.id), 'id': p.id}
                        for p in self.field_extra_photo_ids.filtered(lambda p: p.kind == kind)]

    def _update_field_gallery(self, uploads, removals):
        self.ensure_one()
        self._check_visit_editable()
        available = {item['key'] for kind in ('before', 'after') for item in self._field_gallery(kind)}
        if not set(removals).issubset(available):
            raise ValidationError('נבחרה להסרה תמונה שאינה שייכת לעבודה הזאת. רענן את הדף.')
        # Validate the final counts before making any changes. The controller
        # wraps the entire report in one savepoint, including these removals.
        for kind in ('before', 'after'):
            if len(self._field_gallery(kind)) - sum(k.startswith(kind + ':') for k in set(removals)) + len(uploads[kind]) > 5:
                raise ValidationError('אפשר לשמור עד 5 תמונות בכל אזור: לפני ואחרי ביצוע.')
        for key in set(removals):
            kind, photo_id = key.split(':')
            if photo_id != '0':
                self.field_extra_photo_ids.filtered(lambda p: p.id == int(photo_id)).unlink()
        for kind in ('before', 'after'):
            name = 'field_%s_image' % kind
            if '%s:0' % kind in removals:
                next_photo = self.field_extra_photo_ids.filtered(lambda p: p.kind == kind)[:1]
                value = next_photo.image if next_photo else False
                next_photo.unlink()
                self.write({name: value})
            for image in uploads[kind]:
                if not self[name]:
                    self.write({name: image})
                else:
                    self.env['field.work.photo'].create({'task_id': self.id, 'kind': kind, 'image': image})

    def action_finish_field_work(self):
        self._lock_dispatch_work()
        for task in self.filtered('field_service_lead_id'):
            if not task.field_visit_result:
                raise ValidationError('יש לבחור תוצאת ביקור לפני שליחת הדיווח.')
            if task.field_visit_result == 'completed' and not (task.field_visit_summary or '').strip():
                raise ValidationError('יש לתאר בקצרה מה בוצע בפועל.')
            if task.field_visit_result != 'completed' and not (task.field_visit_reason or '').strip():
                raise ValidationError('יש להסביר מה מנע השלמה ומה נדרש להמשך.')
        return super().action_finish_field_work()

    def action_approve_field_work(self):
        self._lock_dispatch_work()
        if any(t.field_visit_result in ('followup', 'not_done') for t in self):
            raise ValidationError('הביקור לא הושלם. יש להחזיר להמשך טיפול ולתאם את העבודה; אי אפשר לאשר השלמת ביצוע.')
        return super().action_approve_field_work()


class FieldWorkPhoto(models.Model):
    _name = 'field.work.photo'
    _description = 'תמונת תיעוד נוספת לעבודת שטח'
    _order = 'id'
    _rec_name = 'kind'

    task_id = fields.Many2one('project.task', required=True, ondelete='cascade', index=True)
    kind = fields.Selection([('before', 'לפני ביצוע'), ('after', 'אחרי ביצוע')], required=True)
    image = fields.Image(required=True, attachment=False, max_width=1920, max_height=1920, verify_resolution=True)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        if not self.env.su:
            domain = expression.AND([domain, [('task_id', 'in', self.env['project.task']._search([]))]])
        return super()._search(domain, offset=offset, limit=limit, order=order)

    def _check_access(self, operation):
        result = super()._check_access(operation)
        if result or not self:
            return result
        tasks = self.sudo().mapped('task_id').with_env(self.env)
        forbidden = tasks.filtered(lambda t: not t.has_access('read' if operation == 'read' else 'write'))
        if forbidden:
            return self, partial(AccessError, 'אין גישה לתמונות העבודה הזאת.')
        return None

    @api.model_create_multi
    def create(self, vals_list):
        tasks = self.env['project.task'].browse([v.get('task_id') for v in vals_list if v.get('task_id')])
        tasks._check_visit_editable()
        for vals in vals_list:
            self.env['project.task']._validate_field_image_values({'field_before_image': vals.get('image')})
        records = super().create(vals_list)
        tasks._check_gallery_limits()
        return records

    def write(self, vals):
        self.check_access('write')
        if {'task_id', 'kind'}.intersection(vals):
            raise AccessError('אי אפשר להעביר תמונה לעבודה או לאזור אחר. יש להסיר ולהעלות מחדש.')
        self.mapped('task_id')._check_visit_editable()
        self.env['project.task']._validate_field_image_values({'field_before_image': vals.get('image')})
        return super().write(vals)

    def unlink(self):
        self.check_access('unlink')
        self.mapped('task_id')._check_visit_editable()
        return super().unlink()
