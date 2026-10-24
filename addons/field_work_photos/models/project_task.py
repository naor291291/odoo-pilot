import base64
import binascii
from io import BytesIO

from PIL import Image
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ProjectTask(models.Model):
    _inherit = "project.task"

    field_report_required = fields.Boolean(
        string="דיווח תמונות חובה", default=False, copy=True, tracking=True,
        help="לאחר הפעלה לא ניתן לבטל את הדרישה. משימות רגילות אינן מושפעות.",
    )
    # Store on the task itself: deleting an ir.attachment must not bypass the
    # completion invariant. Access is governed by the existing task ACL/rules.
    field_before_image = fields.Image(
        string="תמונה לפני ביצוע", attachment=False, copy=False,
        max_width=1920, max_height=1920, verify_resolution=True,
    )
    field_after_image = fields.Image(
        string="תמונה אחרי ביצוע", attachment=False, copy=False,
        max_width=1920, max_height=1920, verify_resolution=True,
    )
    field_report_ready = fields.Boolean(
        string="התמונות הושלמו", compute="_compute_field_report_ready",
    )
    field_review_state = fields.Selection([
        ("draft", "בביצוע"), ("pending", "ממתין לאישור"),
        ("approved", "אושר"), ("changes_requested", "הוחזר לתיקון"),
    ], string="מצב בדיקת העבודה", default="draft", required=True, copy=False, tracking=True, index=True)
    field_review_note = fields.Text(string="סיבת החזרה לתיקון", copy=False, tracking=True)
    field_submitted_by = fields.Many2one("res.users", string="הוגש על ידי", readonly=True, copy=False)
    field_submitted_at = fields.Datetime(string="תאריך הגשה", readonly=True, copy=False)
    field_approved_by = fields.Many2one("res.users", string="אושר על ידי", readonly=True, copy=False)
    field_approved_at = fields.Datetime(string="תאריך אישור", readonly=True, copy=False)
    field_can_review = fields.Boolean(compute="_compute_field_can_review")

    @api.depends_context("uid")
    def _compute_field_can_review(self):
        allowed = self.env.su or self.env.user.has_group("field_work_photos.group_field_reviewer")
        for task in self:
            task.field_can_review = allowed

    @api.depends("field_before_image", "field_after_image")
    def _compute_field_report_ready(self):
        for task in self:
            task.field_report_ready = bool(task.field_before_image and task.field_after_image)

    @api.constrains("state", "field_report_required", "field_before_image", "field_after_image", "field_review_state")
    def _check_field_work_photos(self):
        for task in self:
            if not task.field_report_required:
                continue
            if task.state == "1_done" or task.field_review_state in ("pending", "approved"):
                missing = []
                if not task.field_before_image:
                    missing.append("לפני ביצוע")
                if not task.field_after_image:
                    missing.append("אחרי ביצוע")
                if missing:
                    raise ValidationError(
                        "לא ניתן להגיש או לאשר את העבודה ללא תמונות: %s."
                        % " ו".join(missing)
                    )
            if task.state == "1_done" and task.field_review_state != "approved":
                raise ValidationError("יש להגיש את העבודה ולקבל אישור לפני סימונה כהושלמה.")
            if task.field_review_state == "approved" and task.state != "1_done":
                raise ValidationError("פתיחת עבודה מאושרת מחייבת החזרה לתיקון על ידי גורם מאשר.")
            if task.field_review_state == "pending" and task.state != "01_in_progress":
                raise ValidationError("עבודה שהוגשה נמצאת בהמתנה לאישור. יש לאשר או להחזיר אותה לתיקון.")

    @staticmethod
    def _review_managed_fields():
        return {"field_review_state", "field_submitted_by", "field_submitted_at", "field_approved_by", "field_approved_at"}

    def write(self, vals):
        if self._review_managed_fields().intersection(vals):
            raise AccessError("עדכון מצב בדיקה ופרטי האישור מתבצע באמצעות כפתורי התהליך בלבד.")
        if "field_review_note" in vals:
            self._require_field_reviewer()
        if {"field_before_image", "field_after_image"}.intersection(vals):
            if any(t.field_report_required and t.field_review_state in ("pending", "approved") for t in self):
                raise ValidationError("התמונות נעולות לאחר הגשה. גורם מאשר יכול להחזיר את העבודה לתיקון.")
        self._validate_field_image_values(vals)
        if "field_report_required" in vals and not vals["field_report_required"]:
            if any(task.field_report_required for task in self):
                raise ValidationError("לא ניתן לבטל דרישת תמונות שהופעלה. אפשר לפתוח מחדש עבודה לצורך תיקון.")
        return super().write(vals)

    @staticmethod
    def _validate_field_image_values(vals):
        for name in ("field_before_image", "field_after_image"):
            value = vals.get(name)
            if not value:
                continue
            try:
                if len(value) > 16 * 1024 * 1024:
                    raise ValidationError("גודל תמונה מרבי הוא 12MB.")
                raw = base64.b64decode(value, validate=True)
                if len(raw) > 12 * 1024 * 1024:
                    raise ValidationError("גודל תמונה מרבי הוא 12MB.")
                with Image.open(BytesIO(raw)) as image:
                    if image.format not in {"JPEG", "PNG", "WEBP"}:
                        raise ValidationError("יש להעלות תמונת JPG, PNG או WebP.")
                    if image.width * image.height > 50_000_000:
                        raise ValidationError("רזולוציית התמונה גדולה מדי. יש להקטין אותה.")
                    image.verify()
            except (ValueError, TypeError, OSError, binascii.Error, Image.DecompressionBombError) as exc:
                raise ValidationError("הקובץ אינו תמונה תקינה. יש להעלות JPG, PNG או WebP.") from exc

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if any(vals.get(key) for key in self._review_managed_fields() - {"field_review_state"}):
                raise AccessError("לא ניתן להזין פרטי אישור ישירות ביצירת משימה.")
            if vals.get("field_review_state", "draft") != "draft":
                raise AccessError("משימה חדשה מתחילה בביצוע. יש להשתמש בכפתורי התהליך.")
            if vals.get("field_review_note"):
                self._require_field_reviewer()
            self._validate_field_image_values(vals)
        return super().create(vals_list)

    def action_enable_field_report(self):
        self.write({"field_report_required": True})
        return True

    def action_finish_field_work(self):
        for task in self:
            if not task.field_report_required or task.field_review_state not in ("draft", "changes_requested") or task.state == "1_canceled":
                raise ValidationError("אפשר להגיש רק עבודת שטח שבביצוע או שהוחזרה לתיקון.")
        self._write_field_review({
            "field_review_state": "pending", "state": "01_in_progress",
            "field_submitted_by": self.env.user.id, "field_submitted_at": fields.Datetime.now(),
            "field_approved_by": False, "field_approved_at": False, "field_review_note": False,
        })
        return True

    def _require_field_reviewer(self):
        if not self.env.su and not self.env.user.has_group("field_work_photos.group_field_reviewer"):
            raise AccessError("רק משתמש בעל הרשאת אישור עבודות שטח יכול לאשר או להחזיר עבודה לתיקון.")

    def _write_field_review(self, vals):
        # Private method, unavailable over RPC; preserve normal task ACLs and
        # record rules through the parent's ORM write, without sudo/context flags.
        return super().write(vals)

    def action_approve_field_work(self):
        self._require_field_reviewer()
        for task in self:
            if not task.field_report_required or task.field_review_state != "pending":
                raise ValidationError("אפשר לאשר רק עבודה שממתינה לאישור.")
        self._write_field_review({
            "field_review_state": "approved", "state": "1_done",
            "field_approved_by": self.env.user.id, "field_approved_at": fields.Datetime.now(),
        })
        return True

    def action_request_field_changes(self):
        self._require_field_reviewer()
        for task in self:
            if not task.field_report_required or task.field_review_state not in ("pending", "approved"):
                raise ValidationError("אפשר להחזיר לתיקון רק עבודה שהוגשה או אושרה.")
            if not (task.field_review_note or "").strip():
                raise ValidationError("יש להזין סיבת החזרה לתיקון לפני החזרת העבודה.")
        self._write_field_review({
            "field_review_state": "changes_requested", "state": "02_changes_requested",
            "field_approved_by": False, "field_approved_at": False,
        })
        return True
