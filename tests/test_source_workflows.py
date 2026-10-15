"""Real n8n collector schedules -> durable job -> worker -> shared intake.
HTTP provider data is controlled here; these are not live source results.
"""
import json,sys,unittest
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import ROOT,sql,literal
from run_workflow import execute
from connector_worker import run_source
from telegram_transport import N8N,settings
class SourceWorkflowTests(unittest.TestCase):
 def test_nine_independent_workflows_and_real_worker_handoff(self):
  kinds=['maps','new_business','telegram_monitor','audit','niche','subcontract','website_forms','partners','content']
  for kind in kinds:
   self.assertTrue(any(json.loads(p.read_text())['id']=='lh-source-'+kind for p in (ROOT/'workflows').glob('*.json')))
  original=sql("SELECT to_jsonb(c) FROM connector_configs c WHERE source_type='partners';")
  marker='test-'+uuid4().hex
  cfg={'records':[{'company_name':'DEMO partner','source_url':'https://example.invalid/post/'+marker,'proof_quote':'Ищем партнёра для разработки сайта','external_id':marker,'is_demo':True}]}
  try:
   sql(f"UPDATE connector_configs SET enabled=true,config={literal(cfg)}::jsonb,last_enqueued_at=NULL WHERE source_type='partners';")
   execute('lh-source-partners')
   self.assertTrue(run_source(N8N(settings())))
   self.assertEqual(sql(f"SELECT state FROM connector_jobs WHERE config->'records'->0->>'external_id'={literal(marker)};"),'DONE')
   execute('lh-lead-import')
   self.assertEqual(sql(f"SELECT count(*) FROM leads WHERE data->>'proof_quote'='Ищем партнёра для разработки сайта' AND company_name='DEMO partner';"),'1')
  finally:
   sql(f"UPDATE connector_configs SET enabled=x.enabled,config=x.config,last_enqueued_at=x.last_enqueued_at FROM jsonb_populate_record(NULL::connector_configs,{literal(original)}::jsonb)x WHERE connector_configs.source_type=x.source_type;")
   sql(f"DELETE FROM notification_outbox WHERE lead_id IN (SELECT lead_id FROM leads WHERE company_name='DEMO partner');DELETE FROM lead_events WHERE lead_id IN (SELECT lead_id FROM leads WHERE company_name='DEMO partner');DELETE FROM leads WHERE company_name='DEMO partner';DELETE FROM connector_jobs WHERE config->'records'->0->>'external_id'={literal(marker)};DELETE FROM import_requests WHERE origin='partners' AND payload->0->>'external_id'={literal(marker)};")
if __name__=='__main__':unittest.main()
