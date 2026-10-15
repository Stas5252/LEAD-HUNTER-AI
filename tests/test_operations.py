import json,sys,unittest,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
class OperationsTests(unittest.TestCase):
 def test_worker_image_and_media_persistence_are_deployable(self):
  d=json.loads(subprocess.check_output(['docker','compose','--profile','workers','--profile','telegram','config','--format','json'],cwd=ROOT))
  self.assertIn('worker',tuple(d['services']),'durable adapter service required');self.assertIn('telegram',tuple(d['services']))
  self.assertTrue(any('/data/media'==v['target'] for v in d['services']['worker']['volumes']))
  self.assertTrue((ROOT/'Dockerfile.worker').is_file())
 def test_importer_backs_up_existing_stable_workflows(self):
  self.assertIn('backup_workflows', (ROOT/'scripts/import-workflows.py').read_text(),'backup must happen before import')
if __name__=='__main__':unittest.main()
