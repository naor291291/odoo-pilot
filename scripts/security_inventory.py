"""Non-secret runtime inventory for dependency triage, not a clean bill of health."""
from importlib.metadata import PackageNotFoundError, version
import json
import platform
import shutil
import subprocess
import sys

PACKAGES = ('Pillow', 'Werkzeug', 'Jinja2', 'lxml', 'lxml-html-clean', 'cryptography',
            'pyOpenSSL', 'requests', 'urllib3', 'cbor2', 'idna', 'zeep', 'PyPDF2', 'pypdf')


def main():
    packages = {}
    for name in PACKAGES:
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            continue
    if '--requirements' in sys.argv:
        print('\n'.join(f'{name}=={value}' for name, value in packages.items()))
        return
    import odoo.release
    result = {'python': platform.python_version(), 'odoo': odoo.release.version,
              'python_packages': packages, 'scope': 'selected runtime parsers, crypto and HTTP libraries'}
    if shutil.which('dpkg-query'):
        completed = subprocess.run(['dpkg-query', '-W', '-f=${Package}\t${Version}\n',
                                    'odoo', 'python3-pil', 'python3-werkzeug', 'wkhtmltox',
                                    'libwebp7', 'libssl3t64', 'postgresql-client-16'], capture_output=True, text=True, check=False)
        result['distribution_packages'] = completed.stdout.strip().splitlines()
    if shutil.which('wkhtmltopdf'):
        result['pdf_engine'] = subprocess.check_output(['wkhtmltopdf', '--version'], text=True).strip()
    result['postgres_backup_tools'] = {}
    for label, command in (('default', shutil.which('pg_dump')),
                           ('compose_16', '/usr/lib/postgresql/16/bin/pg_dump')):
        if command and shutil.which(command):
            result['postgres_backup_tools'][label] = subprocess.check_output([command, '--version'], text=True).strip()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
