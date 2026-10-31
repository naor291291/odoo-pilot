"""Two-session checks against the disposable, synthetic CI pilot on loopback.

Creates synthetic financial records. Never run this against a business database.
Credentials stay in memory and are sent only to this fixed local Odoo instance.
"""
from concurrent.futures import ThreadPoolExecutor
import argparse
import base64
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import threading
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8069'
DATABASE = 'odoo_pilot'


class RpcError(Exception):
    pass


def rpc(session, path, params):
    response = session.post(BASE + path, json={'jsonrpc': '2.0', 'id': 1, 'method': 'call', 'params': params}, timeout=90)
    response.raise_for_status()
    result = response.json()
    if result.get('error'):
        # Do not copy server tracebacks or request data into CI logs.
        raise RpcError(result['error'].get('data', {}).get('name', 'RPC denied'))
    return result.get('result')


def call(session, model, method, args, **kwargs):
    return rpc(session, '/web/dataset/call_kw', {'model': model, 'method': method, 'args': args, 'kwargs': kwargs})


def main(skip_pdf=False):
    for attempt in range(120):
        try:
            if requests.get(BASE + '/web/login', timeout=3).status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(1)
    else:
        raise RuntimeError('Disposable pilot did not become ready')
    credentials = json.loads((ROOT / '.local-data/credentials.json').read_text())

    def login():
        session = requests.Session()
        result = rpc(session, '/web/session/authenticate', {
            'db': DATABASE, 'login': credentials['login'], 'password': credentials['password']})
        assert result['uid']
        return session

    owner = login()
    customer = call(owner, 'res.partner', 'create', [{'name': 'Synthetic runtime security customer', 'phone': '0500000000'}])
    contractor = call(owner, 'res.users', 'search', [[('login', '=', credentials['contractors'][0]['login'])]])[0]
    lead = call(owner, 'crm.lead', 'create', [{
        'name': 'Synthetic runtime security work', 'is_field_service': True, 'partner_id': customer,
        'phone': '0500000000', 'field_site_address': 'Synthetic street', 'field_work_description': 'Fixture only',
        'field_sale_amount': 1000, 'field_customer_due': 1180, 'field_contractor_due': 700,
        'field_quote_number': 'SEC-RUNTIME', 'field_contractor_id': contractor,
        'field_visit_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}])
    sessions = [login(), login()]
    barrier = threading.Barrier(2)

    def pay(index):
        barrier.wait(timeout=10)
        try:
            call(sessions[index], 'field.work.payment', 'create', [{
                'lead_id': lead, 'kind': 'customer', 'amount': 1000, 'reference': 'SEC-PARALLEL-' + str(index)}])
            return 'posted'
        except RpcError:
            return 'rejected'

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(pay, range(2)))
    assert sorted(results) == ['posted', 'rejected'], results
    assert call(owner, 'crm.lead', 'read', [[lead], ['field_customer_paid']])[0]['field_customer_paid'] == 1000
    wizard = call(owner, 'field.work.payment.register', 'create', [{
        'lead_id': lead, 'amount': 180, 'reference': 'SEC-IDEMPOTENT'}])
    barrier.reset()

    def repeat(index):
        barrier.wait(timeout=10)
        return call(sessions[index], 'field.work.payment.register', 'action_apply', [[wizard]])

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(repeat, range(2)))
    assert call(owner, 'field.work.payment', 'search_count', [[('lead_id', '=', lead), ('kind', '=', 'customer')]]) == 2
    assert call(owner, 'crm.lead', 'read', [[lead], ['field_customer_paid']])[0]['field_customer_paid'] == 1180

    # Exercise the legitimate approval/collection path, also leaving a nonempty
    # entitlement/photo fixture for the subsequent offline restore drill.
    for _ in range(4):
        call(owner, 'crm.lead', 'action_next_field_stage', [[lead]])
    from PIL import Image
    photo_stream = BytesIO()
    Image.new('RGB', (8, 8), 'blue').save(photo_stream, 'PNG')
    photo = base64.b64encode(photo_stream.getvalue()).decode('ascii')
    call(owner, 'crm.lead', 'write', [[lead], {'field_report_before_image': photo,
         'field_report_after_image': photo, 'field_visit_summary': 'Synthetic completed fixture'}])
    call(owner, 'crm.lead', 'action_submit_field_report', [[lead]])
    call(owner, 'crm.lead', 'action_approve_field_report', [[lead]])
    call(owner, 'crm.lead', 'action_approve_contractor_amount', [[lead]])
    call(owner, 'crm.lead', 'action_close_field_work', [[lead]])

    reference = '<script>synthetic_security_reference()</script>'
    call(owner, 'field.work.payment', 'create', [{'lead_id': lead, 'kind': 'contractor', 'amount': 123.45, 'reference': reference}])
    statement = call(owner, 'field.contractor.statement', 'create', [{'contractor_id': contractor}])
    call(owner, 'field.contractor.statement', 'action_show_report', [[statement]])
    before = call(owner, 'field.contractor.statement', 'read', [[statement], ['payload']])[0]['payload']
    job_rows = [row for row in before['rows'] if row['work_url'].endswith('/' + str(lead))]
    assert sorted((row['kind'], row['amount']) for row in job_rows) == [('credit', 700), ('payment', -123.45)]
    count_before = call(owner, 'field.work.payment', 'search_count', [[('lead_id', '=', lead)]])
    html_response = owner.get(BASE + '/report/html/field_work_photos.contractor_statement_pdf/' + str(statement), timeout=60)
    assert html_response.status_code == 200
    assert reference not in html_response.text and '&lt;script&gt;' in html_response.text
    assert html_response.headers['Cache-Control'] == 'private, no-store'
    if not skip_pdf:
        pdf_response = owner.get(BASE + '/report/pdf/field_work_photos.contractor_statement_pdf/' + str(statement), timeout=120)
        assert pdf_response.status_code == 200 and pdf_response.content.startswith(b'%PDF')
        assert pdf_response.headers['Cache-Control'] == 'private, no-store'
        from PyPDF2 import PdfReader
        assert len(PdfReader(BytesIO(pdf_response.content)).pages) >= 1
    after = call(owner, 'field.contractor.statement', 'read', [[statement], ['payload']])[0]['payload']
    assert before == after
    assert call(owner, 'field.work.payment', 'search_count', [[('lead_id', '=', lead)]]) == count_before
    old_cookies = owner.cookies.copy()
    rpc(owner, '/web/session/destroy', {})
    replay = requests.Session()
    replay.cookies.update(old_cookies)
    try:
        call(replay, 'crm.lead', 'read', [[lead], ['name']])
    except RpcError:
        pass
    else:
        raise AssertionError('Logged-out session remained usable')
    results = {'parallel_overpayment': 'passed', 'parallel_idempotency': 'passed',
               'statement_html_escape_and_cache': 'passed', 'report_read_only': 'passed',
               'real_pdf': 'not executed (explicit local flag)' if skip_pdf else 'passed',
               'logout_session_replay': 'passed', 'fixture': 'synthetic local CI pilot'}
    output = ROOT / '.local-data/security'
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    (output / 'runtime-results.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(results))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-pdf', action='store_true', help='Explicit local limitation only; CI must render a real PDF')
    main(skip_pdf=parser.parse_args().skip_pdf)
