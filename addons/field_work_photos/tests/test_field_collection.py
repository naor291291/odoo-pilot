import base64
from io import BytesIO

from PIL import Image

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, TransactionCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestFieldCollection(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = new_test_user(cls.env, login='collection_owner', groups='field_work_photos.group_field_finance')
        cls.ops = new_test_user(cls.env, login='collection_ops', groups='field_work_photos.group_field_dispatcher')
        cls.contractor = new_test_user(cls.env, login='collection_contractor', groups='field_work_photos.group_field_contractor')
        cls.other_contractor = new_test_user(cls.env, login='collection_other_contractor', groups='field_work_photos.group_field_contractor')
        cls.sales = new_test_user(cls.env, login='collection_sales', groups='sales_team.group_sale_salesman_all_leads')
        cls.customer = cls.env['res.partner'].create({'name': 'Collection customer', 'phone': '0500000000'})
        stream = BytesIO()
        Image.new('RGB', (8, 8), 'blue').save(stream, 'PNG')
        cls.photo = base64.b64encode(stream.getvalue())

    def lead(self, **vals):
        return self.env['crm.lead'].with_user(self.owner).create({
            'name': 'Collection work', 'is_field_service': True, 'partner_id': self.customer.id,
            'phone': '0500000000', 'field_site_address': 'Work street', 'field_work_description': 'Replace tap',
            'field_sale_amount': 1000, 'field_customer_due': 1180, 'field_contractor_due': 700,
            'field_quote_number': 'COL-1', 'field_contractor_id': self.contractor.id,
            'field_visit_at': fields.Datetime.now(), **vals})

    def complete(self, lead):
        for _ in range(4):
            lead.action_next_field_stage()
        lead.write({'field_report_before_image': self.photo, 'field_report_after_image': self.photo,
                    'field_visit_summary': 'הוחלף הברז ונבדק'})
        lead.action_submit_field_report()
        lead.action_approve_field_report()
        return lead

    def pay(self, lead, amount, reference='PAY-1', kind='customer', **vals):
        return self.env['field.work.payment'].with_user(lead.env.user).create({
            'lead_id': lead.id, 'amount': amount, 'kind': kind,
            'reference': reference, 'method': 'transfer', **vals})

    def test_advance_partial_and_full_keep_workflow_until_explicit_close(self):
        lead = self.lead().with_user(self.ops)
        self.pay(lead, 400)
        self.assertEqual(lead.field_customer_paid, 400)
        self.assertEqual(lead.field_customer_balance, 780)
        self.assertEqual(lead.field_collection_status, 'partial')
        self.assertEqual(lead.field_dispatch_code, 'new')
        self.complete(lead)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.action_close_field_work()
        self.pay(lead, 780, 'PAY-2')
        self.assertEqual(lead.field_dispatch_code, 'completed')
        lead.action_close_field_work()
        self.assertEqual(lead.field_dispatch_code, 'paid')
        self.assertEqual(lead.field_closed_by, self.ops)
        self.assertTrue(lead.field_closed_at)

    def test_full_advance_cannot_close_before_execution_approval(self):
        lead = self.lead()
        self.pay(lead, 1180)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.action_close_field_work()

    def test_approved_legacy_work_needs_explicit_gross_amount(self):
        lead = self.complete(self.lead(field_customer_due=0))
        self.assertEqual(lead.field_collection_status, 'unset')
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.action_register_customer_payment()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.action_close_field_work()
        self.assertEqual(lead.field_sale_amount, 1000)
        lead.field_customer_due = 1180
        self.assertEqual(lead.field_customer_balance, 1180)

    def test_gross_totals_never_change_net_pricing(self):
        lead = self.lead()
        expected = (lead.field_sale_amount, lead.field_contractor_cost, lead.field_gross_profit)
        self.pay(lead, 500)
        self.pay(lead, 100, kind='contractor')
        self.assertEqual((lead.field_sale_amount, lead.field_contractor_cost, lead.field_gross_profit), expected)
        self.assertEqual(lead.field_customer_paid, 500)
        self.assertEqual(lead.field_contractor_paid, 100)

    def test_payment_batch_cannot_overconsume_balance(self):
        lead = self.lead()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['field.work.payment'].create([
                {'lead_id': lead.id, 'amount': 700, 'reference': 'B-1', 'method': 'transfer'},
                {'lead_id': lead.id, 'amount': 700, 'reference': 'B-2', 'method': 'transfer'}])
        self.assertEqual(lead.field_customer_paid, 0)

    def test_overpayment_zero_negative_and_nonfinite_amounts_rejected(self):
        lead = self.lead()
        for amount in [0, -.01, 1180.01, float('inf'), float('nan')]:
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.pay(lead, amount)

    def test_amounts_round_to_cents(self):
        lead = self.lead(field_customer_due=.3)
        self.pay(lead, .1)
        self.pay(lead, .2, 'PAY-2')
        self.assertEqual(lead.field_customer_balance, 0)
        self.assertEqual(lead.field_collection_status, 'paid')
        tiny = self.lead(field_customer_due=.004)
        self.assertEqual(tiny.field_customer_due, 0)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.pay(tiny, .004)

    def test_missing_reference_and_future_date_rejected(self):
        from datetime import timedelta
        lead = self.lead()
        for vals in [dict(reference=' '), dict(payment_date=fields.Date.today() + timedelta(days=2))]:
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.pay(lead, 100, **vals)

    def test_duplicate_reference_normalized_and_reusable_only_after_cancellation(self):
        lead = self.lead()
        payment = self.pay(lead, 100, ' Bank-123 ')
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.pay(lead, 100, 'bank-123')
        payment._cancel_registration('רישום שגוי')
        self.pay(lead, 150, 'bank-123')
        self.assertEqual(lead.field_customer_paid, 150)
        self.assertEqual(len(lead.field_payment_ids), 2)

    def test_registration_dialog_double_submit_is_idempotent(self):
        lead = self.lead().with_user(self.ops)
        action = lead.action_register_customer_payment()
        wizard = self.env['field.work.payment.register'].with_user(self.ops).with_context(**action['context']).create({
            'amount': 200, 'reference': 'DIALOG-1'})
        wizard.action_apply()
        wizard.action_apply()
        self.assertEqual(lead.field_customer_paid, 200)
        self.assertEqual(len(lead.field_payment_ids), 1)

    def test_ledger_immutable_and_audit_cannot_be_forged(self):
        lead = self.lead()
        payment = self.pay(lead, 100)
        for action in [lambda: payment.write({'amount': 1}), lambda: payment.write({'state': 'cancelled'}), payment.unlink, payment.copy]:
            with self.assertRaises(AccessError), self.cr.savepoint():
                action()
        for vals in [dict(state='posted'), dict(cancelled_by=self.owner.id), dict(create_uid=self.contractor.id), dict(company_id=lead.company_id.id)]:
            with self.assertRaises(AccessError), self.cr.savepoint():
                self.pay(lead, 100, **vals)

    def test_direct_balance_relation_closing_and_audit_writes_rejected(self):
        lead = self.complete(self.lead())
        self.pay(lead, 1180)
        for vals in [dict(field_customer_paid=1180), dict(field_customer_balance=0), dict(field_collection_status='paid'),
                     dict(field_payment_ids=[]), dict(field_closed_by=self.ops.id),
                     dict(stage_id=self.env.ref('field_work_photos.stage_field_paid').id)]:
            with self.assertRaises(ValidationError if 'stage_id' in vals else AccessError), self.cr.savepoint():
                lead.write(vals)

    def test_cancellation_reopens_closed_job_and_keeps_audit(self):
        lead = self.complete(self.lead()).with_user(self.ops)
        payment = self.pay(lead, 1180)
        lead.action_close_field_work()
        wizard = self.env['field.work.payment.cancel'].with_user(self.ops).create({'payment_id': payment.id, 'reason': 'רישום כפול'})
        wizard.action_apply()
        self.assertEqual(lead.field_dispatch_code, 'completed')
        self.assertFalse(lead.field_closed_at)
        self.assertFalse(lead.field_closed_by)
        self.assertEqual(lead.field_customer_balance, 1180)
        self.assertEqual(payment.state, 'cancelled')
        self.assertEqual(payment.cancelled_by, self.ops)
        self.assertEqual(payment.cancel_reason, 'רישום כפול')
        self.assertEqual(lead.field_report_state, 'approved')
        self.assertEqual(payment.amount, 1180)

    def test_cancellation_reason_and_double_cancel_guard(self):
        lead = self.lead()
        payment = self.pay(lead, 100)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            payment._cancel_registration(' ')
        payment._cancel_registration('טעות')
        with self.assertRaises(ValidationError), self.cr.savepoint():
            payment._cancel_registration('שוב')

    def test_return_to_correction_reopens_paid_job_without_losing_receipts(self):
        lead = self.complete(self.lead())
        self.pay(lead, 1180)
        lead.action_close_field_work()
        wizard = self.env['field.work.correction'].create({'task_id': lead.field_task_ids.id, 'reason': 'בדיקה נוספת'})
        wizard.action_apply()
        self.assertEqual(lead.field_dispatch_code, 'field')
        self.assertFalse(lead.field_closed_at)
        self.assertEqual(lead.field_customer_paid, 1180)
        self.assertEqual(lead.field_report_state, 'changes_requested')
        lead.action_submit_field_report()
        lead.action_approve_field_report()
        lead.action_close_field_work()
        self.assertEqual(lead.field_dispatch_code, 'paid')

    def test_total_cannot_fall_below_paid_or_change_when_closed(self):
        lead = self.lead()
        self.pay(lead, 300)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.field_customer_due = 200
        lead.field_customer_due = 1200
        self.assertEqual(lead.field_customer_balance, 900)
        self.complete(lead)
        self.pay(lead, 900, 'PAY-2')
        lead.action_close_field_work()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.field_customer_due = 1300

    def test_nonfinite_and_negative_totals_rejected(self):
        for name in ('field_customer_due', 'field_contractor_due'):
            for amount in (-1, float('inf'), float('nan')):
                with self.assertRaises(ValidationError), self.cr.savepoint():
                    self.lead(**{name: amount})

    def test_recorded_parties_cannot_change_even_after_voiding(self):
        lead = self.lead()
        payment = self.pay(lead, 100)
        payment._cancel_registration('טעות')
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.partner_id = self.other_contractor.partner_id
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.unlink()
        lead.active = False
        self.assertFalse(lead.active)

    def test_contractor_installments_can_be_paid_after_customer_job_closes(self):
        lead = self.complete(self.lead())
        self.pay(lead, 1180)
        lead.action_close_field_work()
        payout = self.pay(lead, 300, kind='contractor')
        self.assertEqual(lead.field_contractor_balance, 400)
        self.pay(lead, 400, 'PAYOUT-2', kind='contractor')
        self.assertEqual(lead.field_payout_status, 'paid')
        payout._cancel_registration('רישום שגוי')
        self.assertEqual(lead.field_contractor_balance, 300)
        self.assertEqual(lead.field_dispatch_code, 'paid')
        self.assertEqual(lead.field_customer_paid, 1180)

    def test_operations_cannot_access_or_spoof_payouts(self):
        lead = self.lead()
        payout = self.pay(lead, 100, 'PAYOUT-SECRET', kind='contractor', note='PAYOUT-SECRET')
        ops = lead.with_user(self.ops)
        for action in [lambda: ops.read(['field_contractor_due']), lambda: ops.read(['field_contractor_paid']),
                       ops.action_register_contractor_payment,
                       lambda: self.pay(ops, 100, kind='contractor'),
                       lambda: payout.with_user(self.ops).read(['amount']),
                       lambda: payout.with_user(self.ops).action_cancel_registration(),
                       lambda: ops.write({'field_contractor_due': 1})]:
            with self.assertRaises(AccessError), self.cr.savepoint():
                action()
        self.assertFalse(self.env['field.work.payment'].with_user(self.ops).search([('id', '=', payout.id)]))
        self.assertFalse(any('PAYOUT-SECRET' in (m.body or '') for m in lead.message_ids))

    def test_portal_and_non_dispatcher_have_no_ledger_or_dialog_access(self):
        lead = self.lead()
        payment = self.pay(lead, 100)
        for user in (self.contractor, self.sales):
            for action in [lambda: payment.with_user(user).read(['amount']),
                           lambda: self.pay(lead.with_user(user), 100),
                           lambda: self.env['field.work.payment.register'].with_user(user).create({'lead_id': lead.id, 'amount': 1, 'reference': 'x'}),
                           lambda: lead.with_user(user).action_close_field_work()]:
                with self.assertRaises(AccessError), self.cr.savepoint():
                    action()

    def test_company_is_frozen_and_foreign_company_ledger_denied(self):
        lead = self.lead()
        payment = self.pay(lead, 100)
        company = self.env['res.company'].create({'name': 'Collection other company'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.company_id = company
        restricted = new_test_user(self.env, login='collection_other_company_ops', groups='field_work_photos.group_field_dispatcher', company_id=company.id, company_ids=[(6, 0, company.ids)])
        with self.assertRaises(AccessError), self.cr.savepoint():
            payment.with_user(restricted).read(['amount'])
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.pay(lead.with_user(restricted), 100, 'FOREIGN')

    def test_no_contractor_payout_for_direct_work(self):
        lead = self.lead(field_execution_type='direct', field_worker_id=self.ops.id)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.pay(lead, 100, kind='contractor')

    def test_paid_contractor_assignment_frozen(self):
        lead = self.lead()
        self.pay(lead, 100, kind='contractor')
        for vals in [dict(field_contractor_id=self.other_contractor.id), dict(field_execution_type='direct')]:
            with self.assertRaises(ValidationError), self.cr.savepoint():
                lead.write(vals)

    def test_archived_or_ordinary_work_cannot_register_payment(self):
        ordinary = self.env['crm.lead'].create({'name': 'Ordinary opportunity'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.pay(ordinary, 100)
        lead = self.lead()
        lead.active = False
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.pay(lead, 100)

    def test_copy_of_paid_job_has_no_money_ledger_or_close_metadata(self):
        lead = self.complete(self.lead())
        self.pay(lead, 1180)
        self.pay(lead, 100, kind='contractor')
        lead.action_close_field_work()
        copy = lead.copy()
        self.assertEqual(copy.field_dispatch_code, 'new')
        self.assertEqual(copy.field_customer_due, 0)
        self.assertEqual(copy.field_customer_paid, 0)
        self.assertFalse(copy.field_payment_ids)
        self.assertFalse(copy.field_payout_ids)
        self.assertFalse(copy.field_closed_at)

    def test_context_defaults_cannot_forge_money_or_audit(self):
        lead = self.env['crm.lead'].with_context(default_field_customer_paid=1180,
            default_field_collection_status='paid', default_field_payment_ids=[(0, 0, {'amount': 1180})]).create({
                'name': 'Context spoof', 'is_field_service': True, 'partner_id': self.customer.id,
                'field_customer_due': 1180})
        self.assertEqual(lead.field_customer_paid, 0)
        self.assertEqual(lead.field_collection_status, 'unpaid')
        payment = self.env['field.work.payment'].with_context(default_kind='contractor',
            default_state='cancelled', default_cancel_reason='forged', default_cancelled_by=self.owner.id).create({
                'lead_id': lead.id, 'amount': 100, 'reference': 'CTX-1'})
        self.assertEqual(payment.kind, 'customer')
        self.assertEqual(payment.state, 'posted')
        self.assertFalse(payment.cancel_reason)
        self.assertFalse(payment.cancelled_by)
        self.assertEqual(lead.field_customer_paid, 100)

    def test_collection_and_owner_views_validate_for_their_roles(self):
        for user in (self.owner, self.ops):
            with Form(self.env['crm.lead'].with_user(user).with_context(default_is_field_service=True),
                      view='field_work_photos.view_field_lead_form') as form:
                form.name = 'Payment form draft'
            self.assertEqual(form.record.field_customer_due, 0)
        action = self.env.ref('field_work_photos.action_field_collections')
        lead = self.complete(self.lead())
        from odoo.tools.safe_eval import safe_eval
        self.assertIn(lead, self.env['crm.lead'].search(safe_eval(action.domain)))
        self.pay(lead, 1180)
        lead.action_close_field_work()
        self.assertNotIn(lead, self.env['crm.lead'].search(safe_eval(action.domain)))
