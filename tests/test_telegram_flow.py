import json
from pathlib import Path
import sys
import unittest
import urllib.request
import urllib.error
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import sql, literal, config


def post(path,body,authenticated=True):
    cfg=config()
    headers={'Content-Type':'application/json'}
    if authenticated:
        headers['X-Telegram-Bot-Api-Secret-Token']=cfg['TELEGRAM_WEBHOOK_SECRET']
    req=urllib.request.Request('http://127.0.0.1:'+cfg.get('N8N_PORT','5678')+'/webhook/'+path,
        data=json.dumps(body).encode(),headers=headers)
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)


class TelegramFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=sql('SELECT coalesce(admin_id::text,\'\') FROM app_settings WHERE id=true;')
        cls.old_offset=sql('SELECT telegram_offset FROM app_settings WHERE id=true;')
        cls.old_stopped=sql('SELECT stopped FROM app_settings WHERE id=true;')
        cls.original_outbox=json.loads(sql("SELECT coalesce(jsonb_agg(to_jsonb(notification_outbox)),'[]') FROM notification_outbox WHERE lead_id IS NOT NULL;"))
        # Never replace a real owner's binding in the default verification command.
        if cls.old and cls.old!='424242':
            raise unittest.SkipTest('Live owner configured: run tests in a separate Compose project')
        sql('UPDATE app_settings SET admin_id=424242,stopped=false WHERE id=true;')

    @classmethod
    def tearDownClass(cls):
        sql('UPDATE app_settings SET stopped='+('true' if cls.old_stopped=='t' else 'false')+',telegram_offset='+cls.old_offset+',admin_id='+('NULL' if not cls.old else cls.old)+' WHERE id=true;')
        for row in cls.original_outbox:
            error='NULL' if row['last_error'] is None else literal(row['last_error'])
            sql(f"UPDATE notification_outbox SET state={literal(row['state'])},attempts={row['attempts']},next_attempt_at={literal(row['next_attempt_at'])}::timestamptz,last_error={error},payload={literal(row['payload'])}::jsonb WHERE id={row['id']};")
        sql("DELETE FROM notification_outbox WHERE dedupe_key LIKE 'update:%' AND split_part(dedupe_key,':',2)::bigint>=900000000000; DELETE FROM processed_updates WHERE update_id>=900000000000;")

    def command(self,text,uid=424242,update_id=None):
        update_id=update_id or 900000000000+int(uuid4().int%10000000)
        return post('lh-telegram',{'update_id':update_id,'message':{
            'from':{'id':uid},'chat':{'id':uid,'type':'private'},'text':text}})

    def test_webhook_rejects_missing_secret(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            post('lh-telegram',{'update_id':1},False)
        self.assertIn(error.exception.code,(401,403))

    def test_callback_is_processed_and_acknowledgement_is_queued(self):
        lead=sql("SELECT lead_id FROM leads WHERE source='demo_fixture' LIMIT 1;")
        update=900000000003
        result=post('lh-telegram',{'update_id':update,'callback_query':{'id':'TEST_CALLBACK',
            'from':{'id':424242},'data':'d:'+lead,'message':{'chat':{'id':424242,'type':'private'}}}})
        self.assertEqual(result['queued'],2,'callback ack and owner reply must both be queued')
        self.assertEqual(sql(f"SELECT payload->'data'->>'_method' FROM notification_outbox WHERE dedupe_key='update:{update}:0';"),'answerCallbackQuery')

    def test_foreign_user_is_ignored_and_duplicate_update_does_not_repeat(self):
        self.assertEqual(self.command('/stop',uid=7).get('queued'),0)
        self.assertEqual(sql('SELECT stopped FROM app_settings WHERE id=true;'),'f')
        id=900000000001
        self.command('/stop',update_id=id)
        before=sql(f"SELECT count(*) FROM notification_outbox WHERE dedupe_key LIKE 'update:{id}:%';")
        self.command('/stop',update_id=id)
        self.assertEqual(sql(f"SELECT count(*) FROM notification_outbox WHERE dedupe_key LIKE 'update:{id}:%';"),before)
        self.command('/resume')

    def test_approval_rejects_stale_draft_and_dnc_survives(self):
        lead=sql("SELECT lead_id FROM leads WHERE source='demo_fixture' ORDER BY lead_id LIMIT 1;")
        self.assertTrue(lead,'run DEMO before Telegram tests')
        original=json.loads(sql(f'SELECT to_jsonb(leads) FROM leads WHERE lead_id={literal(lead)}::uuid;'))
        try:
            version=int(original['draft_version'])
            self.command(f'/draft {lead} Проверенный тестовый черновик')
            self.command(f'/approve {lead}')
            self.assertEqual(sql(f'SELECT owner_approved FROM leads WHERE lead_id={literal(lead)}::uuid;'),'f','version is mandatory')
            self.command(f'/approve {lead} {version}')
            self.assertEqual(sql(f'SELECT owner_approved FROM leads WHERE lead_id={literal(lead)}::uuid;'),'f')
            self.command(f'/approve {lead} {version+1}')
            self.assertEqual(sql(f'SELECT status FROM leads WHERE lead_id={literal(lead)}::uuid;'),'APPROVED')
            self.command(f'/reject {lead}')
            self.command(f'/approve {lead} {version+1}')
            self.assertEqual(sql(f'SELECT status FROM leads WHERE lead_id={literal(lead)}::uuid;'),'DNC')
        finally:
            sql(f"DELETE FROM action_approvals WHERE lead_id={literal(lead)}::uuid; UPDATE leads SET status={literal(original['status'])},owner_approved=false,draft_version={version},draft_message={literal(original['draft_message'])} WHERE lead_id={literal(lead)}::uuid;")

    def test_stop_blocks_collection_but_owner_can_resume(self):
        self.command('/stop')
        self.assertEqual(sql('SELECT stopped FROM app_settings WHERE id=true;'),'t')
        jobs=json.loads(sql("SELECT transport_action('{\"action\":\"claim\"}'::jsonb);"))['jobs']
        self.assertTrue(all(j['payload'].get('type')=='message' for j in jobs),'only owner control replies may pass during STOP')
        self.command('/resume')
        self.assertEqual(sql('SELECT stopped FROM app_settings WHERE id=true;'),'f')

    def test_command_result_survives_failure_before_reply_queue(self):
        before=int(sql('SELECT telegram_offset FROM app_settings WHERE id=true;'))
        update=max(900000000002,before+1)
        command={'update_id':update,'ignored':False,'user_id':424242,'chat_id':424242,
                 'chat_type':'private','command':'stats'}
        first=json.loads(sql(f'SELECT handle_command({literal(command)}::jsonb);'))
        self.assertEqual(int(sql('SELECT telegram_offset FROM app_settings WHERE id=true;')),before,
            'polling must not acknowledge an update before replies are durably queued')
        replay=json.loads(sql(f'SELECT handle_command({literal(command)}::jsonb);'))
        self.assertFalse(replay['ignored'],'un-queued result should be recoverable without repeating mutation')
        self.assertEqual(first['text'],replay['text'])
        sql(f"SELECT queue_replies({update},'[]'::jsonb);")
        self.assertGreaterEqual(int(sql('SELECT telegram_offset FROM app_settings WHERE id=true;')),command['update_id']+1)
        self.assertTrue(json.loads(sql(f'SELECT handle_command({literal(command)}::jsonb);'))['ignored'])


if __name__=='__main__':unittest.main()
