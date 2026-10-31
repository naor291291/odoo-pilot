"""Real Chromium regression journeys on the disposable CI database only.

Fixtures use owner RPC; login, edits, file selection, draft/save, review, reload,
and navigation use the rendered UI. --observe records baseline defects without
turning the audit into a failing deployment. Normal CI requires all fixes.
Never targets a forwarded Codespaces address or a live business database.
"""
import argparse
import datetime
import io
import json
import os
from pathlib import Path
import secrets
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--observe', action='store_true', help='Capture defects on unchanged product code')
options = parser.parse_args()

from PIL import Image
from playwright.sync_api import sync_playwright, expect, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.local-data/ui-checks/browser-journeys'
OUTPUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:8069'
login = json.loads((ROOT / '.local-data/credentials.json').read_text())
checks, defects, captures, errors, console_errors, network_errors = [], [], [], [], [], []
focus_path = []
completed = False
failure = None


def settle(page):
    page.bring_to_front()
    page.wait_for_load_state('domcontentloaded')
    try:
        page.wait_for_load_state('networkidle', timeout=2000)
    except PlaywrightTimeoutError:
        expect(page.locator('.o_action_manager .o_content, .o_field_portal').first).to_be_visible(timeout=60000)
    expect(page.locator('.o_blockUI')).to_have_count(0, timeout=60000)
    page.evaluate('document.fonts.ready')


def check(code, description, passed, evidence=None):
    entry = {'id': code, 'description': description, 'passed': bool(passed), 'evidence': evidence}
    checks.append(entry)
    if not passed:
        defects.append(entry)


def capture(page, name):
    settle(page)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), name
    page.screenshot(path=str(OUTPUT / (name + '.png')), full_page=True)
    captures.append({'screen': name, 'width': page.viewport_size['width'], 'file': name + '.png'})


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ['CHROME_BIN'], headless=True, args=['--no-sandbox'])
    owner = browser.new_context(locale='he-IL')

    def rpc(model, method, args, **kwargs):
        result = owner.request.post(BASE + '/web/dataset/call_kw/' + model + '/' + method, data={
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {'model': model, 'method': method, 'args': args, 'kwargs': kwargs}}).json()
        if result.get('error'):
            raise RuntimeError(result['error']['data']['message'])
        return result['result']

    def xmlid(name):
        return rpc('ir.model.data', 'search_read', [[('module', '=', 'field_work_photos'), ('name', '=', name)]], fields=['res_id'])[0]['res_id']

    response = owner.request.post(BASE + '/web/session/authenticate', data={
        'jsonrpc': '2.0', 'method': 'call', 'id': 1,
        'params': {'db': 'odoo_pilot', 'login': login['login'], 'password': login['password']}}).json()
    assert response.get('result', {}).get('uid')
    token, password = secrets.token_hex(5), secrets.token_urlsafe(24)
    username = 'journey.contractor.' + token
    contractor = rpc('res.users', 'create', [{'name': 'קבלן בדיקת מסע', 'login': username, 'password': password,
        'lang': 'he_IL', 'tz': 'Asia/Jerusalem', 'groups_id': [[6, 0, [xmlid('group_field_contractor')]]]}],
        context={'no_reset_password': True})
    context = browser.new_context(viewport={'width': 390, 'height': 844}, locale='he-IL', is_mobile=True, has_touch=True)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
    # Record only same-origin failures; no provider calls or sensitive payloads.
    page.on('response', lambda response: network_errors.append({'path': response.url.split(BASE, 1)[-1].split('?')[0], 'status': response.status})
            if response.url.startswith(BASE) and response.status >= 400 else None)
    try:
        # Ordinary rendered login, not a pre-authenticated browser fixture.
        page.goto(BASE + '/web/login')
        page.locator('#login').fill(username)
        page.locator('#password').fill(password)
        page.locator('form.oe_login_form button[type="submit"]').click()
        page.wait_for_url(lambda url: '/web/login' not in url)
        for scope, phrase in [('active', 'לביצוע'), ('pending', 'לבדיקה'), ('completed', 'הסתיימו')]:
            page.goto(BASE + '/my/field-work?scope=' + scope)
            settle(page)
            heading = page.locator('.o_field_portal h2').inner_text()
            check('EMPTY-' + scope, 'Empty state names the selected scope', phrase in heading, heading)
            capture(page, 'empty-' + scope + '-390')

        customer = rpc('res.partner', 'create', [{'name': 'לקוח מסע מלאכותי', 'phone': '0500000000'}])
        lead = rpc('crm.lead', 'create', [{'name': 'עבודה לבדיקת שמירה ותמונות', 'is_field_service': True,
            'partner_id': customer, 'phone': '0500000000', 'field_site_address': 'רחוב בדיקה 10, גבעתיים',
            'field_work_description': 'החלפת ברז ובדיקת חיבורים.', 'field_quote_number': 'JOURNEY-' + token,
            'field_sale_amount': 1000, 'field_contractor_id': contractor,
            'field_visit_at': datetime.datetime.now(datetime.timezone.utc).replace(second=17).strftime('%Y-%m-%d %H:%M:%S')}])
        for _ in range(4):
            rpc('crm.lead', 'action_next_field_stage', [[lead]])
        task = rpc('crm.lead', 'read', [[lead]], fields=['field_workspace_task_id'])[0]['field_workspace_task_id'][0]
        work_url = BASE + '/my/field-work/' + str(task)
        for width in (1440, 768, 390):
            page.set_viewport_size({'width': width, 'height': 900 if width > 390 else 844})
            page.goto(work_url)
            settle(page)
            details = page.locator('.o_field_job_more')
            check('DETAILS-' + str(width), 'Short work does not repeat a disclosure with no extra details', details.count() == 0)
            capture(page, 'draft-' + str(width))

        summary = page.locator('#field_visit_summary')
        summary.fill('טיוטה שמורה — נבדקו החיבורים')
        page.locator('.o_field_optional_notes summary').click()
        notes = 'הערה חשובה: יש לחזור עם מחבר מתאים.'
        page.locator('#field_visit_notes').fill(notes)
        page.locator('[data-wizard-next]').click()
        expect(page.locator('[data-wizard-panel="2"]')).to_be_visible()
        buffer = io.BytesIO()
        Image.new('RGB', (80, 60), (40, 120, 180)).save(buffer, format='PNG')

        def files(prefix, count):
            return [{'name': f'{prefix}-{n}.png', 'mimeType': 'image/png', 'buffer': buffer.getvalue()} for n in range(count)]

        page.locator('#field_before_image').set_input_files(files('before', 2))
        page.locator('#field_after_image').set_input_files(files('after', 2))
        visible_placeholders = page.locator('[data-photo-placeholder]:visible').count()
        check('PHOTO-EMPTY', 'Photo selection removes misleading empty placeholders', visible_placeholders == 0, visible_placeholders)
        capture(page, 'selected-390')
        page.locator('#field_before_image').set_input_files(files('excess', 4))
        expect(page.locator('#photo-error-before')).to_contain_text('עד 5')
        page.locator('[data-kind="before"] [data-new-photos] .btn-link').first.click()
        check('PHOTO-ERROR', 'Capacity error clears after removing a retained new photo', not page.locator('#photo-error-before').is_visible())
        capture(page, 'capacity-recovered-390')
        page.locator('#field_before_image').set_input_files(files('valid', 1))
        page.locator('[data-wizard-back]').click()
        expect(summary).to_have_value('טיוטה שמורה — נבדקו החיבורים')
        page.locator('[data-wizard-next]').click()
        expect(page.locator('[data-new-photos] img')).to_have_count(4)
        page.locator('[data-report-save]').click()
        expect(page.get_by_text('הדיווח והתמונות נשמרו. אפשר לחזור לעבודה ולהגיש בהמשך.', exact=True)).to_be_visible()
        expect(page.locator('[data-photo-key]')).to_have_count(4)
        summary.click()
        summary.fill('שינוי נוסף שעדיין לא נשמר')
        check('SAVE-STATE', 'Editing a saved draft replaces old success with unsaved state',
              not page.get_by_text('הדיווח והתמונות נשמרו. אפשר לחזור לעבודה ולהגיש בהמשך.', exact=True).is_visible()
              and page.locator('[data-report-dirty]').is_visible())
        capture(page, 'saved-then-edited-390')
        # An actual reload opens the native beforeunload confirmation. Dismiss it
        # first, then accept and prove the previous persisted text is preserved.
        dialogs = []

        def keep_edit(dialog):
            dialogs.append(dialog.type)
            dialog.dismiss()

        page.once('dialog', keep_edit)
        try:
            page.reload(timeout=10000)
        except PlaywrightError as error:
            # A dismissed native beforeunload intentionally aborts navigation.
            # Do not conceal unrelated browser failures/timeouts.
            if 'ERR_ABORTED' not in str(error):
                raise
        expect(summary).to_have_value('שינוי נוסף שעדיין לא נשמר')
        assert dialogs == ['beforeunload'], dialogs
        page.once('dialog', lambda dialog: dialog.accept())
        page.reload()
        settle(page)
        expect(summary).to_have_value('טיוטה שמורה — נבדקו החיבורים')
        page.locator('[data-wizard-next]').click()
        page.locator('[data-wizard-next]').click()
        check('REVIEW-NOTES', 'Review includes optional notes that will be submitted', notes in page.locator('[data-wizard-review]').inner_text())
        capture(page, 'review-notes-390')

        # Server-side image decoding can reject a MIME-labelled corrupt file.
        # The response retains unsaved text; leaving it should still warn, even
        # before another input event on the newly rendered error page.
        page.locator('[data-wizard-go="1"]').click()
        summary.click()
        summary.fill('לא נשמר בגלל תמונה פגומה — יש לשמור מחדש')
        page.locator('[data-wizard-next]').click()
        page.locator('#field_before_image').set_input_files({
            'name': 'corrupt.png', 'mimeType': 'image/png', 'buffer': b'not a decodable PNG'})
        page.locator('[data-report-save]').click()
        expect(page.locator('.o_field_portal .alert-danger')).to_be_visible()
        expect(summary).to_have_value('לא נשמר בגלל תמונה פגומה — יש לשמור מחדש')
        expect(page.locator('[data-photo-key]')).to_have_count(4)
        capture(page, 'rejected-upload-retains-text-390')
        rejected_dialogs = []

        def keep_rejected_edit(dialog):
            rejected_dialogs.append(dialog.type)
            dialog.dismiss()

        page.once('dialog', keep_rejected_edit)
        try:
            page.locator('.o_field_back').click()
        except PlaywrightError as error:
            if 'ERR_ABORTED' not in str(error):
                raise
        page.remove_listener('dialog', keep_rejected_edit)
        check('ERROR-DRAFT-GUARD', 'Rejected-upload text retains native navigation warning',
              rejected_dialogs == ['beforeunload'] and summary.is_visible(), rejected_dialogs)
        persisted = rpc('project.task', 'read', [[task]], fields=['field_visit_summary'])[0]
        assert persisted['field_visit_summary'] == 'טיוטה שמורה — נבדקו החיבורים', persisted
        if rejected_dialogs:
            page.once('dialog', lambda dialog: dialog.accept())
        page.goto(work_url)
        settle(page)
        expect(summary).to_have_value('טיוטה שמורה — נבדקו החיבורים')
        page.locator('[data-wizard-next]').click()

        page.locator('[data-kind="before"] [name="remove_photo"]').first.check()
        page.locator('#field_before_image').set_input_files(files('replacement', 4))
        page.locator('#field_after_image').set_input_files(files('more-after', 3))
        for width in (390, 768, 1440):
            page.set_viewport_size({'width': width, 'height': 900 if width > 390 else 844})
            capture(page, 'ten-photos-' + str(width))
            if width == 390:
                check('PHOTO-DENSITY', 'Ten photos keep the photo step within 1500px while preserving targets',
                      page.locator('[data-wizard-panel="2"]').bounding_box()['height'] <= 1500,
                      page.locator('[data-wizard-panel="2"]').bounding_box()['height'])
            targets = page.locator('[data-wizard-panel="2"] button:visible, [data-wizard-panel="2"] [data-zoom-photo]:visible, [data-wizard-panel="2"] .o_field_photo_remove:visible')
            assert targets.evaluate_all('els => els.every(el => {const box = el.getBoundingClientRect(); return box.width >= 44 && box.height >= 44;})'), f'Photo target below 44px at {width}'
        page.set_viewport_size({'width': 390, 'height': 844})
        # Keyboard image dialog must contain focus and restore it on Escape.
        zoom = page.locator('[data-kind="after"] [data-zoom-photo]').first
        zoom.focus()
        page.keyboard.press('Enter')
        expect(page.locator('[data-photo-dialog]')).to_be_visible()
        for key in ('Tab', 'Shift+Tab'):
            page.keyboard.press(key)
            focused = page.locator('[data-photo-dialog]').evaluate('''el => ({
                key: null, tag: document.activeElement.tagName,
                id: document.activeElement.id, class: document.activeElement.className,
                inDialog: el.contains(document.activeElement),
                browserBoundary: document.activeElement === document.body,
                dialogOpen: el.open
            })''')
            focused['key'] = key
            focus_path.append(focused)
            # A native dialog may hand Tab to browser chrome after its sole
            # close button; Chromium reports body as activeElement then. That
            # is not focus escaping to an underlying page control.
            assert focused['dialogOpen'] and (focused['inDialog'] or focused['browserBoundary']), focused
        expect(page.locator('[data-close-photo]')).to_be_focused()
        page.keyboard.press('Escape')
        expect(zoom).to_be_focused()
        page.locator('[data-report-save]').click()
        expect(page.get_by_text('הדיווח והתמונות נשמרו. אפשר לחזור לעבודה ולהגיש בהמשך.', exact=True)).to_be_visible()
        page.locator('[data-wizard-next]').click()
        expect(page.locator('[data-photo-key]')).to_have_count(10)
        page.locator('[data-wizard-next]').click()
        page.locator('[data-report-submit]').click()
        expect(page.get_by_text('הדיווח והתמונות נשלחו לבדיקת התפעול.', exact=True)).to_be_visible()
        expect(page.locator('input[type="file"]')).to_have_count(0)
        capture(page, 'submitted-390')
        assert not errors, errors
        assert not console_errors, console_errors
        assert not network_errors, network_errors
        completed = True
    except Exception as error:
        failure = {'type': type(error).__name__, 'message': str(error)}
        page.screenshot(path=str(OUTPUT / 'failure.png'), full_page=True)
        raise
    finally:
        result = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            'mode': 'observe' if options.observe else 'regression', 'checks': checks, 'defects': defects,
            'screens': captures, 'page_errors': errors, 'console_errors': console_errors, 'network_errors': network_errors,
            'completed': completed, 'failure': failure, 'dialog_focus_path': focus_path,
            'roles': ['owner (fixtures)', 'contractor (rendered login and journeys)'],
            'environment': 'isolated CI Chromium; synthetic data; localhost only; no live integration'}
        (OUTPUT / 'coverage.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps(result, ensure_ascii=False), flush=True)
        browser.close()

if not options.observe:
    assert not defects, defects
print('PASS: browser journey capture complete; baseline defects' if options.observe else 'PASS: browser journey regressions', len(defects))
