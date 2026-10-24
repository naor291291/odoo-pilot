import base64

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
    def field_work_list(self, page=1, **kw):
        domain = self._task_domain()
        Task = request.env['project.task'].sudo()
        pager = portal_pager(url='/my/field-work', total=Task.search_count(domain), page=page, step=20)
        tasks = Task.search(domain, order='field_visit_at, id', limit=20, offset=pager['offset'])
        return request.render('field_work_photos.portal_field_work_list', {'tasks': tasks, 'pager': pager, 'page_name': 'field_work'})

    @http.route('/my/field-work/<int:task_id>', type='http', auth='user', website=True, methods=['GET'])
    def field_work_detail(self, task_id, **kw):
        return self._render_task(self._task(task_id))

    def _render_task(self, task, error=None):
        return request.render('field_work_photos.portal_field_work_detail', {
            'task': task, 'page_name': 'field_work', 'error': error,
            'editable': task.field_review_state in ('draft', 'changes_requested') and task.state != '1_canceled',
        })

    @http.route('/my/field-work/<int:task_id>/report', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def field_work_report(self, task_id, action=None, **kw):
        task = self._task(task_id, lock=True)
        try:
            with request.env.cr.savepoint():
                if action == 'upload':
                    if task.field_review_state not in ('draft', 'changes_requested') or task.state == '1_canceled':
                        raise UserError('התמונות נעולות. יש לפנות למנהלת התפעול.')
                    values = {}
                    for name in ('field_before_image', 'field_after_image'):
                        upload = request.httprequest.files.get(name)
                        if upload and upload.filename:
                            raw = upload.read(12 * 1024 * 1024 + 1)
                            if len(raw) > 12 * 1024 * 1024:
                                raise UserError('גודל תמונה מרבי הוא 12MB.')
                            values[name] = base64.b64encode(raw)
                    if not values:
                        raise UserError('יש לבחור תמונה להעלאה.')
                    task.write(values)
                elif action == 'submit':
                    task.action_finish_field_work()
                else:
                    raise NotFound()
        except UserError as error:
            return self._render_task(task, str(error))
        return request.redirect('/my/field-work/%s' % task.id, code=303)

    @http.route('/my/field-work/<int:task_id>/photo/<string:kind>', type='http', auth='user', website=True, methods=['GET'])
    def field_work_photo(self, task_id, kind, **kw):
        task = self._task(task_id)
        name = {'before': 'field_before_image', 'after': 'field_after_image'}.get(kind)
        if not name or not task[name]:
            raise NotFound()
        # Odoo's image field re-encodes valid images; do not trust client MIME.
        raw = base64.b64decode(task[name])
        from PIL import Image
        from io import BytesIO
        with Image.open(BytesIO(raw)) as image:
            mimetype = Image.MIME[image.format]
        return request.make_response(raw, headers=[('Content-Type', mimetype),
            ('Cache-Control', 'private, no-store'), ('X-Content-Type-Options', 'nosniff')])
