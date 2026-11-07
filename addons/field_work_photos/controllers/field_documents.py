import base64

from werkzeug.exceptions import NotFound

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from ..models.field_documents import DOCUMENTS


class FieldWorkDocuments(http.Controller):
    @http.route('/field-work/documents/<int:lead_id>/<string:kind>',
                type='http', auth='user', methods=['GET'])
    def document(self, lead_id, kind, download=None):
        if kind not in DOCUMENTS:
            raise NotFound()
        lead = request.env['crm.lead'].browse(lead_id).with_context(bin_size=False)
        try:
            lead._check_field_document_access()
            payload = lead[DOCUMENTS[kind][1]]
        except (AccessError, MissingError):
            raise NotFound() from None
        if not payload:
            raise NotFound()
        disposition = 'attachment' if download == '1' else 'inline'
        return request.make_response(base64.b64decode(payload), headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', f'{disposition}; filename="{kind}-{lead.id}.pdf"'),
            ('Cache-Control', 'private, no-store'),
            ('Content-Security-Policy', "frame-ancestors 'none'; object-src 'none'; script-src 'none'"),
            ('X-Content-Type-Options', 'nosniff'),
        ])
