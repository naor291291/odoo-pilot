"""Focused synthetic Odoo regression run; no existing pilot database is used."""
import argparse
import ast
from pathlib import Path
import re
import secrets
import subprocess
import tempfile

import pilot

parser = argparse.ArgumentParser()
parser.add_argument('--related', action='store_true', help='Also run the 77 existing related regressions')
args = parser.parse_args()
FILES = ['test_pilot_feedback.py']
if args.related:
    FILES += ['test_field_documents.py', 'test_field_pricing.py', 'test_field_collection.py', 'test_field_dispatch.py']
classes = []
expected = 0
for filename in FILES:
    tree = ast.parse((pilot.ROOT / 'addons/field_work_photos/tests' / filename).read_text())
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
            classes.append(node.name)
            expected += sum(isinstance(n, ast.FunctionDef) and n.name.startswith('test_') for n in node.body)
pilot.wait_for_database()
with tempfile.TemporaryDirectory(prefix='field-feedback-') as directory:
    folder = Path(directory)
    conf = folder / 'odoo.conf'
    pilot.config(conf, folder / 'data', secrets.token_urlsafe(24), 'field_feedback_tests')
    result = subprocess.run(['odoo', '-c', str(conf), '-d', 'field_feedback_tests',
                             '-i', 'field_work_photos', '--without-demo=all', '--test-enable',
                             '--test-tags=' + ','.join('/field_work_photos:' + name for name in classes),
                             '--stop-after-init', '--log-level=test'],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = pilot.ROOT / '.local-data/feedback-tests.log'
    log.parent.mkdir(exist_ok=True)
    log.write_text(result.stdout)
    observed = len(re.findall(r'Starting Test[A-Za-z0-9_]+\.test_', result.stdout))
    if result.returncode or observed != expected or not re.search(r'0 failed, 0 error\(s\)', result.stdout):
        print(result.stdout[-22000:])
        raise SystemExit(f'FAIL: expected {expected}, observed {observed}; exit {result.returncode}')
    print(f'PASS: {observed} focused Odoo tests, 0 failed, 0 errors.')
