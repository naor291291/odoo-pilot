"""Synthetic PostgreSQL 16 integration. Run only against disposable CI database."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import psycopg2
import startup as s

@unittest.skipUnless(os.environ.get('CLOADY_SYNTHETIC_TEST') == '1', 'Disposable PostgreSQL required')
class DatabaseTests(unittest.TestCase):
    def test_lease_backup_restore(self):
        cfg=dict(db_host='127.0.0.1', db_port='5432', db_user='odoo',
                 db_password='synthetic_ci_only', db_name='release_test', db_sslmode='disable')
        conn=psycopg2.connect(host=cfg['db_host'],port=cfg['db_port'],user=cfg['db_user'],password=cfg['db_password'],dbname=cfg['db_name'])
        conn.autocommit=True
        other=None
        try:
            with conn.cursor() as cur:
                cur.execute('CREATE TABLE ir_attachment(id int,store_fname text,checksum text)')
                cur.execute('CREATE TABLE ir_module_module(name text,state text,latest_version text)')
                cur.execute("INSERT INTO ir_module_module VALUES ('field_work_photos','installed','18.0.17.0.2')")
                cur.execute('SELECT pg_try_advisory_lock(%s,%s)',s.LOCK)
                self.assertTrue(cur.fetchone()[0])
            other=psycopg2.connect(host=cfg['db_host'],user=cfg['db_user'],password=cfg['db_password'],dbname=cfg['db_name'])
            other.autocommit=True
            with other.cursor() as cur:
                cur.execute('SELECT pg_try_advisory_lock(%s,%s)',s.LOCK)
                self.assertFalse(cur.fetchone()[0])
            with self.assertRaises(s.Stop): s.assert_quiet(conn)
            other.close(); other=None
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder); cfg['data_dir']=folder
                store=root/'filestore'/'release_test'; store.mkdir(parents=True)
                payload=b'%PDF-1.4 synthetic attachment'; checksum=hashlib.sha1(payload).hexdigest()
                name=checksum[:2]+'/'+checksum; (store/checksum[:2]).mkdir(); (store/name).write_bytes(payload)
                with conn.cursor() as cur: cur.execute('INSERT INTO ir_attachment VALUES (1,%s,%s)',(name,checksum))
                backup=s.backup(conn,cfg,root,'18.0.17.0.2','18.0.18.0.0','synthetic-previous-image')
                manifest=json.loads((backup/'manifest.json').read_text())
                self.assertFalse(manifest['restore_tested'])
                self.assertEqual(manifest['attachment_checks'],[[1,name,checksum]])
                env=dict(os.environ,PGHOST=cfg['db_host'],PGUSER=cfg['db_user'],PGPASSWORD=cfg['db_password'])
                subprocess.run([str(s.PG_BIN/'createdb'),'restore_test'],env=env,check=True)
                subprocess.run([str(s.PG_BIN/'pg_restore'),'--exit-on-error','--no-owner','--no-acl','-d','restore_test',str(backup/'database.dump')],env=env,check=True)
                restored=psycopg2.connect(host=cfg['db_host'],user=cfg['db_user'],password=cfg['db_password'],dbname='restore_test')
                try:
                    self.assertEqual(s.module_state(restored),('installed','18.0.17.0.2'))
                    with restored.cursor() as cur:
                        cur.execute('SELECT store_fname,checksum FROM ir_attachment'); rows=cur.fetchall()
                    with tarfile.open(backup/'filestore.tar') as archive:
                        for restored_name,expected in rows:
                            data=archive.extractfile('filestore/release_test/'+restored_name).read()
                            self.assertEqual(hashlib.sha1(data).hexdigest(),expected)
                finally: restored.close()
                (store/name).write_bytes(b'corrupt')
                with self.assertRaisesRegex(s.Stop,'checksum mismatch'):
                    s.backup(conn,cfg,root,'old','new','previous')
        finally:
            if other: other.close()
            conn.close()

if __name__=='__main__': unittest.main()
