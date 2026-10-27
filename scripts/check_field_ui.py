"""Run the real Odoo form in desktop/mobile Chrome against disposable CI data."""
import json
import os
from pathlib import Path
import time

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.local-data' / 'ui-checks'
OUTPUT.mkdir(parents=True, exist_ok=True)
login = json.loads((ROOT / '.local-data' / 'credentials.json').read_text())

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ['CHROME_BIN'], args=['--no-sandbox'])
    context = browser.new_context(viewport={'width': 1440, 'height': 1100}, locale='he-IL')
    for attempt in range(120):
        try:
            response = context.request.get('http://127.0.0.1:8069/web/login', timeout=3000)
            if response.ok:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise RuntimeError('Odoo did not become ready for browser verification')

    def rpc(path, params):
        response = context.request.post('http://127.0.0.1:8069' + path, data={
            'jsonrpc': '2.0', 'method': 'call', 'params': params, 'id': 1,
        })
        result = response.json()
        if result.get('error'):
            raise RuntimeError(result['error']['data'].get('message', 'RPC failed'))
        return result.get('result')

    def model(name, method, args, **kwargs):
        return rpc('/web/dataset/call_kw/' + name + '/' + method,
                   {'model': name, 'method': method, 'args': args, 'kwargs': kwargs})

    session = rpc('/web/session/authenticate', {'db': 'odoo_pilot', 'login': login['login'], 'password': login['password']})
    assert session.get('uid')
    action = model('ir.model.data', 'search_read', [[['module', '=', 'field_work_photos'], ['name', '=', 'action_field_service_leads']]], fields=['res_id'])[0]['res_id']
    customer = model('res.partner', 'create', [{'name': 'לקוח בדיקת מסך'}])
    lead = model('crm.lead', 'create', [{
        'name': 'החלפת ברז — בדיקת ממשק', 'is_field_service': True,
        'partner_id': customer, 'phone': False,
        'field_site_address': 'רחוב לדוגמה 10, גבעתיים',
        'field_work_description': 'החלפת הברז במטבח ובדיקת נזילות לאחר ההתקנה.',
    }])
    page = context.new_page()
    errors = []
    def record_page_error(error):
        errors.append(str(error))
        print('BROWSER PAGE ERROR:', str(error), flush=True)

    def record_console_error(message):
        if message.type != 'error':
            return
        print('BROWSER CONSOLE ERROR:', message.text, flush=True)
        for argument in message.args:
            try:
                detail = argument.evaluate('value => value instanceof Error ? [value.stack, value.cause?.stack].filter(Boolean).join("\\nCaused by: ") : String(value)')
                print(detail, flush=True)
            except Exception:
                pass

    page.on('pageerror', record_page_error)
    page.on('console', record_console_error)
    page.goto(f'http://127.0.0.1:8069/odoo/action-{action}/new')
    expect(page.locator('.o_field_service_hero')).to_be_visible(timeout=60000)
    page.locator('.o_field_service_heading [name="name"] input').fill('טיוטה — בדיקת ממשק')
    page.locator('.o_form_button_save').click()
    expect(page.locator('.o_form_status_indicator_new_record')).to_have_count(0)
    drafts = model('crm.lead', 'search_read', [[['name', '=', 'טיוטה — בדיקת ממשק']]], fields=['field_dispatch_code'])
    assert drafts and drafts[0]['field_dispatch_code'] == 'new', 'New form defaults or partial draft save failed'
    url = f'http://127.0.0.1:8069/odoo/action-{action}/{lead}'
    page.goto(url)
    expect(page.locator('.o_field_service_hero')).to_be_visible(timeout=60000)
    expect(page.locator('.o_field_service_notice_warning')).to_contain_text('טלפון לתיאום')
    page.screenshot(path=str(OUTPUT / 'desktop-missing-details.png'), full_page=True)
    page.get_by_role('button', name='המשך להצעת מחיר', exact=True).click()
    expect(page.locator('.modal:visible')).to_be_visible()
    expect(page.locator('.modal:visible')).to_contain_text('טלפון לתיאום')
    assert model('crm.lead', 'read', [[lead]], fields=['field_dispatch_code'])[0]['field_dispatch_code'] == 'new'
    model('crm.lead', 'write', [[lead], {'phone': '0500000000'}])
    page.goto(url)
    expect(page.locator('.o_field_service_hero')).to_be_visible()
    expect(page.locator('.o_field_service_notice_ready')).to_be_visible()
    page.get_by_role('button', name='המשך להצעת מחיר', exact=True).click()
    expect(page.get_by_role('button', name='המשך — ההצעה נשלחה', exact=True)).to_be_visible()
    assert model('crm.lead', 'read', [[lead]], fields=['field_dispatch_code'])[0]['field_dispatch_code'] == 'quote'
    page.screenshot(path=str(OUTPUT / 'desktop-quote.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    expect(page.locator('.o_field_service_hero')).to_be_visible()
    page.screenshot(path=str(OUTPUT / 'mobile-quote.png'), full_page=True)
    mobile_next = page.get_by_role('button', name='המשך — ההצעה נשלחה', exact=True)
    expect(mobile_next).to_be_in_viewport()
    page.locator('.o_field_service_main .o_field_service_card').nth(1).scroll_into_view_if_needed()
    expect(mobile_next).to_be_in_viewport()
    page.screenshot(path=str(OUTPUT / 'mobile-quote-details.png'), full_page=True)
    mobile_next.click()
    expect(page.locator('.modal:visible')).to_contain_text('מספר הצעת מחיר ממורנינג')
    assert model('crm.lead', 'read', [[lead]], fields=['field_dispatch_code'])[0]['field_dispatch_code'] == 'quote'
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Form overflows mobile viewport'
    assert not errors, errors
    context.close()
    browser.close()
print('PASS: real Chrome rendered new draft, desktop/mobile forms, missing-field dialog and Continue action; no JS errors.')
