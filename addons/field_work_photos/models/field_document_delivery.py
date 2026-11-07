import base64
import hashlib
import re
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import email_normalize

from .field_collection import OPS
from .field_delivery_provider import (
    DeliveryRejected, channel_mode, company_enabled, phone_digits, send_email, send_whatsapp, setting,
)
from .field_documents import DOCUMENTS


DOCUMENT_TYPES = [(kind, values[2]) for kind, values in DOCUMENTS.items()]
CHANNELS = [('email', 'דואר אלקטרוני'), ('whatsapp', 'וואטסאפ')]
DELIVERY_STAGES = {'quote': ('sent', 'schedule', 'field', 'completed', 'paid'), 'invoice': ('paid',)}


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    field_delivery_attempt_ids = fields.One2many(
        'field.work.delivery.attempt', 'lead_id', string='יומן שליחת מסמכים',
        copy=False, readonly=True, groups=OPS,
    )
    field_whatsapp_opt_in = fields.Boolean(string='הלקוח הסכים לקבל מסמכים בוואטסאפ', copy=False, groups=OPS)
    field_whatsapp_event_id = fields.Char(copy=False, readonly=True, groups='base.group_system')

    _sql_constraints = [
        ('field_whatsapp_event_unique', 'unique(field_whatsapp_event_id)', 'הפנייה מוואטסאפ כבר נקלטה.'),
    ]

    def _delivery_document(self, kind):
        number_field, pdf_field, _ = DOCUMENTS[kind]
        number = ' '.join((self[number_field] or '').split())
        payload = self.with_context(bin_size=False)[pdf_field]
        return number, base64.b64decode(payload) if payload else b''

    def _delivery_recipient(self, channel):
        partner = self.partner_id
        if not partner:
            return ''
        if channel == 'email':
            return email_normalize(partner.email or '', strict=True) or ''
        return phone_digits(partner.mobile or partner.phone or self.phone) if self.field_whatsapp_opt_in else ''

    def _enqueue_document_delivery(self, kind):
        for lead in self:
            if not company_enabled(self.env, lead.company_id) or lead.field_dispatch_code not in DELIVERY_STAGES[kind]:
                continue
            channels = [channel for channel, _ in CHANNELS if channel_mode(channel) in ('test', 'live')]
            if not channels:
                continue
            lead._lock_collection()
            number, pdf = lead._delivery_document(kind)
            if not number or not pdf:
                continue
            digest = hashlib.sha256(pdf).hexdigest()
            attempts = self.env['field.work.delivery.attempt'].sudo().with_context({})
            for channel in channels:
                key = hashlib.sha256(f'{kind}:{channel}:{number}:{digest}'.encode()).hexdigest()
                if attempts.search_count([('lead_id', '=', lead.id), ('delivery_key', '=', key)], limit=1):
                    continue
                lead._create_delivery_attempt(kind, channel, number, digest, key)

    def _create_delivery_attempt(self, kind, channel, number, digest, key):
        _, subject, message = self._delivery_message(kind, channel, number)
        recipient = self._delivery_recipient(channel)
        return self.env['field.work.delivery.attempt'].sudo().with_context({}).create({
            'lead_id': self.id, 'company_id': self.company_id.id, 'document_kind': kind,
            'document_number': number, 'channel': channel, 'delivery_key': key,
            'document_digest': digest, 'recipient': recipient, 'delivery_mode': channel_mode(channel),
            'subject': subject, 'message': message, 'status': 'queued' if recipient else 'failed',
            'result_note': False if recipient else 'חסר נמען תקין או אישור לשליחה בוואטסאפ.',
        })

    def _delivery_message(self, kind, channel, number):
        _, _, label = DOCUMENTS[kind]
        subject = f'{label} מספר {number}' if channel == 'email' else False
        greeting = f'שלום {self.partner_id.name or "רב"},'
        body = f'{greeting}\nמצורפת {label} מספר {number} עבור העבודה ״{self.name}״.\nתודה, {self.company_id.name}'
        return number, subject, body

    def _auto_document_stage(self, kind):
        for lead in self.filtered(lambda job: job.is_field_service and job.active):
            if setting('AUTO_STAGES') != '1' or not company_enabled(self.env, lead.company_id):
                continue
            if kind == 'quote' and lead.field_dispatch_code == 'quote':
                number, pdf = DOCUMENTS['quote'][:2]
                if (lead[number] or '').strip() and lead.with_context(bin_size=True)[pdf] and not lead._field_progress_missing('sent'):
                    lead.action_next_field_stage()
            elif kind == 'invoice' and lead.field_dispatch_code == 'completed' and lead.field_collection_status == 'paid':
                number, pdf = DOCUMENTS['invoice'][:2]
                if (lead[number] or '').strip() and lead.with_context(bin_size=True)[pdf]:
                    lead.action_close_field_work()

    def write(self, vals):
        monitored = {'stage_id', 'field_customer_due', *(field for doc in DOCUMENTS.values() for field in doc[:2])}
        if not monitored.intersection(vals) or setting('DELIVERY_DB') != self.env.cr.dbname:
            return super().write(vals)
        before = {lead.id: lead.field_dispatch_code for lead in self if lead.is_field_service}
        result = super().write(vals)
        for lead in self.filtered(lambda job: job.is_field_service and job.active):
            for kind, (number, pdf, _) in DOCUMENTS.items():
                changed = number in vals or pdf in vals
                entered_quote = kind == 'quote' and lead.field_dispatch_code == 'quote' and before.get(lead.id) == 'new'
                if changed or entered_quote or (kind == 'invoice' and 'field_customer_due' in vals):
                    lead._auto_document_stage(kind)
                entered_sent = kind == 'quote' and lead.field_dispatch_code == 'sent' and before.get(lead.id) == 'quote'
                if changed or entered_sent:
                    lead._enqueue_document_delivery(kind)
        return result

    def action_close_field_work(self):
        result = super().action_close_field_work()
        self._enqueue_document_delivery('invoice')
        return result


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
    status = fields.Selection([
        ('simulated', 'סימולציה בלבד'), ('queued', 'ממתין לשליחה'), ('sending', 'שליחה בתהליך'),
        ('accepted', 'הספק קיבל לשליחה'), ('delivered', 'נמסר'), ('failed', 'נכשל'),
        ('unknown', 'נדרש בירור עם הספק'), ('superseded', 'הפרטים השתנו לפני השליחה'),
    ], string='סטטוס', required=True)
    subject = fields.Char(string='נושא')
    message = fields.Text(string='נוסח ההודעה', required=True)
    simulation_id = fields.Integer()
    delivery_key = fields.Char(index=True, groups='base.group_system')
    document_digest = fields.Char(groups='base.group_system')
    recipient = fields.Char(groups='base.group_system')
    delivery_mode = fields.Selection([('test', 'בדיקה'), ('live', 'פעיל')], groups='base.group_system')
    provider_id = fields.Char(index=True, groups='base.group_system')
    result_note = fields.Char(string='תוצאת השליחה')

    _sql_constraints = [
        ('unique_simulation', 'unique(simulation_id)', 'הסימולציה כבר תועדה.'),
        ('unique_document_channel', 'unique(lead_id, delivery_key)', 'המסמך כבר תועד בערוץ הזה.'),
    ]

    def action_retry_delivery(self):
        self.ensure_one()
        self.check_access('read')
        lead = self.lead_id
        lead._check_field_document_access('write')
        lead._lock_collection()
        self.invalidate_recordset()
        attempt = self.sudo()
        key = f'retry:{self.id}'
        number, pdf = lead._delivery_document(self.document_kind)
        if (self.status not in ('failed', 'superseded') or not company_enabled(self.env, self.company_id)
                or lead.company_id != self.company_id or channel_mode(self.channel) != attempt.delivery_mode
                or lead.field_dispatch_code not in DELIVERY_STAGES[self.document_kind]
                or number != self.document_number or hashlib.sha256(pdf).hexdigest() != attempt.document_digest
                or not lead._delivery_recipient(self.channel)):
            raise ValidationError('אפשר לנסות שוב רק לאחר תיקון הנמען או ההגדרות, כשהמסמך המקורי עדיין בתוקף.')
        if not attempt.search_count([('lead_id', '=', lead.id), ('delivery_key', '=', key)], limit=1):
            lead._create_delivery_attempt(self.document_kind, self.channel, number, attempt.document_digest, key)
        return {'type': 'ir.actions.act_window_close'}

    def _deliver(self):
        self.ensure_one()
        lead = self.lead_id
        if (not company_enabled(self.env, self.company_id) or channel_mode(self.channel) != self.delivery_mode
                or lead.company_id != self.company_id or not lead.active
                or lead.field_dispatch_code not in DELIVERY_STAGES[self.document_kind]):
            return 'superseded', 'החברה, שלב העבודה או מצב השליחה השתנו.', ''
        number, pdf = lead._delivery_document(self.document_kind)
        if (number != self.document_number or hashlib.sha256(pdf).hexdigest() != self.document_digest
                or lead._delivery_recipient(self.channel) != self.recipient):
            return 'superseded', 'המסמך, הנמען או ההסכמה לשליחה השתנו.', ''
        if self.delivery_mode == 'test':
            allowed = setting(self.channel.upper() + '_TEST_RECIPIENT').strip()
            if not allowed or allowed.casefold() != self.recipient.casefold():
                return 'failed', 'מצב בדיקה מאפשר שליחה רק לנמען הניסוי המוגדר.', ''
        filename = 'quote.pdf' if self.document_kind == 'quote' else 'invoice.pdf'
        try:
            provider_id = (send_email(self.recipient, self.subject, self.message, filename, pdf)
                           if self.channel == 'email' else
                           send_whatsapp(self.document_kind, self.recipient, number, filename, pdf))
        except DeliveryRejected as error:
            return 'failed', str(error), ''
        except Exception:
            # An interruption after SMTP DATA / Graph POST can have delivered.
            return 'unknown', 'לא התקבל אישור ודאי. יש לבדוק אצל הספק לפני שליחה נוספת.', ''
        return 'accepted', 'הספק קיבל את ההודעה לשליחה.', provider_id

    @api.model
    def _cron_deliver(self):
        if setting('DELIVERY_DB') != self.env.cr.dbname:
            return
        company = setting('DELIVERY_COMPANY')
        if not company.isdecimal():
            return
        domain = [('company_id', '=', int(company))]
        self.sudo().search(domain + [
            ('status', '=', 'sending'), ('write_date', '<', fields.Datetime.now() - timedelta(minutes=30)),
        ]).write({'status': 'unknown', 'result_note': 'השליחה נקטעה. יש לבדוק אצל הספק לפני שליחה נוספת.'})
        ids = self.sudo().search(domain + [('status', '=', 'queued')], limit=6, order='id').ids
        for attempt_id in ids:
            # The claim commits before contacting a provider. An interrupted
            # worker never resends an attempt with an uncertain outcome.
            with self.pool.cursor() as cr:
                cr.execute("""UPDATE field_work_delivery_attempt
                              SET status = 'sending', write_date = (now() AT TIME ZONE 'UTC')
                              WHERE id = %s AND status = 'queued' RETURNING id""", [attempt_id])
                if not cr.fetchone():
                    continue
                cr.commit()
                attempt = api.Environment(cr, self.env.uid, {})[self._name].sudo().browse(attempt_id)
                status, note, provider_id = attempt._deliver()
                attempt.write({'status': status, 'result_note': note, 'provider_id': provider_id or False})


class FieldWorkPayment(models.Model):
    _inherit = 'field.work.payment'

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        payments.filtered(lambda payment: payment.kind == 'customer').lead_id._auto_document_stage('invoice')
        return payments


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def action_approve_field_work(self):
        result = super().action_approve_field_work()
        self.field_service_lead_id._auto_document_stage('invoice')
        return result


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
        number_field, _, _ = DOCUMENTS[self.document_kind]
        number = (lead[number_field] or '').strip()
        return lead._delivery_message(self.document_kind, self.channel, number)

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
