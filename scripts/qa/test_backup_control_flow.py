"""Exercise backup failure handling with fake docker/restic; never touch services."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FAKE = '''#!/usr/bin/env python3
import os,sys
from pathlib import Path
args=' '.join(sys.argv[1:]);name=Path(sys.argv[0]).name
with open(os.environ['QA_CALLS'],'a') as f:f.write(name+' '+args+'\\n')
scenario=os.environ['QA_SCENARIO']
if name=='docker':
 if 'ps --status' in args:
  if scenario!='not_running': print('synthetic-container')
 elif 'pg_dump' in args:
  if scenario=='dump_fails':sys.exit(2)
  print('synthetic-dump')
 elif '--entrypoint tar' in args:
  if scenario=='filestore_fails':sys.exit(2)
  print('synthetic-filestore')
else:
 if args.startswith('snapshots') and scenario=='repository_fails':sys.exit(2)
 if args.startswith('backup') and scenario=='upload_fails':sys.exit(2)
'''


class BackupControlFlowTests(unittest.TestCase):
    def run_case(self, scenario, repository='s3:synthetic.invalid/qa'):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);binpath=root/'bin';binpath.mkdir()
            shutil.copy(ROOT/'deploy/backup.sh',root/'backup.sh')
            for tool in ('docker','restic'):
                p=binpath/tool;p.write_text(FAKE);p.chmod(0o700)
            env={**os.environ,'PATH':str(binpath)+':'+os.environ['PATH'],
                 'QA_CALLS':str(root/'calls'),'QA_SCENARIO':scenario,'RESTIC_REPOSITORY':repository}
            result=subprocess.run(['bash',str(root/'backup.sh')],env=env,capture_output=True,timeout=10)
            calls=(root/'calls').read_text() if (root/'calls').exists() else ''
            return result.returncode,calls

    def test_success_restarts_before_upload(self):
        code,calls=self.run_case('success');self.assertEqual(code,0)
        self.assertLess(calls.index('start odoo'),calls.index('restic backup'))
        self.assertIn('pg_dump',calls);self.assertIn('filestore/field_crm',calls)

    def test_dump_failure_restarts_and_does_not_upload(self):
        code,calls=self.run_case('dump_fails');self.assertNotEqual(code,0)
        self.assertIn('start odoo',calls);self.assertNotIn('restic backup',calls)

    def test_filestore_failure_restarts_and_does_not_upload(self):
        code,calls=self.run_case('filestore_fails');self.assertNotEqual(code,0)
        self.assertIn('start odoo',calls);self.assertNotIn('restic backup',calls)

    def test_upload_failure_is_reported_after_restart(self):
        code,calls=self.run_case('upload_fails');self.assertNotEqual(code,0)
        self.assertLess(calls.index('start odoo'),calls.index('restic backup'))

    def test_unavailable_repository_never_stops_application(self):
        code,calls=self.run_case('repository_fails');self.assertNotEqual(code,0)
        self.assertNotIn('stop odoo',calls)

    def test_stopped_application_is_not_started_by_backup(self):
        code,calls=self.run_case('not_running');self.assertNotEqual(code,0)
        self.assertNotIn('stop odoo',calls);self.assertNotIn('start odoo',calls)

    def test_local_repository_rejected_before_any_command(self):
        code,calls=self.run_case('success','/tmp/not-offsite');self.assertNotEqual(code,0)
        self.assertEqual(calls,'')


if __name__=='__main__':unittest.main()
