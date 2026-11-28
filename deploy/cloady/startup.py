"""Fail-closed Odoo supervisor: hold a DB lease through migration AND serving.

An imported database is required. Never initializes users or resets passwords.
A failed/interrupted upgrade requires operator review; restarts never retry it.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time

MODULE = 'field_work_photos'
LOCK = (181118, 8069)
PG_BIN = Path('/usr/lib/postgresql/16/bin')


class Stop(RuntimeError):
    pass


def version(value):
    if not re.fullmatch(r'18\.0\.(?:\d+\.)*\d+', value or ''):
        raise Stop('Unsupported module version')
    return tuple(map(int, value.split('.')))


def target(root):
    manifest = ast.literal_eval((root / '__manifest__.py').read_text())
    result = manifest['version']
    version(result)
    digest = hashlib.sha256()
    for file in sorted(root.rglob('*')):
        if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
            digest.update(str(file.relative_to(root)).encode())
            digest.update(file.read_bytes())
    return result, digest.hexdigest()


def decision(installed, expected, pending):
    if pending:
        raise Stop('Interrupted upgrade: review backup and database before clearing attempt')
    if installed is None:
        raise Stop('Restore the existing database and filestore first; initialization is disabled')
    state, current = installed
    if state != 'installed':
        raise Stop('Module is not in installed state; manual recovery required')
    if version(current) > version(expected):
        raise Stop('Database is newer than image; database rollback is never automatic')
    return 'upgrade' if version(current) < version(expected) else 'serve'


def private_json(path, data, exclusive=False):
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(data, out, sort_keys=True)
        out.flush()
        os.fsync(out.fileno())
    sync_directory(path.parent)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def module_state(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT state,latest_version FROM ir_module_module WHERE name=%s', (MODULE,))
        return cur.fetchone()


def assert_quiet(conn):
    # The first transfer also checks non-cooperating legacy servers. Do not kill any.
    with conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() '
                    'AND pid<>pg_backend_pid() AND backend_type=%s', ('client backend',))
        if cur.fetchone()[0]:
            raise Stop('Other database clients exist; stop the old server before upgrading')
        cur.execute('SELECT count(*) FROM pg_prepared_xacts WHERE database=current_database()')
        if cur.fetchone()[0]:
            raise Stop('Prepared transactions exist')


def backup(conn, cfg, root, current, expected, previous_release):
    assert_quiet(conn)
    store = Path(cfg['data_dir']) / 'filestore' / cfg['db_name']
    with conn.cursor() as cur:
        cur.execute('SELECT pg_database_size(current_database())')
        db_size = cur.fetchone()[0]
    files = list(store.rglob('*')) if store.exists() else []
    if any(path.is_symlink() for path in files):
        raise Stop('Filestore symlinks require manual review')
    needed = db_size * 2 + sum(p.stat().st_size for p in files if p.is_file()) + 256 * 1024**2
    if shutil.disk_usage(root).free < needed:
        raise Stop('Insufficient backup headroom; no migration attempted')
    folder = root / ('backup-' + str(time.time_ns()))
    folder.mkdir(mode=0o700)
    pg_env = dict(os.environ, PGHOST=cfg['db_host'], PGPORT=str(cfg['db_port']),
                  PGUSER=cfg['db_user'], PGPASSWORD=cfg['db_password'],
                  PGSSLMODE=cfg['db_sslmode'])
    # Never put a credential in argv or print subprocess output on failure.
    with (folder / 'backup.log').open('wb') as log:
        subprocess.run([str(PG_BIN / 'pg_dump'), '-Fc', '--no-owner', '--no-acl', '-f', str(folder / 'database.dump'),
                        cfg['db_name']], env=pg_env, stdout=log, stderr=log, check=True)
        subprocess.run([str(PG_BIN / 'pg_restore'), '--list', str(folder / 'database.dump')],
                       stdout=subprocess.DEVNULL, stderr=log, check=True)
    checks = []
    with conn.cursor() as cur:
        cur.execute('SELECT id,store_fname,checksum FROM ir_attachment WHERE store_fname IS NOT NULL')
        for ident, name, checksum in cur.fetchall():
            path = (store / name).resolve()
            if not path.is_relative_to(store.resolve()) or not path.is_file():
                raise Stop('Filestore reference is missing or unsafe')
            if hashlib.sha1(path.read_bytes()).hexdigest() != checksum:
                raise Stop('Filestore checksum mismatch')
            checks.append((ident, name, checksum))
    with tarfile.open(folder / 'filestore.tar', 'w') as archive:
        if store.exists():
            archive.add(store, arcname='filestore/' + cfg['db_name'])
        elif checks:
            raise Stop('Missing filestore')
    assert_quiet(conn)
    hashes = {}
    for name in ('database.dump', 'filestore.tar'):
        with (folder / name).open('rb') as stream:
            hashes[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
            os.fsync(stream.fileno())
    private_json(folder / 'manifest.json', dict(database=cfg['db_name'], old_version=current,
                 target_version=expected, previous_release=previous_release,
                 attachment_checks=checks, sha256=hashes, restore_tested=False))
    # Local backup validated for completeness; this is NOT a tested off-site restore.
    return folder


def run_child(command, env, conn):
    child = subprocess.Popen(command, env=env)
    interrupted = False
    def stop(signum, frame):
        nonlocal interrupted
        interrupted = True
        child.terminate()
    old = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        while child.poll() is None:
            try:
                with conn.cursor() as cur:
                    cur.execute('SELECT 1')
            except Exception:
                child.terminate()
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait()
                raise Stop('Database lease lost; Odoo stopped') from None
            time.sleep(1)
        if interrupted:
            raise Stop('Termination requested; no subsequent startup action allowed')
        if child.returncode:
            raise Stop('Odoo exited unsuccessfully; inspect private service logs')
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()
        for sig, handler in old.items():
            signal.signal(sig, handler)


def maintenance():
    """Keep the restore shell available without importing Odoo or opening the DB."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'Maintenance: Odoo is stopped. Data migration is not complete.\n'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        for sig in handlers:
            signal.signal(sig, stop)
        with HTTPServer(('0.0.0.0', 8069), Handler) as server:
            server.timeout = 0.5
            print('Maintenance active: no Odoo, cron or database connections', flush=True)
            while not stopped:
                server.handle_request()
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def main():
    mode = os.environ.get('ODOO_MAINTENANCE', '0')
    if mode not in ('0', '1'):
        raise Stop('ODOO_MAINTENANCE must be 0 or 1')
    if mode == '1':
        maintenance()
        return
    import psycopg2
    spec = importlib.util.spec_from_file_location('adapter', '/opt/field-crm/staxa-entrypoint.py')
    adapter = importlib.util.module_from_spec(spec); spec.loader.exec_module(adapter)
    cfg, mode = adapter.settings(os.environ)
    if mode != 'serve':
        raise Stop('Initialization mode is not supported for a migrated instance')
    expected, fingerprint = target(Path('/mnt/extra-addons') / MODULE)
    os.umask(0o077)
    root = Path(cfg['data_dir']) / 'release-control'
    root.mkdir(mode=0o700, exist_ok=True)
    pending = root / 'attempt.json'
    applied = root / 'applied.json'
    conn = psycopg2.connect(host=cfg['db_host'], port=cfg['db_port'], user=cfg['db_user'],
                           password=cfg['db_password'], dbname=cfg['db_name'],
                           sslmode=cfg['db_sslmode'], connect_timeout=10,
                           options='-c statement_timeout=5000',
                           application_name='field-crm-release-supervisor')
    conn.autocommit = True
    try:
        if conn.server_version // 10000 != 16:
            raise Stop('This release requires PostgreSQL 16 backup compatibility')
        with conn.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(%s,%s)', LOCK)
            if not cur.fetchone()[0]:
                raise Stop('Another release supervisor is running; no parallel Odoo allowed')
        installed = module_state(conn)
        action = decision(installed, expected, pending.exists())
        assert_quiet(conn)
        if applied.exists():
            last = json.loads(applied.read_text())
            if last['version'] == expected and last['fingerprint'] != fingerprint:
                raise Stop('Module changed without a version increment')
        config_path = adapter.write_config(cfg)
        env = dict(os.environ)
        for key in ('DB_PASSWORD', 'DATABASE_URL', 'ODOO_ADMIN_PASSWORD', 'POSTGRES_PASSWORD'):
            env.pop(key, None)
        env.update(FIELD_WORK_EMAIL_MODE='off', FIELD_WORK_WHATSAPP_MODE='off',
                   FIELD_WORK_WHATSAPP_INBOUND='0', FIELD_WORK_AUTO_STAGES='0')
        command = ['odoo', '--config', config_path, '-d', cfg['db_name']]
        if action == 'upgrade':
            previous = os.environ.get('ODOO_PREVIOUS_RELEASE', '').strip()
            if not previous:
                raise Stop('Record the previous immutable image/release before upgrading')
            folder = backup(conn, cfg, root, installed[1], expected, previous)
            private_json(pending, dict(old_version=installed[1], target=expected,
                                      fingerprint=fingerprint, backup=str(folder)), exclusive=True)
            run_child(command + ['-u', MODULE, '--stop-after-init', '--no-http', '--max-cron-threads=0'], env, conn)
            if module_state(conn) != ('installed', expected):
                raise Stop('Upgrade did not install the expected version')
        private_json(applied, dict(version=expected, fingerprint=fingerprint))
        if action == 'upgrade':
            pending.unlink()
            sync_directory(root)
        # Keep the advisory-lock connection open for the entire serving lifetime.
        run_child(command, env, conn)
    finally:
        conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never print psycopg/libpq error strings containing connection details.
        print(str(error) if isinstance(error, Stop) else 'Startup failed: ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
