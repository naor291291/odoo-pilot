import base64
from copy import deepcopy
from io import BytesIO
from unittest.mock import Mock, patch

from PIL import Image
from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged, new_test_user

from ..services.morning_api import MorningError


CLIENT = '11111111-1111-4111-8111-111111111111'
DOC = '22222222-2222-4222-8222-222222222222'
OTHER = '33333333-3333-4333-8333-333333333333'


@tagged('post_install', '-at_install')
class TestMorningImport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ops = new_test_user(cls.env, login='morning_ops', groups='field_work_photos.group_field_dispatcher')
        cls.contractor = new_test_user(cls.env, login='morning_contractor', groups='field_work_photos.group_field_contractor')
        cls.connection = cls.env['field.morning.connection'].create({
            'name': 'Test sandbox', 'environment': 'sandbox', 'enabled': True,
            'client_id': 'fake-key', 'client_secret': 'fake-secret',
        })

    def setUp(self):
        super().setUp()
        self.client_data = {'id': CLIENT, 'name': 'לקוח ניסיון', 'active': True,
                            'phone': '0501234567', 'emails': ['customer@example.test'],
                            'address': 'כתובת חיוב 10', 'city': 'תל אביב', 'zip': '1234567',
                            'country': 'IL', 'taxId': '123456789', 'contactPerson': 'איש קשר'}
        self.document_data = {'id': DOC, 'type': 10, 'number': 1001, 'status': 0,
                              'documentDate': '2026-10-30', 'currency': 'ILS',
                              'amount': 1180, 'vat': 180, 'client': {'id': CLIENT}}
        self.service = Mock()
        self.service.search_clients.side_effect = lambda *a, **k: {'items': [deepcopy(self.client_data)], 'pages': 1}
        self.service.get_client.side_effect = lambda *a, **k: deepcopy(self.client_data)
        self.service.search_documents.side_effect = lambda *a, **k: {'items': [deepcopy(self.document_data)], 'pages': 1}
        self.service.get_document.side_effect = lambda *a, **k: deepcopy(self.document_data)
        self.service.get_document_links.return_value = {'origin': 'https://example.test/document.pdf'}
        patcher = patch.object(type(self.connection), '_api', return_value=self.service)
        self.mock_api = patcher.start()
        self.addCleanup(patcher.stop)

    def lead(self, **values):
        return self.env['crm.lead'].with_user(self.ops).create({
            'name': 'עבודת ניסיון מורנינג', 'is_field_service': True,
            'field_site_address': 'כתובת ביצוע אחרת 20', **values,
        })

    def wizard(self, lead, mode='customer'):
        action = lead.action_morning_customer() if mode == 'customer' else lead.action_morning_documents()
        return self.env['field.morning.import'].with_user(self.ops).browse(action['res_id'])

    def link_customer(self, lead):
        wizard = self.wizard(lead)
        wizard.query = 'לקוח'
        wizard.action_search()
        wizard.result_ids.action_select()
        return lead.field_morning_customer_id

    def linked_lead(self):
        lead = self.lead()
        self.link_customer(lead)
        return lead

    def link_document(self, lead):
        wizard = self.wizard(lead, 'document')
        wizard.kind = str(self.document_data['type'])
        wizard.action_search()
        wizard.result_ids.action_select()
        return lead.field_morning_document_ids

    def test_connection_defaults_to_disabled_sandbox(self):
        other = self.env['res.company'].create({'name': 'Default sandbox company'})
        connection = self.env['field.morning.connection'].create({'company_id': other.id})
        self.assertFalse(connection.enabled)
        self.assertEqual(connection.environment, 'sandbox')

    def test_disabled_connection_keeps_manual_workflow(self):
        self.connection.enabled = False
        lead = self.lead(field_quote_number='MANUAL-1', field_sale_amount=1000)
        with self.assertRaises(UserError):
            lead.action_morning_customer()
        self.mock_api.assert_not_called()
        lead.write({'field_quote_number': 'MANUAL-2', 'field_sale_amount': 1500})
        self.assertEqual(lead.field_quote_number, 'MANUAL-2')

    def test_import_creates_customer_and_preserves_site_address(self):
        lead = self.linked_lead()
        partner = lead.partner_id
        self.assertEqual(partner.name, self.client_data['name'])
        self.assertEqual(partner.street, self.client_data['address'])
        self.assertEqual(lead.phone, self.client_data['phone'])
        self.assertEqual(lead.field_site_address, 'כתובת ביצוע אחרת 20')
        self.assertEqual(lead.field_dispatch_code, 'new')

    def test_existing_customer_details_are_not_overwritten(self):
        partner = self.env['res.partner'].create({'name': 'Existing name', 'phone': '0520000000',
                                                  'email': 'keep@example.test', 'street': 'Keep street'})
        lead = self.lead(partner_id=partner.id, phone='0530000000')
        # Native CRM synchronizes the lead phone to the partner on lead creation.
        # Capture the state before Morning import, which must preserve that state.
        previous_partner_phone, previous_lead_phone = partner.phone, lead.phone
        mapping = self.link_customer(lead)
        self.assertEqual(mapping.partner_id, partner)
        self.assertEqual(partner.name, 'Existing name')
        self.assertEqual(partner.phone, previous_partner_phone)
        self.assertEqual(partner.email, 'keep@example.test')
        self.assertEqual(partner.street, 'Keep street')
        self.assertFalse(partner.city)
        self.assertEqual(lead.phone, previous_lead_phone)

    def test_repeat_import_reuses_customer_and_link(self):
        lead = self.linked_lead()
        mapping, partner = lead.field_morning_customer_id, lead.partner_id
        self.link_customer(lead)
        self.assertEqual(lead.partner_id, partner)
        self.assertEqual(lead.field_morning_customer_id, mapping)
        self.assertEqual(self.env['field.morning.customer'].search_count([('connection_id', '=', self.connection.id)]), 1)

    def test_remote_customer_cannot_link_to_second_existing_partner(self):
        self.linked_lead()
        partner = self.env['res.partner'].create({'name': 'Different customer'})
        lead = self.lead(partner_id=partner.id)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.link_customer(lead)
        self.assertFalse(lead.field_morning_customer_id)

    def test_inactive_or_wrong_customer_response_is_rejected(self):
        lead = self.lead()
        wizard = self.wizard(lead)
        wizard.query = 'לקוח'
        wizard.action_search()
        for values in ({'id': OTHER}, {'active': False}):
            original = deepcopy(self.client_data)
            self.client_data.update(values)
            with self.assertRaises(ValidationError), self.cr.savepoint():
                wizard.result_ids.action_select()
            self.client_data = original
        self.assertFalse(lead.partner_id)

    def test_document_requires_explicit_customer_link(self):
        with self.assertRaises(UserError):
            self.lead().action_morning_documents()

    def test_document_links_without_changing_amount_stage_or_payment(self):
        lead = self.linked_lead()
        document = self.link_document(lead)
        self.assertEqual(document.net_amount, 1000)
        self.assertEqual(document.total_amount, 1180)
        self.assertEqual(lead.field_sale_amount, 0)
        self.assertEqual(lead.field_dispatch_code, 'new')
        self.assertEqual(lead.field_quote_number, '1001')

    def test_linking_quote_preserves_existing_manual_number(self):
        lead = self.linked_lead()
        lead.field_quote_number = 'MANUAL-123'
        self.link_document(lead)
        self.assertEqual(lead.field_quote_number, 'MANUAL-123')

    def test_reimport_document_refreshes_same_link(self):
        lead = self.linked_lead()
        document = self.link_document(lead)
        self.document_data['amount'] = 2360
        self.document_data['vat'] = 360
        self.assertEqual(self.link_document(lead), document)
        self.assertEqual(document.net_amount, 2000)
        self.assertEqual(lead.field_sale_amount, 0)

    def test_same_document_cannot_be_linked_to_two_jobs(self):
        first = self.linked_lead()
        self.link_document(first)
        second = self.lead(partner_id=first.partner_id.id)
        self.link_customer(second)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.link_document(second)
        self.assertFalse(second.field_morning_document_ids)

    def test_wrong_customer_document_is_rejected_at_search_and_link(self):
        lead = self.linked_lead()
        wizard = self.wizard(lead, 'document')
        wizard.action_search()
        self.document_data['client'] = {'id': OTHER}
        with self.assertRaises(ValidationError), self.cr.savepoint():
            wizard.result_ids.action_select()
        with self.assertRaises(UserError), self.cr.savepoint():
            wizard.action_search()
        self.assertFalse(lead.field_morning_document_ids)

    def test_browser_preview_is_not_trusted(self):
        lead = self.linked_lead()
        wizard = self.wizard(lead, 'document')
        wizard.action_search()
        wizard.result_ids.write({'total_amount': .01, 'name': 'forged preview'})
        wizard.result_ids.action_select()
        self.assertEqual(lead.field_morning_document_ids.total_amount, 1180)

    def test_refresh_failure_preserves_stored_snapshot(self):
        document = self.link_document(self.linked_lead())
        original = document.synced_at
        self.service.get_document.side_effect = MorningError('Unavailable')
        with self.assertRaises(UserError), self.cr.savepoint():
            document.action_refresh()
        self.assertEqual(document.total_amount, 1180)
        self.assertEqual(document.synced_at, original)

    def test_refresh_marks_cancellation_without_changing_workflow(self):
        lead = self.linked_lead()
        document = self.link_document(lead)
        self.document_data['status'] = 4
        document.action_refresh()
        self.assertEqual(document.status, '4')
        self.assertEqual(lead.field_dispatch_code, 'new')
        with self.assertRaises(ValidationError):
            document.action_apply_amount()

    def test_invalid_amount_or_date_does_not_create_document(self):
        for values in ({'amount': float('nan')}, {'vat': None}, {'documentDate': 'bad-date'}):
            lead = self.linked_lead()
            original = deepcopy(self.document_data)
            self.document_data.update(values)
            with self.assertRaises(UserError), self.cr.savepoint():
                self.link_document(lead)
            self.assertFalse(lead.field_morning_document_ids)
            self.document_data = original

    def test_amount_application_is_explicit_and_does_not_advance_stage(self):
        lead = self.linked_lead()
        document = self.link_document(lead)
        document.action_apply_amount()
        self.assertEqual(lead.field_sale_amount, 1000)
        self.assertEqual(lead.field_dispatch_code, 'new')

    def test_receipts_and_foreign_currency_cannot_replace_job_price(self):
        for values in ({'type': 400}, {'currency': 'USD'}):
            lead = self.linked_lead()
            original = deepcopy(self.document_data)
            self.document_data.update(values)
            self.document_data['id'] = OTHER if values.get('type') else DOC
            document = self.link_document(lead)
            with self.assertRaises(ValidationError):
                document.action_apply_amount()
            self.assertEqual(lead.field_sale_amount, 0)
            self.document_data = original

    def test_pending_review_keeps_price_locked(self):
        lead = self.linked_lead()
        document = self.link_document(lead)
        lead.write({'field_sale_amount': 1000, 'field_work_description': 'Test work',
                    'field_execution_type': 'direct', 'field_worker_id': self.ops.id,
                    'field_visit_at': fields.Datetime.now()})
        for _ in range(4):
            lead.action_next_field_stage()
        stream = BytesIO()
        Image.new('RGB', (8, 8), 'green').save(stream, 'PNG')
        image = base64.b64encode(stream.getvalue())
        lead.field_task_ids.write({'field_before_image': image, 'field_after_image': image,
                                    'field_visit_summary': 'Work completed'})
        lead.field_task_ids.action_finish_field_work()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            document.action_apply_amount()

    def test_remove_link_keeps_original_and_manual_quote_number(self):
        lead = self.linked_lead()
        document = self.link_document(lead)
        document.action_remove_link()
        self.assertFalse(lead.field_morning_document_ids)
        self.assertEqual(lead.field_quote_number, '1001')
        self.service.get_document.assert_called_once()

    def test_partner_change_requires_removing_document_links(self):
        lead = self.linked_lead()
        self.link_document(lead)
        partner = self.env['res.partner'].create({'name': 'Other customer'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.partner_id = partner
        lead.field_morning_document_ids.action_remove_link()
        lead.partner_id = partner
        self.assertFalse(lead.field_morning_customer_id)

    def test_manual_metadata_forgery_is_blocked(self):
        lead = self.linked_lead()
        document = self.link_document(lead)
        for record, values in ((document, {'total_amount': 1}),
                               (lead.field_morning_customer_id, {'remote_id': OTHER}),
                               (lead, {'field_morning_customer_id': False})):
            with self.assertRaises(AccessError), self.cr.savepoint():
                record.write(values)
        with self.assertRaises(AccessError):
            self.env['field.morning.document'].with_user(self.ops).create({'number': 'forged'})

    def test_operations_cannot_read_keys_or_change_connection(self):
        connection = self.connection.with_user(self.ops)
        for field in ('client_id', 'client_secret'):
            with self.assertRaises(AccessError):
                connection.read([field])
        self.assertNotIn('client_secret', connection.fields_get())
        with self.assertRaises(AccessError):
            connection.write({'enabled': False})
        with self.assertRaises(AccessError):
            connection.action_test()

    def test_contractors_cannot_access_imports_or_documents(self):
        lead = self.linked_lead()
        document = self.link_document(lead)
        with self.assertRaises(AccessError):
            lead.with_user(self.contractor).action_morning_customer()
        with self.assertRaises(AccessError):
            document.with_user(self.contractor).read(['number'])
        with self.assertRaises(AccessError):
            document.with_user(self.contractor).action_open_pdf()

    def test_cannot_change_environment_or_key_after_linking(self):
        self.linked_lead()
        for values in ({'environment': 'production'}, {'client_id': 'other-business-key'}):
            with self.assertRaises(ValidationError):
                self.connection.write(values)
        self.connection.write({'company_id': self.connection.company_id.id, 'client_secret': 'rotated-fake-secret'})
        self.assertEqual(self.connection.client_secret, 'rotated-fake-secret')

    def test_other_company_connection_and_documents_are_hidden(self):
        company = self.env['res.company'].create({'name': 'Other Morning company'})
        foreign = self.env['field.morning.connection'].create({'company_id': company.id})
        self.assertFalse(self.env['field.morning.connection'].with_user(self.ops).search([('id', '=', foreign.id)]))
        with self.assertRaises(AccessError):
            foreign.with_user(self.ops).read(['environment'])
        lead = self.lead()
        with self.assertRaises(AccessError):
            lead.with_context(allowed_company_ids=[company.id]).action_morning_customer()

    def test_pdf_is_fresh_and_invalid_urls_are_rejected(self):
        document = self.link_document(self.linked_lead())
        action = document.action_open_pdf()
        self.assertEqual(action['url'], 'https://example.test/document.pdf')
        for value in ('javascript:alert(1)', 'http://example.test', 'https://user:secret@example.test/doc'):
            self.service.get_document_links.return_value = {'origin': value}
            with self.assertRaises(UserError):
                document.action_open_pdf()
        self.document_data['client'] = {'id': OTHER}
        with self.assertRaises(ValidationError):
            document.action_open_pdf()

    def test_pagination_and_empty_results(self):
        wizard = self.wizard(self.lead())
        wizard.query = 'לקוח'
        self.service.search_clients.side_effect = lambda *a, **k: {'items': [deepcopy(self.client_data)], 'pages': 2}
        wizard.action_search()
        self.assertTrue(wizard.has_more)
        wizard.action_next_page()
        self.assertEqual(wizard.page, 2)
        self.assertFalse(wizard.has_more)
        self.service.search_clients.side_effect = lambda *a, **k: {'items': [], 'pages': 0}
        wizard.action_search()
        self.assertFalse(wizard.result_ids)
        self.assertEqual(wizard.message, 'לא נמצאו תוצאות.')

    def test_import_wizard_and_inherited_work_form_are_valid(self):
        lead = self.lead()
        for mode in ('customer', 'document'):
            if mode == 'document':
                self.link_customer(lead)
            wizard = self.wizard(lead, mode)
            with Form(wizard, view='field_work_photos.view_morning_import_form'):
                pass
        with Form(lead, view='field_work_photos.view_field_lead_form'):
            pass
