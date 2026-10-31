import base64
import json
from io import BytesIO

from PIL import Image
from lxml import html

from odoo import fields
from odoo.tests import HttpCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestFieldPortal(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.first = new_test_user(cls.env, login='http_contractor_1', password='test-pass-1', groups='field_work_photos.group_field_contractor')
        cls.second = new_test_user(cls.env, login='http_contractor_2', password='test-pass-2', groups='field_work_photos.group_field_contractor')
        cls.customer = cls.env['res.partner'].create({'name': 'Portal Customer', 'phone': '0501111111'})
        stream = BytesIO()
        Image.new('RGB', (8, 8), 'red').save(stream, 'PNG')
        cls.raw_photo = stream.getvalue()
        cls.leads = cls.env['crm.lead']
        for contractor, name in ((cls.first, 'First contractor private work'), (cls.second, 'Second contractor secret work')):
            lead = cls.env['crm.lead'].create({
                'name': name, 'is_field_service': True, 'partner_id': cls.customer.id,
                'field_sale_amount': 1000, 'field_quote_number': 'PORTAL-Q', 'field_contractor_id': contractor.id,
                'field_visit_at': fields.Datetime.now(), 'field_site_address': 'Portal Street',
                'field_work_description': 'Customer-facing description',
                'description': '<p>INTERNAL-SECRET-NOT-FOR-CONTRACTOR</p>',
                'expected_revenue': 65432,
            })
            for _ in range(4):
                lead.action_next_field_stage()
            cls.leads |= lead
        cls.own_task = cls.leads[0].field_task_ids
        cls.other_task = cls.leads[1].field_task_ids
        cls.own_task.write({'field_visit_summary': 'הוחלף הברז ונבדק', 'field_before_image': base64.b64encode(cls.raw_photo), 'field_after_image': base64.b64encode(cls.raw_photo)})
        cls.other_task.write({'field_before_image': base64.b64encode(cls.raw_photo)})

    def login(self):
        self.authenticate('http_contractor_1', 'test-pass-1')

    def detail(self, task=None):
        return '/my/field-work/%s' % (task or self.own_task).id

    def token(self, response=None):
        response = response or self.url_open(self.detail())
        return html.fromstring(response.content).xpath('//input[@name="csrf_token"]/@value')[0]

    def test_portal_home_and_only_assigned_list(self):
        self.login()
        home = self.url_open('/my/home')
        self.assertEqual(home.status_code, 200)
        self.assertIn('/my/field-work', home.text)
        page = self.url_open('/my/field-work')
        self.assertEqual(page.status_code, 200)
        self.assertIn(self.own_task.name, page.text)
        self.assertNotIn(self.other_task.name, page.text)

    def test_detail_has_no_internal_or_financial_fields(self):
        self.login()
        response = self.url_open(self.detail())
        self.assertEqual(response.status_code, 200)
        self.assertIn('Customer-facing description', response.text)
        self.assertNotIn('INTERNAL-SECRET', response.text)
        self.assertNotIn('65432', response.text)

    def test_foreign_detail_photo_and_post_return_404(self):
        self.login()
        for url in (self.detail(self.other_task), self.detail(self.other_task) + '/photo/before'):
            self.assertEqual(self.url_open(url).status_code, 404)
        response = self.url_open(self.detail(self.other_task) + '/report', data={'csrf_token': self.token(), 'action': 'submit'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.other_task.field_review_state, 'draft')

    def test_submission_records_portal_user_and_freezes_photos(self):
        self.login()
        response = self.url_open(self.detail() + '/report', data={'csrf_token': self.token(), 'action': 'submit', 'field_contractor_id': self.second.id})
        self.assertEqual(response.status_code, 200)
        self.own_task.invalidate_recordset()
        self.assertEqual(self.own_task.field_review_state, 'pending')
        self.assertEqual(self.own_task.field_submitted_by, self.first)
        self.assertEqual(self.own_task.field_contractor_id, self.first)
        response = self.url_open(self.detail() + '/report', data={'csrf_token': self.token(), 'action': 'upload'}, files={'field_before_image': ('photo.png', self.raw_photo, 'image/png')})
        self.assertIn('alert-danger', response.text)

    def test_submission_without_photos_is_rejected(self):
        self.own_task.write({'field_after_image': False})
        self.login()
        response = self.url_open(self.detail() + '/report', data={'csrf_token': self.token(), 'action': 'submit'})
        self.assertIn('alert-danger', response.text)
        self.own_task.invalidate_recordset()
        self.assertEqual(self.own_task.field_review_state, 'draft')

    def test_upload_rejects_invalid_bytes_and_saves_valid_image(self):
        self.login()
        url = self.detail() + '/report'
        response = self.url_open(url, data={'csrf_token': self.token(), 'action': 'upload'}, files={'field_after_image': ('fake.png', b'bad image', 'image/png')})
        self.assertIn('alert-danger', response.text)
        response = self.url_open(url, data={'csrf_token': self.token(), 'action': 'upload'}, files={'field_after_image': ('valid.png', self.raw_photo, 'image/png')})
        self.assertEqual(response.status_code, 200)
        photo = self.url_open(self.detail() + '/photo/after')
        self.assertEqual(photo.status_code, 200)
        self.assertEqual(photo.headers['Cache-Control'], 'private, no-store')
        self.assertTrue(photo.headers['Content-Type'].startswith('image/'))

    def test_reassignment_revokes_old_contractor_access(self):
        self.leads[0].write({'field_contractor_id': self.second.id})
        self.login()
        self.assertEqual(self.url_open(self.detail()).status_code, 404)
        self.assertEqual(self.url_open(self.detail() + '/photo/before').status_code, 404)
        self.authenticate('http_contractor_2', 'test-pass-2')
        self.assertEqual(self.url_open(self.detail()).status_code, 200)

    def test_csrf_and_non_contractor_access(self):
        self.login()
        response = self.url_open(self.detail() + '/report', data={'action': 'submit'})
        self.assertEqual(response.status_code, 400)
        self.authenticate('admin', 'admin')
        self.assertEqual(self.url_open('/my/field-work').status_code, 404)

    def test_combined_upload_and_submit_uses_selected_files(self):
        self.own_task.write({'field_before_image': False, 'field_after_image': False})
        self.login()
        response = self.url_open(self.detail() + '/report', data={'csrf_token': self.token(), 'action': 'submit'}, files={
            'field_before_image': ('before.png', self.raw_photo, 'image/png'),
            'field_after_image': ('after.png', self.raw_photo, 'image/png')})
        self.assertEqual(response.status_code, 200)
        self.assertIn('נשלחו לבדיקת התפעול', response.text)
        self.own_task.invalidate_recordset()
        self.assertEqual(self.own_task.field_review_state, 'pending')
        self.assertEqual(self.own_task.field_submitted_by, self.first)
        self.assertTrue(self.own_task.field_before_image and self.own_task.field_after_image)

    def test_combined_submit_can_use_saved_before_and_new_after(self):
        self.own_task.field_after_image = False
        self.login()
        response = self.url_open(self.detail() + '/report', data={'csrf_token': self.token(), 'action': 'submit'}, files={
            'field_after_image': ('after.png', self.raw_photo, 'image/png')})
        self.assertEqual(response.status_code, 200)
        self.own_task.invalidate_recordset()
        self.assertEqual(self.own_task.field_review_state, 'pending')

    def test_failed_combined_submit_rolls_back_uploaded_photo(self):
        self.own_task.write({'field_before_image': False, 'field_after_image': False})
        self.login()
        response = self.url_open(self.detail() + '/report', data={'csrf_token': self.token(), 'action': 'submit'}, files={
            'field_before_image': ('before.png', self.raw_photo, 'image/png')})
        self.assertIn('alert-danger', response.text)
        self.own_task.invalidate_recordset()
        self.assertEqual(self.own_task.field_review_state, 'draft')
        self.assertFalse(self.own_task.field_before_image)

    def test_bad_combined_upload_cannot_submit_existing_report(self):
        self.login()
        response = self.url_open(self.detail() + '/report', data={'csrf_token': self.token(), 'action': 'submit'}, files={
            'field_after_image': ('bad.png', b'bad image', 'image/png')})
        self.assertIn('alert-danger', response.text)
        self.own_task.invalidate_recordset()
        self.assertEqual(self.own_task.field_review_state, 'draft')

    def test_portal_scope_preserves_ownership_and_separates_pending(self):
        self.own_task.action_finish_field_work()
        self.login()
        active = self.url_open('/my/field-work')
        self.assertNotIn(self.own_task.name, active.text)
        pending = self.url_open('/my/field-work?scope=pending')
        self.assertIn(self.own_task.name, pending.text)
        self.assertNotIn(self.other_task.name, pending.text)

    def test_report_has_one_form_and_contact_links(self):
        self.login()
        response = self.url_open(self.detail())
        page = html.fromstring(response.content)
        self.assertEqual(len(page.xpath('//form[@data-field-report]')), 1)
        self.assertTrue(page.xpath('//a[starts-with(@href, "tel:")]'))
        self.assertIn('google.com/maps/search', response.text)
        self.assertIn('שליחת דיווח לבדיקה', response.text)
        self.assertIn('שמירה והמשך מאוחר יותר', response.text)

    def test_gallery_uploads_five_per_kind_in_one_submission(self):
        self.own_task.write({'field_before_image': False, 'field_after_image': False})
        self.login()
        files = [(f'field_{kind}_image', (f'{kind}-{n}.png', self.raw_photo, 'image/png'))
                 for kind in ('before', 'after') for n in range(5)]
        response = self.url_open(self.detail() + '/report', data={
            'csrf_token': self.token(), 'action': 'submit', 'field_visit_result': 'completed',
            'field_visit_summary': 'הוחלף ונבדק מכל הזוויות'}, files=files)
        self.assertNotIn('alert-danger', response.text)
        self.own_task.invalidate_recordset()
        self.assertEqual(self.own_task.field_review_state, 'pending')
        self.assertEqual(len(self.own_task.field_extra_photo_ids), 8)
        self.assertEqual(len(self.own_task._field_gallery('before')), 5)
        photo = self.own_task.field_extra_photo_ids[:1]
        image = self.url_open(self.detail() + '/photo/%s/%s' % (photo.kind, photo.id))
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers['Cache-Control'], 'private, no-store')

    def test_gallery_foreign_photo_and_removal_are_scoped_to_task(self):
        self.other_task._update_field_gallery({'before': [base64.b64encode(self.raw_photo)], 'after': []}, [])
        photo = self.other_task.field_extra_photo_ids[:1]
        self.login()
        self.assertEqual(self.url_open(self.detail() + '/photo/before/%s' % photo.id).status_code, 404)
        response = self.url_open(self.detail() + '/report', data={
            'csrf_token': self.token(), 'action': 'upload', 'remove_photo': 'before:%s' % photo.id})
        self.assertIn('alert-danger', response.text)
        self.assertTrue(photo.exists())

    def test_failed_report_rolls_back_deletion_and_text_updates(self):
        self.login()
        response = self.url_open(self.detail() + '/report', data={
            'csrf_token': self.token(), 'action': 'submit', 'remove_photo': 'before:0',
            'field_visit_summary': 'טקסט שנשאר לתיקון בטופס'})
        self.assertIn('alert-danger', response.text)
        self.assertIn('טקסט שנשאר לתיקון בטופס', response.text)
        self.own_task.invalidate_recordset()
        self.assertTrue(self.own_task.field_before_image)
        self.assertEqual(self.own_task.field_visit_summary, 'הוחלף הברז ונבדק')
        self.assertEqual(self.own_task.field_review_state, 'draft')

    def test_incomplete_report_without_photos_requires_reason_and_stays_open(self):
        self.own_task.write({'field_before_image': False, 'field_after_image': False})
        self.login()
        payload = {'csrf_token': self.token(), 'action': 'submit', 'field_visit_result': 'not_done', 'field_visit_reason': ''}
        response = self.url_open(self.detail() + '/report', data=payload)
        self.assertIn('alert-danger', response.text)
        payload['field_visit_reason'] = 'הלקוח לא נמצא. נדרש ביקור נוסף.'
        response = self.url_open(self.detail() + '/report', data=payload)
        self.assertIn('נשלחו לבדיקת התפעול', response.text)
        self.own_task.invalidate_recordset()
        self.assertEqual(self.own_task.field_review_state, 'pending')
        self.assertEqual(self.own_task.field_visit_result, 'not_done')
        self.assertEqual(self.leads[0].field_dispatch_code, 'field')
        self.assertNotIn('data-report-submit', response.text)

    def test_save_partial_report_and_reject_excess_images_atomically(self):
        self.login()
        response = self.url_open(self.detail() + '/report', data={
            'csrf_token': self.token(), 'action': 'upload', 'field_visit_summary': '', 'field_visit_notes': 'טיוטה מהשטח'})
        self.assertNotIn('alert-danger', response.text)
        self.own_task.invalidate_recordset()
        self.assertEqual(self.own_task.field_visit_notes, 'טיוטה מהשטח')
        files = [('field_before_image', ('photo.png', self.raw_photo, 'image/png')) for _ in range(5)]
        response = self.url_open(self.detail() + '/report', data={
            'csrf_token': self.token(), 'action': 'upload', 'field_visit_notes': 'לא לשמור'}, files=files)
        self.assertIn('alert-danger', response.text)
        self.own_task.invalidate_recordset()
        self.assertEqual(len(self.own_task._field_gallery('before')), 1)
        self.assertEqual(self.own_task.field_visit_notes, 'טיוטה מהשטח')

    def test_saved_photo_removal_and_new_image_use_single_transaction(self):
        self.login()
        response = self.url_open(self.detail() + '/report', data={
            'csrf_token': self.token(), 'action': 'upload', 'remove_photo': 'before:0'}, files={
                'field_before_image': ('bad.png', b'invalid image', 'image/png')})
        self.assertIn('alert-danger', response.text)
        self.own_task.invalidate_recordset()
        self.assertTrue(self.own_task.field_before_image)
        response = self.url_open(self.detail() + '/report', data={
            'csrf_token': self.token(), 'action': 'upload', 'remove_photo': 'before:0'}, files={
                'field_before_image': ('new.png', self.raw_photo, 'image/png')})
        self.assertNotIn('alert-danger', response.text)
        self.own_task.invalidate_recordset()
        self.assertEqual(len(self.own_task._field_gallery('before')), 1)

    def test_site_details_are_displayed_and_foreign_extra_access_revoked(self):
        self.leads[0].write({'contact_name': 'איש קשר באתר', 'field_site_unit': 'קומה 4 דירה 8',
                             'field_access_instructions': 'כניסה דרך החניון'})
        self.own_task._update_field_gallery({'before': [base64.b64encode(self.raw_photo)], 'after': []}, [])
        photo = self.own_task.field_extra_photo_ids[:1]
        url = self.detail() + '/photo/before/%s' % photo.id
        self.login()
        response = self.url_open(self.detail())
        for text in ('איש קשר באתר', 'קומה 4 דירה 8', 'כניסה דרך החניון'):
            self.assertIn(text, response.text)
        self.assertEqual(self.url_open(url).status_code, 200)
        self.leads[0].write({'field_contractor_id': self.second.id})
        self.assertEqual(self.url_open(url).status_code, 404)

    def test_field_branding_preserves_configured_identity_across_cached_routes(self):
        self.login()
        company = self.first.company_id
        company.name = 'My Company'
        self.url_open('/my/home')  # Prime the shared native portal header cache.
        page = self.url_open(self.detail())
        self.assertEqual(page.status_code, 200)
        tree = html.fromstring(page.content)
        self.assertTrue(tree.xpath('//span[contains(@class,"o_field_portal_brand")][text()="עבודות שטח"]'))
        outside = html.fromstring(self.url_open('/my/home').content)
        self.assertFalse(outside.xpath('//span[contains(@class,"o_field_portal_brand")]'))
        company.write({'name': 'עסק בדיקה מוגדר', 'logo': base64.b64encode(self.raw_photo)})
        page = html.fromstring(self.url_open(self.detail()).content)
        self.assertFalse(page.xpath('//span[contains(@class,"o_field_portal_brand")]'))
        self.assertTrue(page.xpath('//a[contains(@class,"navbar-brand")]/img[@alt="עסק בדיקה מוגדר"]'))

    def test_private_native_binary_routes_and_logout(self):
        self.login()
        own_url = self.detail() + '/photo/before'
        raw = self.url_open(own_url).content
        for task in (self.own_task, self.other_task):
            for route in ('/web/content/project.task/%s/field_before_image',
                          '/web/image/project.task/%s/field_before_image'):
                response = self.url_open(route % task.id)
                self.assertNotEqual(response.content, raw)
        self.authenticate(None, None)
        for url in (self.detail(), own_url, '/my/field-work'):
            response = self.url_open(url, allow_redirects=False)
            self.assertIn(response.status_code, (302, 303))
            self.assertNotEqual(response.content, raw)

    def test_extra_photo_id_and_generic_routes_remain_scoped(self):
        self.other_task._update_field_gallery({'before': [base64.b64encode(self.raw_photo)], 'after': []}, [])
        extra = self.other_task.field_extra_photo_ids[:1]
        self.login()
        self.assertEqual(self.url_open(self.detail() + '/photo/before/%s' % extra.id).status_code, 404)
        response = self.url_open('/web/content/field.work.photo/%s/image' % extra.id)
        self.assertNotEqual(response.status_code, 200)
        response = self.url_open(self.detail() + '/report', data={
            'csrf_token': self.token(), 'action': 'upload', 'remove_photo': 'before:%s' % extra.id})
        self.assertIn('alert-danger', response.text)
        self.assertTrue(extra.exists())

    def test_portal_text_is_escaped_and_pages_are_not_cached(self):
        self.login()
        text = '</textarea><script>synthetic_untrusted_text()</script>'
        response = self.url_open(self.detail() + '/report', data={
            'csrf_token': self.token(), 'action': 'upload', 'field_visit_notes': text})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(text, response.text)
        self.assertIn('&lt;script&gt;', response.text)
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        self.assertEqual(self.url_open('/my/field-work').headers['Cache-Control'], 'private, no-store')

    def test_direct_rpc_actions_and_private_methods_are_denied(self):
        self.login()
        for model, method, args in (
            ('project.task', 'action_approve_field_work', [[self.own_task.id]]),
            ('crm.lead', 'action_close_field_work', [[self.leads[0].id]]),
            ('field.work.payment', 'search_read', [[]]),
            ('field.contractor.statement', 'create', [{}]),
            ('project.task', '_write_field_review', [[self.own_task.id], {'state': '1_done'}]),
        ):
            response = self.url_open('/web/dataset/call_kw', data=json.dumps({
                'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                'params': {'model': model, 'method': method, 'args': args, 'kwargs': {}}}),
                headers={'Content-Type': 'application/json'})
            self.assertIn('error', response.json(), (model, method))
        self.own_task.invalidate_recordset()
        self.assertEqual(self.own_task.field_review_state, 'draft')

    def test_direct_statement_html_pdf_and_attachment_authorization(self):
        owner = new_test_user(self.env, login='security_http_owner', groups='field_work_photos.group_field_finance')
        ops = new_test_user(self.env, login='security_http_ops', groups='field_work_photos.group_field_dispatcher')
        report = self.env['field.contractor.statement'].with_user(owner).create({'contractor_id': self.first.id})
        report.action_show_report()
        attachment = self.env['ir.attachment'].create({
            'name': 'synthetic-private-document.pdf', 'raw': b'%PDF-SYNTHETIC-PRIVATE',
            'res_model': 'project.task', 'res_id': self.own_task.id, 'public': False})
        self.authenticate(owner.login, 'synthetic')
        html_url = '/report/html/field_work_photos.contractor_statement_pdf/%s' % report.id
        allowed = self.url_open(html_url)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.headers['Cache-Control'], 'private, no-store')
        for user in (ops, self.first, self.second):
            self.authenticate(user.login, 'synthetic')
            for converter in ('html', 'pdf'):
                response = self.url_open('/report/%s/field_work_photos.contractor_statement_pdf/%s' % (converter, report.id))
                self.assertNotIn('data-statement-closing', response.text)
                self.assertFalse(response.content.startswith(b'%PDF'))
            if user.share:
                response = self.url_open('/web/content/%s' % attachment.id)
                self.assertNotIn(b'%PDF-SYNTHETIC-PRIVATE', response.content)
        self.authenticate(None, None)
        self.assertIn(self.url_open(html_url, allow_redirects=False).status_code, (302, 303))
        self.assertNotIn(b'%PDF-SYNTHETIC-PRIVATE', self.url_open('/web/content/%s' % attachment.id).content)
