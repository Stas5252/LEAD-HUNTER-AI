import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SetupTests(unittest.TestCase):
    def test_injected_runtime_variables_override_blank_file_bindings(self):
        import sys
        from unittest.mock import patch
        sys.path.insert(0,str(ROOT/'scripts'))
        from common import config
        with patch.dict(os.environ,{'TELEGRAM_ADMIN_ID':'123456'}):
            self.assertEqual(config()['TELEGRAM_ADMIN_ID'],'123456')

    def test_setup_generates_secrets_once_and_preserves_existing_file(self):
        script = ROOT / 'scripts/setup.py'
        self.assertTrue(script.is_file(), 'setup script is required')
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / '.env'
            subprocess.run(['python3', str(script), '--env-file', str(target)], check=True)
            first = target.read_text()
            self.assertIn('APP_DB_PASSWORD=', first)
            self.assertIn('N8N_ENCRYPTION_KEY=', first)
            self.assertNotIn('changeme', first)
            subprocess.run(['python3', str(script), '--env-file', str(target)], check=True)
            self.assertEqual(first, target.read_text())
            if os.name != 'nt':
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_compose_is_valid(self):
        self.assertTrue((ROOT / 'docker-compose.yml').is_file())
        subprocess.run(['docker', 'compose', 'config', '--quiet'], cwd=ROOT, check=True)


class DatabaseTests(unittest.TestCase):
    def test_application_has_no_superuser_or_n8n_database_access(self):
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        from common import sql
        self.assertEqual(sql("SELECT rolsuper FROM pg_roles WHERE rolname=current_user;"), 'f')
        self.assertEqual(sql("SELECT has_database_privilege(current_user,'n8n','CONNECT');"), 'f')
        self.assertEqual(sql("SELECT count(*) FROM schema_migrations;"), str(len(list((ROOT/'migrations').glob('*.sql')))))


if __name__ == '__main__':
    unittest.main()
