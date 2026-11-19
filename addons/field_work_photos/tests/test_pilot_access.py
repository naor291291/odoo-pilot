from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged, new_test_user

from ..models import pilot_access


@tagged('post_install', '-at_install')
class TestPilotAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kobi = new_test_user(cls.env, login='synthetic_kobi', groups=pilot_access.OPS)
        cls.portal = new_test_user(cls.env, login='synthetic_kobi_contractor', groups='field_work_photos.group_field_contractor')
        cls.customer = cls.env['res.partner'].create({'name': 'Synthetic Kobi customer'})

    def enable(self):
        return pilot_access.enable(self.env, self.kobi.login, self.kobi.id)

    def lead(self):
        return self.env['crm.lead'].with_user(self.kobi).create({
            'name': 'Synthetic Kobi work', 'is_field_service': True, 'partner_id': self.customer.id,
            'field_contractor_id': self.portal.id, 'field_sale_amount': 1000, 'field_customer_due': 1180})

    def test_preflight_checks_exact_identity_without_writes(self):
        before = self.kobi.write_date
        result = pilot_access.preflight(self.env, self.kobi.login, self.kobi.id)
        self.assertFalse(result['finance'])
        self.assertEqual(self.kobi.write_date, before)
        with self.assertRaises(ValidationError):
            pilot_access.preflight(self.env, self.kobi.login, self.portal.id)
        with self.assertRaises(ValidationError):
            pilot_access.preflight(self.env, 'missing_pilot_account')
        with self.assertRaises(AccessError):
            pilot_access.preflight(self.env(user=self.kobi), self.kobi.login)

    def test_role_change_and_restore_preserve_companies_and_groups(self):
        groups, companies = self.kobi.groups_id, self.kobi.company_ids
        receipt = self.enable()
        self.assertTrue(self.kobi.has_group(pilot_access.FINANCE))
        for group in ('base.group_system', 'base.group_erp_manager'):
            self.assertFalse(self.kobi.has_group(group))
        pilot_access.restore(self.env, receipt)
        self.assertFalse(self.kobi.has_group(pilot_access.FINANCE))
        self.assertEqual(self.kobi.groups_id, groups)
        self.assertEqual(self.kobi.company_ids, companies)
        pilot_access.restore(self.env, receipt)

    def test_restore_does_not_remove_preexisting_finance(self):
        self.enable()
        receipt = self.enable()
        self.assertFalse(receipt['added_finance'])
        pilot_access.restore(self.env, receipt)
        self.assertTrue(self.kobi.has_group(pilot_access.FINANCE))

    def test_no_system_user_or_permission_management(self):
        self.enable()
        for model in ('res.users', 'res.groups', 'ir.model.access', 'ir.rule'):
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.kobi).check_access('create')
        with self.assertRaises(AccessError):
            self.lead().action_create_field_contractor()

    def test_business_views_and_actions_are_available(self):
        self.enable()
        views = [
            ('crm.lead', 'view_field_lead_form'),
            ('res.partner', 'view_field_client_form'),
            ('res.partner', 'view_partner_field_rates'),
            ('project.task', 'view_field_task_form'),
        ]
        for model, xmlid in views:
            result = self.env[model].with_user(self.kobi).get_view(self.env.ref('field_work_photos.' + xmlid).id, 'form')
            self.assertTrue(result['arch'])
        for model in ('crm.lead', 'res.partner', 'project.task', 'field.work.payment.register',
                      'field.contractor.statement', 'field.work.owner.dashboard'):
            self.env[model].with_user(self.kobi).check_access('read')
            self.env[model].with_user(self.kobi).check_access('create')
            self.env[model].with_user(self.kobi).check_access('write')
        dashboard = self.env['field.work.owner.dashboard'].with_user(self.kobi).create({})
        self.assertEqual(dashboard.currency_id, self.env.ref('base.ILS'))
        lead = self.lead()
        self.assertTrue(lead._field_workspace_action('finance'))

    def test_financial_edits_are_logged_without_disclosing_amounts(self):
        self.enable()
        lead = self.lead()
        before = lead.message_ids
        lead.with_context(tracking_disable=True).write({'field_sale_amount': 1234, 'field_material_cost': 333,
                                                       'field_contractor_due': 500, 'field_sheet_cash': 50})
        messages = lead.message_ids - before
        self.assertTrue(messages)
        self.assertTrue(any('עדכון כספי' in m.body for m in messages))
        self.assertTrue(all(m.author_id == self.kobi.partner_id for m in messages))
        self.assertFalse(messages.tracking_value_ids)
        self.assertFalse(messages.notification_ids)
        for value in ('1234', '333', '500'):
            self.assertTrue(all(value not in m.body for m in messages))
        partner = self.portal.partner_id.with_user(self.kobi)
        before = partner.message_ids
        partner.write({'field_rate_small': 50, 'field_rate_medium': 65, 'field_rate_large': 70})
        self.assertTrue(partner.message_ids - before)
        self.assertEqual(partner.field_rate_small, 50)
        self.assertEqual(lead.field_material_cost, 333)

    def test_receipts_and_payouts_use_existing_audited_ledger(self):
        self.enable()
        lead = self.lead()
        lead.field_contractor_due = 700
        for kind, amount in [('customer', 1180), ('contractor', 700)]:
            payment = self.env['field.work.payment'].with_user(self.kobi).create({
                'lead_id': lead.id, 'kind': kind, 'amount': amount, 'method': 'transfer', 'reference': 'synthetic-' + kind})
            self.assertEqual(payment.create_uid, self.kobi)
            self.assertEqual(payment.amount, amount)
            with self.assertRaises(AccessError), self.cr.savepoint():
                payment.write({'amount': 1})
        with self.assertRaises(ValidationError):
            lead.action_close_field_work()

    def test_restored_ops_cannot_edit_private_finances(self):
        receipt = self.enable()
        lead = self.lead()
        pilot_access.restore(self.env, receipt)
        with self.assertRaises(AccessError), self.cr.savepoint():
            lead.with_user(self.kobi).write({'field_material_cost': 22})
        with self.assertRaises(AccessError):
            lead.with_user(self.kobi)._check_collection_kind('contractor')
        lead.with_user(self.kobi).write({'field_sale_amount': 1200})

    def test_foreign_company_and_admin_accounts_are_rejected(self):
        self.enable()
        company = self.env['res.company'].create({'name': 'Synthetic foreign company'})
        foreign = self.env['crm.lead'].create({'name': 'Foreign', 'is_field_service': True, 'company_id': company.id})
        with self.assertRaises(AccessError), self.cr.savepoint():
            foreign.with_user(self.kobi).write({'field_material_cost': 10})
        with self.assertRaises(ValidationError):
            pilot_access.preflight(self.env, self.env.ref('base.user_admin').login)
