"""Offline restore drill for the disposable synthetic pilot, never production.

Requires the pilot runner stopped. Restores to a new, random database and checks
table counts plus every attachment's filestore checksum. No existing DB is
overwritten; only the database created by this drill is dropped in its finally.
The private backup remains in .local-data/security-backups for inspection.
"""
from contextlib import closing
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local-data'
DATABASE = 'odoo_pilot'
TABLES = ('crm_lead', 'project_task', 'ir_attachment', 'field_work_payment', 'field_work_entitlement')


def snapshot(connection):
    with connection.cursor() as cursor:
        counts = {}
        for table in TABLES:
            cursor.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table)))
            counts[table] = cursor.fetchone()[0]
        cursor.execute("SELECT store_fname, checksum FROM ir_attachment WHERE store_fname IS NOT NULL")
        return counts, sorted(cursor.fetchall())


def main():
    os.umask(0o077)
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    with (LOCAL / 'runner.lock').open('a') as lock:
        # The running pilot holds this same lock for its entire lifetime.
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        backup_root = LOCAL / 'security-backups'
        backup_root.mkdir(mode=0o700, exist_ok=True)
        backup = Path(tempfile.mkdtemp(prefix='restore-drill-', dir=backup_root))
        with closing(psycopg2.connect(dbname=DATABASE)) as source:
            expected = snapshot(source)
            server_major = source.server_version // 10000
        # The Odoo image's default client can be newer than Compose's DB.
        # Newer dumps may emit SET commands unsupported by an older server.
        tools = {}
        for name in ('pg_dump', 'pg_restore'):
            candidate = Path('/usr/lib/postgresql') / str(server_major) / 'bin' / name
            command = str(candidate) if candidate.is_file() else shutil.which(name)
            if not command:
                raise RuntimeError('Missing PostgreSQL backup/restore tool')
            version_text = subprocess.check_output([command, '--version'], text=True)
            match = re.search(r'(\d+)\.\d+', version_text)
            if not match or int(match.group(1)) != server_major:
                raise RuntimeError(f'Backup and restore require PostgreSQL {server_major} client tools; rebuild the development image')
            tools[name] = command
        subprocess.run([tools['pg_dump'], '-Fc', '-d', DATABASE, '-f', str(backup / 'database.dump')], check=True, timeout=180)
        filestore = LOCAL / 'odoo-data/filestore' / DATABASE
        shutil.copytree(filestore, backup / 'filestore')
        restore_name = 'odoo_pilot_restore_' + uuid.uuid4().hex[:16]
        admin = psycopg2.connect(dbname='postgres')
        created = False
        try:
            admin.autocommit = True
            try:
                with admin.cursor() as cursor:
                    cursor.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(restore_name)))
                created = True
                subprocess.run([tools['pg_restore'], '--exit-on-error', '--no-owner', '--no-privileges',
                                '-d', restore_name, str(backup / 'database.dump')], check=True, timeout=180)
                with closing(psycopg2.connect(dbname=restore_name)) as restored:
                    actual = snapshot(restored)
                assert expected == actual, 'Restored record/attachment counts differ'
                for filename, checksum in actual[1]:
                    assert re.fullmatch(r'[0-9a-f]{2}/[0-9a-f]{40}', filename), 'Invalid filestore path'
                    path = backup / 'filestore' / filename
                    assert not path.is_symlink() and path.is_file(), 'Missing attachment file'
                    assert hashlib.sha1(path.read_bytes(), usedforsecurity=False).hexdigest() == checksum
                result = {'database_restore': 'passed', 'record_counts': actual[0],
                          'attachment_checksums_verified': len(actual[1]),
                          'backup_private': (backup.stat().st_mode & 0o077) == 0,
                          'postgres_client_server_major': server_major,
                          'separate_database': True}
                (backup / 'result.json').write_text(json.dumps(result, indent=2))
                print(json.dumps(result))
            finally:
                # Never accepts an operator-supplied database name for deletion.
                if created:
                    with admin.cursor() as cursor:
                        cursor.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(restore_name)))
        finally:
            admin.close()


if __name__ == '__main__':
    main()
