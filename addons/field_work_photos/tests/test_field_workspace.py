import base64
from io import BytesIO
from PIL import Image

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestFieldWorkspace(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ops = new_test_user(cls.env, login='workspace_ops', groups='field_work_photos.group_field_dispatcher')
        cls.contractor = new_test_user(cls.env, login='workspace_contractor', groups='field_work_photos.group_field_contractor')
        cls.customer = cls.env['res.partner'].create({'name': 'Workspace customer', 'phone': '0500000000'})
        image = BytesIO()
        Image.new('RGB', (8, 8), 'blue').save(image, 'PNG')
        cls.photo = base64.b64encode(image.getvalue())

    def lead(self):
        lead = self.env['crm.lead'].with_user(self.ops).create({
            'name': 'Unified work', 'is_field_service': True, 'partner_id': self.customer.id,
            'phone': '0500000000', 'field_site_address': 'Work street', 'field_work_description': 'Replace tap',
            'field_sale_amount': 1000, 'field_quote_number': 'UI-1',
            'field_contractor_id': self.contractor.id, 'field_visit_at': fields.Datetime.now(),
        })
        for _ in range(4):
            result = lead.action_next_field_stage()
        self.assertEqual(result['res_model'], 'crm.lead')
        self.assertEqual(result['res_id'], lead.id)
        return lead

    def test_report_review_and_completion_stay_in_same_workspace(self):
        lead = self.lead()
        lead.write({'field_report_before_image': self.photo, 'field_report_after_image': self.photo})
        self.assertEqual(lead.field_task_ids.field_before_image, self.photo)
        lead.action_submit_field_report()
        self.assertEqual(lead.field_report_state, 'pending')
        self.assertEqual(lead.field_attention_label, 'ממתינה לבדיקת דיווח')
        lead.action_approve_field_report()
        self.assertEqual(lead.field_dispatch_code, 'completed')
        self.assertEqual(lead.field_report_state, 'approved')
        self.assertTrue(lead.field_report_approved_at)
        self.assertEqual(lead.action_open_field_task()['res_model'], 'crm.lead')

    def test_report_images_remain_locked_after_submission(self):
        lead = self.lead()
        lead.write({'field_report_before_image': self.photo, 'field_report_after_image': self.photo})
        lead.action_submit_field_report()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.write({'field_report_after_image': False})

    def test_correction_dialog_requires_reason_and_returns_to_workspace(self):
        lead = self.lead()
        lead.write({'field_report_before_image': self.photo, 'field_report_after_image': self.photo})
        lead.action_submit_field_report()
        action = lead.action_return_field_report()
        self.assertEqual(action['target'], 'new')
        Wizard = self.env['field.work.correction'].with_user(self.ops)
        wizard = Wizard.create({'task_id': lead.field_task_ids.id, 'reason': ' '})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            wizard.action_apply()
        wizard.reason = 'צילום קרוב יותר של החיבור'
        result = wizard.action_apply()
        self.assertEqual(result['res_id'], lead.id)
        self.assertEqual(lead.field_report_state, 'changes_requested')
        self.assertEqual(lead.field_report_note, wizard.reason)
        lead.write({'field_report_after_image': self.photo})
        lead.action_submit_field_report()
        self.assertEqual(lead.field_report_state, 'pending')

    def test_report_requires_both_photos(self):
        lead = self.lead()
        lead.field_report_before_image = self.photo
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.action_submit_field_report()
        self.assertEqual(lead.field_report_state, 'draft')

    def test_direct_workspace_link_and_state_writes_are_rejected(self):
        lead = self.lead()
        for name, value in [('field_workspace_task_id', lead.field_task_ids.id), ('field_report_state', 'approved'), ('field_report_note', 'spoof')]:
            with self.assertRaises(AccessError), self.cr.savepoint():
                lead.write({name: value})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env['crm.lead'].create({'name': 'Spoof', 'field_workspace_task_id': lead.field_task_ids.id, 'field_report_before_image': self.photo})

    def test_contractor_cannot_use_management_workspace_actions(self):
        lead = self.lead().with_user(self.contractor)
        with self.assertRaises(AccessError), self.cr.savepoint():
            lead.action_submit_field_report()
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env['field.work.correction'].with_user(self.contractor).create({'task_id': 1, 'reason': 'spoof'})

    def test_no_report_before_dispatch(self):
        lead = self.env['crm.lead'].with_user(self.ops).create({'name': 'Draft', 'is_field_service': True})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.action_submit_field_report()

    def test_queue_and_price_views_use_dedicated_screens(self):
        self.assertEqual(self.env.ref('field_work_photos.action_field_work_attention').res_model, 'crm.lead')
        views = self.env.ref('field_work_photos.action_field_contractor_rates').view_ids
        self.assertIn(self.env.ref('field_work_photos.view_field_partner_rates_list'), views.view_id)
        self.assertIn(self.env.ref('field_work_photos.view_field_partner_rates_form'), views.view_id)
