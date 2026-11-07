import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import email_normalize

from .field_collection import OPS
from .field_documents import DOCUMENTS


DOCUMENT_TYPES = [(kind, values[2]) for kind, values in DOCUMENTS.items()]
CHANNELS = [('email', 'דואר אלקטרוני'), ('whatsapp', 'וואטסאפ')]


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    field_delivery_attempt_ids = fields.One2many(
        'field.work.delivery.attempt', 'lead_id', string='יומן סימולציות מסמכים',
        copy=False, readonly=True, groups=OPS,
    )

    def _field_delivery_dialog(self, kind):
        self.ensure_one()
        self._check_field_document_access('write')
        return {
            'type': 'ir.actions.act_window', 'name': 'סימולציית שליחת מסמך',
            'res_model': 'field.work.delivery.simulation', 'views': [(False, 'form')],
            'target': 'new', 'context': {'default_lead_id': self.id, 'default_document_kind': kind},
        }

    def action_simulate_field_quote(self):
        return self._field_delivery_dialog('quote')

    def action_simulate_field_invoice(self):
        return self._field_delivery_dialog('invoice')


class FieldWorkDeliveryAttempt(models.Model):
    _name = 'field.work.delivery.attempt'
    _description = 'יומן ניסיונות שליחת מסמכי עבודות שטח'
    _order = 'create_date desc, id desc'

    lead_id = fields.Many2one('crm.lead', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True)
    document_kind = fields.Selection(DOCUMENT_TYPES, string='סוג מסמך', required=True)
    document_number = fields.Char(string='מספר מסמך', required=True)
    channel = fields.Selection(CHANNELS, string='ערוץ', required=True)
    status = fields.Selection([('simulated', 'סימולציה בלבד')], string='סטטוס', required=True)
    subject = fields.Char(string='נושא')
    message = fields.Text(string='נוסח ההודעה', required=True)
    simulation_id = fields.Integer(required=True)

    _sql_constraints = [
        ('unique_simulation', 'unique(simulation_id)', 'הסימולציה כבר תועדה.'),
    ]


class FieldWorkDeliverySimulation(models.TransientModel):
    _name = 'field.work.delivery.simulation'
    _description = 'סימולציית שליחת מסמך'

    lead_id = fields.Many2one('crm.lead', string='עבודה', required=True, readonly=True)
    document_kind = fields.Selection(DOCUMENT_TYPES, string='מסמך', required=True, readonly=True)
    channel = fields.Selection(CHANNELS, string='ערוץ', required=True, default='email')
    subject = fields.Char(compute='_compute_message', string='נושא')
    message = fields.Text(compute='_compute_message', string='נוסח ההודעה')

    def write(self, values):
        if {'lead_id', 'document_kind'} & values.keys():
            raise AccessError('כדי לדמות מסמך אחר, פתחו סימולציה חדשה מכרטיס העבודה.')
        return super().write(values)

    def _render_message(self):
        self.ensure_one()
        lead = self.lead_id
        lead._check_field_document_access()
        number_field, _, label = DOCUMENTS[self.document_kind]
        number = (lead[number_field] or '').strip()
        subject = f'{label} מספר {number}' if self.channel == 'email' else False
        greeting = f'שלום {lead.partner_id.name or "רב"},'
        body = f'{greeting}\nמצורפת {label} מספר {number} עבור העבודה ״{lead.name}״.\nתודה, {lead.company_id.name}'
        return number, subject, body

    @api.depends('lead_id', 'document_kind', 'channel')
    def _compute_message(self):
        for wizard in self:
            wizard.subject = False
            wizard.message = False
            if wizard.lead_id and wizard.document_kind and wizard.channel:
                _, wizard.subject, wizard.message = wizard._render_message()

    def action_apply(self):
        self.ensure_one()
        self.check_access('write')
        lead = self.lead_id
        lead._lock_collection()
        lead._check_field_document_access('write')
        attempts = self.env['field.work.delivery.attempt']
        if not attempts.search_count([('simulation_id', '=', self.id)], limit=1):
            number, subject, message = self._render_message()
            pdf_field = DOCUMENTS[self.document_kind][1]
            if not number or not lead.with_context(bin_size=True)[pdf_field]:
                raise ValidationError('השלימו מספר מסמך והעלו קובץ PDF לפני הפעלת הסימולציה.')
            if self.channel == 'email':
                valid_recipient = email_normalize(lead.partner_id.email or '')
            else:
                phone = lead.partner_id.mobile or lead.phone or lead.partner_id.phone or ''
                valid_recipient = 8 <= len(re.sub(r'[^0-9]', '', phone)) <= 15
            if not valid_recipient:
                raise ValidationError('השלימו כתובת מייל או מספר טלפון תקין ללקוח, בהתאם לערוץ שנבחר.')
            # The pilot's simulated provider records the rendered payload only.
            # No recipient address, mail queue, HTTP request, or external adapter.
            attempts.sudo().with_context({}).create({
                'lead_id': lead.id, 'company_id': lead.company_id.id,
                'document_kind': self.document_kind, 'document_number': number,
                'channel': self.channel, 'status': 'simulated', 'subject': subject,
                'message': message, 'simulation_id': self.id,
            })
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': 'הסימולציה תועדה',
                'message': 'לא נשלחה הודעה ללקוח.',
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
