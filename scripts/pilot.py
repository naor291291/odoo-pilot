"""Initialize and run the disposable Odoo pilot inside its dev container."""
import fcntl
import json
import http.cookiejar
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local-data"
DATABASE = "odoo_pilot"


def prepare_directory():
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    LOCAL.chmod(0o700)


def write_private(path, content):
    # Keep generated credentials outside Git and private to the workspace user.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(content)
    path.chmod(0o600)


def credentials():
    path = LOCAL / "credentials.json"
    if not path.exists():
        write_private(path, json.dumps({
            "login": "admin",
            "password": secrets.token_urlsafe(18),
            "master_password": secrets.token_urlsafe(24),
        }, indent=2))
    login = json.loads(path.read_text())
    if "contractors" not in login:
        login["contractors"] = [
            {"login": "pilot.contractor.1", "name": "יוסי - קבלן ניסיון", "password": secrets.token_urlsafe(18)},
            {"login": "pilot.contractor.2", "name": "משה - קבלן ניסיון", "password": secrets.token_urlsafe(18)},
        ]
        write_private(path, json.dumps(login, ensure_ascii=False, indent=2))
    return login


def config(path, data_dir, master_password, database):
    # Compose's DB is private; no PostgreSQL port is published to the host.
    values = {
        "addons_path": str(ROOT / "addons"),
        "data_dir": str(data_dir),
        "admin_passwd": master_password,
        "db_host": os.environ.get("PGHOST", "db"),
        "db_port": os.environ.get("PGPORT", "5732"),
        "db_user": os.environ.get("PGUSER", "odoo"),
        "db_password": os.environ.get("PGPASSWORD", "odoo_pilot_dev_only"),
        "db_name": database,
        "dbfilter": "^" + database + "$",
        "list_db": "False",
        "proxy_mode": "True",
        "http_interface": "0.0.0.0",
        "http_port": "8069",
        "workers": "0",
        "max_cron_threads": "0",
        "limit_time_real": "300",
    }
    write_private(path, "[options]\n" + "\n".join(f"{k} = {v}" for k, v in values.items()) + "\n")


def wait_for_database():
    import psycopg2
    for attempt in range(60):
        try:
            with psycopg2.connect(dbname="postgres", connect_timeout=3):
                return
        except psycopg2.OperationalError:
            if attempt == 59:
                raise
            time.sleep(1)


def installed():
    import psycopg2
    with psycopg2.connect(dbname="postgres") as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DATABASE,))
            if not cursor.fetchone():
                return False
    with psycopg2.connect(dbname=DATABASE) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.ir_module_module')")
            if not cursor.fetchone()[0]:
                return False
            cursor.execute("SELECT state FROM ir_module_module WHERE name = %s", ("field_work_photos",))
            row = cursor.fetchone()
            return bool(row and row[0] == "installed")


def initialize(conf, login):
    ready = installed()
    print("Updating pilot module..." if ready else "Installing Odoo and the field-photo module...", flush=True)
    subprocess.run([
        "odoo", "-c", str(conf), "-d", DATABASE,
        "-u" if ready else "-i", "field_work_photos",
        "--without-demo=all", "--load-language=he_IL", "--stop-after-init",
    ], check=True)
    # Use the ORM to create one task and a generated login. This is idempotent.
    bootstrap = f"""
from odoo import fields
admin = env.ref('base.user_admin')
admin.write({{'login': {login['login']!r}, 'password': {login['password']!r}, 'lang': 'he_IL', 'tz': 'Asia/Jerusalem'}})
# base.user_admin is noupdate in existing databases, so XML alone cannot grant
# the new owner role during an upgrade. This pilot login is always the owner.
admin.write({{'groups_id': [(4, env.ref('field_work_photos.group_field_finance').id)]}})
Project = env['project.project']
project = Project.search([('name', '=', 'עבודות שטח - פיילוט')], limit=1)
if not project:
    project = Project.create({{'name': 'עבודות שטח - פיילוט'}})
Task = env['project.task']
if not Task.search_count([('project_id', '=', project.id)]):
    Task.create({{'name': 'החלפת ברז במטבח - ניסיון', 'project_id': project.id, 'user_ids': [(6, 0, [admin.id])], 'field_report_required': True}})
contractors = []
for details in {login['contractors']!r}:
    user = env['res.users'].with_context(active_test=False).search([('login', '=', details['login'])], limit=1)
    if not user:
        user = env['res.users'].with_context(no_reset_password=True).create({{
            'name': details['name'], 'login': details['login'], 'password': details['password'],
            'lang': 'he_IL', 'tz': 'Asia/Jerusalem',
            'groups_id': [(6, 0, [env.ref('field_work_photos.group_field_contractor').id])],
        }})
    contractors.append(user)
Lead = env['crm.lead']
if not Lead.search_count([('is_field_service', '=', True)]):
    customer = env['res.partner'].create({{'name': 'דני - לקוח ניסיון', 'phone': '0500000000'}})
    sample_lead = Lead.create({{
        'name': 'החלפת ברז - דוגמת שיבוץ', 'is_field_service': True,
        'partner_id': customer.id, 'field_sale_amount': 1000, 'field_quote_number': 'PILOT-001',
        'field_contractor_id': contractors[0].id, 'field_visit_at': fields.Datetime.now(),
        'field_site_address': 'רחוב לדוגמה 10, גבעתיים',
        'field_work_description': 'החלפת הברז במטבח ובדיקת נזילות לאחר ההתקנה.',
        'stage_id': env.ref('field_work_photos.stage_field_new').id,
    }})
    for _ in range(3):
        sample_lead.action_next_field_stage()
env.cr.commit()
"""
    subprocess.run([
        "odoo", "shell", "-c", str(conf), "-d", DATABASE, "--no-http",
    ], input=bootstrap, text=True, check=True)


def worker():
    prepare_directory()
    lock = open(LOCAL / "runner.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    login = credentials()
    conf = LOCAL / "odoo.conf"
    config(conf, LOCAL / "odoo-data", login["master_password"], DATABASE)
    wait_for_database()
    initialize(conf, login)
    print("Pilot initialized. Run python3 scripts/pilot.py status for login details.", flush=True)
    # Keep the lock in the runner process until Odoo exits.
    process = subprocess.Popen(["odoo", "-c", str(conf), "-d", DATABASE])
    raise SystemExit(process.wait())


def start():
    prepare_directory()
    with open(LOCAL / "odoo.log", "ab") as log:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "worker"],
                         cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True)
    print("Odoo is starting in the background. First setup can take a few minutes.")
    print("Run: python3 scripts/pilot.py status")
    print("Logs: tail -f .local-data/odoo.log")


def status():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8069/web/login", timeout=4) as response:
            ready = response.status == 200
    except (urllib.error.URLError, TimeoutError):
        ready = False
    if not ready:
        print("Odoo is not ready yet. Check: tail -n 60 .local-data/odoo.log")
        return
    path = LOCAL / "credentials.json"
    if not path.exists():
        print("Odoo responds, but pilot credentials are missing. Check the setup log.")
        return
    login = json.loads(path.read_text())
    print("Odoo is ready. Open port 8069 from the Ports tab (keep visibility Private).")
    print("Login:", login["login"])
    print("Password:", login["password"])
    for contractor in login.get("contractors", []):
        print("Contractor:", contractor["login"], "Password:", contractor["password"])
    print("Contractor portal: open /my/field-work in a separate browser session.")


def restart():
    """Restart only this pilot's runner/Odoo, preserving its database and files."""
    script = str(Path(__file__).resolve())
    conf = str(LOCAL / "odoo.conf")
    targets = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            args = (entry / "cmdline").read_bytes().decode().strip("\0").split("\0")
            is_runner = len(args) >= 3 and args[1:] == [script, "worker"]
            is_odoo = any(Path(arg).name == "odoo" for arg in args[:2]) and "-c" in args and args[args.index("-c") + 1] == conf
            if is_runner or is_odoo:
                targets.append(int(entry.name))
        except (FileNotFoundError, PermissionError, IndexError, UnicodeError):
            continue
    for pid in targets:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for attempt in range(30):
        living = []
        for pid in targets:
            try:
                status_text = Path(f"/proc/{pid}/status").read_text()
                if not re.search(r"^State:\s+Z", status_text, re.MULTILINE):
                    living.append(pid)
            except FileNotFoundError:
                pass
        if not living:
            start()
            return
        time.sleep(1)
    raise SystemExit("Pilot is still stopping. Wait and run python3 scripts/pilot.py start.")


def test():
    wait_for_database()
    with tempfile.TemporaryDirectory(prefix="odoo-pilot-tests-") as directory:
        folder = Path(directory)
        conf = folder / "odoo.conf"
        config(conf, folder / "data", secrets.token_urlsafe(24), "odoo_pilot_tests")
        result = subprocess.run([
            "odoo", "-c", str(conf), "-d", "odoo_pilot_tests",
            "-i", "field_work_photos", "--without-demo=all", "--test-enable",
            "--test-tags=/field_work_photos", "--stop-after-init", "--log-level=test",
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(result.stdout)
        if result.returncode:
            raise SystemExit(result.returncode)
        count = len(re.findall(r"Starting Test(FieldWorkPhotos|FieldDispatch|FieldPortal|FieldPricing|FieldWorkspace|FieldVisit|FieldCollection)\.test_", result.stdout))
        if count < 139 or not re.search(r"0 failed, 0 error\(s\)", result.stdout):
            raise SystemExit("Expected all 139 field-review, dispatch, portal, pricing, workspace and collection tests to pass; inspect the log.")
        print(f"Verified {count} Odoo integration tests.")


def smoke():
    """Exercise the same initialization, login and sample task as Codespaces."""
    start()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    for attempt in range(240):
        try:
            with opener.open("http://127.0.0.1:8069/web/login", timeout=3) as response:
                if response.status == 200:
                    break
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(1)
    else:
        raise SystemExit("Pilot did not become ready. Inspect .local-data/odoo.log.")

    def rpc(path, params):
        payload = json.dumps({"jsonrpc": "2.0", "method": "call", "params": params, "id": 1}).encode()
        request = urllib.request.Request("http://127.0.0.1:8069" + path, data=payload,
                                         headers={"Content-Type": "application/json"})
        with opener.open(request, timeout=30) as response:
            data = json.load(response)
        if data.get("error"):
            raise SystemExit("Odoo RPC failed during the pilot smoke check.")
        return data.get("result")

    login = credentials()
    session = rpc("/web/session/authenticate", {
        "db": DATABASE, "login": login["login"], "password": login["password"],
    })
    if not session.get("uid") or session.get("user_context", {}).get("lang") != "he_IL":
        raise SystemExit("Generated login or Hebrew setup did not work.")
    count = rpc("/web/dataset/call_kw/project.task/search_count", {
        "model": "project.task", "method": "search_count",
        "args": [[["field_report_required", "=", True]]], "kwargs": {},
    })
    if not count:
        raise SystemExit("The sample field task was not created.")
    can_review = rpc("/web/dataset/call_kw/res.users/has_group", {
        "model": "res.users", "method": "has_group",
        "args": [[session["uid"]], "field_work_photos.group_field_reviewer"], "kwargs": {},
    })
    if not can_review:
        raise SystemExit("The pilot administrator lacks the field-review role.")
    def has_owner_role(uid):
        return rpc("/web/dataset/call_kw/res.users/has_group", {
            "model": "res.users", "method": "has_group",
            "args": [[uid], "field_work_photos.group_field_finance"], "kwargs": {},
        })

    if not has_owner_role(session["uid"]):
        raise SystemExit("The pilot administrator lacks the pricing-owner role.")
    lead_count = rpc("/web/dataset/call_kw/crm.lead/search_count", {
        "model": "crm.lead", "method": "search_count",
        "args": [[["is_field_service", "=", True]]], "kwargs": {},
    })
    if not lead_count:
        raise SystemExit("The sample dispatch lead was not created.")
    contractor = login["contractors"][0]
    portal_session = rpc("/web/session/authenticate", {
        "db": DATABASE, "login": contractor["login"], "password": contractor["password"],
    })
    if not portal_session.get("uid"):
        raise SystemExit("Generated contractor login did not work.")
    with opener.open("http://127.0.0.1:8069/my/field-work", timeout=30) as response:
        if response.status != 200 or "עבודות השטח שלי" not in response.read().decode():
            raise SystemExit("The contractor portal did not render.")
    # Reproduce an existing pilot from before the pricing role was introduced.
    # The next initialization must restore ownership without relying on XML
    # updates to base.user_admin, whose external ID is marked noupdate.
    subprocess.run([
        "odoo", "shell", "-c", str(LOCAL / "odoo.conf"), "-d", DATABASE, "--no-http",
    ], input="""
admin = env.ref('base.user_admin')
admin.write({'groups_id': [(3, env.ref('field_work_photos.group_field_finance').id)]})
env['ir.model.data'].search([('module', '=', 'base'), ('name', '=', 'user_admin')]).write({'noupdate': True})
assert not admin.has_group('field_work_photos.group_field_finance')
env.cr.commit()
""", text=True, check=True)
    restart()
    for attempt in range(120):
        try:
            with opener.open("http://127.0.0.1:8069/web/login", timeout=3) as response:
                if response.status == 200:
                    break
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(1)
    else:
        raise SystemExit("Pilot did not restart successfully.")
    session = rpc("/web/session/authenticate", {
        "db": DATABASE, "login": login["login"], "password": login["password"],
    })
    if not session.get("uid"):
        raise SystemExit("Generated credentials did not survive restart.")
    if not has_owner_role(session["uid"]):
        raise SystemExit("Restart did not restore the pricing-owner role for the existing pilot administrator.")
    remaining = rpc("/web/dataset/call_kw/project.task/search_count", {
        "model": "project.task", "method": "search_count",
        "args": [[["field_report_required", "=", True]]], "kwargs": {},
    })
    if remaining != count:
        raise SystemExit("Pilot tasks changed unexpectedly during restart.")
    print("PASS: startup, generated admin and contractor logins, Hebrew, sample task/lead, portal, reviewer/owner roles and restart restoring existing-admin ownership while preserving data.")


if __name__ == "__main__":
    commands = {"start": start, "worker": worker, "status": status, "restart": restart, "test": test, "smoke": smoke}
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command not in commands:
        raise SystemExit("Usage: python3 scripts/pilot.py [start|status|restart|test|smoke]")
    commands[command]()
