from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    # Legacy completions were never reviewed. Preserve their photos and send
    # them for review rather than inventing an approver or deleting their work.
    env = api.Environment(cr, SUPERUSER_ID, {})
    tasks = env["project.task"].search([
        ("field_report_required", "=", True), ("state", "=", "1_done"),
        ("field_review_state", "=", "draft"),
    ])
    if tasks:
        tasks._write_field_review({"field_review_state": "pending", "state": "01_in_progress"})
