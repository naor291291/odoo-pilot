import base64
import hashlib
import hmac
from io import BytesIO
import json
import os
from unittest.mock import patch

from PIL import Image
from reportlab.pdfgen import canvas

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

from ..controllers.field_whatsapp import verified_signature


@tagged('post_install', '-at_install')
class TestFieldPilotMetrics(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = new_test_user(cls.env, login='metrics_owner', groups='field_work_photos.group_field_finance')
        cls.ops = new_test_user(cls.env, login='metrics_ops', groups='field_work_photos.group_field_dispatcher')
        cls.portal = new_test_user(cls.env, login='metrics_portal', groups='field_work_photos.group_field_contractor')
        cls.customer = cls.env['res.partner'].create({
            'name': 'Synthetic metrics customer', 'email': 'metrics@example.com', 'phone': '0500000000',
        })
        stream = BytesIO()
        pdf = canvas.Canvas(stream)
        pdf.drawString(20, 20, 'Synthetic fixture')
        pdf.save()
        cls.pdf = base64.b64encode(stream.getvalue())

    def lead(self, **values):
        return self.env['crm.lead'].with_user(self.owner).create({
            'name': 'Synthetic metrics work', 'is_field_service': True,
            'company_id': self.env.company.id, 'partner_id': self.customer.id, 'phone': '0500000000',
            'field_site_address': 'Fixture address', 'field_work_description': 'Fixture description',
            'field_execution_type': 'direct', 'field_quote_number': 'Q-FIXTURE',
            'field_sale_amount': 1000, 'field_customer_due': 1180, 'field_material_cost': 300,
            **values,
        })

    def wizard(self, lead, kind='quote', channel='email'):
        return self.env['field.work.delivery.simulation'].with_user(self.ops).create({
            'lead_id': lead.id, 'document_kind': kind, 'channel': channel,
        })

    def test_dashboard_uses_current_company_stages_and_active_customer_receipts(self):
        accepted = self.lead()
        for _ in range(3):
            accepted.action_next_field_stage()
        offered = self.lead(field_sale_amount=500)
        for _ in range(2):
            offered.action_next_field_stage()
        offered.active = False
        foreign = self.env['res.company'].create({'name': 'Separate metrics company'})
        self.owner.company_ids |= foreign
        other = self.lead(company_id=foreign.id, field_sale_amount=3000)
        for _ in range(3):
            other.action_next_field_stage()
        payments = self.env['field.work.payment'].with_user(self.ops)
        payments.create({'lead_id': accepted.id, 'amount': 300, 'reference': 'ACTIVE', 'method': 'cash'})
        voided = payments.create({'lead_id': accepted.id, 'amount': 200, 'reference': 'VOID', 'method': 'cash'})
        voided._cancel_registration('Synthetic cancellation')
        Dashboard = self.env['field.work.owner.dashboard'].with_user(self.owner)
        board = Dashboard.browse(Dashboard.action_open()['res_id'])
        self.assertEqual((board.sale_total, board.receipt_total, board.estimated_profit), (1000, 300, 700))
        self.assertEqual((board.estimated_margin, board.quoted_count, board.accepted_count, board.conversion), (70, 2, 1, 50))
        self.assertIn('o_field_owner_trends', board.trends)
        self.assertIn('300.00 ₪', board.trends)
        self.assertIn('700.00 ₪', board.trends)
        self.assertIn('50.00 %', board.trends)

    def test_dashboard_rejects_operations_and_portal(self):
        Dashboard = self.env['field.work.owner.dashboard']
        for user in (self.ops, self.portal):
            with self.assertRaises(AccessError):
                Dashboard.with_user(user).action_open()
            with self.assertRaises(AccessError):
                Dashboard.with_user(user).create({})

    def test_both_simulated_channels_log_hebrew_without_email_or_stage_changes(self):
        lead = self.lead(field_quote_pdf=self.pdf, field_invoice_number='I-FIXTURE', field_invoice_pdf=self.pdf)
        quote = self.wizard(lead)
        invoice = self.wizard(lead, 'invoice', 'whatsapp')
        Mail = self.env['mail.mail'].sudo()
        before = Mail.search_count([])
        self.assertIn('הצעת מחיר', quote.subject)
        self.assertIn('חשבונית', invoice.message)
        quote.action_apply()
        quote.action_apply()
        invoice.action_apply()
        attempts = lead.with_user(self.ops).field_delivery_attempt_ids
        self.assertEqual(len(attempts), 2)
        self.assertEqual(set(attempts.mapped('status')), {'simulated'})
        self.assertEqual(set(attempts.mapped('channel')), {'email', 'whatsapp'})
        self.assertEqual(set(attempts.mapped('document_number')), {'Q-FIXTURE', 'I-FIXTURE'})
        self.assertEqual(attempts.create_uid, self.ops)
        self.assertEqual(Mail.search_count([]), before)
        self.assertEqual(lead.field_dispatch_code, 'new')
        self.assertEqual(lead.field_customer_paid, 0)

    def test_simulation_rejects_missing_pdf_or_recipient_without_attempt(self):
        lead = self.lead()
        wizard = self.wizard(lead)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            wizard.action_apply()
        lead.field_quote_pdf = self.pdf
        self.customer.email = False
        with self.assertRaises(ValidationError), self.cr.savepoint():
            wizard.action_apply()
        self.assertFalse(lead.field_delivery_attempt_ids)

    def test_simulation_history_cannot_be_forged_or_read_by_contractors(self):
        lead = self.lead(field_quote_pdf=self.pdf)
        wizard = self.wizard(lead)
        wizard.action_apply()
        attempt = lead.with_user(self.ops).field_delivery_attempt_ids
        with self.assertRaises(AccessError), self.cr.savepoint():
            attempt.write({'document_number': 'FORGED'})
        with self.assertRaises(AccessError), self.cr.savepoint():
            attempt.with_user(self.portal).read(['message'])
        with self.assertRaises(AccessError), self.cr.savepoint():
            attempt.with_user(self.ops).copy()
        with self.assertRaises(AccessError), self.cr.savepoint():
            wizard.with_user(self.portal).action_apply()

    def delivery_config(self, **values):
        return patch.dict(os.environ, {
            'FIELD_WORK_DELIVERY_DB': self.env.cr.dbname, 'FIELD_WORK_DELIVERY_COMPANY': str(self.env.company.id),
            'FIELD_WORK_AUTO_STAGES': '1', 'FIELD_WORK_EMAIL_MODE': 'test', 'FIELD_WORK_WHATSAPP_MODE': 'test',
            'FIELD_WORK_EMAIL_TEST_RECIPIENT': 'metrics@example.com', 'FIELD_WORK_WHATSAPP_TEST_RECIPIENT': '972500000000',
            **values,
        })

    def test_quote_queues_one_per_channel_and_does_not_send_during_write(self):
        lead = self.lead(field_whatsapp_opt_in=True)
        with self.delivery_config(), patch('odoo.addons.field_work_photos.models.field_document_delivery.send_email') as email, \
                patch('odoo.addons.field_work_photos.models.field_document_delivery.send_whatsapp', return_value='wamid.test') as whatsapp:
            lead.action_next_field_stage()
            self.assertEqual(lead.field_dispatch_code, 'quote')
            lead.field_quote_pdf = self.pdf
            self.assertEqual(lead.field_dispatch_code, 'sent')
            lead.field_quote_pdf = self.pdf
            attempts = lead.field_delivery_attempt_ids.sudo()
            self.assertEqual(len(attempts), 2)
            self.assertEqual(set(attempts.mapped('status')), {'queued'})
            email.assert_not_called()
            whatsapp.assert_not_called()
            for attempt in attempts:
                self.assertEqual(attempt._deliver()[0], 'accepted')
            self.assertEqual(email.call_args.args[-1], base64.b64decode(self.pdf))
            self.assertEqual(whatsapp.call_args.args[-1], base64.b64decode(self.pdf))
            lead.action_previous_field_stage()
            self.assertEqual(lead.field_dispatch_code, 'quote')

    def test_test_mode_and_consent_gate_delivery_and_allow_audited_retry(self):
        lead = self.lead(field_quote_pdf=self.pdf)
        with self.delivery_config(FIELD_WORK_EMAIL_TEST_RECIPIENT='allowed@example.com'), \
                patch('odoo.addons.field_work_photos.models.field_document_delivery.send_email') as email:
            lead.action_next_field_stage()
            attempts = lead.field_delivery_attempt_ids.sudo()
            self.assertEqual(len(attempts), 2)
            blocked = attempts.filtered(lambda attempt: attempt.channel == 'whatsapp')
            self.assertEqual(blocked.status, 'failed')
            self.assertEqual(attempts.filtered(lambda attempt: attempt.channel == 'email')._deliver()[0], 'failed')
            email.assert_not_called()
            lead.field_whatsapp_opt_in = True
            blocked.with_user(self.ops).action_retry_delivery()
            blocked.with_user(self.ops).action_retry_delivery()
            self.assertEqual(len(lead.field_delivery_attempt_ids), 3)
            self.assertEqual(blocked.status, 'failed')

    def test_invoice_waits_for_full_collection_and_cancellation_reopens(self):
        lead = self.lead(field_invoice_pdf=self.pdf, field_invoice_number='I-FIXTURE', field_worker_id=self.ops.id,
                         field_visit_at='2026-09-10 09:00:00')
        with self.delivery_config(FIELD_WORK_WHATSAPP_MODE='off'):
            for _ in range(4):
                lead.action_next_field_stage()
            stream = BytesIO()
            Image.new('RGB', (8, 8), 'blue').save(stream, 'PNG')
            photo = base64.b64encode(stream.getvalue())
            lead.write({'field_report_before_image': photo, 'field_report_after_image': photo,
                        'field_visit_summary': 'בדיקה'})
            lead.action_submit_field_report()
            lead.action_approve_field_report()
            self.assertEqual(lead.field_dispatch_code, 'completed')
            payments = self.env['field.work.payment'].with_user(self.ops)
            payments.create({'lead_id': lead.id, 'amount': 400, 'reference': 'PART'})
            self.assertEqual(lead.field_dispatch_code, 'completed')
            self.assertFalse(lead.field_delivery_attempt_ids)
            final = payments.create({'lead_id': lead.id, 'amount': 780, 'reference': 'FINAL'})
            self.assertEqual(lead.field_dispatch_code, 'paid')
            self.assertEqual(lead.field_delivery_attempt_ids.document_kind, 'invoice')
            final._cancel_registration('Synthetic cancellation')
            self.assertEqual(lead.field_dispatch_code, 'completed')
            self.assertEqual(lead.field_delivery_attempt_ids.sudo()._deliver()[0], 'superseded')

    def test_prepaid_invoice_closes_when_execution_is_approved_last(self):
        lead = self.lead(field_invoice_pdf=self.pdf, field_invoice_number='I-PREPAID',
                         field_worker_id=self.ops.id, field_visit_at='2026-09-10 09:00:00')
        with self.delivery_config(FIELD_WORK_WHATSAPP_MODE='off'), \
                patch('odoo.addons.field_work_photos.models.field_document_delivery.send_email') as email:
            for _ in range(4):
                lead.action_next_field_stage()
            self.env['field.work.payment'].with_user(self.ops).create({
                'lead_id': lead.id, 'amount': 1180, 'reference': 'PREPAID'})
            self.assertEqual(lead.field_dispatch_code, 'field')
            self.assertFalse(lead.field_delivery_attempt_ids)
            stream = BytesIO()
            Image.new('RGB', (8, 8), 'blue').save(stream, 'PNG')
            photo = base64.b64encode(stream.getvalue())
            lead.write({'field_report_before_image': photo, 'field_report_after_image': photo,
                        'field_visit_summary': 'בדיקה'})
            lead.action_submit_field_report()
            self.assertEqual(lead.field_dispatch_code, 'field')
            lead.action_approve_field_report()
            self.assertEqual(lead.field_dispatch_code, 'paid')
            self.assertEqual(len(lead.field_delivery_attempt_ids), 1)
            self.assertEqual(lead.field_delivery_attempt_ids.document_kind, 'invoice')
            self.assertEqual(lead.field_delivery_attempt_ids.status, 'queued')
            email.assert_not_called()

    def test_webhook_signature_checks_exact_bytes(self):
        payload = b'{"object":"whatsapp_business_account"}'
        signature = 'sha256=' + hmac.new(b'test-secret', payload, hashlib.sha256).hexdigest()
        self.assertTrue(verified_signature('test-secret', signature, payload))
        self.assertFalse(verified_signature('test-secret', signature, payload + b' '))
        self.assertFalse(verified_signature('wrong-secret', signature, payload))


@tagged('post_install', '-at_install')
class TestFieldWhatsAppWebhook(HttpCase):
    def test_signed_text_import_is_idempotent_and_scoped(self):
        endpoint = '/field-work/whatsapp/webhook'
        body = json.dumps({
            'object': 'whatsapp_business_account',
            'entry': [{'changes': [{'field': 'messages', 'value': {
                'metadata': {'phone_number_id': '1234'},
                'messages': [{'id': 'wamid.fixture', 'from': '972500000000', 'type': 'text',
                              'text': {'body': 'פנייה סינתטית'}}],
            }}]}],
        }).encode()
        signature = 'sha256=' + hmac.new(b'fixture-app', body, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, {
            'FIELD_WORK_DELIVERY_DB': self.env.cr.dbname,
            'FIELD_WORK_DELIVERY_COMPANY': str(self.env.company.id),
            'FIELD_WORK_WHATSAPP_APP_SECRET': 'fixture-app',
            'FIELD_WORK_WHATSAPP_VERIFY_TOKEN': 'fixture-verify',
            'FIELD_WORK_WHATSAPP_PHONE_ID': '1234',
            'FIELD_WORK_WHATSAPP_INBOUND': '1',
        }):
            self.assertEqual(self.url_open(endpoint + '?hub.mode=subscribe&hub.verify_token=fixture-verify&hub.challenge=123').text, '123')
            headers = {'Content-Type': 'application/json', 'X-Hub-Signature-256': 'sha256=invalid'}
            self.assertEqual(self.url_open(endpoint, data=body, headers=headers).status_code, 403)
            headers['X-Hub-Signature-256'] = signature
            for _ in range(2):
                self.assertEqual(self.url_open(endpoint, data=body, headers=headers).status_code, 200)
        lead = self.env['crm.lead'].sudo().search([('field_whatsapp_event_id', '=', 'wamid.fixture')])
        self.assertEqual(len(lead), 1)
        self.assertEqual(lead.field_dispatch_code, 'new')
        self.assertEqual(lead.company_id, self.env.company)
        self.assertEqual(lead.field_work_description, 'פנייה סינתטית')

    def test_signed_malformed_event_structure_is_rejected(self):
        endpoint = '/field-work/whatsapp/webhook'
        malformed = [
            {'entry': 'invalid'},
            {'entry': [None]},
            {'entry': [{'changes': [None]}]},
            {'entry': [{'changes': [{'field': 'messages', 'value': []}]}]},
            {'entry': [{'changes': [{'field': 'messages', 'value': {
                'metadata': {'phone_number_id': '1234'}, 'statuses': [None]}}]}]},
            {'entry': [{'changes': [{'field': 'messages', 'value': {
                'metadata': {'phone_number_id': '1234'}, 'messages': [None]}}]}]},
        ]
        with patch.dict(os.environ, {
            'FIELD_WORK_DELIVERY_DB': self.env.cr.dbname,
            'FIELD_WORK_DELIVERY_COMPANY': str(self.env.company.id),
            'FIELD_WORK_WHATSAPP_APP_SECRET': 'fixture-app',
            'FIELD_WORK_WHATSAPP_PHONE_ID': '1234',
            'FIELD_WORK_WHATSAPP_INBOUND': '1',
        }):
            for data in malformed:
                body = json.dumps({'object': 'whatsapp_business_account', **data}).encode()
                signature = 'sha256=' + hmac.new(b'fixture-app', body, hashlib.sha256).hexdigest()
                response = self.url_open(endpoint, data=body, headers={
                    'Content-Type': 'application/json', 'X-Hub-Signature-256': signature})
                self.assertEqual(response.status_code, 400)
