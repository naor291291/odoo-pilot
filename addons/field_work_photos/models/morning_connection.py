"""Morning configuration, verified customer links and read-only document snapshots."""
import math
from urllib.parse import urlsplit

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services.morning_api import DOCUMENT_TYPES, MorningAPI, MorningError, remote_id

OPS = 'field_work_photos.group_field_dispatcher'
ADMIN = 'base.group_system'
KINDS = [(str(code), label) for code, label in DOCUMENT_TYPES]
STATUSES = [('0', 'פתוח'), ('1', 'סגור'), ('2', 'סומן ידנית כסגור'),
            ('3', 'מסמך מבטל'), ('4', 'בוטל')]
LEAD_FIELDS = {'field_morning_customer_id', 'field_morning_document_ids'}


def identifier(value):
    try:
        return remote_id(value)
    except MorningError as error:
        raise ValidationError(str(error)) from None


def text(value):
    return value.strip() if isinstance(value, str) else ''


def amount(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValidationError('מורנינג החזירה סכום לא תקין. הנתונים הקיימים לא השתנו.')
    return value


def document_values(data, expected_id, customer_id):
    if not isinstance(data, dict) or identifier(data.get('id')) != identifier(expected_id):
        raise ValidationError('מורנינג החזירה מסמך אחר מהמסמך שנבחר.')
    client = data.get('client')
    if not isinstance(client, dict) or identifier(client.get('id')) != identifier(customer_id):
        raise ValidationError('המסמך אינו שייך ללקוח המקושר לעבודה. לא בוצע קישור.')
    kind = data.get('type')
    if isinstance(kind, bool) or kind not in dict(DOCUMENT_TYPES):
        raise ValidationError('סוג המסמך אינו נתמך בשלב זה.')
    number = str(data.get('number') or '')
    status = str(data.get('status'))
    currency = text(data.get('currency'))
    if not number.isdigit() or status not in dict(STATUSES) or len(currency) != 3:
        raise ValidationError('חסרים במסמך מספר, מצב או מטבע תקינים.')
    try:
        date = fields.Date.to_date(data.get('documentDate'))
    except (ValueError, TypeError):
        date = False
    if not date:
        raise ValidationError('תאריך המסמך ממורנינג אינו תקין.')
    total, vat = amount(data.get('amount')), amount(data.get('vat'))
    return {'remote_id': identifier(expected_id), 'kind': str(kind), 'number': number,
            'document_date': date, 'status': status, 'currency_code': currency,
            'net_amount': total - vat, 'vat_amount': vat, 'total_amount': total,
            'synced_at': fields.Datetime.now()}


class MorningConnection(models.Model):
    _name = 'field.morning.connection'
    _description = 'חיבור מורנינג'
    _rec_name = 'name'
    _check_company_auto = True

    name = fields.Char(default='מורנינג — סביבת בדיקות', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, ondelete='restrict')
    environment = fields.Selection([('sandbox', 'סביבת בדיקות — Sandbox'),
                                    ('production', 'חשבון העסק — נתונים אמיתיים')],
                                   required=True, default='sandbox')
    enabled = fields.Boolean(string='החיבור פעיל', default=False)
    client_id = fields.Char(string='מזהה מפתח API', groups=ADMIN, copy=False)
    client_secret = fields.Char(string='מפתח סודי', groups=ADMIN, copy=False)

    _sql_constraints = [('company_unique', 'unique(company_id)', 'ניתן להגדיר חיבור מורנינג אחד לכל חברה.')]

    def write(self, vals):
        # A different key/environment could refer to an entirely different business.
        # Keep existing external IDs tied to the business they were imported from.
        for connection in self:
            if any(key in vals and vals[key] != (connection[key].id if key == 'company_id' else connection[key]) for key in ('company_id', 'environment', 'client_id')):
                if self.env['field.morning.customer'].sudo().search_count([('connection_id', '=', connection.id)]):
                    raise ValidationError('לא ניתן להחליף חברה, סביבה או מזהה מפתח לאחר קישור לקוחות. אפשר לעדכן את הסוד או להשבית את החיבור.')
        return super().write(vals)

    def _api(self, require_enabled=True):
        self.ensure_one()
        if require_enabled and not self.enabled:
            raise UserError('חיבור מורנינג מושבת. אפשר להמשיך בהזנה ידנית.')
        try:
            return MorningAPI(self.environment, self.client_id, self.client_secret)
        except MorningError as error:
            raise UserError(str(error)) from None

    def action_test(self):
        self.ensure_one()
        self.check_access('read')
        if not self.env.user.has_group(ADMIN):
            raise AccessError('בדיקת החיבור זמינה למנהל המערכת בלבד.')
        try:
            self._api(require_enabled=False).search_clients('בדיקה')
        except MorningError as error:
            raise UserError(str(error)) from None
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': 'החיבור למורנינג תקין', 'message': 'בדיקת קריאה בלבד הסתיימה בהצלחה.', 'type': 'success'}}

    @api.model
    def _for_lead(self, lead):
        lead.ensure_one()
        lead._require_dispatcher()
        lead.check_access('write')
        company = lead.company_id or self.env.company
        if company not in self.env.companies:
            raise AccessError('החברה אינה זמינה למשתמש המחובר.')
        connection = self.sudo().search([('company_id', '=', company.id)], limit=1)
        if not connection or not connection.enabled:
            raise UserError('חיבור מורנינג עדיין לא הופעל לחברה זו. אפשר להמשיך בהזנה ידנית.')
        return connection


class MorningCustomer(models.Model):
    _name = 'field.morning.customer'
    _description = 'לקוח מקושר למורנינג'
    _rec_name = 'name'

    name = fields.Char(related='partner_id.name')
    connection_id = fields.Many2one('field.morning.connection', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='connection_id.company_id', store=True, index=True)
    partner_id = fields.Many2one('res.partner', required=True, ondelete='restrict')
    remote_id = fields.Char(required=True, index=True)
    remote_name = fields.Char(string='שם במורנינג')
    tax_id = fields.Char(string='מספר מזהה במורנינג')
    synced_at = fields.Datetime(string='נבדק לאחרונה')

    _sql_constraints = [
        ('remote_unique', 'unique(connection_id, remote_id)', 'הלקוח ממורנינג כבר מקושר ללקוח באודו.'),
        ('partner_unique', 'unique(connection_id, partner_id)', 'הלקוח באודו כבר מקושר ללקוח אחר במורנינג.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError('קישור לקוח מתבצע מתוך חיפוש הלקוחות במורנינג בלבד.')

    def write(self, vals):
        raise AccessError('נתוני הקישור מתעדכנים מתוך מורנינג בלבד.')

    def unlink(self):
        raise AccessError('לא ניתן למחוק קישור לקוח ישירות.')

    @api.model
    def _import(self, lead, connection, data, partner):
        lead._lock_morning_lead()
        if identifier(data.get('id')) and not text(data.get('name')):
            raise ValidationError('ללקוח ממורנינג חסר שם.')
        if data.get('active') is not True:
            raise ValidationError('הלקוח אינו פעיל במורנינג.')
        remote = identifier(data['id'])
        # Serialize imports per connection to prevent duplicate partners on retries.
        self.env.cr.execute('SELECT id FROM field_morning_connection WHERE id = %s FOR UPDATE', [connection.id])
        mapping = self.search([('connection_id', '=', connection.id), ('remote_id', '=', remote)])
        if mapping:
            if partner and mapping.partner_id != partner:
                raise ValidationError('הלקוח ממורנינג כבר מקושר ללקוח אחר באודו. יש לבחור את הלקוח המקושר.')
            partner = mapping.partner_id
        if partner:
            partner.check_access('write')
            if partner.company_id and partner.company_id != connection.company_id:
                raise ValidationError('הלקוח באודו שייך לחברה אחרת.')
            other = self.search([('connection_id', '=', connection.id), ('partner_id', '=', partner.id)])
            if other and other.remote_id != remote:
                raise ValidationError('הלקוח באודו כבר מקושר ללקוח אחר במורנינג.')
        values = {'name': text(data.get('name')), 'phone': text(data.get('phone')) or text(data.get('mobile')),
                  'email': next((text(email) for email in data.get('emails', []) if text(email)), '')}
        country = self.env['res.country'].search([('code', '=', text(data.get('country')))], limit=1)
        if not partner or not any((partner.street, partner.city, partner.zip)):
            if not partner or not partner.country_id or partner.country_id == country:
                values.update(street=text(data.get('address')), city=text(data.get('city')), zip=text(data.get('zip')))
                if country:
                    values['country_id'] = country.id
        if partner:
            partner.write({key: value for key, value in values.items() if value and not partner[key]})
        else:
            partner = self.env['res.partner'].create({**values, 'company_id': connection.company_id.id})
        metadata = {'remote_name': text(data.get('name')), 'tax_id': text(data.get('taxId')), 'synced_at': fields.Datetime.now()}
        if mapping:
            super(MorningCustomer, mapping).write(metadata)
        else:
            mapping = super().create({**metadata, 'connection_id': connection.id, 'partner_id': partner.id, 'remote_id': remote})
        lead._set_morning_customer(mapping, data)
        return mapping


class MorningDocument(models.Model):
    _name = 'field.morning.document'
    _description = 'מסמך מקושר ממורנינג'
    _rec_name = 'number'
    _order = 'document_date desc, id desc'

    lead_id = fields.Many2one('crm.lead', required=True, ondelete='cascade', index=True)
    customer_id = fields.Many2one('field.morning.customer', required=True, ondelete='restrict')
    connection_id = fields.Many2one(related='customer_id.connection_id', store=True)
    company_id = fields.Many2one(related='customer_id.company_id', store=True, index=True)
    remote_id = fields.Char(required=True, index=True)
    kind = fields.Selection(KINDS, string='סוג מסמך', required=True)
    number = fields.Char(string='מספר מסמך', required=True)
    document_date = fields.Date(string='תאריך', required=True)
    status = fields.Selection(STATUSES, string='מצב במורנינג', required=True)
    currency_code = fields.Char(string='מטבע', required=True)
    net_amount = fields.Float(string='סכום ללא מע״מ', digits=(16, 2))
    vat_amount = fields.Float(string='מע״מ', digits=(16, 2))
    total_amount = fields.Float(string='סה״כ כולל מע״מ', digits=(16, 2))
    synced_at = fields.Datetime(string='עודכן ממורנינג')

    _sql_constraints = [('remote_unique', 'unique(connection_id, remote_id)', 'המסמך כבר מקושר לעבודה. לא ניתן לשייך אותו לשתי עבודות.')]

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError('מסמך מקושר רק מתוך בחירת מסמכים ממורנינג.')

    def write(self, vals):
        raise AccessError('מסמך ממורנינג ניתן לעדכן רק באמצעות רענון.')

    def unlink(self):
        raise AccessError('יש להשתמש בפעולת הסרת הקישור בכרטיס העבודה.')

    def _check_operator(self):
        self.ensure_one()
        self.check_access('read')
        self.lead_id._require_dispatcher()
        self.lead_id.check_access('write')

    @api.model
    def _import(self, lead, connection, data, expected_id):
        lead._lock_morning_lead()
        customer = lead.field_morning_customer_id
        if not customer or customer.connection_id != connection or customer.partner_id != lead.partner_id:
            raise ValidationError('יש לקשר תחילה את לקוח העבודה למורנינג.')
        values = document_values(data, expected_id, customer.remote_id)
        self.env.cr.execute('SELECT id FROM field_morning_connection WHERE id = %s FOR UPDATE', [connection.id])
        existing = self.search([('connection_id', '=', connection.id), ('remote_id', '=', values['remote_id'])])
        if existing and existing.lead_id != lead:
            raise ValidationError('המסמך כבר מקושר לעבודה אחרת. לא בוצע שינוי.')
        if existing:
            super(MorningDocument, existing).write(values)
            return existing
        result = super().create({**values, 'lead_id': lead.id, 'customer_id': customer.id})
        if values['kind'] == '10' and values['status'] not in ('3', '4') and not lead.field_quote_number and not lead.field_dispatch_locked:
            lead.write({'field_quote_number': values['number']})
        return result

    def action_refresh(self):
        self._check_operator()
        connection = self.env['field.morning.connection']._for_lead(self.lead_id)
        if connection != self.connection_id:
            raise ValidationError('חיבור מורנינג השתנה. לא בוצע עדכון.')
        try:
            data = connection._api().get_document(self.remote_id)
        except MorningError as error:
            raise UserError(str(error)) from None
        self._import(self.lead_id, connection, data, self.remote_id)
        return True

    def action_open_pdf(self):
        self._check_operator()
        connection = self.env['field.morning.connection']._for_lead(self.lead_id)
        if connection != self.connection_id:
            raise ValidationError('חיבור מורנינג השתנה.')
        try:
            urls = connection._api().get_document_links(self.remote_id)
        except MorningError as error:
            raise UserError(str(error)) from None
        url = urls.get('origin') or urls.get('he')
        if not isinstance(url, str) or urlsplit(url).scheme != 'https' or not urlsplit(url).hostname or urlsplit(url).username:
            raise UserError('מורנינג לא החזירה קישור HTTPS תקין למסמך.')
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    def action_apply_amount(self):
        self._check_operator()
        self.lead_id._lock_morning_lead()
        if self.kind == '400' or self.status in ('3', '4') or self.currency_code != 'ILS' or self.net_amount <= 0:
            raise ValidationError('ניתן לעדכן סכום רק מהצעה או חשבונית תקינה בשקלים ובסכום חיובי.')
        self.lead_id.write({'field_sale_amount': self.net_amount})
        return True

    def action_remove_link(self):
        self._check_operator()
        super(MorningDocument, self).unlink()
        return True


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    field_morning_customer_id = fields.Many2one('field.morning.customer', string='לקוח מקושר במורנינג', readonly=True, copy=False, groups=OPS, ondelete='restrict')
    field_morning_document_ids = fields.One2many('field.morning.document', 'lead_id', string='מסמכי מורנינג', readonly=True, copy=False, groups=OPS)

    def _lock_morning_lead(self):
        self.ensure_one()
        self._require_dispatcher()
        self.check_access('write')
        self.env.cr.execute('SELECT id FROM crm_lead WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        if not self.is_field_service:
            raise ValidationError('החיבור זמין לפניות עבודות שטח בלבד.')

    def _set_morning_customer(self, mapping, data):
        self._lock_morning_lead()
        if self.field_morning_document_ids and self.field_morning_customer_id != mapping:
            raise ValidationError('יש להסיר תחילה את קישורי המסמכים לפני החלפת לקוח מורנינג.')
        values = {'partner_id': mapping.partner_id.id, 'field_morning_customer_id': mapping.id}
        if not self.phone:
            values['phone'] = text(data.get('phone')) or text(data.get('mobile'))
        if not self.contact_name:
            values['contact_name'] = text(data.get('contactPerson')) or text(data.get('name'))
        super(CrmLead, self).write(values)

    def _morning_wizard(self, mode):
        self._lock_morning_lead()
        connection = self.env['field.morning.connection']._for_lead(self)
        if mode == 'document' and (not self.field_morning_customer_id or self.field_morning_customer_id.connection_id != connection):
            raise UserError('יש לבחור תחילה לקוח ממורנינג ולקשר אותו לעבודה.')
        wizard = self.env['field.morning.import'].create({
            'lead_id': self.id, 'mode': mode, 'partner_id': self.partner_id.id,
            'query': self.partner_id.name or self.contact_name or '',
        })
        return wizard._action()

    def action_morning_customer(self):
        return self._morning_wizard('customer')

    def action_morning_documents(self):
        return self._morning_wizard('document')

    @api.model_create_multi
    def create(self, vals_list):
        if any(LEAD_FIELDS.intersection(vals) for vals in vals_list):
            raise AccessError('קישורי מורנינג נוצרים מתוך בחירת לקוח ומסמך בלבד.')
        return super().create(vals_list)

    def write(self, vals):
        if LEAD_FIELDS.intersection(vals):
            raise AccessError('קישורי מורנינג נוצרים מתוך בחירת לקוח ומסמך בלבד.')
        if {'partner_id', 'company_id'}.intersection(vals):
            for lead in self.filtered('field_morning_customer_id'):
                lead._lock_morning_lead()
                if any(key in vals and (vals[key] or False) != lead[key].id for key in ('partner_id', 'company_id')):
                    if lead.field_morning_document_ids:
                        raise ValidationError('יש להסיר תחילה את קישורי המסמכים לפני שינוי לקוח או חברה.')
                    super(CrmLead, lead).write({'field_morning_customer_id': False})
        return super().write(vals)
