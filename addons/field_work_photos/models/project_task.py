import base64
import binascii
from io import BytesIO

from PIL import Image
from odoo import api, fields, models
from odoo.exceptions import ValidationError


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

    @api.depends("field_before_image", "field_after_image")
    def _compute_field_report_ready(self):
        for task in self:
            task.field_report_ready = bool(task.field_before_image and task.field_after_image)

    @api.constrains("state", "field_report_required", "field_before_image", "field_after_image")
    def _check_field_work_photos(self):
        for task in self:
            if task.field_report_required and task.state == "1_done":
                missing = []
                if not task.field_before_image:
                    missing.append("לפני ביצוע")
                if not task.field_after_image:
                    missing.append("אחרי ביצוע")
                if missing:
                    raise ValidationError(
                        "לא ניתן לסיים את העבודה ללא תמונות: %s."
                        % " ו".join(missing)
                    )

    def write(self, vals):
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
            self._validate_field_image_values(vals)
        return super().create(vals_list)

    def action_enable_field_report(self):
        self.write({"field_report_required": True})
        return True

    def action_finish_field_work(self):
        # write + constrains also cover RPC, imports, standard Done controls,
        # batch operations and attempts to clear a photo on a completed task.
        self.write({"state": "1_done"})
        return True
