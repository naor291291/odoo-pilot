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
        lead.field_task_ids.write({'field_visit_summary': 'הוחלף הברז ונבדק'})
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

    def test_dashboard_counts_only_active_field_work(self):
        Dashboard = self.env['field.work.dashboard'].with_user(self.ops)
        dashboard = Dashboard.create({})
        self.assertEqual(dashboard.display_name, 'מרכז העבודה')
        before = dashboard.new_count
        field = self.env['crm.lead'].with_user(self.ops).create({'name': 'Dashboard field', 'is_field_service': True})
        ordinary = self.env['crm.lead'].with_user(self.ops).create({'name': 'Ordinary CRM'})
        dashboard.invalidate_recordset()
        self.assertEqual(dashboard.new_count, before + 1)
        field.active = False
        dashboard.invalidate_recordset()
        self.assertEqual(dashboard.new_count, before)
        self.assertFalse(ordinary.is_field_service)

    def test_dashboard_queues_use_real_stage_domains(self):
        lead = self.lead()
        dashboard = self.env['field.work.dashboard'].with_user(self.ops)
        action = dashboard.action_active_queue()
        self.assertIn(lead, self.env['crm.lead'].with_user(self.ops).search(action['domain']))
        action = dashboard.action_schedule_queue()
        self.assertNotIn(lead, self.env['crm.lead'].with_user(self.ops).search(action['domain']))

    def test_dashboard_denies_contractor_entry(self):
        Dashboard = self.env['field.work.dashboard'].with_user(self.contractor)
        for method in ('action_open', 'action_clients', 'action_new_work', 'action_review_queue'):
            with self.assertRaises(AccessError), self.cr.savepoint():
                getattr(Dashboard, method)()

    def test_dashboard_finance_fields_are_server_protected(self):
        dashboard = self.env['field.work.dashboard'].with_user(self.ops).create({})
        with self.assertRaises(AccessError), self.cr.savepoint():
            dashboard.read(['collection_balance', 'contractor_balance'])

    def test_dashboard_owner_balance_uses_existing_operational_amounts(self):
        Dashboard = self.env['field.work.dashboard'].with_user(self.env.ref('base.user_admin'))
        dashboard = Dashboard.create({})
        before = dashboard.collection_balance
        lead = self.env['crm.lead'].with_user(self.ops).create({
            'name': 'Dashboard amount', 'is_field_service': True, 'partner_id': self.customer.id,
            'field_customer_due': 123.45})
        dashboard.invalidate_recordset()
        self.assertAlmostEqual(dashboard.collection_balance - before, lead.field_customer_balance)

    def test_client_navigation_lists_only_field_work_partners(self):
        self.lead()
        other = self.env['res.partner'].create({'name': 'Ordinary client'})
        self.env['crm.lead'].with_user(self.ops).create({'name': 'Ordinary CRM', 'partner_id': other.id})
        action = self.env['field.work.dashboard'].with_user(self.ops).action_clients()
        clients = self.env['res.partner'].with_user(self.ops).search(action['domain'])
        self.assertIn(self.customer, clients)
        self.assertNotIn(other, clients)

    def test_new_client_stays_in_client_directory_before_first_work(self):
        client = self.env['res.partner'].with_user(self.ops).create({'name': 'New field client', 'field_crm_client': True})
        action = self.env['field.work.dashboard'].with_user(self.ops).action_clients()
        self.assertIn(client, self.env['res.partner'].with_user(self.ops).search(action['domain']))

    def test_task_and_customer_links_return_scoped_work(self):
        lead = self.lead()
        customer_action = lead.with_user(self.ops).action_open_field_customer()
        self.assertEqual(customer_action['res_id'], self.customer.id)
        self.assertEqual(customer_action['target'], 'new')
        with self.assertRaises(AccessError), self.cr.savepoint():
            lead.with_user(self.contractor).action_open_field_customer()
        action = lead.field_task_ids.with_user(self.ops).action_open_field_work_card()
        self.assertEqual(action['res_id'], lead.id)
        action = self.customer.with_user(self.ops).action_open_field_client_work()
        self.assertIn(lead, self.env['crm.lead'].with_user(self.ops).search(action['domain']))

    def test_dashboard_arch_hides_finance_for_operations(self):
        view_id = self.env.ref('field_work_photos.view_field_dashboard').id
        Dashboard = self.env['field.work.dashboard'].with_user(self.ops)
        arch = Dashboard.get_view(view_id, 'form')['arch']
        self.assertNotIn('name="collection_balance"', arch)
        self.assertIn('name="review_count"', arch)
        owner_arch = Dashboard.with_user(self.env.ref('base.user_admin')).get_view(view_id, 'form')['arch']
        self.assertIn('name="collection_balance"', owner_arch)

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

    def test_workspace_focus_follows_planning_execution_and_collection(self):
        draft = self.env['crm.lead'].with_user(self.ops).create({'name': 'Plan', 'is_field_service': True})
        self.assertEqual(draft.action_open_field_workspace()['views'][0][0],
                         self.env.ref('field_work_photos.view_field_lead_form').id)
        lead = self.lead()
        self.assertEqual(lead.action_open_field_workspace()['views'][0][0],
                         self.env.ref('field_work_photos.view_field_lead_execution_focus').id)
        lead.write({'field_report_before_image': self.photo, 'field_report_after_image': self.photo})
        lead.action_submit_field_report()
        action = lead.action_approve_field_report()
        self.assertEqual(action['views'][0][0], self.env.ref('field_work_photos.view_field_lead_collection_focus').id)
        self.assertEqual(action['res_id'], lead.id)
        from lxml import etree
        focused_arch = etree.fromstring(lead.get_view(view_id=action['views'][0][0], view_type='form')['arch'])
        self.assertTrue(focused_arch.xpath('//page[@name="field_collection" and @autofocus="autofocus"]'))
        self.assertEqual(lead.field_dispatch_code, 'completed')

    def test_private_finance_focus_and_portal_workspace_access(self):
        lead = self.lead()
        with self.assertRaises(AccessError), self.cr.savepoint():
            lead._field_workspace_action(focus='finance')
        with self.assertRaises(AccessError), self.cr.savepoint():
            lead.with_user(self.contractor).action_open_field_workspace()
        owner = lead.with_user(self.env.ref('base.user_admin'))
        self.assertEqual(owner._field_workspace_action(focus='finance')['views'][0][0],
                         self.env.ref('field_work_photos.view_field_lead_finance_focus').id)

    def test_workspace_rejects_ordinary_crm_records(self):
        lead = self.env['crm.lead'].with_user(self.ops).create({'name': 'Ordinary sales record'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.action_open_field_workspace()

    def test_tabs_preserve_customer_collection_and_hide_owner_finances(self):
        from lxml import etree
        view_id = self.env.ref('field_work_photos.view_field_lead_form').id
        arch = etree.fromstring(self.env['crm.lead'].with_user(self.ops).get_view(view_id=view_id, view_type='form')['arch'])
        self.assertTrue(arch.xpath('//page[@name="field_planning"]'))
        self.assertTrue(arch.xpath('//page[@name="field_collection"]'))
        self.assertFalse(arch.xpath('//page[@name="field_finance"]'))
        owner_arch = etree.fromstring(self.env['crm.lead'].with_user(self.env.ref('base.user_admin')).get_view(view_id=view_id, view_type='form')['arch'])
        self.assertTrue(owner_arch.xpath('//page[@name="field_finance"]'))
