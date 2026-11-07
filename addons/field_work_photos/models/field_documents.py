import base64
import binascii
import io

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.pdf import PdfReaderBase, PdfReadError

from .field_collection import OPS


DOCUMENTS = {
    'quote': ('field_quote_number', 'field_quote_pdf', 'הצעת מחיר'),
    'invoice': ('field_invoice_number', 'field_invoice_pdf', 'חשבונית'),
}
MAX_PDF_BYTES = 8 * 1024 * 1024


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    field_quote_pdf = fields.Binary(string='PDF הצעת מחיר', copy=False, groups=OPS)
    field_invoice_number = fields.Char(string='מספר חשבונית', copy=False, groups=OPS, tracking=True)
    field_invoice_pdf = fields.Binary(string='PDF חשבונית', copy=False, groups=OPS)

    def _check_field_document_access(self, operation='read'):
        self._require_dispatcher()
        self.check_access(operation)
        if any(not lead.is_field_service or not lead.company_id or
               lead.company_id not in self.env.companies for lead in self):
            raise AccessError('מסמכים זמינים לעבודות שטח בחברה מורשית בלבד.')

    @api.constrains('field_quote_pdf', 'field_invoice_pdf')
    def _check_field_pdfs(self):
        self._check_field_document_access('write')
        for lead in self.with_context(bin_size=False):
            for field in ('field_quote_pdf', 'field_invoice_pdf'):
                payload = lead[field]
                if not payload:
                    continue
                if len(payload) > 4 * ((MAX_PDF_BYTES + 2) // 3):
                    raise ValidationError('גודל קובץ PDF מרבי הוא 8MB.')
                try:
                    pdf = base64.b64decode(payload, validate=True)
                    if len(pdf) > MAX_PDF_BYTES:
                        raise ValidationError('גודל קובץ PDF מרבי הוא 8MB.')
                    if not pdf.startswith(b'%PDF-') or not pdf.rstrip().endswith(b'%%EOF'):
                        raise ValueError('Invalid PDF signature')
                    reader = PdfReaderBase(io.BytesIO(pdf), strict=False)
                    if reader.is_encrypted or '/Root' not in reader.trailer:
                        raise ValueError('Encrypted or incomplete PDF')
                except (binascii.Error, PdfReadError, ValueError, TypeError, KeyError,
                        IndexError, EOFError, OverflowError, RecursionError) as error:
                    raise ValidationError('יש להעלות קובץ PDF תקין ללא סיסמה.') from error

    def _field_document_action(self, kind, download=False):
        self.ensure_one()
        self._check_field_document_access()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/field-work/documents/{self.id}/{kind}' + ('?download=1' if download else ''),
            'target': 'download' if download else 'new',
        }

    def action_preview_field_quote(self):
        return self._field_document_action('quote')

    def action_download_field_quote(self):
        return self._field_document_action('quote', download=True)

    def action_preview_field_invoice(self):
        return self._field_document_action('invoice')

    def action_download_field_invoice(self):
        return self._field_document_action('invoice', download=True)
