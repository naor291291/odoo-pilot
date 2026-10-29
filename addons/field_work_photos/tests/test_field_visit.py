import base64
from io import BytesIO

from PIL import Image
from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestFieldVisit(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ops = new_test_user(cls.env, login='visit_ops', groups='field_work_photos.group_field_dispatcher')
        cls.contractor = new_test_user(cls.env, login='visit_contractor', groups='field_work_photos.group_field_contractor')
        cls.customer = cls.env['res.partner'].create({'name': 'Visit customer', 'phone': '0500000000'})
        stream = BytesIO()
        Image.new('RGB', (8, 8), 'blue').save(stream, 'PNG')
        cls.photo = base64.b64encode(stream.getvalue())

    def task(self):
        lead = self.env['crm.lead'].with_user(self.ops).create({
            'name': 'Visit gallery', 'is_field_service': True, 'partner_id': self.customer.id,
            'phone': '0500000000', 'field_site_address': 'Visit street',
            'field_work_description': 'Replace tap', 'field_quote_number': 'VISIT-1',
            'field_sale_amount': 1000, 'field_contractor_id': self.contractor.id,
            'field_visit_at': fields.Datetime.now(), 'contact_name': 'איש הקשר',
            'field_site_unit': 'קומה 2, דירה 6', 'field_access_instructions': 'כניסה מהחצר',
        })
        for _ in range(4):
            lead.action_next_field_stage()
        return lead.field_task_ids

    def complete(self, task):
        task._update_field_gallery({'before': [self.photo], 'after': [self.photo]}, [])
        task.write({'field_visit_result': 'completed', 'field_visit_summary': 'הוחלף ונבדק'})
        task.action_finish_field_work()

    def test_five_photos_each_preserve_legacy_first_images(self):
        task = self.task()
        task.write({'field_before_image': self.photo, 'field_after_image': self.photo})
        task._update_field_gallery({'before': [self.photo] * 4, 'after': [self.photo] * 4}, [])
        self.assertEqual(len(task._field_gallery('before')), 5)
        self.assertEqual(len(task._field_gallery('after')), 5)
        self.assertEqual(len(task.field_extra_photo_ids), 8)
        self.assertEqual(task.field_before_image, self.photo)

    def test_gallery_limit_is_enforced_on_portal_helper_and_direct_orm(self):
        task = self.task()
        task._update_field_gallery({'before': [self.photo] * 5, 'after': []}, [])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task._update_field_gallery({'before': [self.photo], 'after': []}, [])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['field.work.photo'].with_user(self.ops).create({'task_id': task.id, 'kind': 'before', 'image': self.photo})
        self.assertEqual(len(task._field_gallery('before')), 5)

    def test_delete_first_photo_promotes_extra_and_replacement_keeps_count(self):
        task = self.task()
        task._update_field_gallery({'before': [self.photo] * 3, 'after': []}, [])
        task._update_field_gallery({'before': [self.photo], 'after': []}, ['before:0'])
        self.assertEqual(len(task._field_gallery('before')), 3)
        self.assertTrue(task.field_before_image)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.write({'field_before_image': False})

    def test_foreign_photo_removal_and_reparenting_are_rejected(self):
        task, other = self.task(), self.task()
        other._update_field_gallery({'before': [self.photo] * 2, 'after': []}, [])
        photo = other.field_extra_photo_ids
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task._update_field_gallery({'before': [], 'after': []}, ['before:%s' % photo.id])
        with self.assertRaises(AccessError), self.cr.savepoint():
            photo.write({'task_id': task.id})

    def test_pending_report_locks_all_text_and_extra_photo_operations(self):
        task = self.task()
        task._update_field_gallery({'before': [self.photo] * 2, 'after': []}, [])
        self.complete(task)
        photo = task.field_extra_photo_ids[:1]
        for operation in (lambda: task.write({'field_visit_notes': 'changed'}),
                          lambda: photo.write({'image': self.photo}), lambda: photo.unlink(),
                          lambda: self.env['field.work.photo'].create({'task_id': task.id, 'kind': 'before', 'image': self.photo})):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                operation()

    def test_completed_requires_summary_and_both_photo_categories(self):
        task = self.task()
        task._update_field_gallery({'before': [self.photo], 'after': [self.photo]}, [])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.action_finish_field_work()
        task.field_visit_summary = 'בוצע ונבדק'
        task.field_after_image = False
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.action_finish_field_work()

    def test_incomplete_requires_reason_and_can_submit_without_photos(self):
        task = self.task()
        task.field_visit_result = 'not_done'
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.action_finish_field_work()
        task.field_visit_reason = 'הלקוח לא היה בבית. נדרש תיאום ביקור.'
        task.action_finish_field_work()
        self.assertEqual(task.field_review_state, 'pending')
        self.assertEqual(task.field_service_lead_id.field_dispatch_code, 'field')
        self.assertIn('נדרש טיפול', task.field_service_lead_id.field_attention_label)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.action_approve_field_work()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task._write_field_review({'field_review_state': 'approved', 'state': '1_done'})

    def test_followup_can_be_returned_rescheduled_and_completed(self):
        task = self.task()
        task.write({'field_visit_result': 'followup', 'field_visit_reason': 'חסר חלק. יש לחזור עם מחבר.'})
        task.action_finish_field_work()
        lead = task.field_service_lead_id
        action = lead.action_return_field_report()
        wizard = self.env['field.work.correction'].with_user(self.ops).with_context(action['context']).create({'reason': 'תואם ביקור נוסף עם המחבר'})
        wizard.action_apply()
        lead.write({'field_visit_at': fields.Datetime.now()})
        self.complete(task)
        task.action_approve_field_work()
        self.assertEqual(lead.field_dispatch_code, 'completed')

    def test_contractor_cannot_read_or_mutate_gallery_through_native_orm(self):
        task = self.task()
        task._update_field_gallery({'before': [self.photo] * 2, 'after': []}, [])
        photo = task.field_extra_photo_ids.with_user(self.contractor)
        with self.assertRaises(AccessError), self.cr.savepoint():
            photo.read(['image'])
        with self.assertRaises(AccessError), self.cr.savepoint():
            photo.unlink()

    def test_extra_photo_reads_follow_task_access_rules(self):
        task = self.task()
        task._update_field_gallery({'before': [self.photo] * 2, 'after': []}, [])
        user = new_test_user(self.env, login='visit_other_company', groups='project.group_project_user')
        company = self.env['res.company'].create({'name': 'Other photo company'})
        user.write({'company_ids': [(6, 0, [company.id])], 'company_id': company.id})
        photo = task.field_extra_photo_ids.with_user(user)
        with self.assertRaises(AccessError), self.cr.savepoint():
            photo.read(['image'])
        self.assertFalse(self.env['field.work.photo'].with_user(user).search([('id', '=', photo.id)]))

    def test_invalid_extra_image_and_oversized_report_text_are_rejected(self):
        task = self.task()
        task.field_before_image = self.photo
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['field.work.photo'].create({'task_id': task.id, 'kind': 'before', 'image': base64.b64encode(b'not image')})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.write({'field_visit_summary': 'x' * 4001})

    def test_arrival_details_sync_and_freeze_with_submission(self):
        task = self.task()
        self.assertEqual(task.field_site_contact, 'איש הקשר')
        self.assertEqual(task.field_site_unit, 'קומה 2, דירה 6')
        lead = task.field_service_lead_id
        lead.field_access_instructions = 'כניסה ראשית'
        self.assertEqual(task.field_access_instructions, 'כניסה ראשית')
        self.complete(task)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lead.field_site_unit = 'קומה 3'
