"""Small, read-only Morning API client. No Odoo dependency and no credential logs.

Contract: https://developers.morning.co/docs/openapi.bundled.json (API 2.0.0).
POST is used only for OAuth authentication and the two documented searches.
"""
import json
import math
import time
import urllib.error
import urllib.request
from uuid import UUID


class MorningError(Exception):
    pass


SERVERS = {
    'sandbox': ('https://api.sandbox.morning.dev', 'https://sandbox.d.greeninvoice.co.il/api/v1'),
    'production': ('https://api.morning.co', 'https://api.greeninvoice.co.il/api/v1'),
}
DOCUMENT_TYPES = [(10, 'הצעת מחיר'), (300, 'חשבון עסקה'), (305, 'חשבונית מס'),
                  (320, 'חשבונית מס / קבלה'), (400, 'קבלה')]


def remote_id(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise MorningError('מזהה הרשומה במורנינג אינו תקין.') from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a bearer token or API secret to a redirect target.
        return None


def transport(url, method, payload, headers):
    body = json.dumps(payload).encode('utf-8') if payload is not None else None
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(NoRedirect())
    try:
        response = opener.open(request, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    except (OSError, urllib.error.URLError):
        raise MorningError('לא ניתן להתחבר למורנינג כרגע. אפשר לנסות שוב או להמשיך בהזנה ידנית.') from None
    with response:
        data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise MorningError('התקבלה תשובה גדולה מדי ממורנינג. יש לצמצם את החיפוש.')
        try:
            result = json.loads(data)
        except (ValueError, UnicodeError):
            raise MorningError('התקבלה תשובה לא תקינה ממורנינג. הנתונים הקיימים לא השתנו.') from None
        return response.code, result


class MorningAPI:
    def __init__(self, environment, client_id, client_secret, send=None):
        if environment not in SERVERS:
            raise MorningError('יש לבחור סביבת בדיקות או סביבת עסק.')
        if not client_id or not client_secret:
            raise MorningError('מנהל המערכת צריך להגדיר מפתחות API לחיבור מורנינג.')
        self.auth_base, self.base = SERVERS[environment]
        self.client_id = client_id
        self.client_secret = client_secret
        self.send = send or transport
        self.token = None
        self.expires_at = 0

    @staticmethod
    def _error(status, body):
        if status == 429:
            return MorningError('מורנינג הגבילה זמנית את קצב הבקשות. יש לנסות שוב מאוחר יותר.')
        if status in (400, 401, 403) and isinstance(body, dict) and body.get('error') == 'unauthorized_client':
            return MorningError('אין לחשבון גישת API פעילה. יש לבדוק מנוי Best ומעלה והרשאת המפתח.')
        if status in (401, 403):
            return MorningError('הגישה למורנינג נדחתה. מנהל המערכת צריך לבדוק את המפתחות וההרשאות.')
        if status == 404:
            return MorningError('הרשומה לא נמצאה במורנינג. יש לרענן את החיפוש.')
        return MorningError('הבקשה למורנינג לא הושלמה. הנתונים הקיימים לא השתנו; אפשר לנסות שוב.')

    def _authenticate(self):
        status, body = self.send(self.auth_base + '/idp/v1/oauth/token', 'POST', {
            'grant_type': 'client_credentials', 'client_id': self.client_id,
            'client_secret': self.client_secret,
        }, {'Content-Type': 'application/json', 'Accept': 'application/json'})
        if status != 200:
            raise self._error(status, body)
        if not isinstance(body, dict) or not isinstance(body.get('accessToken'), str) or not body['accessToken']:
            raise MorningError('מורנינג לא החזירה אסימון גישה תקין.')
        expires = body.get('expiresAt')
        if isinstance(expires, bool) or not isinstance(expires, (int, float)) or not math.isfinite(expires) or expires <= time.time():
            raise MorningError('מורנינג החזירה אסימון שפג תוקפו.')
        self.token, self.expires_at = body['accessToken'], expires

    def _read(self, path, payload=None):
        if not self.token or self.expires_at < time.time() + 30:
            self._authenticate()
        method = 'POST' if payload is not None else 'GET'
        for attempt in range(2):
            status, body = self.send(self.base + path, method, payload, {
                'Authorization': 'Bearer ' + self.token,
                'Content-Type': 'application/json', 'Accept': 'application/json',
            })
            if status == 401 and not attempt:
                self._authenticate()
                continue
            if status != 200:
                raise self._error(status, body)
            if not isinstance(body, dict):
                raise MorningError('התקבלה תשובה לא תקינה ממורנינג.')
            return body

    def search_clients(self, name, page=1):
        if not isinstance(name, str) or len(name.strip()) < 2:
            raise MorningError('יש להזין לפחות שתי אותיות בשם הלקוח.')
        return self._read('/clients/search', {'name': name.strip(), 'active': True,
                                            'page': max(1, int(page)), 'pageSize': 25})

    def get_client(self, identifier):
        return self._read('/clients/' + remote_id(identifier))

    def search_documents(self, client_id, kind, number=None, page=1):
        if kind not in dict(DOCUMENT_TYPES):
            raise MorningError('סוג המסמך אינו נתמך בשלב זה.')
        payload = {'clientId': remote_id(client_id), 'type': [kind],
                   'page': max(1, int(page)), 'pageSize': 25, 'sort': 'documentDate'}
        if number:
            if not str(number).isdigit():
                raise MorningError('מספר מסמך חייב להכיל ספרות בלבד.')
            payload['number'] = int(number)
        return self._read('/documents/search', payload)

    def get_document(self, identifier):
        return self._read('/documents/' + remote_id(identifier))

    def get_document_links(self, identifier):
        return self._read('/documents/' + remote_id(identifier) + '/download/links')
