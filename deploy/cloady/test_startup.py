"""Focused deployment safety regressions; no Odoo or production connections."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import startup as s

class StartupTests(unittest.TestCase):
    def test_maintenance_returns_before_config_database_or_odoo(self):
        with patch.dict(os.environ, {'ODOO_MAINTENANCE':'1'}, clear=True), patch.object(s,'maintenance') as hold, patch.object(s.importlib.util,'spec_from_file_location') as config, patch.object(s.subprocess,'Popen') as child:
            s.main()
        hold.assert_called_once(); config.assert_not_called(); child.assert_not_called()
    def test_invalid_maintenance_fails_closed(self):
        with patch.dict(os.environ, {'ODOO_MAINTENANCE':'yes'}), patch.object(s,'maintenance') as hold:
            with self.assertRaises(s.Stop): s.main()
        hold.assert_not_called()
    def test_same_version_serves(self):
        self.assertEqual(s.decision(('installed','18.0.18.0.0'),'18.0.18.0.0',False),'serve')
    def test_upgrade(self):
        self.assertEqual(s.decision(('installed','18.0.17.0.2'),'18.0.18.0.0',False),'upgrade')
    def test_pending_even_after_success_blocks(self):
        with self.assertRaises(s.Stop): s.decision(('installed','18.0.18.0.0'),'18.0.18.0.0',True)
    def test_missing_database_module_blocks(self):
        with self.assertRaises(s.Stop): s.decision(None,'18.0.18.0.0',False)
    def test_downgrade_blocks(self):
        with self.assertRaises(s.Stop): s.decision(('installed','18.0.19.0.0'),'18.0.18.0.0',False)
    def test_partial_state_blocks(self):
        with self.assertRaises(s.Stop): s.decision(('to upgrade','18.0.17.0.2'),'18.0.18.0.0',False)
    def test_invalid_version(self):
        for value in ('19.0.1.0', '18.0.1;echo secret', '', None):
            with self.assertRaises(s.Stop): s.version(value)
    def test_manifest_fingerprint_and_version(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'__manifest__.py').write_text("{'version':'18.0.18.0.0'}")
            before=s.target(root); (root/'model.py').write_text('change')
            self.assertEqual(before[0], '18.0.18.0.0')
            self.assertNotEqual(before[1], s.target(root)[1])
    def test_exclusive_private_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'attempt.json'; s.private_json(path, {'target':'test'}, True)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError): s.private_json(path, {}, True)
            self.assertEqual(json.loads(path.read_text()), {'target':'test'})
    def test_competing_connection_blocks(self):
        conn=MagicMock(); conn.cursor.return_value.__enter__.return_value.fetchone.return_value=(1,)
        with self.assertRaises(s.Stop): s.assert_quiet(conn)
    def test_prepared_transaction_blocks(self):
        conn=MagicMock(); conn.cursor.return_value.__enter__.return_value.fetchone.side_effect=[(0,),(1,)]
        with self.assertRaises(s.Stop): s.assert_quiet(conn)
    def test_quiet(self):
        conn=MagicMock(); conn.cursor.return_value.__enter__.return_value.fetchone.side_effect=[(0,),(0,)]
        s.assert_quiet(conn)
    def test_failed_child_stops(self):
        child=MagicMock(returncode=1); child.poll.return_value=1
        with patch.object(s.subprocess,'Popen',return_value=child):
            with self.assertRaises(s.Stop): s.run_child(['unused'],{},MagicMock())
    def test_lease_loss_stops_child(self):
        child=MagicMock(); child.poll.side_effect=[None,1]
        conn=MagicMock(); conn.cursor.side_effect=RuntimeError('do not leak secret')
        with patch.object(s.subprocess,'Popen',return_value=child):
            with self.assertRaisesRegex(s.Stop,'lease lost'): s.run_child(['unused'],{},conn)
        child.terminate.assert_called_once()
    def test_sigterm_during_upgrade_cannot_start_server(self):
        child=MagicMock(returncode=0); child.poll.side_effect=[None,0,0]
        handlers={}
        def register(sig, fn):
            handlers[sig]=fn
        def terminate(_): handlers[signal.SIGTERM](signal.SIGTERM,None)
        with patch.object(s.subprocess,'Popen',return_value=child), patch.object(s.signal,'signal',side_effect=register), patch.object(s.time,'sleep',side_effect=terminate):
            with self.assertRaisesRegex(s.Stop,'Termination requested'): s.run_child(['unused'],{},MagicMock())
    def test_backup_disk_headroom_blocks_before_dump(self):
        conn=MagicMock(); conn.cursor.return_value.__enter__.return_value.fetchone.return_value=(100,)
        with tempfile.TemporaryDirectory() as folder, patch.object(s,'assert_quiet'), patch.object(s.shutil,'disk_usage',return_value=MagicMock(free=0)), patch.object(s.subprocess,'run') as run:
            with self.assertRaisesRegex(s.Stop,'headroom'): s.backup(conn,{'data_dir':folder,'db_name':'test'},Path(folder),'old','new','sha-old')
            run.assert_not_called()

if __name__=='__main__': unittest.main()
