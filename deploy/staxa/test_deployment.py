"""Focused configuration tests only: no Odoo database or external services."""
import configparser
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

entry = load('staxa_entrypoint', 'entrypoint.py')
generator = load('staxa_generator', 'generate_dockerfile.py')


class DeploymentTests(unittest.TestCase):
    def env(self):
        return dict(DB_HOST='db.invalid', DB_PORT='5432', DB_USER='pilot_role',
                    DB_PASSWORD='synthetic-%-secret', DB_NAME='pilot_test',
                    ODOO_ADMIN_PASSWORD='synthetic-master-' * 3)

    def test_inherits_exact_security_runtime(self):
        self.assertEqual((HERE / 'Dockerfile').read_text(), generator.generated())
        self.assertIn('FROM runtime AS staxa', generator.generated())

    def test_root_context_and_port(self):
        settings = json.loads((HERE / 'settings.example.json').read_text())
        self.assertEqual(settings['build_context'], '.')
        self.assertEqual(settings['app_port'], 8069)
        self.assertEqual(settings['dockerfile_path'], 'deploy/staxa/Dockerfile')
        self.assertIn('COPY --chown=odoo:odoo addons/ /mnt/extra-addons/', generator.generated())
        self.assertIn('EXPOSE 8069', generator.generated())
        self.assertTrue((ROOT / 'addons/field_work_photos/__manifest__.py').is_file())

    def test_db_environment_mapping(self):
        config, mode = entry.settings(self.env())
        self.assertEqual((config['db_host'], config['db_user'], config['db_name']),
                         ('db.invalid', 'pilot_role', 'pilot_test'))
        self.assertEqual(config['db_password'], 'synthetic-%-secret')
        self.assertEqual(mode, 'serve')

    def test_url_percent_encoding_and_ipv6(self):
        config, _ = entry.settings(dict(DATABASE_URL='postgresql://pilot_role:p%40ss%25@[::1]:5433/pilot_test?sslmode=require',
                                       ODOO_ADMIN_PASSWORD='synthetic-master-' * 3))
        self.assertEqual((config['db_password'], config['db_host'], config['db_port']), ('p@ss%', '::1', '5433'))

    def test_complete_db_fields_override_url(self):
        env = self.env(); env['DATABASE_URL'] = 'not-a-url'
        self.assertEqual(entry.settings(env)[0]['db_name'], 'pilot_test')

    def test_partial_fields_fail_without_secret_output(self):
        env = self.env(); del env['DB_USER']; env['DATABASE_URL'] = 'postgresql://secret@other/db'
        with self.assertRaises(entry.ConfigurationError) as error: entry.settings(env)
        self.assertNotIn(env['DB_PASSWORD'], str(error.exception))
        self.assertNotIn('secret@', str(error.exception))

    def test_rejects_unsafe_input(self):
        for key, value in [('DB_PASSWORD', 'secret\nlist_db=True'), ('DB_PORT', '0'),
                           ('DB_NAME', 'db,other'), ('DB_SSLMODE', 'allow'),
                           ('DB_USER', 'postgres'), ('PORT', '8080'),
                           ('ODOO_ADMIN_PASSWORD', 'short'), ('STAXA_ODOO_MODE', 'upgrade')]:
            with self.subTest(key=key):
                env = self.env(); env[key] = value
                with self.assertRaises(entry.ConfigurationError): entry.settings(env)

    def test_url_rejects_unsupported_options_and_missing_password(self):
        for url in ['postgresql://u:p@db/x?options=-csecret', 'postgresql://u@db/x', 'https://u:p@db/x']:
            with self.subTest(url=url):
                with self.assertRaises(entry.ConfigurationError):
                    entry.settings(dict(DATABASE_URL=url, ODOO_ADMIN_PASSWORD='synthetic-' * 5))

    def test_private_config_preserves_literal_percent(self):
        config, _ = entry.settings(self.env())
        with tempfile.TemporaryDirectory() as folder:
            path = entry.write_config(config, folder)
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
            parser = configparser.RawConfigParser(); parser.read(path)
            self.assertEqual(parser['options']['db_password'], config['db_password'])

    def test_small_memory_profile_is_not_worker_limit_claim(self):
        config, _ = entry.settings(self.env())
        self.assertEqual((config['workers'], config['max_cron_threads'], config['db_maxconn']), ('0', '0', '8'))
        self.assertNotIn('limit_memory_hard', config)
        self.assertEqual(config['data_dir'], '/var/lib/odoo')
        self.assertEqual(config['list_db'], 'False')

    def test_exact_database_filter(self):
        env = self.env(); env['DB_NAME'] = 'pilot.test'
        self.assertEqual(entry.settings(env)[0]['dbfilter'], '^pilot\\.test$')

    def test_serve_never_installs_and_disables_live_channels(self):
        env = self.env(); env['FIELD_WORK_EMAIL_MODE'] = 'smtp'
        with patch.object(entry, 'write_config', return_value='/tmp/private.conf'):
            command, child = entry.launch(env)
        self.assertEqual(command, ['odoo', '--config', '/tmp/private.conf'])
        self.assertEqual(child['FIELD_WORK_EMAIL_MODE'], 'off')
        for key in ('DB_PASSWORD', 'DATABASE_URL', 'ODOO_ADMIN_PASSWORD'): self.assertNotIn(key, child)
        self.assertNotIn(env['DB_PASSWORD'], ' '.join(command))

    def test_explicit_init_installs_custom_module_and_exits(self):
        env = self.env(); env['STAXA_ODOO_MODE'] = 'init'
        with patch.object(entry, 'write_config', return_value='/tmp/private.conf'):
            command, _ = entry.launch(env)
        self.assertEqual(command[command.index('--init') + 1], 'field_work_photos')
        for flag in ('--stop-after-init', '--without-demo=all', '--no-http'): self.assertIn(flag, command)

    def test_invalid_startup_exits_redacted_before_odoo(self):
        env = self.env(); env['DB_PASSWORD'] = 'synthetic-secret\ninjection'
        result = subprocess.run([sys.executable, str(HERE / 'entrypoint.py')], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('synthetic-secret', result.stderr + result.stdout)


if __name__ == '__main__':
    unittest.main()
