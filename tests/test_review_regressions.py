import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import sql
from publishers import PostizClient,AmbiguousPublish
from media_factory import synthetic_demo,render_video
from telegram_transport import BotAPI
class ReviewRegressions(unittest.TestCase):
 def test_lost_post_response_protocol_error_is_ambiguous(self):
  def handler(req):raise httpx.RemoteProtocolError('server disconnected')
  c=PostizClient('https://postiz.example.org/api/public/v1','test-key',transport=httpx.MockTransport(handler))
  with self.assertRaises(AmbiguousPublish):c.publish({'channel':'threads','text':'Тест','integration_id':'own','due_at':'2026-10-15T12:00:00Z'},[])
 def test_disabling_account_blocks_final_send_check(self):
  result=sql("""BEGIN;UPDATE app_settings SET stopped=false;INSERT INTO publishing_accounts VALUES('disabled-check','threads','remote',false,'{}');INSERT INTO content_items(account_id,text,state,approved_version,lease_token) VALUES('disabled-check','text','PUBLISHING',1,'00000000-0000-4000-8000-000000000123');SELECT content_action(jsonb_build_object('action','check','content_id',content_id,'lease_token',lease_token)) FROM content_items WHERE account_id='disabled-check';ROLLBACK;""")
  self.assertFalse(json.loads(result.splitlines()[-1])['allowed'])
 def test_threads_cursor_is_consumed_on_next_scheduled_run(self):
  result=sql("""BEGIN;UPDATE app_settings SET stopped=false;UPDATE connector_configs SET enabled=true,config='{"query":"Нужен сайт"}',cursor='{"after":"next-page"}',last_enqueued_at=NULL WHERE source_type='threads_search';SELECT enqueue_configured('threads_search');SELECT config->>'after' FROM connector_jobs WHERE source_type='threads_search' ORDER BY created_at DESC LIMIT 1;ROLLBACK;""")
  self.assertEqual(result.splitlines()[-1],'next-page')
 def test_derived_video_cannot_erase_demo_provenance(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);source=synthetic_demo(root);result=render_video({'scenes':[{'asset_id':source['asset_id'],'seconds':.5,'caption':'Тест'}],'is_demo':False},root)
   self.assertTrue(result['is_demo'])
 def test_malformed_media_acceptance_response_is_uncertain(self):
  from media_factory import render_carousel
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);r=render_carousel({'title':'Test','cards':['Test']*5,'is_demo':True},root);api=BotAPI('test-key');api.media_root=root
   with patch('httpx.Client') as C:
    C.return_value.__enter__.return_value.post.return_value=httpx.Response(200,text='broken json')
    self.assertEqual(api.send({'chat_id':1,'_asset_ids':[a['asset_id'] for a in r['assets']]},'sendMediaGroup')['state'],'UNCERTAIN')
if __name__=='__main__':unittest.main()
