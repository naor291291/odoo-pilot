import base64
from io import BytesIO

from PIL import Image
from odoo import fields, Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestClientWorkcard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = new_test_user(cls.env, login='workcard_owner', groups='field_work_photos.group_field_finance')
        cls.ops = new_test_user(cls.env, login='workcard_ops', groups='field_work_photos.group_field_dispatcher')
        cls.contractor = new_test_user(cls.env, login='workcard_contractor', groups='field_work_photos.group_field_contractor')
        cls.other = new_test_user(cls.env, login='workcard_other', groups='field_work_photos.group_field_contractor')
        cls.partner = cls.env['res.partner'].create({'name': 'Synthetic customer — Shahar scenario', 'phone': '0500000000'})
        stream = BytesIO(); Image.new('RGB', (8, 8), 'blue').save(stream, 'PNG')
        cls.photo = base64.b64encode(stream.getvalue())

    def work(self, **values):
        return self.env['crm.lead'].with_user(self.owner).create({
            'name': 'Synthetic work', 'partner_id': self.partner.id, 'is_field_service': True,
            'phone': '0500000000', 'field_site_address': 'Synthetic Street', 'field_work_description': 'Synthetic repair',
            'field_sale_amount': 700, 'field_material_cost': 273, 'field_visit_at': fields.Datetime.now(),
            'field_contractor_id': self.contractor.id, **values})

    def document(self, work, kind, number, amount=0, **values):
        return self.env['field.work.document'].with_user(self.owner).create({
            'lead_id': work.id, 'kind': kind, 'number': number, 'amount': amount, **values})

    def complete(self, work):
        work.action_workcard_dispatch()
        work.write({'field_report_before_image': self.photo, 'field_report_after_image': self.photo,
                    'field_visit_summary': 'Synthetic completion'})
        work.action_submit_field_report(); work.action_approve_field_report()

    def payment(self, work, amount, key):
        return self.env['field.work.payment'].with_user(self.owner).create({
            'lead_id': work.id, 'kind': 'customer', 'amount': amount, 'method': 'transfer', 'reference': key})

    def test_acceptance_700_273_65(self):
        work = self.work()
        self.assertEqual(work.field_commission_base, 427)
        self.assertEqual(work.field_applied_rate, 65)
        self.assertEqual(work.field_commission_amount, 277.55)
        self.assertEqual(work.field_contractor_cost, 277.55)
        self.assertEqual(work.field_gross_profit, 149.45)

    def test_expenses_deducted_once_and_reimbursement_approved(self):
        work = self.work(field_material_cost=100, field_sheet_business_expenses=173, field_sheet_contractor_expenses=50)
        self.assertEqual(work.field_commission_amount, 277.55)
        self.assertEqual(work.field_contractor_cost, 277.55)
        work.field_expenses_approved = True
        self.assertEqual(work.field_contractor_cost, 327.55)
        work.field_sheet_contractor_expenses = 60
        self.assertFalse(work.field_expenses_approved)
        self.assertEqual(work.field_contractor_cost, 277.55)
        work.field_expenses_approved = True
        work.with_user(self.ops).write({'field_execution_type': 'direct', 'field_worker_id': self.ops.id})
        self.assertFalse(work.field_expenses_approved)

    def test_negative_base_is_visible_and_payout_blocked(self):
        work = self.work(field_material_cost=800, field_contractor_due=100)
        self.assertEqual(work.field_commission_base, -100)
        self.assertEqual(work.field_commission_amount, -65)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            work.action_register_contractor_payment()

    def test_negative_base_blocks_direct_payment_even_with_reimbursement(self):
        work = self.work(field_material_cost=800, field_contractor_due=200,
                         field_sheet_contractor_expenses=300, field_expenses_approved=True)
        self.assertGreater(work.field_contractor_cost, 0)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['field.work.payment'].with_user(self.owner).create({
                'lead_id': work.id, 'kind': 'contractor', 'amount': 10,
                'method': 'transfer', 'reference': 'blocked-negative-base'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            work.action_approve_contractor_amount()
        self.assertFalse(work.field_payout_ids)

    def test_negative_base_does_not_disclose_private_finances_to_dispatcher(self):
        work = self.work(field_material_cost=800, field_contractor_due=100).with_user(self.ops)
        for action in (work.action_register_contractor_payment, work.action_approve_contractor_amount):
            with self.assertRaises(AccessError), self.cr.savepoint():
                action()

    def test_enrolment_rejects_foreign_company_portal_account(self):
        company = self.env['res.company'].create({'name': 'Separate contractor company'})
        self.other.company_ids |= company
        self.other.partner_id.email = 'cross-company@example.invalid'
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.other.partner_id.with_user(self.owner).action_enrol_field_contractor()

    def test_legacy_formula_cannot_bypass_negative_base(self):
        work = self.work(field_material_cost=800)
        with self.assertRaises(AccessError), self.cr.savepoint():
            work.write({'field_commission_formula': 'gross'})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.work(field_commission_formula='gross')
        self.assertEqual(self.work().field_commission_formula, 'net')

    def test_financial_input_change_requires_amount_reapproval(self):
        work = self.work(field_contractor_due=300)
        work.action_approve_contractor_amount()
        self.assertTrue(work.field_contractor_amount_approved)
        work.field_material_cost = 200
        self.assertFalse(work.field_contractor_amount_approved)
        self.assertEqual(work.field_contractor_due, 300)
        self.assertEqual(work.field_commission_amount, 325)

    def test_rate_snapshot_and_cost_updates(self):
        work = self.work(); work.action_workcard_dispatch()
        self.contractor.partner_id.field_rate_medium = 20
        self.assertEqual(work.field_applied_rate, 65)
        work.field_material_cost = 200
        self.assertEqual(work.field_commission_amount, 325)

    def test_two_screens_and_shared_stage(self):
        work = self.work()
        action = work.action_workcard_setup()
        self.assertEqual(action['views'][0][0], self.env.ref('field_work_photos.view_field_workcard').id)
        work.action_workcard_dispatch()
        self.assertEqual(work.field_task_ids.stage_id, self.env.ref('field_work_photos.task_stage_field_dispatch'))
        work.action_workcard_dispatch()
        self.assertEqual(len(work.field_task_ids), 1)

    def test_proforma_and_invoice_one_debt_partial_payment(self):
        work = self.work()
        self.document(work, 'proforma', 'PF-700', 700)
        self.assertEqual(work.field_customer_balance, 700)
        self.document(work, 'invoice', 'INV-700', 700)
        self.assertEqual(work.field_customer_balance, 700)
        self.payment(work, 250, 'partial')
        self.assertEqual(work.field_customer_balance, 450)
        self.assertEqual(work.field_collection_status, 'partial')
        self.assertEqual(len(work.field_document_history_ids), 2)

    def test_manual_total_cannot_bypass_registered_bill(self):
        work = self.work()
        self.document(work, 'invoice', 'ACTUAL-700', 700)
        self.payment(work, 500, 'PART-500')
        with self.assertRaises(ValidationError), self.cr.savepoint():
            work.write({'field_customer_due': 500})
        self.assertEqual(work.field_customer_due, 700)
        self.assertEqual(work.field_customer_balance, 200)
        self.document(work, 'invoice', 'CORRECTED-650', 650)
        self.assertEqual(work.field_customer_balance, 150)
        self.assertEqual(len(work.field_document_history_ids), 2)

    def test_multiple_documents_in_one_save_set_one_final_debt(self):
        work = self.work()
        documents = self.env['field.work.document'].with_user(self.owner).create([
            {'lead_id': work.id, 'kind': 'quote', 'number': 'BATCH-Q'},
            {'lead_id': work.id, 'kind': 'proforma', 'number': 'BATCH-PF', 'amount': 700},
            {'lead_id': work.id, 'kind': 'invoice', 'number': 'BATCH-INV', 'amount': 650}])
        self.assertEqual(len(documents), 3)
        self.assertEqual(work.field_customer_due, 650)
        self.assertEqual(work.field_customer_balance, 650)
        self.assertEqual(work.field_invoice_number, 'BATCH-INV')
        self.assertEqual(work.field_quote_number, 'BATCH-Q')

    def test_full_payment_requires_receipt_then_closes(self):
        work = self.work(); self.document(work, 'invoice', 'INV', 700); self.complete(work)
        self.payment(work, 700, 'paid')
        with self.assertRaises(ValidationError), self.cr.savepoint(): work.action_close_field_work()
        self.document(work, 'receipt', 'R-700', 700)
        work.action_close_field_work()
        self.assertEqual(work.field_dispatch_code, 'paid')
        self.assertEqual(len(work.field_document_history_ids), 2)

    def test_receipt_does_not_fake_payment(self):
        work = self.work(); self.document(work, 'invoice_receipt', 'IR', 700); self.complete(work)
        with self.assertRaises(ValidationError), self.cr.savepoint(): work.action_close_field_work()
        self.assertEqual(work.field_customer_paid, 0)

    def test_document_history_immutable_and_duplicates(self):
        work = self.work(); doc = self.document(work, 'invoice', 'INV', 700)
        for operation in [lambda: doc.write({'number': 'OTHER'}), doc.unlink]:
            with self.assertRaises(AccessError), self.cr.savepoint(): operation()
        with self.assertRaises(ValidationError), self.cr.savepoint(): self.document(work, 'invoice', 'INV', 700)
        self.document(work, 'receipt', 'R', 700)
        self.assertEqual(doc.number, 'INV')

    def test_number_then_pdf_is_archived_once_without_replacement(self):
        from reportlab.pdfgen import canvas
        stream = BytesIO(); pdf = canvas.Canvas(stream); pdf.drawString(20, 20, 'Original'); pdf.save()
        payload = base64.b64encode(stream.getvalue())
        work = self.work()
        work.field_quote_number = 'LEGACY-Q'
        doc = work.field_document_history_ids
        self.assertEqual(len(doc), 1)
        self.assertFalse(doc.pdf)
        work.write({'field_quote_pdf': payload, 'field_quote_filename': 'original.pdf'})
        self.assertEqual(doc.pdf, payload)
        self.assertEqual(doc.filename, 'original.pdf')
        self.assertEqual(len(work.field_document_history_ids), 1)
        with self.assertRaises(AccessError), self.cr.savepoint():
            doc.with_user(self.ops).write({'pdf': payload})

    def test_historical_archive_does_not_rewrite_debt(self):
        # A migration snapshot must not rerun collection writes on historical work.
        work = self.work(field_customer_due=700, field_invoice_number='HIST-INV')
        old_due = work.field_customer_due
        work._archive_legacy_documents(update_debt=False)
        self.assertEqual(work.field_customer_due, old_due)
        self.assertEqual(work.field_document_history_ids.number, 'HIST-INV')

    def test_upgrade_preserves_historical_formula_and_documents(self):
        import importlib.util
        from pathlib import Path
        migration = Path(__file__).resolve().parents[1] / 'migrations/18.0.18.0.0'
        closed = self.work(field_customer_due=700, field_invoice_number='MIG-INV')
        opened = self.work()
        approved = self.work(field_contractor_due=300)
        approved.action_approve_contractor_amount()
        approved.sudo()._migrate_commission_formula('gross')
        # Model a pre-upgrade closed row: old releases did not require a receipt.
        self.env.flush_all()
        self.cr.execute("UPDATE crm_lead SET stage_id=%s, field_commission_formula='gross' WHERE id=%s",
                        [self.env.ref('field_work_photos.stage_field_paid').id, closed.id])
        self.cr.execute("UPDATE crm_lead SET field_commission_formula='gross' WHERE id=%s", [opened.id])
        for name in ('pre', 'post'):
            spec = importlib.util.spec_from_file_location('workcard_' + name, migration / (name + '-migrate.py'))
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            self.env.invalidate_all()
            module.migrate(self.cr, '18.0.17.0.2')
        self.env.invalidate_all()
        self.assertEqual(closed.field_commission_formula, 'gross')
        self.assertEqual(opened.field_commission_formula, 'net')
        self.assertEqual(approved.field_commission_formula, 'gross')
        self.assertTrue(approved.field_contractor_amount_approved)
        self.assertEqual(closed.field_customer_due, 700)
        self.assertEqual(closed.field_dispatch_code, 'paid')
        self.assertEqual(closed.field_document_history_ids.number, 'MIG-INV')
        self.assertFalse(closed.field_document_history_ids.filtered(lambda doc: doc.kind == 'receipt'))

    def test_zero_rate_contractor_can_still_receive_approved_expenses(self):
        self.contractor.partner_id.field_rate_medium = 0
        work = self.work(field_sheet_contractor_expenses=50, field_expenses_approved=True)
        self.assertEqual(work.field_commission_amount, 0)
        self.assertEqual(work.field_contractor_cost, 50)

    def test_register_keeps_existing_document_integration_current(self):
        work = self.work()
        first = self.document(work, 'invoice', 'ORIGINAL', 700)
        self.assertEqual(work.field_invoice_number, 'ORIGINAL')
        self.document(work, 'invoice_receipt', 'COMBINED', 700)
        self.assertEqual(work.field_invoice_number, 'COMBINED')
        self.assertEqual(len(work.field_document_history_ids), 2)
        self.assertEqual(first.number, 'ORIGINAL')
        self.assertEqual(work.field_customer_due, 700)

    def test_document_audit_identity_cannot_be_spoofed(self):
        work = self.work()
        for extra in ({'create_uid': self.ops.id}, {'company_id': self.env.company.id}, {'currency_id': self.env.ref('base.USD').id}):
            with self.assertRaises(AccessError), self.cr.savepoint():
                self.document(work, 'receipt', 'SPOOF', **extra)
        model = self.env['field.work.document'].with_user(self.owner).with_context(default_create_uid=self.ops.id)
        self.assertNotIn('create_uid', model.default_get(['create_uid']))
        document = self.document(work, 'receipt', 'REAL')
        self.assertEqual(document.create_uid, self.owner)

    def test_issued_document_cannot_be_moved_to_another_customer(self):
        work = self.work()
        document = self.document(work, 'invoice', 'BOUND-TO-CUSTOMER', 700)
        customer = self.env['res.partner'].create({'name': 'Different synthetic customer'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            work.write({'partner_id': customer.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            work.write({'is_field_service': False})
        self.assertEqual(work.partner_id, self.partner)
        self.assertEqual(document.lead_id.partner_id, self.partner)
        work.write({'field_site_address': 'Corrected work address'})
        self.assertEqual(work.field_site_address, 'Corrected work address')

    def test_legacy_invoice_without_amount_is_preserved_without_inventing_debt(self):
        work = self.work(field_invoice_number='LEGACY-UNKNOWN')
        work._archive_legacy_documents()
        document = work.field_document_history_ids
        self.assertEqual(document.kind, 'invoice')
        self.assertFalse(document.amount_known)
        self.assertEqual(work.field_customer_due, 0)
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.document(work, 'invoice', 'FORGED-UNKNOWN', 100, amount_known=False)

    def test_invalid_pdf_and_receipt_number(self):
        work = self.work()
        with self.assertRaises(ValidationError), self.cr.savepoint(): self.document(work, 'receipt', '   ')
        with self.assertRaises(ValidationError), self.cr.savepoint(): self.document(work, 'invoice', 'BAD', 700, pdf=base64.b64encode(b'not pdf'))

    def test_contractor_cannot_read_other_work_documents(self):
        work = self.work(); doc = self.document(work, 'invoice', 'INV', 700)
        for user in (self.contractor, self.other):
            with self.assertRaises(AccessError), self.cr.savepoint(): doc.with_user(user).read(['number', 'pdf'])

    def test_finance_enrolment_is_idempotent_and_not_admin(self):
        partner = self.env['res.partner'].with_user(self.owner).create({'name': 'Synthetic new contractor', 'email': 'workcard-new@example.invalid'})
        partner.action_enrol_field_contractor(); partner.action_enrol_field_contractor()
        users = self.env['res.users'].search([('partner_id', '=', partner.id)])
        self.assertEqual(len(users), 1); self.assertTrue(users.share)
        self.assertTrue(users.has_group('field_work_photos.group_field_contractor'))
        self.assertFalse(users.has_group('base.group_system'))
        self.assertFalse(self.owner.has_group('base.group_erp_manager'))

    def test_enrolment_denies_ops_and_internal_takeover(self):
        with self.assertRaises(AccessError), self.cr.savepoint(): self.partner.with_user(self.ops).action_enrol_field_contractor()
        self.owner.partner_id.email = 'workcard-internal@example.invalid'
        with self.assertRaises(ValidationError), self.cr.savepoint(): self.owner.partner_id.with_user(self.owner).action_enrol_field_contractor()

    def test_paid_and_outstanding_actions_are_disjoint(self):
        from odoo.tools.safe_eval import safe_eval
        pending = safe_eval(self.env.ref('field_work_photos.action_field_collections').domain)
        paid = safe_eval(self.env.ref('field_work_photos.action_field_collections_paid').domain)
        work = self.work(); self.document(work, 'proforma', 'PF', 700)
        self.assertIn(work.id, self.env['crm.lead'].search(pending).ids)
        self.assertNotIn(work.id, self.env['crm.lead'].search(paid).ids)

    def test_all_business_entry_points_open_the_central_card(self):
        card = self.env.ref('field_work_photos.view_field_workcard')
        for name in ('action_field_service_leads', 'action_field_collections', 'action_field_collections_paid',
                     'action_field_payouts', 'action_field_work_attention'):
            action = self.env.ref('field_work_photos.' + name)
            self.assertEqual(action.view_ids.filtered(lambda view: view.view_mode == 'form').view_id, card)

    def test_new_workcard_has_no_tabs_and_finance_fields_hidden_from_ops(self):
        view = self.env.ref('field_work_photos.view_field_workcard')
        result = self.env['crm.lead'].with_user(self.ops).get_view(view.id, 'form')['arch']
        self.assertNotIn('<notebook', result)
        self.assertNotIn('name="field_commission_amount"', result)

    def test_live_acceptance_navigation_and_document_widgets(self):
        from lxml import etree
        root = self.env.ref('field_work_photos.menu_field_money')
        collections = self.env.ref('field_work_photos.menu_field_collections_root')
        self.assertEqual(collections.parent_id, root)
        self.assertNotEqual(collections.name, root.name)
        self.assertEqual(self.env.ref('field_work_photos.action_field_collections_paid').search_view_id,
                         self.env.ref('field_work_photos.view_field_collection_search'))
        view = self.env.ref('field_work_photos.view_field_workcard')
        arch = etree.fromstring(self.env['crm.lead'].with_user(self.owner).get_view(view.id, 'form')['arch'])
        pdf = arch.xpath("//field[@name='field_document_history_ids']/list/field[@name='pdf']")[0]
        self.assertEqual(pdf.get('widget'), 'binary')
        self.assertEqual(pdf.get('filename'), 'filename')
        self.assertEqual(arch.xpath("//field[@name='field_commission_formula']")[0].get('string'), 'שיטת חישוב העמלה')
