"""Run Odoo's own image compatibility tests in a new disposable CI database."""
import re
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pilot import config, wait_for_database

wait_for_database()
with tempfile.TemporaryDirectory(prefix='native-image-qa-') as directory:
    folder = Path(directory)
    conf = folder / 'odoo.conf'
    database = 'qa_native_image_' + secrets.token_hex(4)
    config(conf, folder / 'data', secrets.token_urlsafe(24), database)
    result = subprocess.run(['odoo', '-c', str(conf), '-d', database,
        '-i', 'base', '--without-demo=all', '--test-enable',
        '--test-tags=/base:TestImage', '--stop-after-init', '--log-level=test'],
        capture_output=True, text=True, timeout=300)
    output = result.stdout + result.stderr
    count = len(re.findall(r'Starting TestImage\.test_', output))
    if result.returncode or count < 15 or not re.search(r'0 failed, 0 error\(s\)', output):
        print(output[-14000:])
        raise SystemExit('Native Odoo image compatibility failed or insufficient coverage')
    print(f'PASS: {count} native Odoo image tests; synthetic isolated database')
