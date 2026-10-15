"""Visitor flow tests run in rolled-back transactions; no messages reach live chats."""
import json,sys,unittest
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import sql,literal
class VisitorIntakeTests(unittest.TestCase):
 def run_events(self,texts,extra='',contact=None,username='visitor_test'):
  user=7_000_000_000_000+int(uuid4().hex[:8],16);base=user+100000
  queries=['BEGIN;',"SET LOCAL lock_timeout='3s';"]
  for i,text in enumerate(texts):
   m={'message_id':i+1,'chat':{'id':user,'type':'private'},'from':{'id':user,'first_name':'TEST','username':'visitor_test'},'text':text}
   if username is None:m['from'].pop('username')
   if contact and i==len(texts)-1:m['contact']=contact|{'user_id':contact.get('user_id',user)};m.pop('text')
   u={'update_id':base+i,'message':m}
   queries.append(f'SELECT visitor_update({literal(u)}::jsonb);')
  if extra:queries.append(extra.replace(':user',str(user)).replace(':update',str(base+len(texts)-1)))
  queries.append('ROLLBACK;')
  return [json.loads(x) for x in sql('\n'.join(queries)).splitlines() if x.startswith('{')],user
 def test_requires_explicit_consent_before_collecting_request(self):
  r,_=self.run_events(['/start web_landing','Нужен сайт'])
  self.assertEqual(r[0]['result']['visitor_stage'],'CONSENT')
  self.assertEqual(r[1]['result']['visitor_stage'],'CONSENT')
 def test_complete_submission_once_and_visitor_is_only_reply_recipient(self):
  q="""SELECT queue_visitor_replies(:update,jsonb_build_array(jsonb_build_object('text','TEST reply')));
  SELECT queue_visitor_replies(:update,jsonb_build_array(jsonb_build_object('text','TEST reply')));
  SELECT jsonb_build_object('imports',count(*)) FROM import_requests WHERE payload->0->>'external_id' IN (SELECT 'visitor:'||submission_id FROM visitor_submissions WHERE user_id=:user);
  SELECT jsonb_build_object('recipient',payload->>'visitor_chat_id','replies',count(*)) FROM notification_outbox WHERE dedupe_key='visitor-update:'||:update||':0' GROUP BY payload;
  SELECT visitor_update(jsonb_build_object('update_id',:update,'message',jsonb_build_object('chat',jsonb_build_object('id',:user,'type','private'),'from',jsonb_build_object('id',:user),'text','Ответить мне в Telegram')));"""
  r,user=self.run_events(['/start web_landing','Согласен','Нужен сайт для магазина','Ответить мне в Telegram'],q)
  self.assertEqual(r[3]['result']['visitor_stage'],'DONE')
  self.assertEqual(r[4]['queued'],1);self.assertEqual(r[5]['queued'],0)
  self.assertEqual(r[6]['imports'],1);self.assertEqual(int(r[7]['recipient']),user)
  self.assertTrue(r[8]['result']['ignored'])
 def test_public_visitor_cannot_execute_owner_commands(self):
  r,_=self.run_events(['/start web_general','/stop','/leads'])
  self.assertEqual(r[1]['result']['visitor_stage'],'CONSENT');self.assertNotIn('leads',r[2]['result'])
 def test_contact_must_belong_to_sender(self):
  r,_=self.run_events(['/start web_crm','Согласен','Нужна CRM',''],contact={'phone_number':'70000000000','user_id':1})
  self.assertEqual(r[-1]['result']['visitor_stage'],'CONTACT')
 def test_no_username_does_not_accept_unusable_contact(self):
  r,_=self.run_events(['/start web_general','Согласен','Хочу обсудить проект','Ответить мне в Telegram'],"SELECT jsonb_build_object('count',count(*)) FROM visitor_submissions WHERE user_id=:user;",username=None)
  self.assertEqual(r[3]['result']['visitor_stage'],'CONTACT');self.assertEqual(r[4]['count'],0)
 def test_inbound_bypasses_ai_even_when_generation_is_enabled(self):
  lead={'source':'telegram_inbound','source_type':'website_forms','score_0_100':95,'attribution':{'intake':'telegram_inbound','consent':True}}
  q="BEGIN; UPDATE app_settings SET daily_api_budget_usd=1,max_llm_calls_per_day=10000; UPDATE llm_settings SET enabled=true,mock_mode=false,has_credentials=true,free_quota_confirmed=true,input_price=0,output_price=0;"
  q+=f"SELECT reserve_score({literal({'lead':lead})}::jsonb,{literal('visitor-test-'+uuid4().hex)},100,'{{}}'::jsonb); ROLLBACK;"
  r=json.loads(sql(q));self.assertEqual(r['mode'],'FALLBACK');self.assertEqual(r['lead']['score_0_100'],95)
 def test_claim_routes_only_visitor_reply_to_visitor(self):
  q="""UPDATE notification_outbox SET next_attempt_at=now()+interval '1 hour' WHERE state IN ('PENDING','SENDING');
  SELECT queue_visitor_replies(:update,jsonb_build_array(jsonb_build_object('text','visitor response')));
  SELECT transport_action('{"action":"claim"}'::jsonb);"""
  r,user=self.run_events(['/start web_general'],q)
  self.assertEqual(len(r[2]['jobs']),1);self.assertEqual(r[2]['jobs'][0]['chat_id'],user)
  self.assertEqual(r[2]['jobs'][0]['payload']['data']['text'],'visitor response')
 def test_cancel_does_not_create_lead(self):
  r,_=self.run_events(['/start web_ai','Согласен','Нужно видео','Отмена'],"SELECT jsonb_build_object('count',count(*)) FROM visitor_submissions WHERE user_id=:user;")
  self.assertEqual(r[3]['result']['visitor_stage'],'CANCELLED');self.assertEqual(r[4]['count'],0)
 def test_unrelated_chats_and_owner_are_not_reinterpreted(self):
  queries=['BEGIN;']
  for chat,actor in [({'id':-100123,'type':'supergroup'},42),({'id':761405171,'type':'private'},761405171)]:
   u={'update_id':7_500_000_000_001,'message':{'chat':chat,'from':{'id':actor},'text':'/start'}}
   queries.append(f'SELECT visitor_update({literal(u)}::jsonb);')
  queries.append('ROLLBACK;');r=[json.loads(x) for x in sql('\n'.join(queries)).splitlines() if x.startswith('{')]
  self.assertTrue(all(not x['handled'] for x in r))
if __name__=='__main__':unittest.main()
