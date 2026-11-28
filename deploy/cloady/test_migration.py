"""Run the actual release supervisor against a disposable old-version Odoo DB.

CI only: Docker services, fixture credentials and volumes; never reads production.
"""
import json
from pathlib import Path
import subprocess
import time
import urllib.request

IMAGE='cloady-odoo:ci'
NAME='cloady-migration-smoke'
VOLUME='cloady-migration-fixture'
ENV=['-e','DB_HOST=127.0.0.1','-e','DB_PORT=5432','-e','DB_USER=odoo',
     '-e','DB_PASSWORD=synthetic_ci_only','-e','DB_NAME=field_crm','-e','DB_SSLMODE=disable',
     '-e','ODOO_ADMIN_PASSWORD=synthetic_master_password_32_characters',
     '-e','ODOO_PREVIOUS_RELEASE=693156a-synthetic-fixture']

def run(*args, **kw):
    return subprocess.run(args, check=True, text=True, **kw)

def snapshot():
    code="""import json,psycopg2
c=psycopg2.connect(host='127.0.0.1',user='odoo',password='synthetic_ci_only',dbname='field_crm')
try:
 with c.cursor() as q:
  q.execute('SELECT id,login,password,active FROM res_users ORDER BY id'); users=q.fetchall()
  q.execute("SELECT state,latest_version FROM ir_module_module WHERE name='field_work_photos'"); state=q.fetchone()
 print(json.dumps({'users':users,'state':state}))
finally:c.close()
"""
    # Captured only; never log password hashes even for synthetic users.
    return json.loads(run('docker','run','--rm','--network','host','--entrypoint','python3',IMAGE,'-c',code,capture_output=True).stdout)

def ready():
    for _ in range(180):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8069/web/login',timeout=2) as response:
                if response.status==200: return
        except Exception: pass
        time.sleep(1)
    raise RuntimeError('Managed Odoo did not become ready')

old=Path('.cloady-old-addons').resolve()
run('docker','volume','create',VOLUME,stdout=subprocess.DEVNULL)
try:
    run('docker','run','--rm','--network','host',*ENV,'-e','STAXA_ODOO_MODE=init',
        '-v',str(old)+':/mnt/extra-addons:ro','-v',VOLUME+':/var/lib/odoo',
        '--entrypoint','python3',IMAGE,'/opt/field-crm/staxa-entrypoint.py',stdout=subprocess.DEVNULL)
    before=snapshot()
    assert before['state']==['installed','18.0.17.0.2'], before['state']
    run('docker','run','-d','--name',NAME,'--network','host',*ENV,
        '-v',VOLUME+':/var/lib/odoo',IMAGE,stdout=subprocess.DEVNULL)
    ready(); after=snapshot()
    assert after['state']==['installed','18.0.18.0.0'], after['state']
    assert before['users']==after['users'], 'Synthetic users/password hashes changed'
    result=subprocess.run(['docker','run','--rm','--network','host',*ENV,
        '-v',VOLUME+':/var/lib/odoo',IMAGE],capture_output=True,text=True,timeout=30)
    assert result.returncode!=0 and 'Another release supervisor' in result.stderr
    run('docker','restart','--time','60',NAME,stdout=subprocess.DEVNULL)
    ready(); restarted=snapshot()
    assert restarted==after, 'Restart changed module state or users'
    run('docker','exec',NAME,'python3','-c',
        "from pathlib import Path; r=Path('/var/lib/odoo/release-control'); assert not (r/'attempt.json').exists(); assert len(list(r.glob('backup-*')))==1")
    print('PASS: actual 18.0.17.0.2 -> 18.0.18.0.0 migration, HTTP, preserved users, competing-server refusal, restart without duplicate migration')
except Exception:
    subprocess.run(['docker','logs','--tail','80',NAME],check=False)
    raise
finally:
    subprocess.run(['docker','rm','-f',NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    subprocess.run(['docker','volume','rm',VOLUME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
