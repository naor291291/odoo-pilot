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
    amount_known = fields.Boolean(string='סכום הוזן', default=True, readonly=True,
        help='בחשבונית היסטורית ללא סכום מתועד נשמר המסמך בלי להמציא סכום חוב.')
    filename = fields.Char(string='שם קובץ')
    pdf = fields.Binary(string='מסמך PDF', attachment=False)
    _sql_constraints = [('work_document_number_unique', 'unique(lead_id, kind, number)', 'מספר המסמך כבר קיים בעבודה.')]

    @api.model
    def default_get(self, names):
        protected = {'company_id', 'currency_id', 'amount_known', 'create_uid', 'create_date', 'write_uid', 'write_date'}
        values = {key: value for key, value in super().default_get(names).items() if key not in protected}
        if 'amount_known' in names:
            values['amount_known'] = True
        return values

    @api.model_create_multi
    def create(self, values_list):
        return self._create_documents(values_list)

    def _create_documents(self, values_list, update_debt=True):
        if not self.env.su and not self.env.user.has_group(OPS):
            raise AccessError('רישום מסמך מחייב הרשאת תפעול.')
        prepared = []
        seen = set()
        for values in values_list:
            values = dict(values)
            if {'company_id', 'currency_id', 'create_uid', 'create_date', 'write_uid', 'write_date'}.intersection(values) or values.get('amount_known') is False:
                raise AccessError('פרטי הבקרה והחברה נשמרים אוטומטית ואינם ניתנים להזנה ישירה.')
            lead = self.env['crm.lead'].browse(values.get('lead_id')).exists()
            if len(lead) != 1:
                raise ValidationError('יש לבחור עבודה קיימת.')
            lead._check_field_document_access('write')
            lead._lock_collection()
            number = (values.get('number') or '').strip()
            amount = values.get('amount', 0)
            if not number or len(number) > 128 or not math.isfinite(amount) or amount < 0:
                raise ValidationError('יש להזין מספר מסמך תקין וסכום לא שלילי.')
            if update_debt and values.get('kind') in ('proforma', 'invoice', 'invoice_receipt') and amount <= 0:
                raise ValidationError('מסמך חיוב מחייב סכום כולל מע״מ חיובי.')
            key = (lead.id, values.get('kind'), number)
            if key in seen or self.search_count([('lead_id', '=', lead.id), ('kind', '=', values.get('kind')), ('number', '=', number)]):
                raise ValidationError('מספר המסמך כבר קיים בעבודה. לא נוצר חיוב נוסף.')
            seen.add(key)
            values['number'] = number
            values['amount'] = self.env.ref('base.ILS').round(amount)
            values['amount_known'] = not (not update_debt and values.get('kind') in ('invoice', 'invoice_receipt', 'proforma') and amount <= 0)
            prepared.append(values)
        records = super().create(prepared)
        last_billing = {doc.lead_id.id: doc.id for doc in records
                        if doc.kind in ('proforma', 'invoice', 'invoice_receipt')}
        for doc in records:
            if update_debt:
                # Keep the existing download/delivery integrations pointed at the
                # current document, while originals remain in immutable history.
                lead_values = {}
                if doc.kind in ('proforma', 'invoice', 'invoice_receipt') and last_billing[doc.lead_id.id] == doc.id:
                    # One explicit VAT-inclusive debt per work, never a sum of documents.
                    lead_values['field_customer_due'] = doc.amount
                if doc.kind in ('quote', 'invoice', 'invoice_receipt'):
                    prefix = 'field_quote' if doc.kind == 'quote' else 'field_invoice'
                    lead_values.update({prefix + '_number': doc.number,
                                        prefix + '_pdf': doc.with_context(bin_size=False).pdf,
                                        prefix + '_filename': doc.filename})
                if lead_values:
                    doc.lead_id.write(lead_values)
            doc.lead_id._message_log(body='נוסף מסמך להיסטוריית העבודה; מסמכים קודמים נשמרו.')
            if update_debt and doc.kind in ('receipt', 'invoice_receipt'):
                doc.lead_id._auto_document_stage('invoice')
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

    @api.model_create_multi
    def create(self, values_list):
        records = super().create(values_list)
        for lead in records.filtered('is_field_service'):
            lead._archive_legacy_documents()
        records._validate_registered_document_debt()
        return records

    def _validate_registered_document_debt(self):
        # A manual total must not bypass an issued bill by lowering the debt to
        # the amount already collected. Corrections remain separate documents.
        currency = self.env.ref('base.ILS')
        for lead in self.filtered('is_field_service'):
            latest = self.env['field.work.document'].sudo().search([
                ('lead_id', '=', lead.id), ('kind', 'in', ['proforma', 'invoice', 'invoice_receipt']),
                ('amount_known', '=', True)], order='id desc', limit=1)
            if latest and currency.compare_amounts(lead.field_customer_due, latest.amount):
                raise ValidationError('החוב נקבע לפי מסמך החיוב העדכני. לשינוי הסכום יש לרשום מסמך מתקן בהיסטוריה, בלי לדרוס מסמך קיים.')

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
        self._validate_registered_document_debt()
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
            self._check_collection_kind(kind)
            self._lock_collection()
            self._check_contractor_commission_payment()
        return super()._payment_dialog(kind)

    def action_approve_contractor_amount(self):
        self._check_collection_kind('contractor')
        self._lock_collection()
        self._check_contractor_commission_payment()
        return super().action_approve_contractor_amount()

    def _field_workspace_action(self, focus=None):
        action = super()._field_workspace_action(focus=focus)
        action['views'] = [(self.env.ref('field_work_photos.view_field_workcard').id, 'form')]
        return action

    def write(self, values):
        if {'partner_id', 'company_id', 'is_field_service'}.intersection(values):
            service = self.filtered('is_field_service')
            service._lock_collection()
            for lead in service:
                if (values.get('is_field_service') is False
                        or ('partner_id' in values and lead.partner_id and values['partner_id'] != lead.partner_id.id)
                        or ('company_id' in values and values['company_id'] != lead.company_id.id)):
                    if self.env['field.work.document'].sudo().search_count([('lead_id', '=', lead.id)]):
                        raise ValidationError('אין לשנות לקוח או חברה בעבודה עם מסמכים שנרשמו. יש לפתוח עבודה נפרדת ולשמור על היסטוריית המסמכים.')
        # Legacy single-PDF integrations remain available. Snapshot both old and
        # new files in an append-only register, so replacement never erases history.
        changed = set(values).intersection({'field_quote_number', 'field_quote_pdf', 'field_quote_filename',
                                           'field_invoice_number', 'field_invoice_pdf', 'field_invoice_filename'})
        documents = self.filtered(lambda lead: lead.is_field_service or any(values.get(key) for key in changed)) if changed else self.browse()
        if documents:
            documents._check_field_document_access('write')
            documents._lock_collection()
            for lead in documents:
                lead._archive_legacy_documents()
        result = super().write(values)
        if documents:
            for lead in documents:
                lead._archive_legacy_documents()
        if {'field_customer_due', 'stage_id', 'field_document_history_ids'}.intersection(values) or changed:
            self._validate_registered_document_debt()
        return result

    def _archive_legacy_documents(self, update_debt=True):
        self.ensure_one()
        for kind, prefix in [('quote', 'field_quote'), ('invoice', 'field_invoice')]:
            number = self[prefix + '_number']
            if not number:
                continue
            pdf = self.with_context(bin_size=False)[prefix + '_pdf']
            existing = self.env['field.work.document'].search([('lead_id', '=', self.id), ('kind', 'in', ['invoice', 'invoice_receipt'] if kind == 'invoice' else ['quote']), ('number', '=', number)], limit=1)
            if existing:
                if pdf:
                    self.env.cr.execute('SELECT id FROM field_work_document WHERE id = %s FOR UPDATE', [existing.id])
                    existing.invalidate_recordset(['pdf'])
                    original = existing.with_context(bin_size=False).pdf
                    if original and pdf != original:
                        raise ValidationError('אין להחליף PDF של מספר מסמך קיים. יש להוסיף מסמך חדש עם מספר חדש.')
                    if not original:
                        # One-time attachment of the issued original; no RPC write
                        # permission, identity/amount changes or replacement allowed.
                        super(FieldWorkDocument, existing.sudo()).write({'pdf': pdf, 'filename': self[prefix + '_filename']})
                        self._message_log(body='צורף PDF מקורי למסמך שנרשם בהיסטוריה.')
                continue
            # Unknown legacy amounts are archived, without inventing a debt.
            change_debt = update_debt and (kind != 'invoice' or self.field_customer_due > 0)
            self.env['field.work.document']._create_documents([{'lead_id': self.id, 'kind': kind, 'number': number,
                'amount': self.field_customer_due if kind == 'invoice' else 0,
                'pdf': pdf, 'filename': self[prefix + '_filename']}], update_debt=change_debt)


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
