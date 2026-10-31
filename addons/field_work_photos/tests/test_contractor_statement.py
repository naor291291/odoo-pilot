import base64
from datetime import date
from io import BytesIO
import time

from freezegun import freeze_time
from lxml import html
from PIL import Image

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged, new_test_user

from ..models.contractor_statement import utc_boundary


@tagged('post_install', '-at_install')
class TestContractorStatement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = new_test_user(cls.env, login='statement_owner', groups='field_work_photos.group_field_finance')
        cls.ops = new_test_user(cls.env, login='statement_ops', groups='field_work_photos.group_field_dispatcher')
        cls.contractor = new_test_user(cls.env, login='statement_contractor', groups='field_work_photos.group_field_contractor')
        cls.other = new_test_user(cls.env, login='statement_other', groups='field_work_photos.group_field_contractor')
        cls.customer = cls.env['res.partner'].create({'name': 'לקוח דוח מלאכותי', 'phone': '0500000000'})
        stream = BytesIO()
        Image.new('RGB', (8, 8), 'blue').save(stream, 'PNG')
        cls.photo = base64.b64encode(stream.getvalue())

    def lead(self, **values):
        return self.env['crm.lead'].with_user(self.owner).create({
            'name': 'עבודה לדוח התחשבנות', 'is_field_service': True, 'partner_id': self.customer.id,
            'phone': '0500000000', 'field_site_address': 'רחוב בדיקה 1', 'field_work_description': 'בדיקת עבודה',
            'field_sale_amount': 1000, 'field_customer_due': 1180, 'field_contractor_due': 700,
            'field_quote_number': 'STATEMENT-1', 'field_contractor_id': self.contractor.id,
            'field_visit_at': '2026-08-10 09:00:00', **values})

    def pay(self, lead, amount, when, reference='PAY-1', kind='contractor'):
        with freeze_time(when + ' 10:00:00'):
            return self.env['field.work.payment'].with_user(self.owner).create({
                'lead_id': lead.id, 'kind': kind, 'amount': amount,
                'payment_date': when, 'reference': reference})

    def close(self, lead, when, approve=True):
        with freeze_time(when + ' 10:00:00'):
            for _ in range(4):
                lead.action_next_field_stage()
            lead.write({'field_report_before_image': self.photo, 'field_report_after_image': self.photo,
                        'field_visit_summary': 'העבודה הושלמה ונבדקה'})
            lead.action_submit_field_report()
            lead.action_approve_field_report()
            self.pay(lead, 1180, when, kind='customer')
            if approve:
                lead.action_approve_contractor_amount()
            lead.with_user(self.ops).action_close_field_work()

    def statement(self, start='2026-09-01', end='2026-09-30', contractor=None, **values):
        return self.env['field.contractor.statement'].with_user(self.owner).create({
            'contractor_id': (contractor or self.contractor).id, 'period_mode': 'range',
            'date_from': start, 'date_to': end, **values})

    def test_work_and_payment_same_month(self):
        with freeze_time('2026-09-01'):
            lead = self.lead()
        self.close(lead, '2026-09-10')
        self.pay(lead, 200, '2026-09-15')
        report = self.statement()._build_statement()
        self.assertEqual((report['opening'], report['credit'], report['paid'], report['closing']), (0, 700, 200, 500))
        self.assertEqual(sum(item['amount'] for item in report['rows']), 500)
        self.assertEqual(report['rows'][-1]['balance'], 500)

    def test_prior_work_current_payment_opening_partial(self):
        lead = self.lead()
        self.close(lead, '2026-08-10')
        self.pay(lead, 100, '2026-08-20')
        self.pay(lead, 250, '2026-09-12', 'PAY-2')
        report = self.statement()._build_statement()
        self.assertEqual((report['opening'], report['credit'], report['paid'], report['closing']), (600, 0, 250, 350))
        self.assertIn('PAY-2', report['rows'][0]['reference'])

    def test_advance_before_eligibility_is_negative_not_income(self):
        with freeze_time('2026-09-01'):
            lead = self.lead()
        self.pay(lead, 150, '2026-09-03')
        report = self.statement()._build_statement()
        self.assertEqual((report['credit'], report['paid'], report['closing']), (0, 150, -150))
        self.assertEqual(len(report['exceptions']), 1)
        self.close(lead, '2026-10-01')
        october = self.statement('2026-10-01', '2026-10-31')._build_statement()
        self.assertEqual((october['opening'], october['credit'], october['closing']), (-150, 700, 550))

    def test_later_payment_cancellation_does_not_erase_historic_payment(self):
        lead = self.lead()
        self.close(lead, '2026-08-10')
        payment = self.pay(lead, 200, '2026-09-05')
        with freeze_time('2026-10-02 10:00:00'):
            payment._cancel_registration('רישום שגוי')
        september = self.statement()._build_statement()
        october = self.statement('2026-10-01', '2026-10-31')._build_statement()
        self.assertEqual((september['opening'], september['paid'], september['adjustments'], september['closing']), (700, 200, 0, 500))
        self.assertEqual((october['opening'], october['paid'], october['adjustments'], october['closing']), (500, 0, 200, 700))
        # A legacy cancellation with no timestamp cannot be placed in a month.
        self.cr.execute('UPDATE field_work_payment SET cancelled_at = NULL WHERE id = %s', [payment.id])
        payment.invalidate_recordset()
        incomplete = self.statement()._build_statement()
        self.assertEqual(incomplete['unknown_cancellations'], 1)
        self.assertEqual(incomplete['paid'], 0)

    def test_same_month_cancellation_and_replacement(self):
        lead = self.lead()
        self.close(lead, '2026-08-10')
        payment = self.pay(lead, 200, '2026-09-05')
        with freeze_time('2026-09-07 10:00:00'):
            payment._cancel_registration('תיקון אסמכתה')
        self.pay(lead, 250, '2026-09-08', 'PAY-2')
        report = self.statement()._build_statement()
        self.assertEqual((report['opening'], report['paid'], report['adjustments'], report['closing']), (700, 450, 200, 450))

    def test_reopen_reverses_credit_and_reclose_preserves_prior_month(self):
        lead = self.lead()
        self.close(lead, '2026-08-10')
        with freeze_time('2026-09-02 10:00:00'):
            customer_payment = lead.field_payment_ids
            customer_payment._cancel_registration('תקבול שגוי')
        report = self.statement()._build_statement()
        self.assertEqual((report['opening'], report['adjustments'], report['closing']), (700, -700, 0))
        with freeze_time('2026-09-03 10:00:00'):
            self.pay(lead, 1180, '2026-09-03', 'CUSTOMER-NEW', kind='customer')
            lead.action_close_field_work()
        report = self.statement()._build_statement()
        self.assertEqual((report['credit'], report['adjustments'], report['closing']), (700, -700, 700))
        self.assertEqual(self.statement('2026-08-01', '2026-08-31')._build_statement()['closing'], 700)

    def test_due_change_requires_new_approval_and_delta_is_audited(self):
        lead = self.lead()
        self.close(lead, '2026-08-10')
        with freeze_time('2026-09-01 10:00:00'):
            lead.field_contractor_due = 800
        self.assertFalse(lead.field_contractor_amount_approved)
        self.assertEqual(self.statement()._build_statement()['closing'], 0)
        with freeze_time('2026-09-02 10:00:00'):
            lead.action_approve_contractor_amount()
            lead.action_approve_contractor_amount()
        report = self.statement()._build_statement()
        self.assertEqual((report['opening'], report['credit'], report['adjustments'], report['closing']), (700, 800, -700, 800))

    def test_rate_changes_do_not_change_approved_history(self):
        lead = self.lead()
        self.close(lead, '2026-09-10')
        self.contractor.partner_id.with_user(self.owner).field_rate_medium = 90
        report = self.statement()._build_statement()
        self.assertEqual(report['credit'], 700)
        self.assertEqual(report['rows'][0]['rate'], 65)
        self.assertEqual(report['rows'][0]['net_estimate'], 650)

    def test_missing_is_distinct_from_explicitly_approved_zero(self):
        with freeze_time('2026-09-01'):
            lead = self.lead(field_contractor_due=0)
        self.close(lead, '2026-09-10', approve=False)
        missing = self.statement()._build_statement()
        self.assertEqual(missing['credit'], 0)
        self.assertIsNone(missing['exceptions'][0]['gross'])
        self.assertEqual(len(missing['rows']), 0)
        with freeze_time('2026-09-11 10:00:00'):
            lead.action_approve_contractor_amount()
        zero = self.statement()._build_statement()
        self.assertEqual(zero['exceptions'], [])
        self.assertEqual(len(zero['rows']), 1)
        self.assertEqual(zero['rows'][0]['amount'], 0)

    def test_late_approval_is_not_backdated(self):
        lead = self.lead()
        self.close(lead, '2026-08-10', approve=False)
        with freeze_time('2026-09-12 10:00:00'):
            lead.action_approve_contractor_amount()
        report = self.statement()._build_statement()
        self.assertEqual((report['opening'], report['credit']), (0, 700))
        self.assertEqual(report['rows'][0]['date'], '2026-09-12')

    def test_month_boundaries_timezone_and_cents(self):
        lead = self.lead(field_contractor_due=0.30)
        self.close(lead, '2026-09-01', approve=False)
        with freeze_time('2026-09-30 21:00:00'):
            lead.action_approve_contractor_amount()
        self.assertEqual(self.statement()._build_statement()['credit'], 0)
        self.pay(lead, 0.10, '2026-10-01')
        self.pay(lead, 0.20, '2026-10-02', 'PAY-2')
        report = self.statement('2026-10-01', '2026-10-31')._build_statement()
        self.assertEqual((report['credit'], report['paid'], report['closing']), (0.30, 0.30, 0))
        self.assertEqual(str(utc_boundary(date(2026, 10, 1))), '2026-09-30 21:00:00')
        self.assertEqual(str(utc_boundary(date(2026, 11, 1))), '2026-10-31 22:00:00')
        viewer = self.statement().with_context(tz='America/Los_Angeles')
        self.assertEqual(viewer._build_statement()['credit'], 0)
        # A contractor advance entered from UTC+14 on October 1, while it is
        # still September 30 in Israel, must reverse in October when voided.
        edge = self.lead(field_contractor_due=10, field_contractor_id=self.other.id)
        with freeze_time('2026-09-30 20:30:00'):
            payment = self.env['field.work.payment'].with_user(self.owner).with_context(tz='Pacific/Kiritimati').create({
                'lead_id': edge.id, 'kind': 'contractor', 'amount': 1,
                'payment_date': '2026-10-01', 'reference': 'TIMEZONE-EDGE'})
            payment._cancel_registration('ביטול רישום באותו רגע')
        october = self.statement('2026-10-01', '2026-10-31', contractor=self.other)._build_statement()
        self.assertEqual((october['opening'], october['paid'], october['adjustments'], october['closing']), (0, 1, 1, 0))

    def test_period_validation_and_month_picker(self):
        with self.assertRaises(ValidationError):
            self.statement('2026-09-30', '2026-09-01')._build_statement()
        report = self.statement(period_mode='month', month_date='2024-02-15')
        self.assertEqual(report._period(), (date(2024, 2, 1), date(2024, 2, 29)))
        report._onchange_period()
        self.assertEqual(report.date_to, date(2024, 2, 29))

    def test_roles_direct_calls_output_injection_and_immutable_entries(self):
        lead = self.lead()
        self.close(lead, '2026-09-10')
        report = self.statement()
        for user in (self.ops, self.contractor, self.other):
            with self.assertRaises(AccessError), self.cr.savepoint():
                report.with_user(user).action_show_report()
            with self.assertRaises(AccessError), self.cr.savepoint():
                lead.with_user(user).action_approve_contractor_amount()
            with self.assertRaises(AccessError), self.cr.savepoint():
                self.env['report.field_work_photos.contractor_statement_pdf'].with_user(user)._get_report_values(report.ids)
        for action in (lambda: report.write({'payload': {'closing': 999}}),
                       lambda: self.statement(payload={'closing': 999}),
                       lambda: lead.write({'field_contractor_amount_approved': True})):
            with self.assertRaises(AccessError), self.cr.savepoint():
                action()
        defaults = self.env['field.contractor.statement'].with_user(self.owner).with_context(default_payload={'closing': 999}).default_get(['payload'])
        self.assertNotIn('payload', defaults)
        other_owner = new_test_user(self.env, login='statement_other_owner', groups='field_work_photos.group_field_finance')
        with self.assertRaises(AccessError), self.cr.savepoint():
            report.with_user(other_owner).read(['payload'])
        entry = self.env['field.work.entitlement'].with_user(self.owner).search([('lead_id', '=', lead.id)])
        for action in (lambda: entry.write({'amount': 1}), entry.unlink, entry.copy,
                       lambda: entry.create({'amount': 999})):
            with self.assertRaises(AccessError), self.cr.savepoint():
                action()

    def test_contractors_and_company_separation_and_archived_work(self):
        lead = self.lead()
        self.close(lead, '2026-09-10')
        lead.active = False
        self.assertEqual(self.statement()._build_statement()['credit'], 700)
        self.assertEqual(self.statement(contractor=self.other)._build_statement()['closing'], 0)
        company = self.env['res.company'].create({'name': 'חברה אחרת לבדיקת הפרדה'})
        owner_companies = self.owner.company_ids | company
        self.owner.company_ids = owner_companies
        report = self.statement().with_context(allowed_company_ids=owner_companies.ids)
        report.company_id = company
        self.assertEqual(report._build_statement()['closing'], 0)
        with self.assertRaises(AccessError), self.cr.savepoint():
            report.with_context(allowed_company_ids=[lead.company_id.id]).action_show_report()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.write({'field_contractor_id': self.other.id})

    def test_screen_pdf_use_identical_snapshot_and_do_not_change_business_records(self):
        lead = self.lead()
        self.close(lead, '2026-09-10')
        report = self.statement()
        before = (lead.write_date, self.env['field.work.entitlement'].search_count([]), self.env['field.work.payment'].search_count([]))
        report.action_show_report()
        screen = html.fromstring(report.report_html)
        action = self.env.ref('field_work_photos.action_report_contractor_statement').with_user(self.owner)
        pdf_html, _kind = action._render_qweb_html(action.report_name, report.ids)
        printed = html.fromstring(pdf_html)
        selector = '//*[@data-statement-closing]'
        self.assertEqual(screen.xpath(selector)[0].text_content(), printed.xpath(selector)[0].text_content())
        self.assertEqual(len(screen.xpath('//tbody/tr')), len(printed.xpath('//tbody/tr')))
        self.pay(lead, 200, '2026-09-12')
        self.assertEqual(report.payload['closing'], 700)
        self.assertEqual(report._build_statement()['closing'], 500)
        self.assertEqual(before[0], lead.write_date)
        self.assertEqual(before[1], self.env['field.work.entitlement'].search_count([]))
        self.assertEqual(before[2] + 1, self.env['field.work.payment'].search_count([]))
        report.date_to = '2026-10-31'
        self.assertFalse(report.payload)
        with self.assertRaises(ValidationError):
            report.action_print_pdf()

    def test_pdf_action_requires_own_finance_snapshot(self):
        lead = self.lead()
        self.close(lead, '2026-09-10')
        report = self.statement()
        report.action_show_report()
        action = report.action_print_pdf()
        self.assertEqual(action['report_type'], 'qweb-pdf')
        self.assertEqual(action['report_name'], 'field_work_photos.contractor_statement_pdf')
        self.assertEqual(action['context']['active_ids'], report.ids)
        with self.assertRaises(AccessError), self.cr.savepoint():
            report.with_user(self.ops).action_print_pdf()
        with self.assertRaises(AccessError), self.cr.savepoint():
            report.with_user(self.contractor).action_print_pdf()
        # A fresh pilot has no external document layout. Admins must still
        # receive the report action, not a business-settings configuration wizard.
        self.env.company.external_report_layout_id = False
        admin_report = self.env['field.contractor.statement'].with_user(self.env.ref('base.user_admin')).create({
            'contractor_id': self.contractor.id, 'period_mode': 'range',
            'date_from': '2026-09-01', 'date_to': '2026-09-30'})
        admin_report.action_show_report()
        self.assertEqual(admin_report.action_print_pdf()['type'], 'ir.actions.report')
        # Actual wkhtmltopdf output is mandatory in the HTTP/Playwright suite.
        # It must run with an HTTP server serving the report font/assets, not
        # inside an isolated TransactionCase lacking such a server.

    def test_representative_ledger_performance(self):
        # Bulk synthetic rows exercise report size, not the dispatch actions
        # (whose invariants are exercised above and by the existing suite).
        from ..models.field_entitlement import FieldWorkEntitlement
        lead = self.lead()
        self.close(lead, '2026-09-10')
        entry = self.env['field.work.entitlement'].search([('lead_id', '=', lead.id)])
        values = entry.copy_data()[0]
        values.pop('reversal_of_id', None)
        # Distinct source jobs ensure that prefetching is tested, rather than
        # reading the same cached work identity one thousand times. These
        # historical synthetic snapshots bypass dispatch only in this fixture.
        jobs = self.env['crm.lead'].with_user(self.owner).create([{
            'name': f'Synthetic performance job {index}', 'is_field_service': True,
            'partner_id': self.customer.id, 'field_contractor_id': self.contractor.id,
        } for index in range(1000)])
        super(FieldWorkEntitlement, self.env['field.work.entitlement']).create([
            dict(values, lead_id=job.id, amount=0.01) for job in jobs])
        self.env.flush_all()
        self.env.invalidate_all()
        report = self.statement()
        started = time.monotonic()
        queries_before = self.cr.sql_log_count
        payload = report._build_statement()
        query_count = self.cr.sql_log_count - queries_before
        self.assertEqual(len(payload['rows']), 1001)
        self.assertEqual(payload['closing'], 710)
        self.assertEqual([row['source_id'] for row in payload['rows']], sorted(row['source_id'] for row in payload['rows']))
        self.assertLess(query_count, 100, 'Report must use batched queries, not one query per movement')
        self.assertLess(time.monotonic() - started, 10)
