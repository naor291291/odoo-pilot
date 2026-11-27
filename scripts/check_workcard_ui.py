"""Two-screen acceptance journey on disposable CI data; never targets production."""
import base64
import datetime
import json
import os
from io import BytesIO
from pathlib import Path
import secrets
from PIL import Image
from pypdf import PdfWriter
from playwright.sync_api import sync_playwright, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

def settle(page):
    page.wait_for_load_state('domcontentloaded')
    try:
        page.wait_for_load_state('networkidle', timeout=2000)
    except PlaywrightTimeoutError:
        expect(page.locator('.o_action_manager .o_content').first).to_be_visible(timeout=60000)
    expect(page.locator('.o_blockUI')).to_have_count(0, timeout=60000)
    page.evaluate('document.fonts.ready')

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.local-data/ui-checks/workcard'
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:8069'
credentials = json.loads((ROOT / '.local-data/credentials.json').read_text())
checks, errors, network_errors, captures = [], [], [], []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ['CHROME_BIN'], args=['--no-sandbox'])
    context = browser.new_context(viewport={'width': 1440, 'height': 1100}, locale='he-IL')
    auth = context.request.post(BASE + '/web/session/authenticate', data={
        'jsonrpc': '2.0', 'method': 'call', 'id': 1, 'params': {
            'db': 'odoo_pilot', 'login': credentials['login'], 'password': credentials['password']}}).json()
    assert auth.get('result', {}).get('uid')

    def rpc(model, method, args, **kwargs):
        data = context.request.post(BASE + '/web/dataset/call_kw/' + model + '/' + method, data={
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {'model': model, 'method': method, 'args': args, 'kwargs': kwargs}}).json()
        if data.get('error'):
            raise RuntimeError(data['error']['data']['message'])
        return data['result']

    def xmlid(name):
        return rpc('ir.model.data', 'search_read', [[('module', '=', 'field_work_photos'), ('name', '=', name)]], fields=['res_id'])[0]['res_id']

    def read(*names):
        return rpc('crm.lead', 'read', [[lead]], fields=list(names))[0]

    page = context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('response', lambda response: network_errors.append(str(response.status) + ' ' + response.url.split('?')[0]) if response.status >= 400 else None)

    def input_field(name, parent=None):
        return (parent or page).locator('[name="' + name + '"]:visible input').first

    def save():
        page.locator('.o_form_button_save').click()
        expect(page.locator('.o_form_button_save')).to_be_hidden()
        settle(page)

    def capture(name):
        settle(page)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), name
        page.screenshot(path=str(OUT / (name + '.png')), full_page=True)
        captures.append({'screen': name, 'width': page.viewport_size['width'], 'file': name + '.png'})

    def document(kind, number, amount=0, pdf=None):
        table = page.locator('[name="field_document_history_ids"]')
        table.get_by_text('הוסף שורה', exact=True).click()
        dialog = page.locator('.modal:visible')
        dialog.locator('[name="kind"] select').select_option(kind)
        input_field('number', dialog).fill(number)
        input_field('amount', dialog).fill(str(amount))
        if pdf:
            dialog.locator('input[type="file"]').set_input_files({'name': number + '.pdf', 'mimeType': 'application/pdf', 'buffer': pdf})
        dialog.get_by_role('button', name='שמור וסגור', exact=True).click()
        expect(dialog).to_have_count(0)
        save()

    def pay(amount, reference):
        page.get_by_role('button', name='רישום תשלום מהלקוח', exact=True).click()
        dialog = page.locator('.modal:visible')
        input_field('amount', dialog).fill(str(amount))
        input_field('reference', dialog).fill(reference)
        dialog.get_by_role('button', name='אישור רישום תשלום', exact=True).click()
        expect(dialog).to_have_count(0)
        settle(page)

    try:
        token = secrets.token_hex(4)
        customer_name = 'לקוח בדיקת שני מסכים ' + token
        customer = rpc('res.partner', 'create', [{'name': customer_name, 'phone': '0500000000', 'street': 'רחוב בדיקה 10'}])
        contractor = rpc('res.users', 'search_read', [[('login', '=', credentials['contractors'][0]['login'])]], fields=['name'])[0]
        action = xmlid('action_field_service_leads')
        page.goto(f'{BASE}/odoo/action-{action}/new'); settle(page)
        expect(page.get_by_role('button', name='שמירה ופתיחת כרטיס העבודה', exact=True)).to_be_visible()
        expect(page.locator('.o_notebook')).to_have_count(0)
        input_field('partner_id').fill(customer_name)
        page.locator('.o-autocomplete--dropdown-item').filter(has_text=customer_name).first.click()
        input_field('name').fill('תרחיש שחר פרי — נתונים מלאכותיים ' + token)
        input_field('field_site_address').fill('רחוב בדיקה 10')
        page.locator('[name="field_work_description"]:visible textarea').fill('החלפת ברז ובדיקת נזילות')
        capture('setup-1440')
        page.get_by_role('button', name='שמירה ופתיחת כרטיס העבודה', exact=True).click(); settle(page)
        lead = rpc('crm.lead', 'search', [[('partner_id', '=', customer)]])[0]
        expect(page.locator('.o_field_central_workcard')).to_be_visible()
        expect(page.locator('.o_notebook')).to_have_count(0)
        checks.append('two-screen UI creation')
        input_field('field_sale_amount').fill('700')
        input_field('field_material_cost').fill('273')
        input_field('field_contractor_id').fill(contractor['name'])
        page.locator('.o-autocomplete--dropdown-item').filter(has_text=contractor['name']).first.click()
        save()
        assert read('field_commission_amount')['field_commission_amount'] == 277.55
        checks.append('700 - 273 at 65% = 277.55')
        for width in (1440, 768, 390, 375):
            page.set_viewport_size({'width': width, 'height': 1000})
            capture('workcard-' + str(width))
            assert page.locator('.o_field_central_workcard').evaluate("el => getComputedStyle(el).direction") == 'rtl'
        checks.append('RTL and responsive 1440/768/390/375')
        page.set_viewport_size({'width': 1440, 'height': 1100})
        pdf = BytesIO(); writer = PdfWriter(); writer.add_blank_page(width=300, height=400); writer.write(pdf)
        document('proforma', 'PF-' + token, 700, pdf.getvalue())
        assert read('field_customer_balance')['field_customer_balance'] == 700
        document('invoice', 'INV-' + token, 700, pdf.getvalue())
        assert read('field_customer_balance')['field_customer_balance'] == 700
        checks.append('proforma and invoice create one debt and retain PDF filenames')
        doc = rpc('field.work.document', 'search', [[('lead_id', '=', lead), ('kind', '=', 'invoice')]])[0]
        download = context.request.get(f'{BASE}/web/content/field.work.document/{doc}/pdf/INV-{token}.pdf?download=true')
        assert download.ok and download.body() == pdf.getvalue()
        checks.append('authenticated PDF download')
        pay(250, 'PART-' + token)
        assert read('field_customer_balance')['field_customer_balance'] == 450
        checks.append('partial payment updates balance')
        rpc('crm.lead', 'write', [[lead], {'field_visit_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}])
        page.reload(); settle(page)
        page.get_by_role('button', name='אישור שיבוץ', exact=True).click(); settle(page)
        assert read('field_dispatch_code')['field_dispatch_code'] == 'field'
        photo = BytesIO(); Image.new('RGB', (16, 16), '#086b74').save(photo, 'PNG')
        for field in ('field_report_before_image', 'field_report_after_image'):
            page.locator('[name="' + field + '"] input[type="file"]').set_input_files({'name': field + '.png', 'mimeType': 'image/png', 'buffer': photo.getvalue()})
        page.locator('[name="field_visit_summary"] textarea').fill('עבודת בדיקה בלבד — הושלמה')
        save()
        page.get_by_role('button', name='הגשת ביצוע לאישור', exact=True).click(); settle(page)
        page.get_by_role('button', name='אישור ביצוע', exact=True).click(); settle(page)
        pay(450, 'FULL-' + token)
        page.get_by_role('button', name='סגירת עבודה — שולם', exact=True).click()
        expect(page.locator('.modal:visible')).to_contain_text('קבלה')
        page.locator('.modal:visible').get_by_role('button', name='סגור', exact=True).click()
        assert read('field_dispatch_code')['field_dispatch_code'] == 'completed'
        document('receipt', 'RECEIPT-' + token, 700, pdf.getvalue())
        page.get_by_role('button', name='סגירת עבודה — שולם', exact=True).click(); settle(page)
        assert read('field_dispatch_code')['field_dispatch_code'] == 'paid'
        assert len(rpc('field.work.document', 'search', [[('lead_id', '=', lead)]])) == 3
        checks.append('approved completion + full payment + receipt required for closure; history retained')
        page.set_viewport_size({'width': 390, 'height': 1000}); capture('paid-390')
        page.goto(f'{BASE}/odoo/action-{xmlid("action_field_collections_paid")}'); settle(page)
        expect(page.get_by_text('תרחיש שחר פרי — נתונים מלאכותיים ' + token, exact=True)).to_be_visible()
        checks.append('paid collections filter')
        assert not errors, errors
        assert not network_errors, network_errors
    except Exception:
        page.screenshot(path=str(OUT / 'failure.png'), full_page=True)
        raise
    finally:
        (OUT / 'results.json').write_text(json.dumps({'checks': checks, 'captures': captures, 'javascript_errors': errors, 'http_errors': network_errors}, ensure_ascii=False, indent=2))
        print('WORKCARD BROWSER:', len(checks), 'checks completed;', len(errors), 'JS errors;', len(network_errors), 'HTTP errors')
        browser.close()
