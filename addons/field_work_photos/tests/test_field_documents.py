import base64
from io import BytesIO

from reportlab.pdfgen import canvas

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestFieldDocuments(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ops = new_test_user(cls.env, login='docs_ops', groups='field_work_photos.group_field_dispatcher')
        cls.contractor = new_test_user(cls.env, login='docs_portal', groups='field_work_photos.group_field_contractor')
        cls.lead = cls.env['crm.lead'].with_user(cls.ops).create({
            'name': 'Synthetic documents', 'is_field_service': True, 'company_id': cls.env.company.id,
        })
        cls.documents = {}
        for kind in ('quote', 'invoice'):
            stream = BytesIO()
            pdf = canvas.Canvas(stream)
            pdf.drawString(20, 20, kind)
            pdf.save()
            cls.documents[kind] = stream.getvalue()

    def test_document_files_and_numbers_are_independent(self):
        self.lead.write({
            'field_quote_number': 'Q-123', 'field_invoice_number': 'I-456',
            'field_quote_pdf': base64.b64encode(self.documents['quote']),
            'field_invoice_pdf': base64.b64encode(self.documents['invoice']),
        })
        self.assertEqual(base64.b64decode(self.lead.field_quote_pdf), self.documents['quote'])
        self.assertEqual(base64.b64decode(self.lead.field_invoice_pdf), self.documents['invoice'])
        self.assertEqual(self.lead.field_dispatch_code, 'new')
        self.assertEqual(self.lead.field_customer_paid, 0)
        duplicate = self.lead.copy()
        self.assertFalse(duplicate.field_quote_pdf or duplicate.field_invoice_pdf or duplicate.field_invoice_number)

    def test_invalid_pdf_is_rejected_without_replacing_existing_document(self):
        original = base64.b64encode(self.documents['invoice'])
        self.lead.field_invoice_pdf = original
        for invalid in (b'fake PDF', b'%PDF-1.4\ninvalid contents\n%%EOF'):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.lead.field_invoice_pdf = base64.b64encode(invalid)
        self.assertEqual(self.lead.field_invoice_pdf, original)

    def test_preview_and_download_require_internal_company_access(self):
        self.lead.field_quote_pdf = base64.b64encode(self.documents['quote'])
        path = self.lead.action_preview_field_quote()['url']
        self.assertNotEqual(self.url_open(path, allow_redirects=False).status_code, 200)
        self.authenticate(self.ops.login, self.ops.login)
        response = self.url_open(path)
        self.assertEqual(response.content, self.documents['quote'])
        self.assertEqual(response.headers['Content-Type'], 'application/pdf')
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertIn('inline', response.headers['Content-Disposition'])
        response = self.url_open(self.lead.action_download_field_quote()['url'])
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.authenticate(self.contractor.login, self.contractor.login)
        self.assertEqual(self.url_open(path, allow_redirects=False).status_code, 404)
        for native in (
            f'/web/content/crm.lead/{self.lead.id}/field_quote_pdf',
            f'/web/image/crm.lead/{self.lead.id}/field_quote_pdf',
        ):
            self.assertNotEqual(self.url_open(native).content, self.documents['quote'])
        company = self.env['res.company'].create({'name': 'Separate document company'})
        other = new_test_user(self.env, login='docs_other_company',
                              groups='field_work_photos.group_field_dispatcher',
                              company_id=company.id, company_ids=[(6, 0, company.ids)])
        with self.assertRaises(AccessError):
            self.lead.with_user(other).action_preview_field_quote()
        self.authenticate(other.login, other.login)
        self.assertEqual(self.url_open(path, allow_redirects=False).status_code, 404)
