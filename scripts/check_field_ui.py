"""Run the real Odoo form in desktop/mobile Chrome against disposable CI data."""
import json
from contextlib import contextmanager
import os
import re
import secrets
from pathlib import Path
import time

from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.local-data' / 'ui-checks'
OUTPUT.mkdir(parents=True, exist_ok=True)
login = json.loads((ROOT / '.local-data' / 'credentials.json').read_text())

def settle(page):
    """Attempt network idle; Odoo's persistent bus can keep it unavailable."""
    page.wait_for_load_state('domcontentloaded')
    try:
        page.wait_for_load_state('networkidle', timeout=2000)
    except PlaywrightTimeoutError:
        # Wait for the real UI, not an arbitrary sleep or an endless bus request.
        if '/odoo' in page.url:
            expect(page.locator('.o_action_manager .o_content').first).to_be_visible(timeout=60000)
        else:
            expect(page.locator('.o_field_portal')).to_be_visible(timeout=60000)
    expect(page.locator('.o_blockUI')).to_have_count(0, timeout=60000)
    page.evaluate('document.fonts.ready')
    page.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')

@contextmanager
def capture_on_failure():
    try:
        yield
    except Exception:
        active_browser = globals().get('browser')
        if active_browser:
            for context_index, context in enumerate(active_browser.contexts):
                for page_index, failed_page in enumerate(context.pages):
                    try:
                        failed_page.screenshot(path=str(OUTPUT / f'failure-{context_index}-{page_index}.png'), full_page=True)
                    except Exception:
                        pass
        raise

with sync_playwright() as playwright, capture_on_failure():
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
    def select_tab(title, target_page=page):
        tab = target_page.locator('.o_field_work_tabs').get_by_role('tab', name=title, exact=True)
        expect(tab).to_be_visible()
        tab.click()
        expect(tab).to_have_class(re.compile(r'\bactive\b'))

    page.goto(f'http://127.0.0.1:8069/odoo/action-{action}/new')
    settle(page)
    expect(page.locator('.o_field_service_hero')).to_be_visible(timeout=60000)
    page.locator('.o_field_customer_card [name="name"] input').fill('טיוטה — בדיקת ממשק')
    page.locator('.o_form_button_save').click()
    expect(page.locator('.o_form_status_indicator_new_record')).to_have_count(0)
    drafts = model('crm.lead', 'search_read', [[['name', '=', 'טיוטה — בדיקת ממשק']]], fields=['field_dispatch_code'])
    assert drafts and drafts[0]['field_dispatch_code'] == 'new', 'New form defaults or partial draft save failed'
    select_tab('גבייה')
    expect(page.locator('.o_field_collection_panel')).to_contain_text('בחרו תחילה לקוח')
    expect(page.locator('.o_field_collection_panel .o_list_table')).to_have_count(0)
    page.screenshot(path=str(OUTPUT / 'collections-empty-desktop.png'), full_page=True)
    url = f'http://127.0.0.1:8069/odoo/action-{action}/{lead}'
    page.goto(url)
    settle(page)
    expect(page.locator('.o_field_service_hero')).to_be_visible(timeout=60000)
    expect(page.locator('.o_field_service_notice_warning')).to_contain_text('טלפון לתיאום')
    page.screenshot(path=str(OUTPUT / 'desktop-missing-details.png'), full_page=True)
    page.get_by_role('button', name='המשך להצעת מחיר', exact=True).click()
    expect(page.locator('.modal:visible')).to_be_visible()
    expect(page.locator('.modal:visible')).to_contain_text('טלפון לתיאום')
    assert model('crm.lead', 'read', [[lead]], fields=['field_dispatch_code'])[0]['field_dispatch_code'] == 'new'
    model('crm.lead', 'write', [[lead], {'phone': '0500000000'}])
    page.goto(url)
    settle(page)
    expect(page.locator('.o_field_service_hero')).to_be_visible()
    expect(page.locator('.o_field_service_notice_ready')).to_be_visible()
    page.get_by_role('button', name='המשך להצעת מחיר', exact=True).click()
    expect(page.get_by_role('button', name='ההצעה נשלחה — המשך', exact=True)).to_be_visible()
    assert model('crm.lead', 'read', [[lead]], fields=['field_dispatch_code'])[0]['field_dispatch_code'] == 'quote'
    expect(page.locator('.o_field_next_step')).to_contain_text('הצעה')
    expect(page.locator('.o_field_payout_panel')).to_have_count(0)
    expect(page.locator('.o_field_pricing_card')).to_have_count(0)
    page.evaluate('document.fonts.ready')
    assert page.evaluate('document.fonts.check(\'16px "Field Heebo"\')'), 'Bundled Hebrew font failed to load'
    # RTL text follows its container; it must not be mirrored twice by asset compilation.
    label_alignment = page.locator('.o_field_customer_card label').first.evaluate("el => ({align: getComputedStyle(el).textAlign, direction: getComputedStyle(el).direction})")
    assert label_alignment['direction'] == 'rtl' and label_alignment['align'] in ('start', 'right'), label_alignment
    page.screenshot(path=str(OUTPUT / 'desktop-quote.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    expect(page.locator('.o_field_service_hero')).to_be_visible()
    title = page.locator('.o_field_title_text')
    expect(title).to_contain_text('החלפת ברז — בדיקת ממשק')
    assert title.evaluate('(el) => el.scrollWidth <= el.clientWidth + 1'), 'Mobile work title clips'
    page.screenshot(path=str(OUTPUT / 'mobile-quote.png'), full_page=True)
    more = page.locator('.o_field_more_actions')
    more.locator('summary').focus()
    page.keyboard.press('Enter')
    expect(more.locator('button[name="action_save_field_draft"]')).to_be_visible()
    more.locator('summary').press('Enter')
    expect(more.locator('button[name="action_save_field_draft"]')).not_to_be_visible()
    mobile_next = page.get_by_role('button', name='ההצעה נשלחה — המשך', exact=True)
    expect(mobile_next).to_be_in_viewport()
    page.locator('.o_field_quote_card').scroll_into_view_if_needed()
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
    settle(page)
    select_tab('עלויות וקבלן')
    pricing = page.locator('.o_field_pricing_card')
    material = pricing.locator('[name="field_material_cost"] input')
    for width in (1440, 1024, 768, 390):
        page.set_viewport_size({'width': width, 'height': 1000})
        material.scroll_into_view_if_needed()
        material.click()
        expect(material).to_be_focused()
        geometry = material.evaluate("""input => {
            const widget = input.closest('.o_field_monetary');
            const card = input.closest('.o_field_pricing_card').getBoundingClientRect();
            const label = input.closest('.o_field_control').querySelector('label').getBoundingClientRect();
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
        try:
            page.wait_for_function('document.documentElement.scrollWidth <= innerWidth + 1', timeout=5000)
        except Exception:
            page.screenshot(path=str(OUTPUT / f'overflow-pricing-{width}.png'), full_page=True)
            print('OVERFLOW DETAILS', width, page.evaluate("[...document.querySelectorAll('body *')].filter(el => {const r=el.getBoundingClientRect();return r.width > 0 && (r.left < -1 || r.right > innerWidth+1)}).slice(0,20).map(el => ({tag:el.tagName,cls:el.className,x:el.getBoundingClientRect().x,width:el.getBoundingClientRect().width}))"), flush=True)
            raise

        metric_label = page.locator('.o_field_finance_metrics label').first
        assert metric_label.evaluate("el => getComputedStyle(el).opacity") == '1', 'Computed amount labels are faded'
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
    settle(page)
    page.get_by_role('button', name='ההצעה נשלחה — המשך', exact=True).click()
    page.get_by_role('button', name='הלקוח אישר — לתיאום', exact=True).click()
    page.get_by_role('button', name='אישור השיבוץ', exact=True).click()
    expect(page.locator('.o_field_report_panel')).to_be_visible()
    task = model('crm.lead', 'read', [[lead]], fields=['field_workspace_task_id'])[0]['field_workspace_task_id'][0]
    login_contractor = model('project.task', 'read', [[task]], fields=['field_contractor_id'])[0]['field_contractor_id'][0]
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
    settle(portal)
    expect(portal.get_by_role('heading', name='עבודות השטח שלי', exact=True)).to_be_visible()
    portal.get_by_role('link', name='החלפת ברז — בדיקת ממשק', exact=False).click()
    submit_report = portal.locator('[data-report-submit]')
    expect(submit_report).to_be_disabled()
    portal.locator('[data-wizard-next]').click()
    expect(portal.locator('[data-report-errors]')).to_contain_text('מה בוצע בפועל')
    expect(portal.locator('#field_visit_summary')).to_have_attribute('aria-invalid', 'true')
    portal.screenshot(path=str(OUTPUT / 'portal-step-error-mobile.png'), full_page=True)
    portal.locator('#field_visit_summary').fill('הוחלף הברז ונבדקו כל החיבורים')
    portal.locator('[data-wizard-next]').click()
    expect(portal.locator('[data-wizard-panel="2"]')).to_be_visible()
    portal.locator('[data-wizard-back]').click()
    expect(portal.locator('#field_visit_summary')).to_have_value('הוחלף הברז ונבדקו כל החיבורים')
    portal.locator('[data-wizard-next]').click()
    portal.locator('[data-wizard-next]').click()
    expect(portal.locator('[data-report-errors]')).to_contain_text('לפחות תמונה אחת לפני ביצוע')
    portal.locator('[data-report-errors] a').first.click()
    expect(portal.locator('[data-kind="before"] [data-select-photo]')).to_be_focused()
    portal.locator('#field_before_image').set_input_files({'name': 'invalid.txt', 'mimeType': 'text/plain', 'buffer': b'not an image'})
    expect(portal.locator('#photo-error-before')).to_contain_text('JPG')
    with portal.expect_file_chooser() as chooser:
        portal.get_by_role('button', name='הוספת תמונות לפני ביצוע', exact=True).click()
    chooser.value.set_files([{'name': f'before-{n}.png', 'mimeType': 'image/png', 'buffer': png((200, 50, 20))} for n in range(2)])
    expect(portal.locator('[data-new-photos]').first).to_contain_text('עדיין לא נשמרה')
    expect(submit_report).to_be_disabled()
    portal.locator('#field_after_image').set_input_files([{'name': f'after-{n}.png', 'mimeType': 'image/png', 'buffer': png((30, 100, 220))} for n in range(2)])
    expect(submit_report).to_be_enabled()
    expect(portal.locator('.o_field_gallery_image')).to_have_count(4)
    portal.locator('[data-new-photos] .o_field_photo_zoom').first.click()
    expect(portal.locator('[data-photo-dialog]')).to_be_visible()
    portal.keyboard.press('Escape')
    expect(portal.locator('[data-photo-dialog]')).not_to_be_visible()
    expect(portal.locator('[data-new-photos] .o_field_photo_zoom').first).to_be_focused()
    portal.locator('[data-new-photos] .o_field_photo_zoom').first.click()
    portal.get_by_role('button', name='סגירת התמונה', exact=True).click()
    expect(portal.locator('[data-photo-dialog]')).not_to_be_visible()
    # Reject an over-limit batch without losing the already selected files.
    portal.locator('#field_before_image').set_input_files([{'name': f'excess-{n}.png', 'mimeType': 'image/png', 'buffer': png((50, 60, 70))} for n in range(4)])
    expect(portal.locator('#photo-error-before')).to_contain_text('עד 5')
    expect(portal.locator('.o_field_gallery_image')).to_have_count(4)
    portal.locator('[data-report-save]').click()
    expect(portal.get_by_text('הדיווח והתמונות נשמרו. אפשר לחזור לעבודה ולהגיש בהמשך.', exact=True)).to_be_visible()
    expect(portal.locator('[data-photo-key]')).to_have_count(4)
    portal.locator('[data-wizard-next]').click()
    portal.locator('[data-kind="before"] [name="remove_photo"]').first.check()
    portal.locator('#field_before_image').set_input_files([{'name': f'replacement-{n}.png', 'mimeType': 'image/png', 'buffer': png((90, 80, 30))} for n in range(3)])
    expect(portal.locator('[data-report-summary]')).to_contain_text('4 תמונות לפני · 2 תמונות אחרי')
    assert portal.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Portal overflows mobile viewport'
    portal.screenshot(path=str(OUTPUT / 'portal-mobile-selected.png'), full_page=True)
    portal.locator('[data-wizard-next]').click()
    expect(portal.locator('[data-review-description]')).to_contain_text('הוחלף הברז')
    portal.screenshot(path=str(OUTPUT / 'portal-review-mobile.png'), full_page=True)
    submit_report.click()
    expect(portal.get_by_text('הדיווח והתמונות נשלחו לבדיקת התפעול.', exact=True)).to_be_visible()
    expect(portal.locator('input[type="file"]')).to_have_count(0)
    gallery_data = model('project.task', 'read', [[task]], fields=['field_extra_photo_ids', 'field_visit_summary'])[0]
    assert len(gallery_data['field_extra_photo_ids']) == 4, gallery_data
    page.goto(url)
    settle(page)
    select_tab('ביצוע')
    expect(page.locator('.o_field_report_panel [name="field_visit_summary"]')).to_contain_text('הוחלף הברז')
    page.get_by_role('button', name='החזרה לתיקון', exact=True).click()
    dialog = page.locator('.modal:visible')
    dialog.locator('[name="reason"] textarea').fill('צילום קרוב יותר של החיבור')
    dialog.get_by_role('button', name='שליחת בקשת תיקון', exact=True).click()
    expect(page.locator('.modal:visible')).to_have_count(0)
    portal.goto(f'http://127.0.0.1:8069/my/field-work/{task}')
    settle(portal)
    expect(portal.get_by_text('צילום קרוב יותר של החיבור', exact=True)).to_be_visible()
    portal.locator('[data-wizard-next]').click()
    portal.locator('#field_after_image').set_input_files({'name': 'corrected.png', 'mimeType': 'image/png', 'buffer': png((20, 180, 70))})
    portal.locator('[data-wizard-next]').click()
    portal.locator('[data-report-submit]').click()
    expect(portal.get_by_text('הדיווח והתמונות נשלחו לבדיקת התפעול.', exact=True)).to_be_visible()
    page.goto(url)
    settle(page)
    page.get_by_role('button', name='אישור ביצוע', exact=True).click()
    expect(page.locator('.o_field_collection_panel')).to_be_visible()
    select_tab('ביצוע')
    expect(page.locator('.o_field_report_panel [name="field_report_state"]')).to_contain_text('אושר')
    extra_images = page.locator('.o_field_extra_gallery .o_field_image img')
    expect(extra_images).to_have_count(5)
    for image in extra_images.all():
        image.scroll_into_view_if_needed()
        expect(image).to_have_js_property('complete', True)
        assert image.evaluate('(el) => el.naturalWidth > 0 && !el.src.includes("placeholder")'), 'A manager gallery photo did not load'
    page.locator('.o_field_report_panel').scroll_into_view_if_needed()
    page.screenshot(path=str(OUTPUT / 'workspace-approved-desktop.png'), full_page=True)
    assert model('crm.lead', 'read', [[lead]], fields=['field_dispatch_code'])[0]['field_dispatch_code'] == 'completed'
    portal.goto('http://127.0.0.1:8069/my/field-work?scope=completed')
    settle(portal)
    expect(portal.get_by_role('link', name='החלפת ברז — בדיקת ממשק', exact=False)).to_be_visible()
    # An incomplete visit has no photo requirement and cannot be approved as done.
    followup_lead = model('crm.lead', 'create', [{
        'name': 'ביקור המשך — בדיקת ממשק', 'is_field_service': True, 'partner_id': customer,
        'phone': '0500000000', 'field_site_address': 'רחוב הביקור 5',
        'field_work_description': 'בדיקת ביקור שלא הושלם', 'field_quote_number': 'UI-FOLLOWUP',
        'field_sale_amount': 1000,
        'field_contractor_id': login_contractor, 'field_visit_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
    }])
    for _ in range(4):
        model('crm.lead', 'action_next_field_stage', [[followup_lead]])
    followup_task = model('crm.lead', 'read', [[followup_lead]], fields=['field_workspace_task_id'])[0]['field_workspace_task_id'][0]
    portal.goto(f'http://127.0.0.1:8069/my/field-work/{followup_task}')
    settle(portal)
    portal.locator('#field_visit_result').select_option('not_done')
    expect(portal.locator('[data-report-submit]')).to_be_disabled()
    portal.locator('#field_visit_reason').fill('הלקוח לא נמצא בבית. נדרש תיאום ביקור נוסף.')
    expect(portal.locator('[data-report-submit]')).to_be_enabled()
    portal.screenshot(path=str(OUTPUT / 'portal-mobile-incomplete.png'), full_page=True)
    portal.locator('[data-wizard-next]').click()
    portal.locator('[data-wizard-next]').click()
    portal.locator('[data-report-submit]').click()
    expect(portal.get_by_text('הדיווח והתמונות נשלחו לבדיקת התפעול.', exact=True)).to_be_visible()
    page.goto(f'http://127.0.0.1:8069/odoo/action-{action}/{followup_lead}')
    settle(page)
    select_tab('ביצוע')
    expect(page.get_by_role('button', name='אישור ביצוע', exact=True)).to_have_count(0)
    expect(page.locator('.o_field_report_panel [name="field_visit_reason"]')).to_contain_text('הלקוח לא נמצא')
    page.locator('.o_field_report_panel').scroll_into_view_if_needed()
    page.screenshot(path=str(OUTPUT / 'workspace-incomplete-desktop.png'), full_page=True)
    page.get_by_role('button', name='החזרה להמשך טיפול', exact=True).click()
    dialog = page.locator('.modal:visible')
    dialog.locator('[name="reason"] textarea').fill('תאם ביקור נוסף עם הלקוח')
    dialog.get_by_role('button', name='שליחת בקשת תיקון', exact=True).click()
    expect(page.locator('.modal:visible')).to_have_count(0)
    assert model('crm.lead', 'read', [[followup_lead]], fields=['field_dispatch_code'])[0]['field_dispatch_code'] == 'field'
    assert model('project.task', 'read', [[followup_task]], fields=['field_review_state'])[0]['field_review_state'] == 'changes_requested'
    contractor_context.close()
    rates_action = model('ir.model.data', 'search_read', [[['module', '=', 'field_work_photos'], ['name', '=', 'action_field_contractor_rates']]], fields=['res_id'])[0]['res_id']
    page.goto(f'http://127.0.0.1:8069/odoo/action-{rates_action}')
    settle(page)
    expect(page.locator('.o_list_view')).to_be_visible()
    for rate in ('field_rate_small', 'field_rate_medium', 'field_rate_large'):
        expect(page.locator(f'th[data-name="{rate}"]')).to_be_visible()
        title = page.locator(f'th[data-name="{rate}"] .text-truncate')
        assert title.evaluate('(el) => el.scrollWidth <= el.clientWidth'), f'{rate} heading is truncated'
    page.screenshot(path=str(OUTPUT / 'contractor-rates-desktop.png'), full_page=True)
    # Customer installments, explicit closure, owner payout after closure and
    # cancellation all run through the real dialogs, including a narrow screen.
    model('crm.lead', 'write', [[lead], {'field_customer_due': 1180, 'field_contractor_due': 700}])
    page.goto(url)
    settle(page)
    select_tab('גבייה')
    collection = page.locator('.o_field_collection_panel')
    collection.scroll_into_view_if_needed()
    expect(collection.locator('[name="field_collection_status"]')).to_contain_text('טרם שולם')
    page.get_by_role('button', name='רישום תשלום מהלקוח', exact=True).click()
    dialog = page.locator('.modal:visible')
    dialog.locator('[name="amount"] input').fill('400')
    dialog.locator('[name="reference"] input').fill('UI-CUSTOMER-1')
    dialog.get_by_role('button', name='אישור רישום תשלום', exact=True).click()
    expect(page.locator('.modal:visible')).to_have_count(0)
    expect(collection.locator('[name="field_collection_status"]')).to_contain_text('שולם חלקית')
    assert model('crm.lead', 'read', [[lead]], fields=['field_customer_balance'])[0]['field_customer_balance'] == 780
    collection.scroll_into_view_if_needed()
    page.screenshot(path=str(OUTPUT / 'collections-partial-desktop.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto(url)
    settle(page)
    select_tab('גבייה')
    expect(collection).to_be_visible()
    collection.scroll_into_view_if_needed()
    page.screenshot(path=str(OUTPUT / 'collections-partial-mobile.png'), full_page=True)
    expect(collection.locator('.o_field_payment_meta')).to_have_count(1)
    expect(collection.locator('[name="field_customer_balance"]')).to_contain_text('780')
    for field_name in ('field_customer_due', 'field_customer_paid', 'field_customer_balance'):
        bounds = collection.locator(f'[name="{field_name}"]').bounding_box()
        assert bounds and bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= 391, (field_name, bounds)
    collection.scroll_into_view_if_needed()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Collections overflow mobile viewport'
    page.screenshot(path=str(OUTPUT / 'collections-partial-mobile.png'), full_page=True)
    page.get_by_role('button', name='רישום תשלום מהלקוח', exact=True).click()
    dialog = page.locator('.modal:visible')
    dialog.locator('[name="amount"] input').fill('780')
    dialog.locator('[name="reference"] input').fill('UI-CUSTOMER-2')
    page.screenshot(path=str(OUTPUT / 'collections-dialog-mobile.png'), full_page=True)
    dialog.get_by_role('button', name='אישור רישום תשלום', exact=True).click()
    expect(page.locator('.modal:visible')).to_have_count(0)
    page.get_by_role('button', name='סגירת עבודה — טופל ושולם', exact=True).click()
    page.locator('.modal:visible .btn-primary').click()
    expect(collection.locator('[name="field_closed_at"]')).to_be_visible()
    assert model('crm.lead', 'read', [[lead]], fields=['field_dispatch_code'])[0]['field_dispatch_code'] == 'paid'
    page.set_viewport_size({'width': 1440, 'height': 1100})
    page.goto(url)
    settle(page)
    select_tab('עלויות וקבלן')
    page.get_by_role('button', name='רישום תשלום לקבלן', exact=True).click()
    dialog = page.locator('.modal:visible')
    dialog.locator('[name="amount"] input').fill('300')
    dialog.locator('[name="reference"] input').fill('UI-PAYOUT-1')
    dialog.get_by_role('button', name='אישור רישום תשלום', exact=True).click()
    expect(page.locator('.modal:visible')).to_have_count(0)
    expect(page.locator('.o_field_payout_panel [name="field_payout_status"]')).to_contain_text('שולם חלקית')
    assert model('crm.lead', 'read', [[lead]], fields=['field_contractor_balance'])[0]['field_contractor_balance'] == 400
    page.screenshot(path=str(OUTPUT / 'payout-detail-desktop.png'), full_page=True)
    select_tab('גבייה')
    collection.scroll_into_view_if_needed()
    page.screenshot(path=str(OUTPUT / 'collections-closed-desktop.png'), full_page=True)
    row = collection.locator('.o_data_row').filter(has_text='UI-CUSTOMER-1')
    row.get_by_role('button', name='ביטול רישום', exact=True).click()
    dialog = page.locator('.modal:visible')
    dialog.locator('[name="reason"] textarea').fill('בדיקת ביטול רישום כפול')
    dialog.get_by_role('button', name='ביטול הרישום ושמירת הסיבה', exact=True).click()
    expect(page.locator('.modal:visible')).to_have_count(0)
    expect(collection.locator('.o_data_row').filter(has_text='UI-CUSTOMER-1')).to_contain_text('בוטל')
    reopened = model('crm.lead', 'read', [[lead]], fields=['field_dispatch_code', 'field_customer_balance', 'field_contractor_paid'])[0]
    assert reopened['field_dispatch_code'] == 'completed' and reopened['field_customer_balance'] == 400 and reopened['field_contractor_paid'] == 300, reopened
    collections_action = model('ir.model.data', 'search_read', [[['module', '=', 'field_work_photos'], ['name', '=', 'action_field_collections']]], fields=['res_id'])[0]['res_id']
    page.goto(f'http://127.0.0.1:8069/odoo/action-{collections_action}')
    settle(page)
    expect(page.locator('.o_data_row').filter(has_text='החלפת ברז — בדיקת ממשק')).to_be_visible()
    page.screenshot(path=str(OUTPUT / 'collections-queue-desktop.png'), full_page=True)
    page.locator('.o_data_row').filter(has_text='החלפת ברז — בדיקת ממשק').click()
    expect(collection).to_be_visible()
    expect(page.locator('.o_field_work_tabs').get_by_role('tab', name='גבייה', exact=True)).to_have_class(re.compile(r'\bactive\b'))
    payouts_action = model('ir.model.data', 'search_read', [[['module', '=', 'field_work_photos'], ['name', '=', 'action_field_payouts']]], fields=['res_id'])[0]['res_id']
    page.goto(f'http://127.0.0.1:8069/odoo/action-{payouts_action}')
    settle(page)
    expect(page.locator('.o_list_view')).to_be_visible()
    expect(page.locator('th[data-name="field_contractor_balance"]')).to_be_visible()
    page.screenshot(path=str(OUTPUT / 'payouts-queue-desktop.png'), full_page=True)
    attention_action = model('ir.model.data', 'search_read', [[['module', '=', 'field_work_photos'], ['name', '=', 'action_field_work_attention']]], fields=['res_id'])[0]['res_id']
    page.goto(f'http://127.0.0.1:8069/odoo/action-{attention_action}')
    settle(page)
    expect(page.locator('.o_list_view')).to_be_visible()
    expect(page.locator('.o_data_row').filter(has_text='טיוטה — בדיקת ממשק')).to_be_visible()
    expect(page.locator('.o_data_row').filter(has_text='החלפת ברז — בדיקת ממשק')).to_have_count(0)
    page.screenshot(path=str(OUTPUT / 'attention-queue-desktop.png'), full_page=True)
    page.goto(url)
    settle(page)
    tab = page.locator('.o_field_work_tabs').get_by_role('tab', name='גבייה', exact=True)
    tab.focus()
    page.keyboard.press('Enter')
    expect(collection).to_be_visible()
    group = model('ir.model.data', 'search_read', [[['module', '=', 'field_work_photos'], ['name', '=', 'group_field_dispatcher']]], fields=['res_id'])[0]['res_id']
    ops_password = secrets.token_urlsafe(24)
    model('res.users', 'create', [{'name': 'תפעול — בדיקת ממשק', 'login': 'ui.operations', 'password': ops_password,
        'lang': 'he_IL', 'groups_id': [[6, 0, [group]]]}], context={'no_reset_password': True})
    ops_context = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='he-IL')
    result = ops_context.request.post('http://127.0.0.1:8069/web/session/authenticate', data={
        'jsonrpc': '2.0', 'method': 'call', 'id': 1,
        'params': {'db': 'odoo_pilot', 'login': 'ui.operations', 'password': ops_password}}).json()
    assert result.get('result', {}).get('uid')
    ops_page = ops_context.new_page()
    ops_page.on('pageerror', record_page_error)
    ops_page.goto(url)
    settle(ops_page)
    expect(ops_page.locator('.o_field_work_tabs').get_by_role('tab', name='עלויות וקבלן', exact=True)).to_have_count(0)
    select_tab('גבייה', ops_page)
    expect(ops_page.locator('.o_field_collection_panel')).to_be_visible()
    expect(ops_page.locator('.o_field_payout_panel')).to_have_count(0)
    settle(ops_page)
    ops_page.screenshot(path=str(OUTPUT / 'operations-collection-desktop.png'), full_page=True)
    ops_context.close()
    assert not errors, errors
    context.close()
    browser.close()
print('PASS: real Chrome rendered new draft, desktop/mobile forms, missing-field dialog Continue action, focused pricing input geometry, amount saving and negative values; partial receipts, paid closure, contractor payout, cancellation and collection queues; no JS errors.')
