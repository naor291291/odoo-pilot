import base64
from io import BytesIO

from lxml import etree
from reportlab.pdfgen import canvas

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class TestPilotFeedback(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ops = new_test_user(cls.env, login='feedback_ops', groups='field_work_photos.group_field_dispatcher')
        cls.owner = new_test_user(cls.env, login='feedback_owner', groups='field_work_photos.group_field_finance')
        cls.portal = new_test_user(cls.env, login='feedback_portal', groups='field_work_photos.group_field_contractor')
        cls.customer = cls.env['res.partner'].create({'name': 'Synthetic customer', 'street': 'Test 1', 'city': 'Test city'})
        stream = BytesIO()
        pdf = canvas.Canvas(stream); pdf.drawString(20, 20, 'Synthetic'); pdf.save()
        cls.pdf = base64.b64encode(stream.getvalue())

    def lead(self, **values):
        return self.env['crm.lead'].with_user(self.ops).create({'name': 'Synthetic work', 'is_field_service': True,
                 'company_id': self.env.company.id, **values})

    def test_field_action_creation_defaults(self):
        action = self.env.ref('field_work_photos.action_field_service_leads')
        lead = self.env['crm.lead'].with_user(self.ops).with_context(**safe_eval(action.context)).create({'name': 'Action work'})
        self.assertTrue(lead.is_field_service)
        self.assertEqual(lead.team_id, self.env.ref('field_work_photos.team_field_service'))
        self.assertEqual(lead.field_dispatch_code, 'new')
        lead.write({'field_quote_pdf': self.pdf})
        lead._lock_collection()

    def test_ordinary_opportunity_empty_documents_remain_editable(self):
        lead = self.env['crm.lead'].with_user(self.ops).create({'name': 'Ordinary', 'field_quote_pdf': False, 'field_invoice_pdf': False})
        lead.write({'field_quote_pdf': False})
        self.assertFalse(lead.is_field_service)
        with self.assertRaises(AccessError), self.cr.savepoint():
            lead.write({'field_quote_pdf': self.pdf})
        with self.assertRaisesRegex(ValidationError, 'לוח עבודות'):
            lead._lock_collection()
        self.assertFalse(lead.is_field_service)

    def test_document_filenames_are_separate_from_payload(self):
        lead = self.lead(field_quote_pdf=self.pdf, field_quote_filename='synthetic-quote.pdf',
                         field_invoice_pdf=self.pdf, field_invoice_filename='synthetic-invoice.pdf')
        lead.invalidate_recordset()
        self.assertEqual(lead.field_quote_filename, 'synthetic-quote.pdf')
        self.assertEqual(lead.field_invoice_filename, 'synthetic-invoice.pdf')
        self.assertEqual(lead.field_quote_pdf, self.pdf)
        self.assertEqual(self.lead(field_quote_pdf=self.pdf).field_quote_filename, 'quote.pdf')
        self.assertNotEqual(lead.copy().field_quote_filename, 'synthetic-quote.pdf')

    def test_pdf_size_limit_is_unchanged(self):
        with self.assertRaisesRegex(ValidationError, '8MB'), self.cr.savepoint():
            self.lead(field_quote_pdf=base64.b64encode(b'x' * (8 * 1024 * 1024 + 1)))

    def test_permissions_and_company_boundaries(self):
        lead = self.lead()
        for method in ('_check_field_document_access', '_lock_collection'):
            with self.assertRaises(AccessError):
                getattr(lead.with_user(self.portal), method)()
        other = self.env['res.company'].create({'name': 'Synthetic other company'})
        user = new_test_user(self.env, login='feedback_other', groups='field_work_photos.group_field_dispatcher',
                             company_id=other.id, company_ids=[(6, 0, other.ids)])
        with self.assertRaises(AccessError):
            lead.with_user(user)._check_field_document_access()
        with self.assertRaises((AccessError, ValidationError)):
            lead.with_user(user)._lock_collection()
        with self.assertRaises(AccessError):
            lead._check_collection_kind('contractor')
        lead.with_user(self.owner)._check_collection_kind('contractor')

    def test_address_on_create_and_explicit_override(self):
        self.assertEqual(self.lead(partner_id=self.customer.id).field_site_address, 'Test 1, Test city')
        self.assertEqual(self.lead(partner_id=self.customer.id, field_site_address='Manual').field_site_address, 'Manual')
        self.assertFalse(self.lead(partner_id=self.customer.id, field_site_address=False).field_site_address)

    def test_address_onchange_preserves_manual_input(self):
        lead = self.env['crm.lead'].new({'is_field_service': True, 'partner_id': self.customer.id})
        lead._onchange_field_site_address()
        self.assertEqual(lead.field_site_address, 'Test 1, Test city')
        lead.field_site_address = 'Manual address'
        lead.partner_id = False
        lead._onchange_field_site_address()
        self.assertEqual(lead.field_site_address, 'Manual address')
        lead.partner_id = self.customer
        lead._onchange_field_site_address()
        self.assertEqual(lead.field_site_address, 'Manual address')

    def test_ordinary_address_is_not_changed(self):
        lead = self.env['crm.lead'].new({'partner_id': self.customer.id})
        lead._onchange_field_site_address()
        self.assertFalse(lead.field_site_address)

    def test_contractor_creation_does_not_elevate_dispatcher_or_finance(self):
        lead = self.lead()
        for user in (self.ops, self.owner, self.portal):
            with self.assertRaises(AccessError):
                lead.with_user(user).action_create_field_contractor()

    def test_admin_contractor_action_creates_portal_only(self):
        lead = self.lead().with_user(self.env.ref('base.user_admin'))
        action = lead.action_create_field_contractor()
        user = self.env['res.users'].with_user(self.env.ref('base.user_admin')).with_context(**action['context']).create({
            'name': 'Synthetic new contractor', 'login': 'feedback_new_contractor'})
        self.assertTrue(user.share)
        self.assertTrue(user.has_group('field_work_photos.group_field_contractor'))
        self.assertFalse(user.has_group('field_work_photos.group_field_finance'))
        self.assertFalse(user.has_group('base.group_user'))
        self.assertEqual(user.company_ids, lead.company_id)
        self.assertTrue(action['context']['no_reset_password'])
        for name, value in [('field_rate_small', 70), ('field_rate_medium', 65), ('field_rate_large', 50)]:
            self.assertEqual(user.partner_id[name], value)
        with self.assertRaises(AccessError):
            user.partner_id.with_user(self.ops).read(['field_rate_small'])

    def test_client_language_default_is_scoped_and_optional(self):
        hebrew = self.env['res.lang'].with_context(active_test=False).search([('code', '=', 'he_IL')])
        hebrew.active = True
        model = self.env['res.partner'].with_user(self.ops)
        self.assertEqual(model.with_context(default_field_crm_client=True).default_get(['lang'])['lang'], 'he_IL')
        self.assertEqual(model.with_context(default_field_crm_client=True, default_lang='en_US').default_get(['lang'])['lang'], 'en_US')
        self.assertEqual(model.with_context(default_lang='en_US').default_get(['lang'])['lang'], 'en_US')

    def test_field_currency_does_not_change_company_or_amounts(self):
        company = self.env.company
        original = company.currency_id
        lead = self.lead(field_sale_amount=123.45)
        self.assertEqual(lead.field_pricing_currency_id, self.env.ref('base.ILS'))
        self.assertEqual(lead.field_sale_amount, 123.45)
        self.assertEqual(company.currency_id, original)

    def test_compiled_field_view_labels_filenames_and_finance_visibility(self):
        result = self.env['crm.lead'].with_user(self.ops).get_view(
            self.env.ref('field_work_photos.view_field_lead_form').id, 'form')
        root = etree.fromstring(result['arch'].encode())
        for kind in ('quote', 'invoice'):
            nodes = root.xpath(f"//field[@name='field_{kind}_pdf']")
            self.assertTrue(nodes)
            self.assertTrue(all(n.get('filename') == f'field_{kind}_filename' for n in nodes))
        self.assertTrue(root.xpath("//field[@name='name'][@string='תיאור הפנייה / סוג עבודה']"))
        for name in ('field_material_cost', 'field_gross_profit', 'field_contractor_cost'):
            self.assertFalse(root.xpath(f"//field[@name='{name}']"))
        self.assertFalse(root.xpath("//field[@name='expected_revenue']"))
