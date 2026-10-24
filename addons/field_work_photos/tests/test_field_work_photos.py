import base64
from io import BytesIO

from PIL import Image
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFieldWorkPhotos(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        stream = BytesIO()
        Image.new("RGB", (16, 16), "blue").save(stream, "PNG")
        cls.photo = base64.b64encode(stream.getvalue())
        cls.project = cls.env["project.project"].create({"name": "Photo gate test"})

    def task(self, **vals):
        return self.env["project.task"].create({
            "name": "Field work", "project_id": self.project.id,
            "field_report_required": True, **vals,
        })

    def test_completion_requires_both_photos(self):
        task = self.task()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.action_finish_field_work()
        task.field_before_image = self.photo
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.write({"state": "1_done"})
        task.field_after_image = self.photo
        task.action_finish_field_work()
        self.assertEqual(task.state, "1_done")
        self.assertTrue(task.field_report_ready)

    def test_after_only_cannot_complete(self):
        task = self.task(field_after_image=self.photo)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.write({"state": "1_done"})

    def test_create_completed_is_checked(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.task(state="1_done")
        task = self.task(state="1_done", field_before_image=self.photo, field_after_image=self.photo)
        self.assertEqual(task.state, "1_done")

    def test_completed_photo_cannot_be_removed(self):
        task = self.task(state="1_done", field_before_image=self.photo, field_after_image=self.photo)
        for name in ("field_before_image", "field_after_image"):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                task.write({name: False})

    def test_requirement_cannot_be_disabled(self):
        task = self.task()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.write({"field_report_required": False, "state": "1_done"})

    def test_normal_tasks_are_unaffected(self):
        task = self.task(field_report_required=False)
        task.write({"state": "1_done"})
        self.assertEqual(task.state, "1_done")

    def test_opt_in_checks_existing_completed_task(self):
        task = self.task(field_report_required=False, state="1_done")
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.action_enable_field_report()

    def test_copy_does_not_reuse_evidence(self):
        task = self.task(state="1_done", field_before_image=self.photo, field_after_image=self.photo)
        copied = task.copy()
        self.assertTrue(copied.field_report_required)
        self.assertNotEqual(copied.state, "1_done")
        self.assertFalse(copied.field_before_image)
        self.assertFalse(copied.field_after_image)

    def test_batch_completion_is_atomic(self):
        ready = self.task(field_before_image=self.photo, field_after_image=self.photo)
        missing = self.task()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            (ready | missing).write({"state": "1_done"})
        self.assertNotEqual(ready.state, "1_done")

    def test_reopen_allows_photo_correction(self):
        task = self.task(state="1_done", field_before_image=self.photo, field_after_image=self.photo)
        task.write({"state": "01_in_progress", "field_after_image": False})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.action_finish_field_work()

    def test_invalid_image_is_rejected(self):
        with self.assertRaises(UserError), self.cr.savepoint():
            self.task(field_before_image=base64.b64encode(b"not an image"))
        task = self.task()
        with self.assertRaises(UserError), self.cr.savepoint():
            task.write({"field_after_image": base64.b64encode(b"not an image")})
