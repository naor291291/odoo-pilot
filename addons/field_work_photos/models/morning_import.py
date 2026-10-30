from odoo import Command, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services.morning_api import MorningError
from .morning_connection import KINDS, STATUSES, amount, identifier, text


class MorningImport(models.TransientModel):
    _name = 'field.morning.import'
    _description = 'בחירת לקוח או מסמך ממורנינג'

    lead_id = fields.Many2one('crm.lead', required=True, readonly=True, ondelete='cascade')
    mode = fields.Selection([('customer', 'לקוח'), ('document', 'מסמך')], required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='לקוח באודו לקישור', help='אם השדה ריק, ייווצר לקוח חדש; לקוח שכבר קושר בעבר ימוחזר.')
    query = fields.Char(string='שם לקוח במורנינג')
    kind = fields.Selection(KINDS, string='סוג מסמך', required=True, default='10')
    number = fields.Char(string='מספר מסמך — אופציונלי')
    page = fields.Integer(default=1, readonly=True)
    has_more = fields.Boolean(readonly=True)
    message = fields.Char(readonly=True, default='בחר פרטי חיפוש ולחץ על חיפוש במורנינג.')
    result_ids = fields.One2many('field.morning.import.result', 'wizard_id', readonly=True)

    def _action(self):
        return {'type': 'ir.actions.act_window', 'name': 'בחירה ממורנינג',
                'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    def _context_records(self):
        self.ensure_one()
        self.check_access('read')
        self.lead_id._lock_morning_lead()
        connection = self.env['field.morning.connection']._for_lead(self.lead_id)
        if self.mode == 'document':
            customer = self.lead_id.field_morning_customer_id
            if not customer or customer.connection_id != connection or customer.partner_id != self.lead_id.partner_id:
                raise ValidationError('יש לקשר תחילה את לקוח העבודה למורנינג.')
        return self.lead_id, connection

    def _search_page(self, page):
        lead, connection = self._context_records()
        page = max(1, min(page, 10000))
        try:
            service = connection._api()
            if self.mode == 'customer':
                data = service.search_clients(self.query or '', page=page)
            else:
                data = service.search_documents(lead.field_morning_customer_id.remote_id, int(self.kind), self.number, page=page)
        except MorningError as error:
            raise UserError(str(error)) from None
        items = data.get('items')
        if not isinstance(items, list) or len(items) > 25 or not all(isinstance(item, dict) for item in items):
            raise UserError('מורנינג החזירה תוצאות לא תקינות. יש לנסות שוב.')
        rows = []
        for item in items:
            remote = identifier(item.get('id'))
            if self.mode == 'customer':
                name = text(item.get('name'))
                detail = ' · '.join(filter(None, [text(item.get('phone')) or text(item.get('mobile')),
                                                  text(item.get('city')), text(item.get('taxId'))]))
                values = {'name': name, 'detail': detail}
            else:
                number = str(item.get('number') or '')
                if not number.isdigit() or str(item.get('type')) != self.kind:
                    raise UserError('מורנינג החזירה תוצאת מסמך לא תקינה.')
                client = item.get('client') or {}
                if identifier(client.get('id')) != lead.field_morning_customer_id.remote_id:
                    raise UserError('תוצאות החיפוש כוללות מסמך של לקוח אחר. לא בוצע קישור.')
                values = {'name': dict(KINDS)[self.kind] + ' ' + number,
                          'detail': str(item.get('documentDate') or '') + ' · ' + dict(STATUSES).get(str(item.get('status')), 'לא ידוע'),
                          'total_amount': amount(item.get('amount')), 'currency_code': text(item.get('currency'))}
            rows.append(Command.create({**values, 'remote_id': remote}))
        pages = data.get('pages', 1)
        if not isinstance(pages, int) or pages < 0:
            raise UserError('מורנינג החזירה נתוני עמודים לא תקינים.')
        self.write({'page': page, 'has_more': page < pages,
                    'message': 'לא נמצאו תוצאות.' if not rows else 'נמצאו %s תוצאות בעמוד %s. יש לבחור במפורש את הרשומה המתאימה.' % (len(rows), page),
                    'result_ids': [Command.clear(), *rows]})
        return self._action()

    def action_search(self):
        return self._search_page(1)

    def action_next_page(self):
        if not self.has_more:
            return self._action()
        return self._search_page(self.page + 1)

    def action_previous_page(self):
        return self._search_page(max(1, self.page - 1))


class MorningImportResult(models.TransientModel):
    _name = 'field.morning.import.result'
    _description = 'תוצאת חיפוש ממורנינג'

    wizard_id = fields.Many2one('field.morning.import', required=True, ondelete='cascade')
    remote_id = fields.Char(required=True)
    name = fields.Char(string='לקוח / מסמך')
    detail = fields.Char(string='פרטי זיהוי')
    total_amount = fields.Float(string='סה״כ כולל מע״מ', digits=(16, 2))
    currency_code = fields.Char(string='מטבע')

    def action_select(self):
        self.ensure_one()
        self.check_access('read')
        wizard = self.wizard_id
        lead, connection = wizard._context_records()
        remote = identifier(self.remote_id)
        try:
            service = connection._api()
            # Re-fetch the selected ID. Browser-supplied preview fields are never
            # trusted, and a stale result cannot silently change the wrong record.
            if wizard.mode == 'customer':
                data = service.get_client(remote)
                if not isinstance(data, dict) or identifier(data.get('id')) != remote:
                    raise ValidationError('מורנינג החזירה לקוח אחר מהלקוח שנבחר.')
                if not isinstance(data.get('emails', []), list):
                    raise ValidationError('פרטי הדואר של הלקוח ממורנינג אינם תקינים.')
                self.env['field.morning.customer']._import(lead, connection, data, wizard.partner_id)
            else:
                data = service.get_document(remote)
                if str(data.get('type')) != wizard.kind:
                    raise ValidationError('סוג המסמך השתנה. יש לחפש אותו מחדש.')
                self.env['field.morning.document']._import(lead, connection, data, remote)
        except MorningError as error:
            raise UserError(str(error)) from None
        return {'type': 'ir.actions.act_window', 'res_model': 'crm.lead', 'res_id': lead.id,
                'views': [(self.env.ref('field_work_photos.view_field_lead_form').id, 'form')],
                'target': 'current'}
