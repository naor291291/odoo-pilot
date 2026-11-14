"""Disposable Docker-only 512MiB init/login probe; never touches a hosted pilot."""
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time


def docker(*args, check=True):
    return subprocess.run(['docker', *args], capture_output=True, text=True, check=check)


def main():
    tag = 'staxa-probe-' + secrets.token_hex(5)
    network, volume = tag + '-net', tag + '-data'
    containers = [tag + '-db', tag + '-init', tag + '-web']
    result = {'scope': 'synthetic CI, 512MiB limit, no swap, 0.5 CPU',
              'memory_limit_bytes': 536870912, 'initialization': 'not_run', 'login': 'not_run',
              'capacity_for_3_to_5_users': 'NOT_VERIFIED', 'peak_bytes': {}}
    output = Path('staxa-probe-result.json')
    with tempfile.TemporaryDirectory() as tmp:
        env = Path(tmp) / 'db.env'
        password = secrets.token_urlsafe(32)
        env.write_text('POSTGRES_USER=pilot_role\nPOSTGRES_DB=staxa_probe\nPOSTGRES_PASSWORD=' + password + '\n')
        env.chmod(0o600)
        app_env = Path(tmp) / 'app.env'
        app_env.write_text('DB_HOST=db\nDB_PORT=5432\nDB_USER=pilot_role\nDB_NAME=staxa_probe\nDB_SSLMODE=disable\nDB_PASSWORD=' + password + '\nODOO_ADMIN_PASSWORD=' + secrets.token_urlsafe(40) + '\n')
        app_env.chmod(0o600)
        try:
            docker('network', 'create', '--internal', network)
            docker('volume', 'create', volume)
            docker('run', '-d', '--name', containers[0], '--network', network, '--network-alias', 'db',
                   '--env-file', str(env), 'postgres:16')
            for _ in range(60):
                if docker('exec', containers[0], 'pg_isready', '-U', 'pilot_role', '-d', 'staxa_probe', check=False).returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError('Synthetic PostgreSQL did not start')
            common = ['--network', network, '--memory=512m', '--memory-swap=512m', '--cpus=0.5',
                      '--env-file', str(app_env), '-v', volume + ':/var/lib/odoo']
            for phase, name in [('initialization', containers[1]), ('login', containers[2])]:
                mode = 'init' if phase == 'initialization' else 'serve'
                docker('run', '-d', '--name', name, *common, '-e', 'STAXA_ODOO_MODE=' + mode, 'staxa-odoo:probe')
                deadline = time.monotonic() + (300 if mode == 'init' else 90)
                peak = 0
                status = 'TIMEOUT'
                while time.monotonic() < deadline:
                    state = json.loads(docker('inspect', '--format', '{{json .State}}', name).stdout)
                    if not state['Running']:
                        status = 'OOM' if state['OOMKilled'] else ('PASS' if mode == 'init' and state['ExitCode'] == 0 else 'FAIL')
                        result[phase + '_exit_code'] = state['ExitCode']
                        break
                    sample = docker('exec', name, 'cat', '/sys/fs/cgroup/memory.peak', check=False).stdout.strip()
                    if sample.isdecimal():
                        peak = max(peak, int(sample))
                    if mode == 'serve':
                        check = docker('exec', name, 'python3', '-c',
                            "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8069/web/login',timeout=2); assert r.status==200 and b'<html' in r.read(100000).lower()",
                            check=False)
                        if check.returncode == 0:
                            status = 'PASS'
                            break
                    time.sleep(2)
                if phase == 'initialization' and status == 'PASS':
                    installed = docker('exec', containers[0], 'psql', '-U', 'pilot_role', '-d', 'staxa_probe', '-Atc',
                        "SELECT state FROM ir_module_module WHERE name='field_work_photos'", check=False)
                    result['custom_module_installed'] = installed.returncode == 0 and installed.stdout.strip() == 'installed'
                    if not result['custom_module_installed']:
                        status = 'FAIL'
                if phase == 'login' and status == 'PASS':
                    sample = docker('exec', name, 'cat', '/sys/fs/cgroup/memory.peak', check=False).stdout.strip()
                    if sample.isdecimal():
                        peak = max(peak, int(sample))
                result[phase] = status
                result['peak_bytes'][phase] = peak or None
                docker('stop', '-t', '5', name, check=False)
                if status != 'PASS':
                    break
        except Exception as error:
            # Do not expose Docker argv/env or configuration in error output.
            result['probe_error_type'] = type(error).__name__
        finally:
            for name in reversed(containers):
                docker('rm', '-fv', name, check=False)
            docker('volume', 'rm', volume, check=False)
            docker('network', 'rm', network, check=False)
            output.write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result))
    # A measured OOM is a valid NO-GO finding, not a reason to hide the artifact.
    return 1 if 'probe_error_type' in result else 0


if __name__ == '__main__':
    raise SystemExit(main())
