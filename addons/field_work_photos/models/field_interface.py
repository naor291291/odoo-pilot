"""Presentation context and native Odoo workspace navigation."""
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

OPS = 'field_work_photos.group_field_dispatcher'


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    field_workspace_summary = fields.Char(compute='_compute_workspace_context', groups=OPS)
    field_workspace_title = fields.Char(compute='_compute_workspace_context', groups=OPS)
    field_next_step = fields.Char(compute='_compute_workspace_context', groups=OPS)

    @api.depends('name', 'partner_id.name', 'field_site_address', 'field_dispatch_code',
                 'field_report_state', 'field_visit_result', 'field_collection_status')
    def _compute_workspace_context(self):
        for lead in self:
            lead.field_workspace_title = lead.name or 'עבודה חדשה'
            lead.field_workspace_summary = ' · '.join(value for value in (
                lead.partner_id.name, lead.field_site_address) if value) or 'פרטי הלקוח והכתובת יופיעו כאן לאחר מילוי התכנון.'
            code = lead.field_dispatch_code
            text = {
                'new': 'מלאו את פרטי הלקוח והעבודה, ואז המשיכו להכנת הצעת המחיר.',
                'quote': 'הזינו את סכום העסקה ומספר ההצעה שנשלחה ללקוח בלשונית תכנון.',
                'sent': 'לאחר אישור הלקוח להצעה, המשיכו לתיאום המבצע והמועד.',
                'schedule': 'בחרו מבצע וקבעו מועד בלשונית תכנון, ואז אשרו את השיבוץ.',
                'field': 'המבצע מדווח מהשטח. הדיווח והתמונות זמינים בלשונית ביצוע.',
                'completed': 'הביצוע אושר. המשיכו לרישום התקבולים בלשונית גבייה.',
                'paid': 'העבודה נסגרה. הדיווח והתשלומים זמינים לעיון בכרטיס.',
            }.get(code, '')
            if code == 'field' and lead.field_report_state == 'pending':
                text = ('פתחו את לשונית ביצוע, בדקו את סיבת אי־ההשלמה והחזירו להמשך טיפול.'
                        if lead.field_visit_result in ('followup', 'not_done') else
                        'בדקו את הסיכום והתמונות בלשונית ביצוע, ואז אשרו או החזירו לתיקון.')
            elif code == 'field' and lead.field_report_state == 'changes_requested':
                text = 'העבודה הוחזרה לתיקון. ההנחיה והדיווח המעודכן זמינים בלשונית ביצוע.'
            elif code == 'completed':
                if lead.field_collection_status == 'unset':
                    text = 'הביצוע אושר. הזינו את הסכום הכולל לתשלום בלשונית גבייה.'
                elif lead.field_collection_status == 'paid':
                    text = 'הביצוע אושר וכל הסכום התקבל. אפשר לסגור את העבודה בלשונית גבייה.'
            lead.field_next_step = text

    def _field_workspace_action(self, focus=None):
        self.ensure_one()
        self._require_dispatcher()
        self.check_access('read')
        if not self.is_field_service:
            raise ValidationError('כרטיס זה מיועד לעבודות שטח בלבד.')
        if not focus:
            focus = ('execution' if self.field_dispatch_code == 'field' else
                     'collection' if self.field_dispatch_code in ('completed', 'paid') else 'planning')
        views = {'planning': 'view_field_lead_form', 'execution': 'view_field_lead_execution_focus',
                 'collection': 'view_field_lead_collection_focus', 'finance': 'view_field_lead_finance_focus'}
        if focus not in views:
            raise ValidationError('אזור העבודה אינו קיים.')
        if focus == 'finance' and not (self.env.su or self.env.user.has_group('field_work_photos.group_field_finance')):
            raise AccessError('עלויות והתחשבנות קבלן זמינות לבעלים בלבד.')
        return {'type': 'ir.actions.act_window', 'res_model': 'crm.lead', 'res_id': self.id,
                'views': [(self.env.ref('field_work_photos.' + views[focus]).id, 'form')], 'target': 'current'}

    def action_open_field_workspace(self):
        return self._field_workspace_action()
