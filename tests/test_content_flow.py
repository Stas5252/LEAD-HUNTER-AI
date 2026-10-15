import json,sys,unittest,time,hashlib,hmac
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import sql,literal,config
from telegram_transport import N8N,settings
class ContentFlowTests(unittest.TestCase):
 def test_content_and_media_routes_owner_controls(self):
  n=N8N(settings());original=sql('SELECT admin_id FROM app_settings WHERE id=true;')
  try:
   sql('UPDATE app_settings SET admin_id=123 WHERE id=true;')
   self.assertEqual(n.post('lh-content',{'action':'list','user_id':999})['status'],'FORBIDDEN')
   self.assertIn('items',n.post('lh-content',{'action':'list','user_id':123}))
   self.assertIn('assets',n.post('lh-media',{'action':'list','user_id':123}))
  finally:sql('UPDATE app_settings SET admin_id='+('NULL' if not original else original)+' WHERE id=true;')
if __name__=='__main__':unittest.main()
