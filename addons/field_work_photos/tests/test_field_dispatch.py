from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged, new_test_user



@tagged('post_install', '-at_install')
class TestFieldDispatch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ops = new_test_user(cls.env, login='dispatch_ops', groups='field_work_photos.group_field_dispatcher')
        cls.first = new_test_user(cls.env, login='contractor_first', groups='field_work_photos.group_field_contractor')
        cls.second = new_test_user(cls.env, login='contractor_second', groups='field_work_photos.group_field_contractor')
        cls.customer = cls.env['res.partner'].create({'name': 'Test Customer', 'phone': '0501234567'})
        import base64
        from io import BytesIO
        from PIL import Image
        stream = BytesIO()
        Image.new('RGB', (8, 8), 'green').save(stream, 'PNG')
        cls.photo = base64.b64encode(stream.getvalue())

    def lead(self, **values):
        return self.env['crm.lead'].with_user(self.ops).create({
            'name': 'Replace kitchen tap', 'is_field_service': True,
            'partner_id': self.customer.id, 'phone': '0501234567',
            'field_quote_number': 'QUOTE-100', 'field_contractor_id': self.first.id,
            'field_visit_at': fields.Datetime.now(), 'field_site_address': 'Test Street 10',
            'field_work_description': 'Replace the tap',
            'stage_id': self.env.ref('field_work_photos.stage_field_schedule').id, **values,
        })

    def dispatch(self):
        lead = self.lead()
        lead.action_dispatch_field_work()
        return lead, lead.field_task_ids

    def test_dispatch_creates_linked_snapshot_and_is_idempotent(self):
        lead, task = self.dispatch()
        self.assertEqual(len(task), 1)
        self.assertEqual(task.field_customer_name, self.customer.name)
        self.assertEqual(task.field_site_address, lead.field_site_address)
        self.assertEqual(task.field_contractor_id, self.first)
        self.assertTrue(task.field_report_required)
        lead.action_dispatch_field_work()
        self.assertEqual(lead.field_task_ids, task)

    def test_kanban_transition_creates_task(self):
        lead = self.lead()
        lead.write({'stage_id': self.env.ref('field_work_photos.stage_field_field').id})
        self.assertEqual(len(lead.field_task_ids), 1)

    def test_create_in_field_stage_creates_task(self):
        lead = self.lead(stage_id=self.env.ref('field_work_photos.stage_field_field').id)
        self.assertEqual(len(lead.field_task_ids), 1)

    def test_dispatch_requires_all_details(self):
        for field in ('partner_id', 'field_contractor_id', 'field_visit_at', 'field_site_address', 'field_work_description'):
            lead = self.lead(**{field: False})
            with self.assertRaises(ValidationError), self.cr.savepoint():
                lead.action_dispatch_field_work()
            self.assertFalse(lead.field_task_ids)
            self.assertEqual(lead.field_dispatch_code, 'schedule')

    def test_invalid_contractor_is_rejected(self):
        lead = self.lead(field_contractor_id=self.ops.id)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.action_dispatch_field_work()
        self.second.active = False
        lead.field_contractor_id = self.second
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.action_dispatch_field_work()

    def test_quote_number_advances_stage(self):
        lead = self.lead(field_quote_number=False, stage_id=self.env.ref('field_work_photos.stage_field_new').id)
        lead.field_quote_number = 'M-2026'
        self.assertEqual(lead.field_dispatch_code, 'sent')

    def test_quote_required_before_sent(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.lead(field_quote_number=False)

    def test_reassignment_and_schedule_sync(self):
        lead, task = self.dispatch()
        lead.write({'field_contractor_id': self.second.id, 'field_site_address': 'New Address'})
        self.assertEqual(task.field_contractor_id, self.second)
        self.assertEqual(task.field_site_address, 'New Address')

    def test_pending_assignment_and_details_are_locked(self):
        lead, task = self.dispatch()
        task.write({'field_before_image': self.photo, 'field_after_image': self.photo})
        task.action_finish_field_work()
        for values in ({'field_contractor_id': self.second.id}, {'field_site_address': 'Changed'}):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                lead.write(values)

    def test_review_moves_lead_and_return_reopens_it(self):
        lead, task = self.dispatch()
        task.write({'field_before_image': self.photo, 'field_after_image': self.photo})
        task.action_finish_field_work()
        task.action_approve_field_work()
        self.assertEqual(lead.field_dispatch_code, 'completed')
        task.field_review_note = 'Please fix'
        task.action_request_field_changes()
        self.assertEqual(lead.field_dispatch_code, 'field')
        lead.field_contractor_id = self.second
        self.assertEqual(task.field_contractor_id, self.second)

    def test_cannot_manually_complete_or_rewind_dispatch(self):
        lead, task = self.dispatch()
        for stage in ('completed', 'new'):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                lead.write({'stage_id': self.env.ref('field_work_photos.stage_field_' + stage).id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.write({'is_field_service': False})

    def test_task_link_assignment_and_deletion_cannot_be_forged(self):
        lead, task = self.dispatch()
        for values in ({'field_contractor_id': self.second.id}, {'field_service_lead_id': False}, {'user_ids': [(4, self.ops.id)]}):
            with self.assertRaises(AccessError), self.cr.savepoint():
                task.write(values)
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env['project.task'].create({'name': 'Forged', 'field_service_lead_id': lead.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.unlink()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.unlink()

    def test_copy_does_not_reuse_dispatch(self):
        lead, task = self.dispatch()
        copied = task.copy()
        self.assertFalse(copied.field_service_lead_id)
        self.assertFalse(copied.field_contractor_id)

    def test_contractors_have_no_crm_or_native_project_access(self):
        lead, task = self.dispatch()
        for user in (self.first, self.second):
            self.assertTrue(user.share)
            self.assertFalse(user.has_group('base.group_user'))
            with self.assertRaises(AccessError), self.cr.savepoint():
                lead.with_user(user).read(['name'])
            with self.assertRaises(AccessError), self.cr.savepoint():
                task.with_user(user).read(['name'])
            with self.assertRaises(AccessError), self.cr.savepoint():
                task.with_user(user).write({'field_before_image': self.photo})

    def test_regular_crm_is_unaffected(self):
        lead = self.env['crm.lead'].with_user(self.ops).create({'name': 'Ordinary opportunity'})
        self.assertFalse(lead.is_field_service)
        self.assertFalse(lead.field_task_ids)

    def test_non_dispatcher_cannot_modify_service_lead(self):
        ordinary = new_test_user(self.env, login='ordinary_sales', groups='sales_team.group_sale_salesman_all_leads')
        lead = self.lead()
        with self.assertRaises(AccessError), self.cr.savepoint():
            lead.with_user(ordinary).write({'field_site_address': 'Unauthorized'})
