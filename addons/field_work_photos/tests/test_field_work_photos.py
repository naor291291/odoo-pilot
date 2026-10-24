import base64
from io import BytesIO

from PIL import Image
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestFieldWorkPhotos(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        stream = BytesIO()
        Image.new('RGB', (16, 16), 'blue').save(stream, 'PNG')
        cls.photo = base64.b64encode(stream.getvalue())
        cls.project = cls.env['project.project'].create({'name': 'Field review test', 'privacy_visibility': 'employees'})
        cls.worker = new_test_user(cls.env, login='field_worker', groups='project.group_project_user')
        cls.reviewer = new_test_user(cls.env, login='field_reviewer', groups='project.group_project_user,field_work_photos.group_field_reviewer')

    def task(self, **vals):
        return self.env['project.task'].create({
            'name': 'Field work', 'project_id': self.project.id,
            'field_report_required': True, 'user_ids': [(6, 0, [self.worker.id])], **vals,
        })

    def submitted(self):
        task = self.task(field_before_image=self.photo, field_after_image=self.photo)
        task.with_user(self.worker).action_finish_field_work()
        return task

    def approved(self):
        task = self.submitted()
        task.with_user(self.reviewer).action_approve_field_work()
        return task

    def test_submission_requires_both_photos(self):
        task = self.task()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.with_user(self.worker).action_finish_field_work()
        task.field_before_image = self.photo
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.with_user(self.worker).action_finish_field_work()
        task.field_after_image = self.photo
        task.with_user(self.worker).action_finish_field_work()
        self.assertEqual(task.field_review_state, 'pending')
        self.assertNotEqual(task.state, '1_done')

    def test_after_only_cannot_submit(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.task(field_after_image=self.photo).action_finish_field_work()

    def test_approval_records_actor_and_time(self):
        task = self.approved()
        self.assertEqual(task.state, '1_done')
        self.assertEqual(task.field_review_state, 'approved')
        self.assertEqual(task.field_submitted_by, self.worker)
        self.assertEqual(task.field_approved_by, self.reviewer)
        self.assertTrue(task.field_submitted_at)
        self.assertTrue(task.field_approved_at)
        self.assertLessEqual(task.field_submitted_at, task.field_approved_at)

    def test_worker_cannot_review(self):
        task = self.submitted().with_user(self.worker)
        for method in (task.action_approve_field_work, task.action_request_field_changes):
            with self.assertRaises(AccessError), self.cr.savepoint():
                method()
        self.assertFalse(task.field_can_review)
        self.assertTrue(task.with_user(self.reviewer).field_can_review)

    def test_direct_done_is_blocked_even_with_photos(self):
        task = self.task(field_before_image=self.photo, field_after_image=self.photo)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.with_user(self.worker).write({'state': '1_done'})

    def test_review_fields_cannot_be_forged(self):
        task = self.submitted()
        for user in (self.worker, self.reviewer):
            for vals in ({'field_review_state': 'approved', 'state': '1_done'}, {'field_approved_by': user.id}):
                with self.assertRaises(AccessError), self.cr.savepoint():
                    task.with_user(user).with_context(field_review_internal=True).write(vals)

    def test_create_cannot_skip_review(self):
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.task(field_review_state='approved', state='1_done', field_before_image=self.photo, field_after_image=self.photo)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.task(state='1_done', field_before_image=self.photo, field_after_image=self.photo)

    def test_photos_are_frozen_pending_and_approved(self):
        task = self.submitted()
        for approved in (False, True):
            if approved:
                task.with_user(self.reviewer).action_approve_field_work()
            for name in ('field_before_image', 'field_after_image'):
                for value in (False, self.photo):
                    with self.assertRaises(ValidationError), self.cr.savepoint():
                        task.write({name: value})

    def test_return_requires_reason(self):
        task = self.submitted().with_user(self.reviewer)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.action_request_field_changes()
        task.field_review_note = '  '
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.action_request_field_changes()

    def test_return_correct_resubmit_and_approve(self):
        task = self.submitted()
        task.with_user(self.reviewer).write({'field_review_note': 'Take a closer photo'})
        task.with_user(self.reviewer).action_request_field_changes()
        self.assertEqual(task.field_review_state, 'changes_requested')
        self.assertEqual(task.state, '02_changes_requested')
        self.assertEqual(task.with_user(self.worker).field_review_note, 'Take a closer photo')
        task.with_user(self.worker).write({'field_after_image': False})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.with_user(self.worker).action_finish_field_work()
        task.with_user(self.worker).write({'field_after_image': self.photo})
        task.with_user(self.worker).action_finish_field_work()
        task.with_user(self.reviewer).action_approve_field_work()
        self.assertEqual(task.field_review_state, 'approved')

    def test_approved_task_can_be_returned_with_reason(self):
        task = self.approved()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.with_user(self.worker).write({'state': '01_in_progress'})
        task.with_user(self.reviewer).write({'field_review_note': 'Additional correction'})
        task.with_user(self.reviewer).action_request_field_changes()
        self.assertFalse(task.field_approved_by)
        self.assertFalse(task.field_approved_at)
        self.assertEqual(task.field_review_state, 'changes_requested')

    def test_worker_cannot_change_review_reason(self):
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.submitted().with_user(self.worker).write({'field_review_note': 'forged reason'})

    def test_duplicate_or_out_of_order_actions_rejected(self):
        task = self.task()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.with_user(self.reviewer).action_approve_field_work()
        task.write({'field_before_image': self.photo, 'field_after_image': self.photo})
        task.action_finish_field_work()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.action_finish_field_work()
        task.with_user(self.reviewer).action_approve_field_work()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.with_user(self.reviewer).action_approve_field_work()

    def test_requirement_cannot_be_disabled(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.task().write({'field_report_required': False, 'state': '1_done'})

    def test_normal_tasks_are_unaffected(self):
        task = self.task(field_report_required=False)
        task.write({'state': '1_done'})
        self.assertEqual(task.state, '1_done')

    def test_opt_in_checks_existing_completed_task(self):
        task = self.task(field_report_required=False, state='1_done')
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.action_enable_field_report()

    def test_copy_does_not_reuse_photos_or_approval(self):
        copied = self.approved().copy()
        self.assertTrue(copied.field_report_required)
        self.assertEqual(copied.field_review_state, 'draft')
        self.assertNotEqual(copied.state, '1_done')
        self.assertFalse(copied.field_before_image)
        self.assertFalse(copied.field_after_image)
        self.assertFalse(copied.field_approved_by)

    def test_batch_submission_is_atomic(self):
        ready = self.task(field_before_image=self.photo, field_after_image=self.photo)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            (ready | self.task()).action_finish_field_work()
        self.assertEqual(ready.field_review_state, 'draft')

    def test_invalid_image_is_rejected(self):
        with self.assertRaises(UserError), self.cr.savepoint():
            self.task(field_before_image=base64.b64encode(b'not an image'))
        task = self.task()
        with self.assertRaises(UserError), self.cr.savepoint():
            task.write({'field_after_image': base64.b64encode(b'not an image')})
