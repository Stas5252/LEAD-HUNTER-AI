import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import sql,literal

class SourcesDBTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(sql("SELECT count(*) FROM pg_proc WHERE proname='enqueue_connector';"),'1','durable source queue required')
    def test_stop_blocks_queue_and_duplicate_key_does_not_duplicate_job(self):
        q="""BEGIN; UPDATE app_settings SET stopped=false; SELECT enqueue_connector('partners','{"records":[]}', 'test:source'); SELECT enqueue_connector('partners','{"records":[]}', 'test:source'); SELECT count(*) FROM connector_jobs WHERE dedupe_key='test:source'; UPDATE app_settings SET stopped=true; SELECT enqueue_connector('partners','{}','test:stopped'); ROLLBACK;"""
        r=sql(q).splitlines();self.assertEqual(r[-2],'1');self.assertIn('STOPPED',r[-1])
    def test_allowed_chat_edit_keeps_identity_and_atomic_offset(self):
        u={'update_id':9000001,'channel_post':{'message_id':12,'chat':{'id':-100555,'username':'test_channel','title':'Тест'},'date':1792051200,'text':'Нужен сайт'}}
        v={'update_id':9000002,'edited_channel_post':{**u['channel_post'],'text':'Нужен сайт с каталогом'}}
        q=f"BEGIN; UPDATE app_settings SET stopped=false; INSERT INTO monitored_chats(chat_id) VALUES(-100555); SELECT monitor_update({literal(u)}::jsonb); SELECT monitor_update({literal(u)}::jsonb); SELECT monitor_update({literal(v)}::jsonb); SELECT jsonb_build_object('count',count(*),'ids',jsonb_agg(payload->0->>'external_id')) FROM import_requests WHERE origin='telegram_monitor'; ROLLBACK;"
        rows=sql(q).splitlines();result=json.loads(rows[-1]);self.assertEqual(result['count'],2);self.assertEqual(result['ids'][0],result['ids'][1])
    def test_unauthorized_chat_does_not_enqueue(self):
        u={'update_id':9000003,'message':{'message_id':1,'chat':{'id':-100999},'text':'Нужен сайт'}}
        r=sql(f"BEGIN;SELECT monitor_update({literal(u)}::jsonb);ROLLBACK;")
        self.assertIn('ignored',r)

if __name__=='__main__':unittest.main()
