"""Public Meta callback authenticated with an HMAC over the exact request bytes."""
import hashlib
import hmac
import json

from psycopg2.errors import UniqueViolation
from werkzeug.exceptions import BadRequest, Forbidden, NotFound, RequestEntityTooLarge, ServiceUnavailable

from odoo import http
from odoo.http import request

from ..models.field_delivery_provider import phone_digits, setting


MAX_WEBHOOK_BYTES = 256 * 1024


def verified_signature(secret, signature, body):
    if not secret or not signature:
        return False
    expected = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.encode(), expected.encode())


def validate_event_structure(event):
    """Reject malformed signed batches before applying any of their changes."""
    def objects(parent, key):
        value = parent.get(key, [])
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise BadRequest()
        return value

    for entry in objects(event, 'entry'):
        for change in objects(entry, 'changes'):
            value = change.get('value', {})
            if not isinstance(value, dict) or not isinstance(value.get('metadata', {}), dict):
                raise BadRequest()
            objects(value, 'statuses')
            for message in objects(value, 'messages'):
                if not isinstance(message.get('text', {}), dict):
                    raise BadRequest()


class FieldWorkWhatsApp(http.Controller):

    @http.route('/field-work/whatsapp/webhook', type='http', auth='public',
                methods=['GET', 'POST'], csrf=False, save_session=False)
    def webhook(self, **params):
        company_id = setting('DELIVERY_COMPANY')
        secret = setting('WHATSAPP_APP_SECRET')
        phone_id = setting('WHATSAPP_PHONE_ID')
        if (setting('DELIVERY_DB') != request.env.cr.dbname
                or not (company_id.isdecimal() and phone_id.isdecimal() and secret)):
            raise NotFound()
        incoming = request.httprequest
        if incoming.method == 'GET':
            token = setting('WHATSAPP_VERIFY_TOKEN')
            supplied = params.get('hub.verify_token', '')
            challenge = params.get('hub.challenge', '')
            if (params.get('hub.mode') != 'subscribe' or not token or not challenge
                    or not hmac.compare_digest(token.encode(), supplied.encode())):
                raise Forbidden()
            return request.make_response(challenge, headers=[('Content-Type', 'text/plain')])
        if (incoming.content_length or 0) > MAX_WEBHOOK_BYTES:
            raise RequestEntityTooLarge()
        incoming.max_content_length = MAX_WEBHOOK_BYTES
        body = incoming.get_data()
        if len(body) > MAX_WEBHOOK_BYTES:
            raise RequestEntityTooLarge()
        if not verified_signature(secret, incoming.headers.get('X-Hub-Signature-256'), body):
            raise Forbidden()
        try:
            event = json.loads(body)
        except (ValueError, RecursionError) as error:
            raise BadRequest() from error
        if not isinstance(event, dict) or event.get('object') != 'whatsapp_business_account':
            raise BadRequest()
        validate_event_structure(event)
        company = request.env['res.company'].sudo().browse(int(company_id)).exists()
        if not company:
            raise NotFound()
        for entry in event.get('entry') or []:
            for change in entry.get('changes') or []:
                value = change.get('value') or {}
                if change.get('field') == 'messages' and (value.get('metadata') or {}).get('phone_number_id') == phone_id:
                    self._apply_change(company, value)
        return request.make_response('OK', headers=[('Content-Type', 'text/plain')])

    def _apply_change(self, company, value):
        env = request.env
        attempts = env['field.work.delivery.attempt'].sudo()
        for event in value.get('statuses') or []:
            provider_id = event.get('id')
            status = event.get('status')
            if not isinstance(provider_id, str) or not provider_id.startswith('wamid.') or len(provider_id) > 255:
                continue
            attempt = attempts.search([('company_id', '=', company.id), ('channel', '=', 'whatsapp'),
                                       ('provider_id', '=', provider_id)], limit=1)
            if not attempt:
                # A callback can arrive while the worker is committing the ID.
                if attempts.search_count([('company_id', '=', company.id), ('channel', '=', 'whatsapp'),
                                          ('status', '=', 'sending')], limit=1):
                    raise ServiceUnavailable()
                continue
            env.cr.execute('SELECT id FROM field_work_delivery_attempt WHERE id = %s FOR UPDATE', [attempt.id])
            attempt.invalidate_recordset(['status'])
            if status in ('delivered', 'read') and attempt.status != 'delivered':
                attempt.write({'status': 'delivered', 'result_note': 'WhatsApp אישר מסירה.'})
            elif status == 'failed' and attempt.status == 'accepted':
                attempt.write({'status': 'failed', 'result_note': 'WhatsApp דיווח שההודעה לא נמסרה.'})
        if setting('WHATSAPP_INBOUND') != '1' or not value.get('messages'):
            return
        leads = env['crm.lead'].sudo().with_context(allowed_company_ids=[company.id], active_test=False)
        for message in value['messages']:
            event_id = message.get('id')
            sender = phone_digits(message.get('from'))
            body = (message.get('text') or {}).get('body')
            if (message.get('type') != 'text' or not isinstance(event_id, str)
                    or not event_id.startswith('wamid.') or len(event_id) > 255
                    or not sender or not isinstance(body, str) or not body.strip()):
                continue
            if leads.search_count([('field_whatsapp_event_id', '=', event_id)], limit=1):
                continue
            try:
                with env.cr.savepoint():
                    leads.create({'name': 'פנייה מוואטסאפ', 'company_id': company.id,
                                  'is_field_service': True, 'phone': '+' + sender,
                                  'field_work_description': body[:4000], 'field_whatsapp_event_id': event_id})
            except UniqueViolation as error:
                if error.diag.constraint_name != 'crm_lead_field_whatsapp_event_unique':
                    raise
