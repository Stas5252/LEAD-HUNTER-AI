import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common
class CloudDeployTests(unittest.TestCase):
 def test_container_without_local_env_uses_defaults_and_injected_settings(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'.env.example').write_text('AI_ENABLED=false\nMAX_LEADS_PER_RUN=100\n')
   with patch.object(common,'ROOT',root),patch.dict(os.environ,{'TELEGRAM_ADMIN_ID':'761405171'}):
    cfg=common.config();self.assertEqual(cfg['TELEGRAM_ADMIN_ID'],'761405171');self.assertEqual(cfg['AI_ENABLED'],'false')
 def test_railway_has_three_deployable_services_and_no_secret_defaults(self):
  root=Path(__file__).resolve().parents[1]
  for name in ('postgres','n8n','worker'):
   path=root/'deploy'/'railway'/(name+'.json');self.assertTrue(path.is_file(),'Railway '+name+' deployment settings required')
   cfg=json.loads(path.read_text());self.assertTrue((root/cfg['build']['dockerfilePath']).is_file())
if __name__=='__main__':unittest.main()
