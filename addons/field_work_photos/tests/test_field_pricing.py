from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestFieldPricing(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = new_test_user(cls.env, login='pricing_owner', groups='field_work_photos.group_field_finance')
        cls.ops = new_test_user(cls.env, login='pricing_ops', groups='field_work_photos.group_field_dispatcher')
        cls.contractor = new_test_user(cls.env, login='pricing_contractor', groups='field_work_photos.group_field_contractor')
        cls.other = new_test_user(cls.env, login='pricing_other', groups='field_work_photos.group_field_contractor')
        cls.customer = cls.env['res.partner'].create({'name': 'Pricing customer', 'phone': '0501234567'})

    def lead(self, amount=1000, materials=0, **vals):
        return self.env['crm.lead'].with_user(self.owner).create({
            'name': 'Pricing example', 'is_field_service': True,
            'partner_id': self.customer.id, 'phone': '0501234567',
            'field_quote_number': 'PRICE-100', 'field_contractor_id': self.contractor.id,
            'field_visit_at': fields.Datetime.now(), 'field_site_address': 'Test Street 10',
            'field_work_description': 'Replace tap', 'field_sale_amount': amount,
            'field_material_cost': materials, **vals,
        })

    def dispatch(self, lead):
        for _ in range(4):
            lead.action_next_field_stage()
        return lead.field_task_ids

    def test_default_tier_boundaries_and_fractional_shekel(self):
        for amount, rate, cost in [(500, 70, 350), (500.01, 65, 325.01),
                                   (1250, 65, 812.5), (1250.01, 50, 625.01)]:
            lead = self.lead(amount)
            self.assertEqual(lead.field_applied_rate, rate)
            self.assertEqual(lead.field_contractor_cost, cost)

    def test_personal_rates_recompute_before_dispatch(self):
        lead = self.lead(1000, 100)
        self.contractor.partner_id.write({'field_rate_medium': 60})
        self.assertEqual(lead.field_contractor_cost, 600)
        self.assertEqual(lead.field_gross_profit, 300)
        self.assertAlmostEqual(lead.field_gross_margin, 30)
        self.assertTrue(lead.field_low_margin)

    def test_exact_threshold_and_below(self):
        lead = self.lead(1000)
        self.assertFalse(lead.field_low_margin)
        lead.field_material_cost = .01
        self.assertTrue(lead.field_low_margin)
        tiny = self.lead(.01, .01, field_execution_type='direct')
        self.assertTrue(tiny.field_low_margin)

    def test_zero_amount_and_negative_profit(self):
        lead = self.lead(0, 100)
        self.assertEqual(lead.field_gross_profit, -100)
        self.assertEqual(lead.field_gross_margin, 0)
        self.assertFalse(lead.field_low_margin)
        lead.field_sale_amount = 100
        self.assertTrue(lead.field_low_margin)
        self.assertEqual(lead.field_gross_profit, -70)

    def test_direct_work_has_no_contractor_cost(self):
        lead = self.lead(1000, 200, field_execution_type='direct', field_worker_id=self.ops.id)
        self.assertEqual(lead.field_contractor_cost, 0)
        self.assertEqual(lead.field_gross_profit, 800)
        self.assertEqual(lead.field_gross_margin, 80)
        self.assertFalse(lead.field_low_margin)
        task = self.dispatch(lead)
        self.assertFalse(task.field_contractor_id)
        self.assertEqual(task.user_ids, self.ops)
        self.assertEqual(task.with_user(self.ops).name, lead.name)

    def test_direct_work_requires_internal_worker(self):
        for worker in (False, self.contractor.id):
            lead = self.lead(field_execution_type='direct', field_worker_id=worker)
            for _ in range(3):
                lead.action_next_field_stage()
            with self.assertRaises(ValidationError), self.cr.savepoint():
                lead.action_next_field_stage()
            self.assertFalse(lead.field_task_ids)

    def test_rates_frozen_and_reassignment_refreshes(self):
        lead = self.lead()
        # Operations can dispatch without access to the private rates.
        self.dispatch(lead.with_user(self.ops))
        self.assertTrue(lead.field_rates_frozen)
        self.contractor.partner_id.field_rate_medium = 20
        self.assertEqual(lead.field_applied_rate, 65)
        lead.with_user(self.ops).write({'field_contractor_id': self.contractor.id})
        self.assertEqual(lead.field_applied_rate, 65)
        self.other.partner_id.field_rate_medium = 55
        lead.with_user(self.ops).field_contractor_id = self.other
        self.assertEqual(lead.field_applied_rate, 55)
        self.assertEqual(lead.field_task_ids.field_contractor_id, self.other)

    def test_direct_reassignment_removes_portal_access(self):
        lead = self.lead()
        task = self.dispatch(lead)
        lead.write({'field_execution_type': 'direct', 'field_worker_id': self.ops.id})
        self.assertFalse(task.field_contractor_id)
        self.assertEqual(task.user_ids, self.ops)
        self.assertEqual(lead.field_contractor_cost, 0)

    def test_rates_outside_range_rejected(self):
        for value in (-1, 101, float('inf'), float('nan')):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.contractor.partner_id.field_rate_small = value

    def test_negative_amounts_rejected(self):
        for name in ('field_sale_amount', 'field_material_cost'):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.lead(**{name: -1})

    def test_ops_can_set_sale_but_not_read_private_finances(self):
        lead = self.lead()
        ops_lead = lead.with_user(self.ops)
        ops_lead.field_sale_amount = 2000
        for name in ('field_material_cost', 'field_gross_profit', 'field_gross_margin',
                     'field_contractor_cost', 'field_applied_rate', 'field_low_margin', 'field_rates_frozen'):
            with self.assertRaises(AccessError), self.cr.savepoint():
                ops_lead.read([name])
        with self.assertRaises(AccessError), self.cr.savepoint():
            ops_lead.write({'field_material_cost': 10})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.contractor.partner_id.with_user(self.ops).read(['field_rate_small'])
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.contractor.partner_id.with_user(self.ops).write({'field_rate_small': 10})

    def test_private_fields_absent_from_ops_views_and_metadata(self):
        Lead = self.env['crm.lead'].with_user(self.ops)
        self.assertNotIn('field_gross_profit', Lead.fields_get())
        view = Lead.get_view(self.env.ref('field_work_photos.view_field_lead_form').id, 'form')
        self.assertNotIn('field_gross_profit', view['arch'])
        self.assertNotIn('field_low_margin', view['arch'])

    def test_no_private_tracking_messages(self):
        lead = self.lead()
        before = lead.message_ids
        lead.field_material_cost = 999
        messages = lead.message_ids - before
        self.assertFalse(messages.tracking_value_ids)

    def test_snapshot_rpc_writes_rejected_even_for_owner(self):
        lead = self.lead()
        with self.assertRaises(AccessError), self.cr.savepoint():
            lead.write({'field_rate_medium_snapshot': 1})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.lead(field_rates_frozen=True)

    def test_quote_progress_requires_positive_sale_amount(self):
        lead = self.lead(0)
        lead.action_next_field_stage()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.action_next_field_stage()
        lead.field_sale_amount = 1000
        lead.action_next_field_stage()
        self.assertEqual(lead.field_dispatch_code, 'sent')

    def test_amounts_locked_after_submission(self):
        import base64
        from io import BytesIO
        from PIL import Image
        stream = BytesIO()
        Image.new('RGB', (8, 8), 'green').save(stream, 'PNG')
        lead = self.lead()
        task = self.dispatch(lead)
        task.write({'field_before_image': base64.b64encode(stream.getvalue()), 'field_after_image': base64.b64encode(stream.getvalue())})
        task.action_finish_field_work()
        for name in ('field_sale_amount', 'field_material_cost'):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                lead.write({name: 10})
