"""Delivery adapters. Configuration is scoped to one explicitly selected database and company."""
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.policy import SMTP

import requests


class DeliveryRejected(Exception):
    """A definite rejection, safe to show to operators without provider payloads."""


def setting(name):
    return os.environ.get('FIELD_WORK_' + name, '')


def company_enabled(env, company):
    return setting('DELIVERY_DB') == env.cr.dbname and setting('DELIVERY_COMPANY') == str(company.id)


def channel_mode(channel):
    return setting(channel.upper() + '_MODE')


def phone_digits(value):
    if not isinstance(value, str):
        return ''
    value = (value or '').strip()
    if not re.fullmatch(r'\+?[0-9(). -]+', value):
        return ''
    digits = re.sub(r'[^0-9]', '', value)
    if digits.startswith('00'):
        digits = digits[2:]
    if len(digits) in (9, 10) and digits.startswith('0'):
        digits = '972' + digits[1:]
    return digits if re.fullmatch(r'[1-9][0-9]{7,14}', digits) else ''


def send_email(recipient, subject, body, filename, pdf):
    host = setting('SMTP_HOST')
    sender = setting('SMTP_FROM')
    username = setting('SMTP_USERNAME')
    password = setting('SMTP_PASSWORD')
    port = setting('SMTP_PORT') or '465'
    security = setting('SMTP_SECURITY') or 'ssl'
    if (not all((host, sender, username, password)) or not port.isdecimal()
            or not 0 < int(port) <= 65535 or security not in ('ssl', 'starttls')):
        raise DeliveryRejected('הגדרות שרת המייל אינן מלאות.')
    message = EmailMessage(policy=SMTP)
    message['From'] = sender
    message['To'] = recipient
    message['Subject'] = subject
    message.set_content(body)
    message.add_attachment(pdf, maintype='application', subtype='pdf', filename=filename)
    context = ssl.create_default_context()
    options = {'host': host, 'port': int(port), 'timeout': 15}
    client = smtplib.SMTP_SSL(context=context, **options) if security == 'ssl' else smtplib.SMTP(**options)
    try:
        if security == 'starttls':
            client.starttls(context=context)
        client.login(username, password)
        client.send_message(message)
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPAuthenticationError):
        raise DeliveryRejected('שרת המייל דחה את השולח, הנמען או פרטי החיבור.') from None
    finally:
        client.close()
    return ''


def send_whatsapp(kind, recipient, number, filename, pdf):
    version = setting('WHATSAPP_API_VERSION')
    phone_id = setting('WHATSAPP_PHONE_ID')
    token = setting('WHATSAPP_TOKEN')
    template = setting('WHATSAPP_' + kind.upper() + '_TEMPLATE')
    language = setting('WHATSAPP_LANGUAGE') or 'he'
    if (not re.fullmatch(r'v[0-9]+\.[0-9]+', version) or not phone_id.isdecimal()
            or not token or not re.fullmatch(r'[a-z0-9_]+', template)):
        raise DeliveryRejected('הגדרות WhatsApp או תבנית המסמך אינן מלאות.')
    base = f'https://graph.facebook.com/{version}/{phone_id}'
    headers = {'Authorization': f'Bearer {token}'}
    upload = requests.post(
        base + '/media', headers=headers, data={'messaging_product': 'whatsapp'},
        files={'file': (filename, pdf, 'application/pdf')}, timeout=(5, 20), allow_redirects=False,
    )
    if not 200 <= upload.status_code < 300:
        raise DeliveryRejected('WhatsApp לא קיבל את קובץ ה־PDF.')
    media_id = upload.json().get('id')
    if not isinstance(media_id, str) or not media_id.isdecimal():
        raise DeliveryRejected('WhatsApp לא החזיר מזהה קובץ תקין.')
    response = requests.post(base + '/messages', headers=headers, json={
        'messaging_product': 'whatsapp', 'to': recipient, 'type': 'template',
        'template': {
            'name': template, 'language': {'code': language},
            'components': [
                {'type': 'header', 'parameters': [
                    {'type': 'document', 'document': {'id': media_id, 'filename': filename}},
                ]},
                {'type': 'body', 'parameters': [{'type': 'text', 'text': number}]},
            ],
        },
    }, timeout=(5, 20), allow_redirects=False)
    if 400 <= response.status_code < 500:
        raise DeliveryRejected('WhatsApp דחה את ההודעה. בדקו את התבנית, הנמען וההרשאות.')
    if not 200 <= response.status_code < 300:
        raise RuntimeError('WhatsApp acknowledgement unavailable')
    message_id = response.json()['messages'][0]['id']
    if not isinstance(message_id, str) or not message_id.startswith('wamid.') or len(message_id) > 255:
        raise RuntimeError('WhatsApp acknowledgement unavailable')
    return message_id
