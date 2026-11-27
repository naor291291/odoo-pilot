"""Two-screen work card, immutable document register and scoped contractor enrolment."""
import base64
import binascii
import io
import math

from odoo import api, fields, models, Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import email_normalize
from odoo.tools.pdf import PdfReaderBase, PdfReadError

from .field_collection import OPS, OWNER
from .field_documents import MAX_PDF_BYTES


class FieldWorkDocument(models.Model):
    _name = 'field.work.document'
    _description = 'היסטוריית מסמכי עבודה'
    _order = 'id desc'
    _rec_name = 'number'

    lead_id = fields.Many2one('crm.lead', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(related='lead_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='lead_id.field_pricing_currency_id')
    kind = fields.Selection([('quote', 'הצעת מחיר'), ('proforma', 'חשבון עסקה'),
                             ('invoice', 'חשבונית מס'), ('receipt', 'קבלה'),
                             ('invoice_receipt', 'חשבונית מס קבלה')], required=True, string='סוג מסמך')
    number = fields.Char(required=True, string='מספר מסמך')
    amount = fields.Monetary(currency_field='currency_id', string='סכום כולל מע״מ')
    filename = fields.Char(string='שם קובץ')
    pdf = fields.Binary(string='מסמך PDF', attachment=False)
    _sql_constraints = [('work_document_number_unique', 'unique(lead_id, kind, number)', 'מספר המסמך כבר קיים בעבודה.')]

    @api.model_create_multi
    def create(self, values_list):
        return self._create_documents(values_list)

    def _create_documents(self, values_list, update_debt=True):
        if not self.env.su and not self.env.user.has_group(OPS):
            raise AccessError('רישום מסמך מחייב הרשאת תפעול.')
        prepared = []
        for values in values_list:
            values = dict(values)
            lead = self.env['crm.lead'].browse(values.get('lead_id')).exists()
            if len(lead) != 1:
                raise ValidationError('יש לבחור עבודה קיימת.')
            lead._check_field_document_access('write')
            lead._lock_collection()
            number = (values.get('number') or '').strip()
            amount = values.get('amount', 0)
            if not number or len(number) > 128 or not math.isfinite(amount) or amount < 0:
                raise ValidationError('יש להזין מספר מסמך תקין וסכום לא שלילי.')
            if values.get('kind') in ('proforma', 'invoice', 'invoice_receipt') and amount <= 0:
                raise ValidationError('מסמך חיוב מחייב סכום כולל מע״מ חיובי.')
            values['number'] = number
            values['amount'] = self.env.ref('base.ILS').round(amount)
            prepared.append(values)
        records = super().create(prepared)
        for doc in records:
            if update_debt and doc.kind in ('proforma', 'invoice', 'invoice_receipt'):
                # One debt per work, not one debt per fiscal document. The amount
                # is entered explicitly including VAT; never infer a VAT rate.
                doc.lead_id.write({'field_customer_due': doc.amount})
            doc.lead_id._message_log(body='נוסף מסמך להיסטוריית העבודה; מסמכים קודמים נשמרו.')
        return records

    @api.constrains('pdf')
    def _validate_pdf(self):
        for doc in self.with_context(bin_size=False):
            if not doc.pdf:
                continue
            try:
                if len(doc.pdf) > 4 * ((MAX_PDF_BYTES + 2) // 3):
                    raise ValueError()
                raw = base64.b64decode(doc.pdf, validate=True)
                if len(raw) > MAX_PDF_BYTES or not raw.startswith(b'%PDF-') or not raw.rstrip().endswith(b'%%EOF'):
                    raise ValueError()
                reader = PdfReaderBase(io.BytesIO(raw), strict=False)
                if reader.is_encrypted or '/Root' not in reader.trailer:
                    raise ValueError()
            except (binascii.Error, PdfReadError, ValueError, TypeError, KeyError, IndexError, EOFError, OverflowError, RecursionError) as error:
                raise ValidationError('יש לצרף PDF תקין ללא סיסמה, עד 8MB.') from error

    def write(self, values):
        raise AccessError('מסמך שנרשם אינו ניתן לשינוי. יש להוסיף מסמך מתקן להיסטוריה.')

    def unlink(self):
        raise AccessError('אין למחוק מסמכי עבודה שנרשמו.')


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    field_document_history_ids = fields.One2many('field.work.document', 'lead_id', string='היסטוריית מסמכים', groups=OPS, copy=False)

    def _field_progress_missing(self, target_code):
        # Internal statuses remain for reports. Quotation numbering must no longer
        # force users through a sequence of screens before they can schedule work.
        missing = super()._field_progress_missing(target_code)
        return [item for item in missing if item != 'מספר הצעת מחיר ממורנינג']

    def action_workcard_dispatch(self):
        self.ensure_one()
        self._lock_collection()
        if self.field_dispatch_code in ('completed', 'paid'):
            raise ValidationError('יש להחזיר את הביצוע לתיקון לפני שינוי שיבוץ שאושר.')
        while self.field_dispatch_code in ('new', 'quote', 'sent', 'schedule'):
            self.action_next_field_stage()
        return True

    def action_workcard_setup(self):
        self.ensure_one()
        self._lock_collection()
        if not self.partner_id or not (self.field_site_address or '').strip() or not (self.field_work_description or '').strip():
            raise ValidationError('יש להשלים לקוח, כתובת ביצוע ותיאור העבודה.')
        return {'type': 'ir.actions.act_window', 'res_model': 'crm.lead', 'res_id': self.id,
                'views': [(self.env.ref('field_work_photos.view_field_workcard').id, 'form')], 'target': 'current'}

    @api.constrains('stage_id', 'field_document_history_ids')
    def _check_workcard_receipt(self):
        for lead in self:
            if lead.is_field_service and lead.field_dispatch_code == 'paid':
                if not self.env['field.work.document'].sudo().search_count([
                    ('lead_id', '=', lead.id), ('kind', 'in', ['receipt', 'invoice_receipt'])]):
                    raise ValidationError('סגירת עבודה מחייבת מספר קבלה או חשבונית מס קבלה בהיסטוריית המסמכים.')

    def action_close_field_work(self):
        self._lock_collection()
        if not self.env['field.work.document'].search_count([
                ('lead_id', 'in', self.ids), ('kind', 'in', ['receipt', 'invoice_receipt'])]):
            raise ValidationError('לפני הסגירה יש לרשום קבלה או חשבונית מס קבלה.')
        return super().action_close_field_work()

    def _check_contractor_commission_payment(self):
        # Check the base, even when reimbursement makes the total positive.
        if any(lead.field_execution_type == 'subcontractor' and lead.sudo().field_commission_base < 0 for lead in self):
            raise ValidationError('בסיס העמלה שלילי. נדרשת החלטה עסקית לפני רישום תשלום לקבלן.')

    def _payment_dialog(self, kind):
        if kind == 'contractor':
            self._check_contractor_commission_payment()
        return super()._payment_dialog(kind)

    def action_approve_contractor_amount(self):
        self._check_contractor_commission_payment()
        return super().action_approve_contractor_amount()

    def _field_workspace_action(self, focus=None):
        action = super()._field_workspace_action(focus=focus)
        action['views'] = [(self.env.ref('field_work_photos.view_field_workcard').id, 'form')]
        return action

    def write(self, values):
        # Legacy single-PDF integrations remain available. Snapshot both old and
        # new files in an append-only register, so replacement never erases history.
        changed = set(values).intersection({'field_quote_number', 'field_quote_pdf', 'field_quote_filename',
                                           'field_invoice_number', 'field_invoice_pdf', 'field_invoice_filename'})
        if changed:
            self._check_field_document_access('write')
            self._lock_collection()
            for lead in self:
                lead._archive_legacy_documents()
        result = super().write(values)
        if changed:
            for lead in self:
                lead._archive_legacy_documents()
        return result

    def _archive_legacy_documents(self, update_debt=True):
        self.ensure_one()
        for kind, prefix in [('quote', 'field_quote'), ('invoice', 'field_invoice')]:
            number = self[prefix + '_number']
            if not number:
                continue
            pdf = self.with_context(bin_size=False)[prefix + '_pdf']
            existing = self.env['field.work.document'].search([('lead_id', '=', self.id), ('kind', '=', kind), ('number', '=', number)], limit=1)
            if existing:
                if pdf and existing.with_context(bin_size=False).pdf and pdf != existing.with_context(bin_size=False).pdf:
                    raise ValidationError('אין להחליף PDF של מספר מסמך קיים. יש להוסיף מסמך חדש עם מספר חדש.')
                continue
            # Old invoices had no explicit document amount. Do not invent a debt.
            if kind == 'invoice' and self.field_customer_due <= 0:
                continue
            self.env['field.work.document']._create_documents([{'lead_id': self.id, 'kind': kind, 'number': number,
                'amount': self.field_customer_due if kind == 'invoice' else 0,
                'pdf': pdf, 'filename': self[prefix + '_filename']}], update_debt=update_debt)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_enrol_field_contractor(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group(OWNER):
            raise AccessError('הקמת קבלן מחייבת הרשאת תמחור ורווחיות.')
        self.check_access('write')
        if self.company_id and self.company_id not in self.env.companies:
            raise AccessError('איש הקשר אינו בחברה מורשית.')
        self.env.cr.execute('SELECT id FROM res_partner WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset(['email', 'company_id'])
        email = email_normalize(self.email or '')
        if not email:
            raise ValidationError('יש להזין כתובת דוא״ל תקינה של הקבלן.')
        # Scoped elevation only after checking the source partner. Never accepts
        # arbitrary group IDs, login, company or user payloads from RPC/context.
        users = self.env['res.users'].sudo().with_context(active_test=False).search([
            '|', ('partner_id', '=', self.id), ('login', '=ilike', email)])
        if len(users) > 1 or (users and (users.partner_id != self or not users.share or not users.active)):
            raise ValidationError('קיים חשבון אחר או חשבון פנימי. מנהל המערכת צריך לבדוק את הזהות; לא נוצרה כפילות.')
        group = self.env.ref('field_work_photos.group_field_contractor')
        if users:
            if users.company_id not in self.env.companies or any(company not in self.env.companies for company in users.company_ids):
                raise AccessError('חשבון הפורטל משויך לחברה שאינה מורשית.')
            if users.has_group('base.group_public'):
                raise ValidationError('אין להסב משתמש ציבורי לקבלן.')
            users.write({'groups_id': [Command.link(group.id)]})
        else:
            company = self.company_id or self.env.company
            users = self.env['res.users'].sudo().with_context({}, no_reset_password=True).create({
                'name': self.name, 'login': email, 'email': email, 'partner_id': self.id,
                'company_id': company.id, 'company_ids': [Command.set([company.id])],
                'groups_id': [Command.set([group.id, self.env.ref('base.group_portal').id])],
                'lang': 'he_IL' if self.env['res.lang'].search_count([('code', '=', 'he_IL'), ('active', '=', True)]) else self.env.user.lang,
            })
        self._message_log(body='הופעלה גישת פורטל קבלנים מוגבלת. הגדרת סיסמה מתבצעת בערוץ מאובטח; לא נשלחה הזמנה אוטומטית.')
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': 'הקבלן מוכן לשיבוץ', 'message': 'נוצרה גישת פורטל מוגבלת. הגדרת סיסמה באמצעות מנהל המערכת.',
            'type': 'success', 'sticky': True}}
