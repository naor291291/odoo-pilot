"""Actual Odoo/Chrome + wkhtmltopdf checks, using disposable synthetic data."""
import base64
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import secrets
import time
from zoneinfo import ZoneInfo

from PIL import Image
from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.local-data/ui-checks/statement'
OUTPUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:8069'
credentials = json.loads((ROOT / '.local-data/credentials.json').read_text())
errors, coverage = [], []


def settle(page):
    page.wait_for_load_state('domcontentloaded')
    try:
        page.wait_for_load_state('networkidle', timeout=2000)
    except PlaywrightTimeoutError:
        expect(page.locator('.o_action_manager .o_content').first).to_be_visible(timeout=60000)
    expect(page.locator('.o_blockUI')).to_have_count(0, timeout=60000)
    page.evaluate('document.fonts.ready')


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ['CHROME_BIN'], headless=True, args=['--no-sandbox'])
    owner = browser.new_context(viewport={'width': 1440, 'height': 1100}, locale='he-IL')

    def auth(context, username, password):
        result = context.request.post(BASE + '/web/session/authenticate', data={
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {'db': 'odoo_pilot', 'login': username, 'password': password}}).json()
        assert result.get('result', {}).get('uid'), 'Synthetic session authentication failed'

    def rpc(model, method, args, browser_context=owner, raw=False, **kwargs):
        response = browser_context.request.post(f'{BASE}/web/dataset/call_kw/{model}/{method}', data={
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {'model': model, 'method': method, 'args': args, 'kwargs': kwargs}}).json()
        if raw:
            return response
        if response.get('error'):
            raise RuntimeError(response['error']['data']['message'])
        return response['result']

    def xmlid(name):
        return rpc('ir.model.data', 'search_read', [[('module', '=', 'field_work_photos'), ('name', '=', name)]], fields=['res_id'])[0]['res_id']

    for attempt in range(120):
        try:
            if owner.request.get(BASE + '/web/login', timeout=3000).ok:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise RuntimeError('Odoo did not become ready for statement verification')
    auth(owner, credentials['login'], credentials['password'])
    page = owner.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))

    def capture(name):
        settle(page)
        page.wait_for_function('document.documentElement.scrollWidth <= innerWidth + 1')
        page.screenshot(path=str(OUTPUT / (name + '.png')), full_page=True)
        coverage.append({'screen': name, 'width': page.viewport_size['width'], 'passed': True})

    try:
        # Independent contractor avoids pre-existing test jobs and advances.
        token = secrets.token_hex(4)
        contractor_name = 'קבלן בדיקת דוח — שם ארוך לבדיקת תצוגה ' + token
        password = secrets.token_urlsafe(18)
        contractor = rpc('res.users', 'create', [{'name': contractor_name,
            'login': 'statement.browser.' + token, 'password': password, 'lang': 'he_IL',
            'groups_id': [(6, 0, [xmlid('group_field_contractor')])]}], context={'no_reset_password': True})
        customer = rpc('res.partner', 'create', [{'name': 'לקוח מלאכותי לבדיקת דוח', 'phone': '0500000000'}])
        now = datetime.now(ZoneInfo('Asia/Jerusalem'))
        today, month_start = now.date(), now.date().replace(day=1)
        prior = month_start - timedelta(days=1)
        lead = rpc('crm.lead', 'create', [{
            'name': 'החלפת צנרת ובדיקת לחץ מים — רשומת בדיקה מלאכותית עם תיאור ארוך',
            'is_field_service': True, 'partner_id': customer, 'phone': '0500000000',
            'field_site_address': 'רחוב בדיקה 10', 'field_work_description': 'דוגמת התחשבנות בלבד',
            'field_contractor_id': contractor, 'field_visit_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
            'field_quote_number': 'STATEMENT-UI', 'field_sale_amount': 1000,
            'field_customer_due': 1180, 'field_contractor_due': 700}])

        def pay(amount, day, reference, kind='contractor'):
            return rpc('field.work.payment', 'create', [{'lead_id': lead, 'kind': kind,
                'amount': amount, 'payment_date': str(day), 'reference': reference}])

        pay(100, prior, 'ADVANCE-PRIOR')
        pay(250, today, 'CURRENT-250')
        for _ in range(4):
            rpc('crm.lead', 'action_next_field_stage', [[lead]])
        stream = BytesIO()
        Image.new('RGB', (16, 16), '#086b74').save(stream, 'PNG')
        photo = base64.b64encode(stream.getvalue()).decode()
        rpc('crm.lead', 'write', [[lead], {'field_report_before_image': photo,
            'field_report_after_image': photo, 'field_visit_summary': 'הבדיקה הושלמה'}])
        rpc('crm.lead', 'action_submit_field_report', [[lead]])
        rpc('crm.lead', 'action_approve_field_report', [[lead]])
        pay(1180, today, 'CUSTOMER-NOT-PAYOUT', kind='customer')

        # Verify approval control in the real native finance tab, including confirmation.
        page.goto(f'{BASE}/odoo/action-{xmlid("action_field_payouts")}/{lead}')
        settle(page)
        finance_tab = page.get_by_role('tab', name='עלויות וקבלן', exact=True)
        if finance_tab.count():
            finance_tab.click()
        else:
            page.locator('.o_notebook_headers').get_by_text('עלויות', exact=False).click()
        page.get_by_role('button', name='אישור סכום הקבלן לדוח', exact=True).click()
        page.get_by_role('button', name='אישור', exact=True).click()
        settle(page)
        capture('amount-approved-1440')
        rpc('crm.lead', 'action_close_field_work', [[lead]])

        action_id = xmlid('action_contractor_statement')
        page.goto(f'{BASE}/odoo/action-{action_id}')
        settle(page)
        # Required contractor field: the native form must explain what is missing.
        page.get_by_role('button', name='הצגת דוח', exact=True).click()
        expect(page.locator('[name="contractor_id"]')).to_have_class(__import__('re').compile('o_field_invalid'))
        selector = page.locator('[name="contractor_id"] input')
        selector.fill(contractor_name)
        page.get_by_role('option', name=contractor_name, exact=True).click()
        page.get_by_role('button', name='הצגת דוח', exact=True).click()
        settle(page)
        closing = page.locator('[data-statement-closing]')
        expect(closing).to_have_text('350.00 ₪')
        expect(page.locator('.o_statement_result')).to_contain_text('CURRENT-250')
        expect(page.locator('.o_statement_result')).not_to_contain_text('CUSTOMER-NOT-PAYOUT')
        report_rows = rpc('field.contractor.statement', 'search_read', [[('contractor_id', '=', contractor)]], fields=['payload'], order='id desc', limit=1)
        report_id = report_rows[0]['id']
        expected = report_rows[0]['payload']
        assert (expected['opening'], expected['credit'], expected['paid'], expected['closing']) == (-100, 700, 250, 350)
        for width in (1440, 1024, 768, 390):
            page.set_viewport_size({'width': width, 'height': 1000})
            capture(f'statement-{width}')
            assert closing.evaluate('el => getComputedStyle(el).direction') == 'ltr'
            page.locator('.o_statement_table').first.scroll_into_view_if_needed()
            capture(f'movements-{width}')

        # Keyboard focus and both levels of source drill-down.
        page.set_viewport_size({'width': 1440, 'height': 1100})
        source = page.locator('.o_statement_result a.o_statement_source').first
        source.focus()
        expect(source).to_be_focused()
        # Odoo's native readonly HTML field intentionally opens links in a tab.
        report_page = page
        with page.expect_popup() as opened:
            source.press('Enter')
        page = opened.value
        page.on('pageerror', lambda error: errors.append(str(error)))
        settle(page)
        expect(page.locator('.o_form_view')).to_contain_text('תנועה כולל מע״מ')
        expect(page.get_by_text('סוג תנועה', exact=True)).to_be_visible()
        expect(page.get_by_text('חברה', exact=True)).to_be_visible()
        capture('entitlement-source')
        page.set_viewport_size({'width': 390, 'height': 1000})
        capture('entitlement-source-390')
        page.close()
        page = report_page
        with page.expect_popup() as opened:
            page.locator('.o_statement_result a').filter(has_text='החלפת צנרת').first.click()
        page = opened.value
        page.on('pageerror', lambda error: errors.append(str(error)))
        settle(page)
        expect(page.locator('.o_form_view')).to_contain_text('החלפת צנרת')
        capture('work-source')
        page.close()
        page = report_page
        settle(page)
        page.get_by_text('בדיקת הרשומות שמרכיבות את יתרת הפתיחה', exact=True).click()
        page.get_by_role('button', name='תשלומים לפני התקופה', exact=True).click()
        settle(page)
        expect(page.locator('.o_list_view')).to_contain_text('ADVANCE-PRIOR')
        capture('opening-payments')

        # Actual Odoo PDF engine, not browser print-to-PDF.
        page.goto(f'{BASE}/odoo/action-{action_id}/{report_id}')
        settle(page)
        pdf_path = OUTPUT / 'contractor-statement-example.pdf'
        with page.expect_download(timeout=120000) as printed:
            page.get_by_role('button', name='הפקת PDF', exact=True).click()
        printed.value.save_as(str(pdf_path))
        assert pdf_path.read_bytes().startswith(b'%PDF'), 'Odoo did not return a real PDF'
        reader = PdfReader(pdf_path)
        text = '\n'.join(p.extract_text() for p in reader.pages)
        assert '350.00' in text, 'PDF closing differs from screen snapshot'
        assert 'CURRENT-250' in text
        assert 'CUSTOMER-NOT-PAYOUT' not in text
        assert any('\u0590' <= char <= '\u05ff' for char in text), 'PDF must contain actual Hebrew text'

        # Multiple pages with long work names, references and repeated table headings.
        rpc('field.work.payment', 'create', [[{'lead_id': lead, 'kind': 'contractor', 'amount': 1,
            'payment_date': str(today), 'reference': f'MULTIPAGE-{index:02d}-בדיקת אסמכתה ארוכה'} for index in range(24)]])
        rpc('field.contractor.statement', 'action_show_report', [[report_id]])
        pdf_response = owner.request.get(f'{BASE}/report/pdf/field_work_photos.contractor_statement_pdf/{report_id}', timeout=120000)
        multi_path = OUTPUT / 'contractor-statement-multipage.pdf'
        multi_path.write_bytes(pdf_response.body())
        multi = PdfReader(multi_path)
        assert len(multi.pages) >= 3
        multi_text = '\n'.join(p.extract_text() for p in multi.pages)
        assert '326.00' in multi_text and 'MULTIPAGE-23' in multi_text

        # Empty month, range mode and invalid order through the native UI.
        empty = rpc('field.contractor.statement', 'create', [{'contractor_id': contractor,
            'period_mode': 'range', 'date_from': str(prior.replace(day=1) - timedelta(days=62)),
            'date_to': str(prior.replace(day=1) - timedelta(days=32))}])
        rpc('field.contractor.statement', 'action_show_report', [[empty]])
        page.goto(f'{BASE}/odoo/action-{action_id}/{empty}')
        settle(page)
        expect(page.locator('.o_statement_empty')).to_be_visible()
        page.set_viewport_size({'width': 390, 'height': 1000})
        capture('empty-range-390')
        date_from = page.locator('[name="date_from"] input')
        date_to = page.locator('[name="date_to"] input')
        date_from.fill('31/12/2026')
        date_from.press('Tab')
        date_to.fill('01/01/2026')
        date_to.press('Tab')
        page.get_by_role('button', name='הצגת דוח', exact=True).click()
        expect(page.get_by_role('dialog')).to_contain_text('טווח תקין')
        capture('invalid-date-range-390')

        # Contractor URL and direct RPC/PDF access stay denied.
        external = browser.new_context()
        auth(external, 'statement.browser.' + token, password)
        denied = rpc('field.contractor.statement', 'action_show_report', [[report_id]], browser_context=external, raw=True)
        assert denied.get('error')
        denied_pdf = external.request.get(f'{BASE}/report/pdf/field_work_photos.contractor_statement_pdf/{report_id}')
        assert not denied_pdf.body().startswith(b'%PDF')
        external.close()
        assert not errors, errors
        (OUTPUT / 'coverage.json').write_text(json.dumps({'screens': coverage, 'page_errors': errors,
            'example': expected, 'pdf_pages': len(reader.pages), 'multipage_pdf_pages': len(multi.pages)}, ensure_ascii=False, indent=2))
        print(json.dumps({'statement_captures': len(coverage), 'pdf_pages': len(reader.pages),
            'multipage_pdf_pages': len(multi.pages), 'page_errors': errors}, ensure_ascii=False))
    except Exception:
        page.screenshot(path=str(OUTPUT / 'failure.png'), full_page=True)
        print('STATEMENT PAGE ERRORS:', errors)
        raise
    finally:
        browser.close()
