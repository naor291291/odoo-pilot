"""Apply the upstream CVE-2023-36464 workaround to the supported Noble parser.

Build-time only; fail closed on an unexpected version/source, never monkeypatch
Odoo workers. Source: github.com/py-pdf/pypdf/security/advisories/GHSA-4vvm-4w3v-6mr8
"""
from pathlib import Path
import PyPDF2
import PyPDF2.generic._data_structures as module

OLD = 'while peek not in (b"\\r", b"\\n"):'
NEW = 'while peek not in (b"\\r", b"\\n", b""):'


def apply():
    if PyPDF2.__version__ != '2.12.1':
        raise RuntimeError('Review PDF security backport for the new parser version')
    path = Path(module.__file__)
    source = path.read_text()
    if source.count(OLD) == 0 and source.count(NEW) == 1:
        print('CVE-2023-36464 backport already present')
        return
    if source.count(OLD) != 1 or NEW in source:
        raise RuntimeError('Unexpected PDF parser source; review instead of patching blindly')
    path.write_text(source.replace(OLD, NEW))
    # Remove bytecode so same-size/timestamp caching cannot mask the source change.
    for cached in (path.parent / '__pycache__').glob('_data_structures.*.pyc'):
        cached.unlink()
    print('Applied upstream CVE-2023-36464 EOF guard')


if __name__ == '__main__':
    apply()
