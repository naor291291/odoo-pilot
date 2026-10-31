"""Synthetic regression fixtures for public ORM authorization boundaries."""
import base64
from io import BytesIO

from PIL import Image

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestSecurityHardening(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = new_test_user(cls.env, login='security_owner', groups='field_work_photos.group_field_finance')
        cls.ops = new_test_user(cls.env, login='security_ops', groups='field_work_photos.group_field_dispatcher')
        cls.peer = new_test_user(cls.env, login='security_peer', groups='field_work_photos.group_field_finance')
        # Exercise field/record protection even when native export is enabled.
        for user in (cls.owner, cls.ops):
            user.groups_id |= cls.env.ref('base.group_allow_export')
        cls.first = new_test_user(cls.env, login='security_first', groups='field_work_photos.group_field_contractor')
        cls.second = new_test_user(cls.env, login='security_second', groups='field_work_photos.group_field_contractor')
        cls.customer = cls.env['res.partner'].create({'name': 'Synthetic security customer', 'phone': '0500000000'})
        stream = BytesIO()
        Image.new('RGB', (8, 8), 'blue').save(stream, 'PNG')
        cls.photo = base64.b64encode(stream.getvalue())

    def lead(self, model=None, **values):
        model = model if model is not None else self.env['crm.lead'].with_user(self.owner)
        return model.create({
            'name': 'Synthetic security work', 'is_field_service': True, 'partner_id': self.customer.id,
            'phone': '0500000000', 'field_site_address': 'Synthetic street', 'field_work_description': 'Fixture',
            'field_sale_amount': 1000, 'field_customer_due': 1180, 'field_contractor_due': 700,
            'field_quote_number': 'SEC-Q', 'field_contractor_id': self.first.id,
            'field_visit_at': fields.Datetime.now(), **values})

    def dispatch(self, lead=None):
        lead = lead if lead is not None else self.lead()
        for _ in range(4):
            lead.action_next_field_stage()
        return lead.field_task_ids

    def test_review_defaults_do_not_create_approval_or_audit(self):
        task = self.env['project.task'].with_user(self.ops).with_context(
            default_field_report_required=True, default_field_review_state='pending',
            default_state='1_done', default_field_before_image=self.photo,
            default_field_after_image=self.photo, default_field_approved_by=self.owner.id,
            default_field_approved_at='2026-01-01 00:00:00',
        ).create({'name': 'Synthetic task', 'state': '01_in_progress'})
        self.assertEqual(task.field_review_state, 'draft')
        self.assertFalse(task.field_approved_by or task.field_approved_at)

    def test_dispatch_link_default_cannot_create_linked_task(self):
        lead = self.lead()
        task = self.env['project.task'].with_user(self.ops).with_context(
            default_field_service_lead_id=lead.id).create({'name': 'Standalone fixture'})
        self.assertFalse(task.field_service_lead_id)
        self.assertFalse(lead.field_task_ids)

    def test_pricing_defaults_do_not_freeze_fabricated_rates(self):
        model = self.env['crm.lead'].with_user(self.owner).with_context(
            default_field_rates_frozen=True, default_field_rate_medium_snapshot=1)
        lead = self.lead(model=model)
        self.assertFalse(lead.field_rates_frozen)
        self.dispatch(lead)
        self.assertEqual(lead.field_rate_medium_snapshot, self.first.partner_id.field_rate_medium)
        self.assertEqual(lead.field_contractor_cost, 650)

    def test_photo_default_parent_cannot_bypass_review_lock(self):
        task = self.dispatch()
        task.write({'field_before_image': self.photo, 'field_after_image': self.photo,
                    'field_visit_summary': 'Synthetic completed fixture'})
        task.action_finish_field_work()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['field.work.photo'].with_user(self.ops).with_context(default_task_id=task.id).create(
                {'kind': 'before', 'image': self.photo})

    def test_photo_default_parent_enforces_gallery_limit(self):
        task = self.dispatch()
        task.write({'field_before_image': self.photo})
        Photo = self.env['field.work.photo'].with_user(self.ops).with_context(default_task_id=task.id)
        for _ in range(4):
            Photo.create({'kind': 'before', 'image': self.photo})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            Photo.create({'kind': 'before', 'image': self.photo})

    def test_photo_defaults_validate_file_content(self):
        task = self.dispatch()
        task.write({'field_before_image': self.photo})
        stream = BytesIO()
        Image.new('RGB', (8, 8), 'green').save(stream, 'GIF')
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['field.work.photo'].with_user(self.ops).with_context(
                default_task_id=task.id, default_image=base64.b64encode(stream.getvalue())
            ).create({'kind': 'before'})

    def test_financial_dialogs_are_private_to_creator(self):
        lead = self.lead()
        wizard = self.env['field.work.payment.register'].with_user(self.owner).create({
            'lead_id': lead.id, 'kind': 'contractor', 'amount': 200, 'reference': 'SYNTHETIC-PRIVATE'})
        for user in (self.ops, self.peer):
            with self.subTest(user=user.login):
                self.assertFalse(wizard.with_user(user).search([('id', '=', wizard.id)]))
                with self.assertRaises(AccessError), self.cr.savepoint():
                    wizard.with_user(user).read(['amount', 'reference'])
                with self.assertRaises(AccessError), self.cr.savepoint():
                    wizard.with_user(user).action_apply()
        wizard.action_apply()
        wizard.action_apply()
        self.assertEqual(lead.field_contractor_paid, 200)

    def test_uploaded_images_drop_metadata_and_preserve_orientation(self):
        task = self.dispatch()
        stream = BytesIO()
        image = Image.new('RGB', (10, 20), 'green')
        exif = Image.Exif()
        exif[0x0112] = 6
        exif[0x010E] = 'SYNTHETIC-PRIVATE-METADATA'
        exif[0x8825] = {1: 'N', 2: (32.0, 0.0, 0.0), 3: 'E', 4: (34.0, 0.0, 0.0)}
        image.save(stream, 'JPEG', exif=exif)
        photo = base64.b64encode(stream.getvalue())
        task.write({'field_before_image': photo})
        extra = self.env['field.work.photo'].with_user(self.ops).create({
            'task_id': task.id, 'kind': 'before', 'image': photo})
        for value in (task.field_before_image, extra.image):
            with Image.open(BytesIO(base64.b64decode(value))) as stored:
                self.assertFalse(stored.getexif())
                self.assertEqual(stored.size, (20, 10))

    def test_private_cancellation_and_correction_dialogs(self):
        lead = self.lead()
        payment = self.env['field.work.payment'].with_user(self.owner).create({
            'lead_id': lead.id, 'kind': 'contractor', 'amount': 100, 'reference': 'PRIVATE-CANCEL'})
        cancel = self.env['field.work.payment.cancel'].with_user(self.owner).create({
            'payment_id': payment.id, 'reason': 'Synthetic private reason'})
        task = self.dispatch(lead)
        task.write({'field_before_image': self.photo, 'field_after_image': self.photo,
                    'field_visit_summary': 'Synthetic completed fixture'})
        task.action_finish_field_work()
        correction = self.env['field.work.correction'].with_user(self.owner).create({
            'task_id': task.id, 'reason': 'Synthetic correction'})
        for wizard in (cancel, correction):
            with self.assertRaises(AccessError), self.cr.savepoint():
                wizard.with_user(self.ops).export_data(['reason'])
            with self.assertRaises(AccessError), self.cr.savepoint():
                wizard.with_user(self.ops).action_apply()
        correction.action_apply()
        cancel.action_apply()
        self.assertEqual(task.field_review_state, 'changes_requested')
        self.assertEqual(payment.state, 'cancelled')

    def test_operations_cannot_create_private_contractor_dialog(self):
        lead = self.lead()
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env['field.work.payment.register'].with_user(self.ops).create({
                'lead_id': lead.id, 'kind': 'contractor', 'amount': 100, 'reference': 'PRIVATE'})
        own = self.env['field.work.payment.register'].with_user(self.ops).create({
            'lead_id': lead.id, 'kind': 'customer', 'amount': 100, 'reference': 'VALID-RECEIPT'})
        own.action_apply()
        self.assertEqual(lead.field_customer_paid, 100)

    def test_private_fields_deny_read_search_aggregation_and_export(self):
        lead = self.lead(field_material_cost=100)
        for field in ('field_material_cost', 'field_rate_medium_snapshot', 'field_contractor_due'):
            record = lead.with_user(self.ops)
            for call in (lambda: record.read([field]), lambda: record.export_data([field]),
                         lambda: record.search_count([('id', '=', lead.id), (field, '>', 0)]),
                         lambda: record.read_group([('id', '=', lead.id)], [field + ':sum'], [])):
                with self.assertRaises(AccessError), self.cr.savepoint():
                    call()
        self.assertEqual(lead.export_data(['field_material_cost'])['datas'], [[100.0]])

    def test_company_switch_revokes_dialog_and_statement(self):
        other = self.env['res.company'].create({'name': 'Synthetic company'})
        self.owner.company_ids |= other
        lead = self.lead()
        wizard = self.env['field.work.payment.register'].with_user(self.owner).create({
            'lead_id': lead.id, 'amount': 100, 'reference': 'COMPANY-RECEIPT'})
        switched = wizard.with_context(allowed_company_ids=[other.id])
        with self.assertRaises(AccessError), self.cr.savepoint():
            switched.read(['amount'])
        with self.assertRaises(AccessError), self.cr.savepoint():
            switched.action_apply()
        wizard.action_apply()
        self.assertEqual(lead.field_customer_paid, 100)

    def test_webp_resize_and_invalid_image_preserve_saved_data(self):
        task = self.dispatch()
        stream = BytesIO()
        Image.new('RGB', (2000, 20), 'red').save(stream, 'WEBP')
        task.write({'field_before_image': base64.b64encode(stream.getvalue())})
        with Image.open(BytesIO(base64.b64decode(task.field_before_image))) as stored:
            self.assertLessEqual(max(stored.size), 1920)
        before = task.field_before_image
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.write({'field_before_image': base64.b64encode(b'<svg onload="invalid"/>')})
        self.assertEqual(task.field_before_image, before)


