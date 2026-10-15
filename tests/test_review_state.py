import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import sql,literal
try:from credential_policy import should_replace
except ImportError:should_replace=None
class ReviewStateTests(unittest.TestCase):
 def test_placeholder_does_not_replace_existing_configured_credential(self):
  self.assertIsNotNone(should_replace,'credential replacement policy required')
  self.assertFalse(should_replace('lh-openai',False,{'lh-openai'}));self.assertTrue(should_replace('lh-openai',True,{'lh-openai'}));self.assertTrue(should_replace('lh-openai',False,set()))
 def test_short_telegram_edit_revokes_existing_approval(self):
  u={'update_id':9000456,'edited_channel_post':{'message_id':12,'chat':{'id':-100555,'username':'test_channel','title':'Тест'},'date':1792051200,'text':'ok'}}
  key=sql("SELECT encode(digest('real:external:telegram_monitor:-100555:12','sha256'),'hex');")
  lead={'dedupe_key':key,'source':'telegram_monitor','source_type':'telegram_monitor','source_url':'https://t.me/test_channel/12','company_name':'Тест','proof_quote':'Нужен сайт','content_hash':'test','classification':'DIRECT_REQUEST','score_0_100':80,'confidence_0_1':.8,'why_relevant':'Запрос','offer_type':'Сайт','draft_message':'КП','is_demo':True}
  result=sql(f"BEGIN;UPDATE app_settings SET stopped=false;INSERT INTO monitored_chats(chat_id) VALUES(-100555);SELECT ingest_batch({literal([lead])}::jsonb);UPDATE leads SET owner_approved=true,status='APPROVED' WHERE dedupe_key={literal(key)};SELECT monitor_update({literal(u)}::jsonb);SELECT jsonb_build_object('approved',owner_approved,'status',status,'score',score_0_100,'draft',draft_message) FROM leads WHERE dedupe_key={literal(key)};ROLLBACK;")
  state=json.loads(result.splitlines()[-1]);self.assertFalse(state['approved']);self.assertEqual(state['status'],'REVIEW');self.assertLess(state['score'],40);self.assertEqual(state['draft'],'')
if __name__=='__main__':unittest.main()

class RightsLockTest(unittest.TestCase):
 def test_revoke_committing_before_final_check_makes_check_false(self):
  from concurrent.futures import ThreadPoolExecutor
  import time
  from uuid import uuid4
  token=str(uuid4());account='lock-'+uuid4().hex;asset=uuid4().hex*2
  before=sql('SELECT admin_id FROM app_settings WHERE id=true;')
  content=None
  try:
   sql(f"UPDATE app_settings SET admin_id=123;INSERT INTO publishing_accounts VALUES('{account}','threads','remote',true,'{{}}');INSERT INTO media_assets(asset_id,manifest) VALUES('{asset}','{{\"rights\":{{\"kind\":\"own\",\"grant\":\"test\"}}}}');")
   content=sql(f"INSERT INTO content_items(account_id,text,media_ids,state,approved_version,lease_token) VALUES('{account}','Тест','[\"{asset}\"]','PUBLISHING',1,'{token}') RETURNING content_id;")
   with ThreadPoolExecutor(max_workers=2) as pool:
    revoke=pool.submit(sql,f"BEGIN;SELECT id FROM app_settings WHERE id=true FOR UPDATE;SELECT pg_sleep(2);SELECT media_action('{{\"action\":\"revoke\",\"user_id\":123,\"asset_id\":\"{asset}\"}}');COMMIT;")
    time.sleep(.3)
    result=sql(f"SELECT content_action('{{\"action\":\"check\",\"content_id\":\"{content}\",\"lease_token\":\"{token}\"}}');")
    revoke.result()
   self.assertFalse(json.loads(result)['allowed'])
  finally:
   if content:sql(f"DELETE FROM content_events WHERE content_id='{content}';DELETE FROM content_items WHERE content_id='{content}';")
   sql(f"DELETE FROM publishing_accounts WHERE account_id='{account}';DELETE FROM media_assets WHERE asset_id='{asset}';UPDATE app_settings SET admin_id={before or 'NULL'};")
