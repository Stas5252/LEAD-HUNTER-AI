import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import sql,literal
class ContentDBTests(unittest.TestCase):
 def setUp(self):self.assertEqual(sql("SELECT count(*) FROM pg_proc WHERE proname='content_action';"),'1','versioned content queue required')
 def test_edit_revokes_approval_and_stop_blocks_claim(self):
  r=sql("""BEGIN;UPDATE app_settings SET admin_id=123,stopped=false;INSERT INTO publishing_accounts(account_id,channel,integration_id,enabled) VALUES('test-owner','threads','remote-1',true); SELECT content_action('{"action":"create","user_id":123,"account_id":"test-owner","text":"Первый текст","is_demo":true}');SELECT content_action(jsonb_build_object('action','approve','user_id',123,'content_id',content_id,'version',version)) FROM content_items WHERE account_id='test-owner';SELECT content_action(jsonb_build_object('action','edit','user_id',123,'content_id',content_id,'text','Новый текст')) FROM content_items WHERE account_id='test-owner';SELECT content_action(jsonb_build_object('action','schedule','user_id',123,'content_id',content_id,'version',1)) FROM content_items WHERE account_id='test-owner';UPDATE app_settings SET stopped=true;SELECT content_action('{"action":"claim"}');ROLLBACK;""").splitlines()
  self.assertIn('APPROVAL_REQUIRED',r[-2]);self.assertIn('STOPPED',r[-1])
 def test_nonowner_cannot_approve(self):
  self.assertIn('FORBIDDEN',sql("BEGIN;UPDATE app_settings SET admin_id=123;SELECT content_action('{\"action\":\"list\",\"user_id\":456}');ROLLBACK;"))
 def test_stale_delivery_becomes_uncertain(self):
  r=sql("""BEGIN;UPDATE app_settings SET stopped=false;INSERT INTO publishing_accounts VALUES('test-expired','threads','remote',true,'{}');INSERT INTO content_items(account_id,text,state,started_at,is_demo) VALUES('test-expired','text','PUBLISHING',now()-interval '20 minutes',true);SELECT content_action('{"action":"claim"}');SELECT state FROM content_items WHERE account_id='test-expired';ROLLBACK;""")
  self.assertIn('UNCERTAIN',r)
if __name__=='__main__':unittest.main()
