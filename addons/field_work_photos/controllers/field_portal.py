import base64
import re
from urllib.parse import urlencode

from werkzeug.exceptions import NotFound

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class FieldWorkPortal(CustomerPortal):
    def _require_contractor(self):
        if not request.env.user.share or not request.env.user.has_group('field_work_photos.group_field_contractor'):
            raise NotFound()

    def _task_domain(self):
        self._require_contractor()
        return [('field_contractor_id', '=', request.env.uid), ('field_report_required', '=', True),
                ('field_service_lead_id', '!=', False), ('field_service_lead_id.active', '=', True), ('active', '=', True),
                ('company_id', 'in', request.env.user.company_ids.ids)]

    def _task(self, task_id, lock=False):
        domain = self._task_domain() + [('id', '=', task_id)]
        # Elevated reads/writes are limited to this domain and explicit fields;
        # no task ID, user ID or arbitrary values from a form are trusted.
        task = request.env['project.task'].sudo().search(domain, limit=1)
        if not task:
            raise NotFound()
        if lock:
            task._lock_dispatch_work()
            # Recheck ownership after waiting for a concurrent reassignment.
            task = request.env['project.task'].sudo().search(domain, limit=1)
            if not task:
                raise NotFound()
        return task

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'field_work_count' in counters and request.env.user.has_group('field_work_photos.group_field_contractor'):
            values['field_work_count'] = request.env['project.task'].sudo().search_count(self._task_domain())
        return values

    @http.route(['/my/field-work', '/my/field-work/page/<int:page>'], type='http', auth='user', website=True, methods=['GET'])
    def field_work_list(self, page=1, scope='active', **kw):
        domain = self._task_domain()
        Task = request.env['project.task'].sudo()
        scopes = {
            'active': [('field_review_state', 'in', ['draft', 'changes_requested']), ('state', '!=', '1_canceled')],
            'pending': [('field_review_state', '=', 'pending'), ('state', '!=', '1_canceled')],
            'completed': ['|', ('field_review_state', '=', 'approved'), ('state', '=', '1_canceled')],
        }
        scope = scope if scope in scopes else 'active'
        counts = {key: Task.search_count(domain + value) for key, value in scopes.items()}
        pager = portal_pager(url='/my/field-work', total=counts[scope], page=page, step=20, url_args={'scope': scope})
        tasks = Task.search(domain + scopes[scope], order='field_approved_at desc, id desc' if scope == 'completed' else 'field_visit_at, id', limit=20, offset=pager['offset'])
        return request.render('field_work_photos.portal_field_work_list', {
            'tasks': tasks, 'pager': pager, 'page_name': 'field_work', 'scope': scope, 'counts': counts})

    @http.route('/my/field-work/<int:task_id>', type='http', auth='user', website=True, methods=['GET'])
    def field_work_detail(self, task_id, notice=None, **kw):
        return self._render_task(self._task(task_id), notice=notice)

    def _render_task(self, task, error=None, notice=None, report_values=None):
        messages = {'saved': 'הדיווח והתמונות נשמרו. אפשר לחזור לעבודה ולהגיש בהמשך.',
                    'submitted': 'הדיווח והתמונות נשלחו לבדיקת התפעול.'}
        message = messages.get(notice) if notice != 'submitted' or task.field_review_state == 'pending' else None
        return request.render('field_work_photos.portal_field_work_detail', {
            'task': task, 'page_name': 'field_work', 'error': error, 'notice': message,
            'galleries': {kind: task._field_gallery(kind) for kind in ('before', 'after')},
            'report': report_values or {name: task[name] or '' for name in ('field_visit_result', 'field_visit_summary', 'field_visit_reason', 'field_visit_notes')},
            'phone_url': 'tel:' + re.sub(r'[^0-9+]', '', task.field_customer_phone or ''),
            'navigation_url': 'https://www.google.com/maps/search/?' + urlencode({'api': 1, 'query': task.field_site_address or ''}),
            'editable': task.field_review_state in ('draft', 'changes_requested') and task.state != '1_canceled',
        })

    @http.route('/my/field-work/<int:task_id>/report', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def field_work_report(self, task_id, action=None, **kw):
        task = self._task(task_id, lock=True)
        try:
            with request.env.cr.savepoint():
                if action not in ('upload', 'submit'):
                    raise NotFound()
                if task.field_review_state not in ('draft', 'changes_requested') or task.state == '1_canceled':
                    raise UserError('התמונות נעולות. יש לפנות למנהלת התפעול.')
                values = {name: kw[name] for name in ('field_visit_result', 'field_visit_summary', 'field_visit_reason', 'field_visit_notes') if name in kw}
                if 'field_visit_result' in values and values['field_visit_result'] not in ('', 'completed', 'followup', 'not_done'):
                    raise UserError('יש לבחור תוצאת ביקור תקינה.')
                uploads = {'before': [], 'after': []}
                for kind in uploads:
                    files = request.httprequest.files.getlist('field_%s_image' % kind)
                    if len(files) > 5:
                        raise UserError('אפשר להעלות עד 5 תמונות בכל אזור.')
                    for upload in files:
                        if not upload.filename:
                            continue
                        raw = upload.read(12 * 1024 * 1024 + 1)
                        if len(raw) > 12 * 1024 * 1024:
                            raise UserError('גודל תמונה מרבי הוא 12MB.')
                        uploads[kind].append(base64.b64encode(raw))
                removals = request.httprequest.form.getlist('remove_photo')
                task._update_field_gallery(uploads, removals)
                if values:
                    task.write(values)
                if action == 'submit':
                    task.action_finish_field_work()
        except UserError as error:
            return self._render_task(task, str(error), report_values={name: kw.get(name, task[name] or '') for name in ('field_visit_result', 'field_visit_summary', 'field_visit_reason', 'field_visit_notes')})
        return request.redirect('/my/field-work/%s?notice=%s' % (task.id, 'submitted' if action == 'submit' else 'saved'), code=303)

    @http.route(['/my/field-work/<int:task_id>/photo/<string:kind>', '/my/field-work/<int:task_id>/photo/<string:kind>/<int:photo_id>'], type='http', auth='user', website=True, methods=['GET'])
    def field_work_photo(self, task_id, kind, photo_id=0, **kw):
        task = self._task(task_id)
        name = {'before': 'field_before_image', 'after': 'field_after_image'}.get(kind)
        if not name:
            raise NotFound()
        photo = task.field_extra_photo_ids.filtered(lambda p: p.id == photo_id and p.kind == kind) if photo_id else False
        image_value = photo.image if photo else (task[name] if not photo_id else False)
        if not image_value:
            raise NotFound()
        # Odoo's image field re-encodes valid images; do not trust client MIME.
        raw = base64.b64decode(image_value)
        from PIL import Image
        from io import BytesIO
        with Image.open(BytesIO(raw)) as image:
            mimetype = Image.MIME[image.format]
        return request.make_response(raw, headers=[('Content-Type', mimetype),
            ('Cache-Control', 'private, no-store'), ('X-Content-Type-Options', 'nosniff')])
