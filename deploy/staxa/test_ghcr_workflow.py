"""Local workflow contract tests; PyYAML is a validation-only dependency.

Mocked Docker verifies orchestration, not an image build or registry publication.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = yaml.load((ROOT / '.github/workflows/staxa-ghcr.yml').read_text(), Loader=yaml.BaseLoader)
STEPS = WORKFLOW['jobs']['publish']['steps']


class WorkflowTests(unittest.TestCase):
    def test_manual_and_permissions(self):
        self.assertEqual(set(WORKFLOW['on']), {'workflow_dispatch'})
        job = WORKFLOW['jobs']['publish']
        self.assertEqual(job['permissions'], {'contents': 'read', 'packages': 'write'})
        self.assertEqual(job['if'], "github.event_name == 'workflow_dispatch'")
        text = str(WORKFLOW)
        self.assertNotIn(':latest', text)
        self.assertNotIn('--build-arg', text)
        self.assertIn('secrets.GITHUB_TOKEN', text)
        self.assertEqual(STEPS[-1]['if'], 'always()')

    def exercise(self, failure=''):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            docker = path / 'docker'
            docker.write_text('''#!/bin/bash
set -eu
printf '%s\\n' "$*" >> "$TRACE"
if [ "$1" = build ]; then
  test -z "${GHCR_TOKEN:-}"
  test "$PWD" = "$REPO_ROOT"
  test "${!#}" = .
fi
if [ "$1" = login ]; then
  read -r token || true
  test "$token" = synthetic_test_token
fi
if [ "$1" = "$FAILURE" ]; then exit 1; fi
if [ "$1" = manifest ]; then echo '{}'; fi
''')
            docker.chmod(0o755)
            env = dict(os.environ, PATH=td + ':' + os.environ['PATH'], TRACE=td+'/trace',
                       FAILURE=failure, REPO_ROOT=str(ROOT), DOCKER_CONFIG=td+'/auth',
                       RUNNER_TEMP=td, GITHUB_OUTPUT=td+'/output', GITHUB_STEP_SUMMARY=td+'/summary',
                       REPOSITORY='Example/Odoo', COMMIT_SHA='a'*40)
            failed = False
            for step in STEPS[2:]:
                if failed and step.get('if') != 'always()':
                    continue
                step_env = dict(env)
                if step['name'] == 'Authenticate to GHCR':
                    step_env.update(GHCR_TOKEN='synthetic_test_token', GHCR_ACTOR='test')
                result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', step['run']],
                                        cwd=ROOT, env=step_env, capture_output=True)
                failed |= result.returncode != 0
                if (path/'output').exists():
                    env['IMAGE'] = (path/'output').read_text().strip().removeprefix('ref=')
            trace = (path/'trace').read_text()
            summary = (path/'summary').read_text() if (path/'summary').exists() else ''
            self.assertFalse((path/'auth').exists())
            return trace, summary, failed

    def test_success_reports_only_after_manifest(self):
        trace, summary, failed = self.exercise()
        self.assertFalse(failed)
        self.assertEqual([line.split()[0] for line in trace.splitlines()], ['build', 'login', 'push', 'manifest'])
        self.assertIn('sha-' + 'a'*40, summary)
        self.assertIn('--file deploy/staxa/Dockerfile', trace)

    def test_build_failure_prevents_login_and_push(self):
        trace, summary, failed = self.exercise('build')
        self.assertTrue(failed)
        self.assertNotIn('login', trace)
        self.assertNotIn('push', trace)
        self.assertEqual(summary, '')

    def test_push_failure_does_not_report_success(self):
        trace, summary, failed = self.exercise('push')
        self.assertTrue(failed)
        self.assertNotIn('manifest', trace)
        self.assertEqual(summary, '')

    def test_manifest_failure_does_not_report_success(self):
        _, summary, failed = self.exercise('manifest')
        self.assertTrue(failed)
        self.assertEqual(summary, '')


if __name__ == '__main__':
    unittest.main()
