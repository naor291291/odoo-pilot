import base64
from io import BytesIO

from reportlab.pdfgen import canvas

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


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
