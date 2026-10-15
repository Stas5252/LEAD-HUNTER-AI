import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import sql
class MediaFlowTests(unittest.TestCase):
 def setUp(self):self.assertEqual(sql("SELECT count(*) FROM pg_proc WHERE proname='media_action';"),'1','durable render jobs required')
 def test_queue_requires_owner_and_explicit_asset_rights(self):
  self.assertIn('FORBIDDEN',sql("BEGIN;UPDATE app_settings SET admin_id=123;SELECT media_action('{\"action\":\"list\",\"user_id\":999}');ROLLBACK;"))
 def test_stop_blocks_media_claim(self):
  self.assertIn('STOPPED',sql("BEGIN;UPDATE app_settings SET stopped=true;SELECT media_action('{\"action\":\"claim\"}');ROLLBACK;"))
 def test_missing_or_revoked_asset_blocks_approval(self):
  r=sql("""BEGIN;UPDATE app_settings SET admin_id=123,stopped=false;INSERT INTO publishing_accounts VALUES('media-test','instagram','remote',true,'{}');SELECT content_action('{"action":"create","user_id":123,"account_id":"media-test","text":"Текст","media_ids":["missing"]}');SELECT content_action(jsonb_build_object('action','approve','user_id',123,'content_id',content_id,'version',version)) FROM content_items WHERE account_id='media-test';ROLLBACK;""")
  self.assertIn('MEDIA_RIGHTS_REQUIRED',r)
if __name__=='__main__':unittest.main()

class MediaEndToEndTests(unittest.TestCase):
 def test_real_n8n_queue_renderer_and_owner_preview_outbox(self):
  import tempfile
  from connector_worker import run_media
  from telegram_transport import N8N,settings
  cfg=settings();n=N8N(cfg);original=sql('SELECT admin_id FROM app_settings WHERE id=true;')
  job=None;assets=[]
  try:
   sql('UPDATE app_settings SET admin_id=123 WHERE id=true;')
   job=n.post('lh-media',{'action':'enqueue','kind':'carousel','user_id':123,'spec':{'title':'DEMO queue integration','cards':['DEMO test '+str(i) for i in range(5)],'cta':'stanislavweb.ru','is_demo':True}})
   with tempfile.TemporaryDirectory() as t:self.assertTrue(run_media(n,Path(t)))
   state=json.loads(sql(f"SELECT to_jsonb(j) FROM media_jobs j WHERE job_id='{job['job_id']}';"))
   self.assertEqual(state['state'],'DONE');assets=[a['asset_id'] for a in state['result']['assets']]
   payload=json.loads(sql(f"SELECT payload FROM notification_outbox WHERE dedupe_key='media:{job['job_id']}';"))
   self.assertEqual(payload['data']['_method'],'sendMediaGroup');self.assertEqual(len(payload['data']['_asset_ids']),5)
   self.assertIn('не одобрена',payload['data']['caption'])
  finally:
   if job and job.get('job_id'):sql(f"DELETE FROM notification_outbox WHERE dedupe_key='media:{job['job_id']}';DELETE FROM media_jobs WHERE job_id='{job['job_id']}';")
   for asset in assets:sql(f"DELETE FROM media_assets WHERE asset_id='{asset}';")
   sql('UPDATE app_settings SET admin_id='+('NULL' if not original else original)+' WHERE id=true;')
