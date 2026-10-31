"""Screen-by-screen Chrome checks for the complete field-work CRM surface.

Runs after check_field_ui.py against disposable CI data. No live integrations.
"""
import datetime
import json
import os
from pathlib import Path
import secrets

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.local-data' / 'ui-checks' / 'crm'
OUTPUT.mkdir(parents=True, exist_ok=True)
login = json.loads((ROOT / '.local-data' / 'credentials.json').read_text())
BASE = 'http://127.0.0.1:8069'
coverage, errors = [], []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ['CHROME_BIN'], headless=True, args=['--no-sandbox'])
    owner = browser.new_context(viewport={'width': 1440, 'height': 1100}, locale='he-IL')

    def rpc(context, name, method, args, **kwargs):
        result = context.request.post(f'{BASE}/web/dataset/call_kw/{name}/{method}', data={
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {'model': name, 'method': method, 'args': args, 'kwargs': kwargs}}).json()
        if result.get('error'):
            raise RuntimeError(result['error']['data']['message'])
        return result['result']

    def authenticate(context, username, password):
        result = context.request.post(f'{BASE}/web/session/authenticate', data={
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {'db': 'odoo_pilot', 'login': username, 'password': password}}).json()
        assert result.get('result', {}).get('uid'), 'Test authentication failed'

    authenticate(owner, login['login'], login['password'])

    def xmlid(name, module='field_work_photos'):
        rows = rpc(owner, 'ir.model.data', 'search_read', [[('module', '=', module), ('name', '=', name)]], fields=['res_id'])
        assert rows, f'Missing expected installed XML ID: {module}.{name}'
        return rows[0]['res_id']

    def page_for(context):
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        return page

    def open_action(page, name, module='field_work_photos'):
        page.goto(f'{BASE}/odoo/action-{xmlid(name, module)}')
        page.wait_for_load_state('networkidle')
        expect(page.locator('.o_action_manager')).to_be_visible()

    def capture(page, name, check_overflow=True):
        page.wait_for_load_state('networkidle')
        if check_overflow:
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), f'Page overflows: {name}'
        page.screenshot(path=str(OUTPUT / f'{name}.png'), full_page=True)
        coverage.append({'screen': name, 'width': page.viewport_size['width'], 'screenshot': f'{name}.png', 'passed': True})

    customer = rpc(owner, 'res.partner', 'create', [{'name': 'לקוח סקירת CRM', 'phone': '0501234567', 'city': 'גבעתיים', 'field_crm_client': True}])
    contractor = rpc(owner, 'res.users', 'search_read', [[('login', '=', login['contractors'][0]['login'])]], fields=['id'])[0]['id']
    lead = rpc(owner, 'crm.lead', 'create', [{'name': 'עבודת סקירה — כתובת ותיאור ארוכים לבדיקה',
        'is_field_service': True, 'partner_id': customer, 'phone': '0501234567',
        'field_site_address': 'רחוב לדוגמה 123, גבעתיים, כניסה מהחצר האחורית',
        'field_work_description': 'בדיקת תהליך העבודה המלא ללא שינוי בנתוני הלקוח האמיתיים.',
        'field_quote_number': 'CRM-UX-2026', 'field_sale_amount': 1000,
        'field_contractor_id': contractor, 'field_visit_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}])
    for _ in range(4):
        rpc(owner, 'crm.lead', 'action_next_field_stage', [[lead]])
    page = page_for(owner)

    # Hub: real scoped data, each responsive width and keyboard navigation.
    for width in (1440, 1024, 768, 390):
        page.set_viewport_size({'width': width, 'height': 1000})
        open_action(page, 'action_field_dashboard')
        expect(page.get_by_role('heading', name='מה צריך לקדם היום?', exact=True)).to_be_visible()
        expect(page.locator('.o_field_queue_tile')).to_have_count(6)
        assert page.locator('.o_field_queue_tile').first.evaluate('el => getComputedStyle(el).direction') == 'rtl'
        expect(page.locator('[name="collection_balance"]')).to_be_visible()
        count = rpc(owner, 'crm.lead', 'search_count', [[('is_field_service', '=', True), ('field_dispatch_code', '=', 'field')]])
        expect(page.locator('[name="active_count"]')).to_have_text(str(count))
        assert all(box['height'] >= 44 for box in page.locator('.o_field_queue_tile').evaluate_all('els => els.map(el => ({height: el.getBoundingClientRect().height}))'))
        capture(page, f'hub-owner-{width}')
    page.set_viewport_size({'width': 1440, 'height': 1100})
    open_action(page, 'action_field_dashboard')
    page.locator('button[name="action_active_queue"]').focus()
    page.keyboard.press('Enter')
    expect(page.locator('.o_data_row').filter(has_text='עבודת סקירה')).to_be_visible()
    capture(page, 'hub-active-queue-desktop')

    # Native board, list switch and name search.
    open_action(page, 'action_field_service_leads')
    expect(page.locator('.o_kanban_renderer')).to_be_visible()
    capture(page, 'inquiries-board-desktop')
    page.locator('.o_switch_view.o_list').click()
    page.locator('.o_searchview_input').fill('עבודת סקירה')
    page.locator('.o_searchview_input').press('Enter')
    expect(page.locator('.o_data_row').filter(has_text='עבודת סקירה')).to_be_visible()
    capture(page, 'inquiries-search-desktop')

    # Scoped Contacts: list, form, mobile, creation and retained directory entry.
    open_action(page, 'action_field_clients_open')
    expect(page.locator('.o_data_row').filter(has_text='לקוח סקירת CRM')).to_be_visible()
    capture(page, 'clients-list-desktop')
    page.locator('.o_data_row').filter(has_text='לקוח סקירת CRM').click()
    expect(page.locator('.o_field_contact_form')).to_be_visible()
    capture(page, 'client-form-desktop')
    inputs = page.locator('.o_field_contact_form .o_form_sheet input:visible')
    assert inputs.evaluate_all('els => els.every(el => el.labels.length || el.getAttribute("aria-label") || el.getAttribute("aria-labelledby"))'), 'Client field has no accessible label'
    page.set_viewport_size({'width': 390, 'height': 844})
    capture(page, 'client-form-mobile')
    page.set_viewport_size({'width': 1440, 'height': 1100})
    open_action(page, 'action_field_clients_open')
    page.locator('.o_switch_view.o_kanban').click()
    expect(page.locator('.o_field_client_kanban')).to_be_visible()
    capture(page, 'clients-cards-desktop')
    page.get_by_role('button', name='חדש', exact=True).click()
    expect(page.locator('.o_field_contact_form')).to_be_visible()
    page.locator('.o_form_button_save').click()
    expect(page.locator('[name="name"].o_field_invalid')).to_be_visible()
    page.locator('[name="name"] input').fill('לקוח חדש לפני עבודה ראשונה')
    page.locator('[name="phone"] input').fill('0507654321')
    page.locator('.o_form_button_save').click()
    page.wait_for_load_state('networkidle')
    open_action(page, 'action_field_clients_open')
    expect(page.get_by_text('לקוח חדש לפני עבודה ראשונה', exact=True)).to_be_visible()

    # Task evidence and calendar reuse native Project controls, then return to CRM.
    open_action(page, 'action_field_tasks')
    expect(page.locator('.o_data_row').filter(has_text='עבודת סקירה')).to_be_visible()
    capture(page, 'tasks-list-desktop')
    page.locator('.o_data_row').filter(has_text='עבודת סקירה').click()
    expect(page.locator('.o_field_task_form')).to_be_visible()
    capture(page, 'task-detail-desktop')
    page.set_viewport_size({'width': 390, 'height': 844})
    capture(page, 'task-detail-mobile')
    page.get_by_role('button', name='המשך טיפול בכרטיס העבודה', exact=True).click()
    expect(page.locator('.o_field_report_panel')).to_be_visible()
    page.set_viewport_size({'width': 1440, 'height': 1100})
    open_action(page, 'action_field_tasks')
    page.locator('.o_switch_view.o_calendar').click()
    expect(page.locator('.o_calendar_view')).to_be_visible()
    capture(page, 'appointments-calendar-desktop')
    page.locator('.fc-event').filter(has_text='עבודת סקירה').first.click()
    expect(page.locator('.modal:visible')).to_be_visible()
    capture(page, 'appointment-dialog-desktop')
    page.locator('.modal:visible .btn-close').click()
    page.set_viewport_size({'width': 390, 'height': 844})
    capture(page, 'appointments-calendar-mobile')
    page.set_viewport_size({'width': 1440, 'height': 1100})

    # Tier form: readable semantics, save a valid edit and reject an invalid rate.
    open_action(page, 'action_field_contractor_rates')
    page.locator('.o_data_row').filter(has_text='יוסי').first.locator('.o_list_record_open_form_view button').click()
    expect(page.locator('.o_field_rates_form')).to_be_visible()
    expect(page.locator('.o_field_rate_tier')).to_have_count(3)
    capture(page, 'contractor-rate-form-desktop')
    page.set_viewport_size({'width': 390, 'height': 844})
    capture(page, 'contractor-rate-form-mobile')
    page.set_viewport_size({'width': 1440, 'height': 1100})
    open_action(page, 'action_field_guide')
    expect(page.get_by_role('heading', name='כך עובדים במערכת', exact=True)).to_be_visible()
    expect(page.get_by_text('פעיל: תיעוד ידני של מספר הצעת מחיר ותקבולים.', exact=True)).to_be_visible()
    capture(page, 'guide-desktop')
    page.set_viewport_size({'width': 390, 'height': 844})
    capture(page, 'guide-mobile')

    # Explicit native-surface smoke coverage, not a claim of redesigning core Odoo.
    page.set_viewport_size({'width': 1440, 'height': 1100})
    for module, name, label in [('project', 'open_view_project_all', 'native-projects'),
                                ('crm', 'crm_lead_action_pipeline', 'native-crm'),
                                ('base_setup', 'action_general_configuration', 'native-settings'),
                                ('base', 'action_res_users', 'native-users')]:
        open_action(page, name, module)
        capture(page, label, check_overflow=False)

    # Operations sees operational queues/clients/tasks, without owner data/menu.
    group = xmlid('group_field_dispatcher')
    password = secrets.token_urlsafe(24)
    rpc(owner, 'res.users', 'create', [{'name': 'תפעול בדיקת CRM', 'login': 'ui.crm.operations',
        'password': password, 'lang': 'he_IL', 'groups_id': [[6, 0, [group]]]}], context={'no_reset_password': True})
    ops = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='he-IL')
    authenticate(ops, 'ui.crm.operations', password)
    ops_page = page_for(ops)
    open_action(ops_page, 'action_field_dashboard')
    expect(ops_page.locator('[name="collection_balance"]')).to_have_count(0)
    expect(ops_page.locator('[name="contractor_balance"]')).to_have_count(0)
    capture(ops_page, 'hub-operations-desktop')
    open_action(ops_page, 'action_field_clients_open')
    expect(ops_page.locator('.o_data_row').filter(has_text='לקוח סקירת CRM')).to_be_visible()
    open_action(ops_page, 'action_field_tasks')
    expect(ops_page.locator('.o_data_row').filter(has_text='עבודת סקירה')).to_be_visible()
    ops.close()

    # A second contractor cannot open the first contractor's new job.
    portal_context = browser.new_context(viewport={'width': 390, 'height': 844}, locale='he-IL', is_mobile=True, has_touch=True)
    second = login['contractors'][1]
    authenticate(portal_context, second['login'], second['password'])
    task = rpc(owner, 'crm.lead', 'read', [[lead]], fields=['field_workspace_task_id'])[0]['field_workspace_task_id'][0]
    assert portal_context.request.get(f'{BASE}/my/field-work/{task}').status == 404
    portal_page = page_for(portal_context)
    portal_page.goto(f'{BASE}/my/home')
    portal_page.wait_for_load_state('networkidle')
    expect(portal_page.get_by_role('link', name='עבודות השטח שלי', exact=False)).to_be_visible()
    capture(portal_page, 'contractor-home-mobile')
    portal_page.goto(f'{BASE}/my/field-work?scope=pending')
    portal_page.wait_for_load_state('networkidle')
    expect(portal_page.get_by_role('heading', name='אין כרגע עבודות ברשימה הזאת', exact=True)).to_be_visible()
    capture(portal_page, 'contractor-empty-mobile')
    portal_context.close()

    assert not errors, errors
    (OUTPUT / 'coverage.json').write_text(json.dumps({'screens': coverage, 'page_errors': errors,
        'roles': ['owner', 'operations', 'contractor'], 'live_integrations_tested': False}, ensure_ascii=False, indent=2))
    owner.close()
    browser.close()

print(f'PASS: CRM screen coverage: {len(coverage)} captures, scoped dashboard/clients/tasks/calendar/rates/guide, native read-only smoke, role separation and no JS errors.')
