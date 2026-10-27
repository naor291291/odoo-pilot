import base64
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
        cls.own_task.write({'field_before_image': base64.b64encode(cls.raw_photo), 'field_after_image': base64.b64encode(cls.raw_photo)})
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
        self.assertIn('שמירת התמונות והגשה לאישור', response.text)
        self.assertIn('שמירה והמשך מאוחר יותר', response.text)
