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
    expect(page.get_by_role('button', name='אישור פרטי ההצעה והמשך', exact=True)).to_be_visible()
    assert model('crm.lead', 'read', [[lead]], fields=['field_dispatch_code'])[0]['field_dispatch_code'] == 'quote'
    page.screenshot(path=str(OUTPUT / 'desktop-quote.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    expect(page.locator('.o_field_service_hero')).to_be_visible()
    page.screenshot(path=str(OUTPUT / 'mobile-quote.png'), full_page=True)
    mobile_next = page.get_by_role('button', name='אישור פרטי ההצעה והמשך', exact=True)
    expect(mobile_next).to_be_in_viewport()
    page.locator('.o_field_service_main .o_field_service_card').nth(1).scroll_into_view_if_needed()
    expect(mobile_next).to_be_in_viewport()
    page.screenshot(path=str(OUTPUT / 'mobile-quote-details.png'), full_page=True)
    mobile_next.click()
    expect(page.locator('.modal:visible')).to_contain_text('מספר הצעת מחיר ממורנינג')
    assert model('crm.lead', 'read', [[lead]], fields=['field_dispatch_code'])[0]['field_dispatch_code'] == 'quote'
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Form overflows mobile viewport'
    # Reproduce the narrow RTL pricing card from the reported screenshot.
    # Check focus borders and label/input geometry, then save an actual amount.
    contractor = model('res.users', 'search', [[['login', '=', login['contractors'][0]['login']]]])[0]
    model('crm.lead', 'write', [[lead], {
        'field_contractor_id': contractor, 'field_sale_amount': 12354,
        'field_material_cost': 100,
    }])
    page.goto(url)
    pricing = page.locator('.o_field_pricing_card')
    material = pricing.locator('[name="field_material_cost"] input')
    for width in (1440, 1100, 390):
        page.set_viewport_size({'width': width, 'height': 1000})
        material.scroll_into_view_if_needed()
        material.click()
        expect(material).to_be_focused()
        geometry = material.evaluate("""input => {
            const widget = input.closest('.o_field_monetary');
            const card = input.closest('.o_field_pricing_card').getBoundingClientRect();
            const label = input.closest('.o_field_pricing_row').querySelector('label').getBoundingClientRect();
            const box = input.getBoundingClientRect();
            const frames = [...widget.querySelectorAll('*')].filter(element => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return rect.width > 0 && rect.height > 0 &&
                    ['borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth']
                        .some(edge => parseFloat(style[edge]) > 0);
            });
            return {
                frames: frames.length, above: label.bottom <= box.top,
                contained: box.left >= card.left && box.right <= card.right,
                width: box.width,
            };
        }""")
        assert geometry['frames'] == 1, f'Duplicate monetary borders at {width}px: {geometry}'
        assert geometry['above'] and geometry['contained'] and geometry['width'] > 150, geometry
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Pricing form overflows viewport'
        page.screenshot(path=str(OUTPUT / f'pricing-focused-{width}.png'), full_page=True)
    material.fill('11000')
    material.press('Tab')
    page.locator('.o_form_button_save').click()
    expect(page.locator('.o_form_button_save')).to_be_hidden()
    saved = model('crm.lead', 'read', [[lead]], fields=['field_material_cost', 'field_gross_profit'])[0]
    assert saved['field_material_cost'] == 11000 and saved['field_gross_profit'] == -4823, saved
    profit = pricing.locator('[name="field_gross_profit"]')
    assert profit.evaluate('element => getComputedStyle(element).direction') == 'ltr', 'Negative amount uses RTL ordering'
    expect(profit).to_contain_text('-4,823.00')
    # Exercise the same work item in the manager workspace and contractor portal.
    import datetime
    import struct
    import zlib
    def png(rgb):
        def chunk(kind, data):
            return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)
        raw = b''.join(b'\0' + bytes(rgb) * 8 for _ in range(8))
        return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 8, 8, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
    model('crm.lead', 'write', [[lead], {'field_sale_amount': 1000, 'field_material_cost': 100, 'field_quote_number': 'UI-WORK', 'field_visit_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}])
    page.set_viewport_size({'width': 1440, 'height': 1100})
    page.goto(url)
    page.get_by_role('button', name='אישור פרטי ההצעה והמשך', exact=True).click()
    page.get_by_role('button', name='אישור הצעה והמשך לתיאום', exact=True).click()
    page.get_by_role('button', name='המשך — שיבוץ ופתיחת משימה', exact=True).click()
    expect(page.locator('.o_field_report_panel')).to_be_visible()
    task = model('crm.lead', 'read', [[lead]], fields=['field_workspace_task_id'])[0]['field_workspace_task_id'][0]
    contractor_context = browser.new_context(viewport={'width': 390, 'height': 844}, locale='he-IL')
    response = contractor_context.request.post('http://127.0.0.1:8069/web/session/authenticate', data={
        'jsonrpc': '2.0', 'method': 'call', 'id': 1,
        'params': {'db': 'odoo_pilot', 'login': login['contractors'][0]['login'], 'password': login['contractors'][0]['password']},
    })
    assert response.json().get('result', {}).get('uid'), 'Contractor authentication failed'
    portal = contractor_context.new_page()
    portal.on('pageerror', record_page_error)
    portal.on('console', record_console_error)
    portal.goto('http://127.0.0.1:8069/my/field-work')
    expect(portal.get_by_role('heading', name='עבודות השטח שלי', exact=True)).to_be_visible()
    portal.get_by_role('link', name='החלפת ברז — בדיקת ממשק', exact=False).click()
    submit_report = portal.locator('[data-report-submit]')
    expect(submit_report).to_be_disabled()
    with portal.expect_file_chooser() as chooser:
        portal.get_by_role('button', name='בחירת תמונה לפני ביצוע', exact=True).click()
    chooser.value.set_files({'name': 'before.png', 'mimeType': 'image/png', 'buffer': png((200, 50, 20))})
    expect(portal.locator('[data-file-status]').first).to_contain_text('עדיין לא נשמרה')
    expect(submit_report).to_be_disabled()
    portal.locator('#field_after_image').set_input_files({'name': 'after.png', 'mimeType': 'image/png', 'buffer': png((30, 100, 220))})
    expect(submit_report).to_be_enabled()
    expect(portal.locator('.o_field_photo_preview')).to_have_count(2)
    assert portal.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Portal overflows mobile viewport'
    portal.screenshot(path=str(OUTPUT / 'portal-mobile-selected.png'), full_page=True)
    submit_report.click()
    expect(portal.get_by_text('הדיווח והתמונות נשלחו לבדיקת התפעול.', exact=True)).to_be_visible()
    expect(portal.locator('input[type="file"]')).to_have_count(0)
    page.goto(url)
    page.get_by_role('button', name='החזרה לתיקון', exact=True).click()
    dialog = page.locator('.modal:visible')
    dialog.locator('[name="reason"] textarea').fill('צילום קרוב יותר של החיבור')
    dialog.get_by_role('button', name='שליחת בקשת תיקון', exact=True).click()
    expect(page.locator('.modal:visible')).to_have_count(0)
    portal.goto(f'http://127.0.0.1:8069/my/field-work/{task}')
    expect(portal.get_by_text('צילום קרוב יותר של החיבור', exact=True)).to_be_visible()
    portal.locator('#field_after_image').set_input_files({'name': 'corrected.png', 'mimeType': 'image/png', 'buffer': png((20, 180, 70))})
    portal.locator('[data-report-submit]').click()
    expect(portal.get_by_text('הדיווח והתמונות נשלחו לבדיקת התפעול.', exact=True)).to_be_visible()
    page.goto(url)
    page.get_by_role('button', name='אישור ביצוע', exact=True).click()
    expect(page.locator('.o_field_report_panel [name="field_report_state"]')).to_contain_text('אושר')
    page.locator('.o_field_report_panel').scroll_into_view_if_needed()
    page.screenshot(path=str(OUTPUT / 'workspace-approved-desktop.png'), full_page=True)
    assert model('crm.lead', 'read', [[lead]], fields=['field_dispatch_code'])[0]['field_dispatch_code'] == 'completed'
    portal.goto('http://127.0.0.1:8069/my/field-work?scope=completed')
    expect(portal.get_by_role('link', name='החלפת ברז — בדיקת ממשק', exact=False)).to_be_visible()
    contractor_context.close()
    rates_action = model('ir.model.data', 'search_read', [[['module', '=', 'field_work_photos'], ['name', '=', 'action_field_contractor_rates']]], fields=['res_id'])[0]['res_id']
    page.goto(f'http://127.0.0.1:8069/odoo/action-{rates_action}')
    expect(page.locator('.o_list_view')).to_be_visible()
    for rate in ('field_rate_small', 'field_rate_medium', 'field_rate_large'):
        expect(page.locator(f'th[data-name="{rate}"]')).to_be_visible()
    page.screenshot(path=str(OUTPUT / 'contractor-rates-desktop.png'), full_page=True)
    attention_action = model('ir.model.data', 'search_read', [[['module', '=', 'field_work_photos'], ['name', '=', 'action_field_work_attention']]], fields=['res_id'])[0]['res_id']
    page.goto(f'http://127.0.0.1:8069/odoo/action-{attention_action}')
    expect(page.locator('.o_list_view')).to_be_visible()
    expect(page.locator('.o_data_row').filter(has_text='טיוטה — בדיקת ממשק')).to_be_visible()
    expect(page.locator('.o_data_row').filter(has_text='החלפת ברז — בדיקת ממשק')).to_have_count(0)
    page.screenshot(path=str(OUTPUT / 'attention-queue-desktop.png'), full_page=True)
    assert not errors, errors
    context.close()
    browser.close()
print('PASS: real Chrome rendered new draft, desktop/mobile forms, missing-field dialog Continue action, focused pricing input geometry, amount saving and negative values; no JS errors.')
