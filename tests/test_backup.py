import json
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import sql


class BackupTests(unittest.TestCase):
    def test_restore_into_new_database_preserves_leads_and_migrations(self):
        result=subprocess.run(['python3','scripts/backup.py'],cwd=ROOT,check=True,capture_output=True,text=True)
        folder=Path(result.stdout.splitlines()[0]);db='lh_restore_'+uuid4().hex[:12]
        expected=sql('SELECT count(*) FROM leads;')
        try:
            subprocess.run(['python3','scripts/restore.py','--backup',str(folder/'lead_hunter.sql'),'--database',db],cwd=ROOT,check=True,capture_output=True)
            self.assertEqual(sql('SELECT count(*) FROM leads;',database=db),expected)
            self.assertEqual(sql('SELECT count(*) FROM schema_migrations;',database=db),sql('SELECT count(*) FROM schema_migrations;'))
            again=subprocess.run(['python3','scripts/restore.py','--backup',str(folder/'lead_hunter.sql'),'--database',db],cwd=ROOT,capture_output=True)
            self.assertNotEqual(again.returncode,0,'existing database must never be overwritten')
        finally:
            sql(f'DROP DATABASE IF EXISTS {db};',admin=True)


if __name__=='__main__':unittest.main()
