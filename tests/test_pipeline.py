import json
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import sql, literal


class PipelineTests(unittest.TestCase):
    def test_workflows_exist_and_import_into_n8n(self):
        path = ROOT / 'workflows/01-lead-import.json'
        self.assertTrue(path.is_file(), 'real n8n workflow is required')
        flow = json.loads(path.read_text())
        self.assertTrue(any(n['type'] == 'n8n-nodes-base.postgres' for n in flow['nodes']))
        subprocess.run(['python3', 'scripts/import-workflows.py','--activate-local'], cwd=ROOT, check=True, capture_output=True)

    def test_json_and_csv_execute_in_n8n_without_duplicate_rows(self):
        self.assertTrue((ROOT / 'scripts/demo.py').is_file(), 'demo runner is required')
        for format in ('json', 'csv'):
            r = subprocess.run(['python3', 'scripts/demo.py', '--format', format, '--json'],
                               cwd=ROOT, check=True, capture_output=True, text=True)
            result = json.loads(r.stdout)
            self.assertEqual(len(result['cards']), 3)
            self.assertTrue(all('DEMO: вымышленный пример' in c['text'] for c in result['cards']))
        self.assertEqual(sql("SELECT count(*) FROM leads WHERE source='demo_fixture';"), '3')
        self.assertEqual(sql("SELECT count(*) FROM notification_outbox WHERE dedupe_key LIKE 'lead:%';"), '2')

    def test_dnc_survives_reimport_and_source_change_revokes_approval(self):
        self.assertIn('ingest_batch', sql("SELECT proname FROM pg_proc WHERE proname='ingest_batch';"))
        lead = dict(dedupe_key='test-' + str(uuid4()), source='test', source_type='manual',
                    source_url='https://example.invalid/test', company_name='TEST', text='Нужен сайт',
                    proof_quote='Нужен сайт', content_hash='one', classification='DIRECT_REQUEST',
                    score_0_100=80, confidence_0_1=0.8, why_relevant='Запрос', offer_type='Сайт',
                    draft_message='Первый черновик', is_demo=True)
        result = json.loads(sql(f'SELECT ingest_batch({literal([lead])}::jsonb);'))
        id = result['leads'][0]['lead_id']
        try:
            sql(f"UPDATE leads SET status='DNC' WHERE lead_id='{id}';")
            sql(f'SELECT ingest_batch({literal([lead])}::jsonb);')
            self.assertEqual(sql(f"SELECT status FROM leads WHERE lead_id='{id}';"), 'DNC')
            sql(f"UPDATE leads SET status='APPROVED',owner_approved=true WHERE lead_id='{id}';")
            lead['content_hash'] = 'two'
            lead['draft_message'] = 'Изменённый черновик'
            sql(f'SELECT ingest_batch({literal([lead])}::jsonb);')
            self.assertEqual(sql(f"SELECT owner_approved::text||':'||draft_version::text FROM leads WHERE lead_id='{id}';"), 'false:2')
        finally:
            sql(f"DELETE FROM notification_outbox WHERE lead_id='{id}'; DELETE FROM lead_events WHERE lead_id='{id}'; DELETE FROM leads WHERE lead_id='{id}';")

    def test_reimport_refreshes_factual_fields_and_preserves_dnc(self):
        lead=dict(dedupe_key='test-facts-'+str(uuid4()),source='test_facts',source_type='manual',
                  source_url='https://example.invalid/old',company_name='TEST OLD',niche='мебель',city='Самара',
                  website=None,website_status='ABSENT_CONFIRMED',public_contact='old',contact_source_url='https://example.invalid/old',
                  proof_quote='Нужен сайт',content_hash='old',classification='DIRECT_REQUEST',score_0_100=80,
                  confidence_0_1=.8,why_relevant='Запрос',offer_type='Старый оффер',draft_message='КП',is_demo=True,estimated_cost=.2)
        result=json.loads(sql(f'SELECT ingest_batch({literal([lead])}::jsonb);'));id=result['leads'][0]['lead_id']
        try:
            sql(f"UPDATE leads SET status='DNC' WHERE lead_id='{id}';")
            lead.update(content_hash='new',source_url='https://example.invalid/new',company_name='TEST NEW',niche='ресторан',city='Казань',
                        website='https://site.example.invalid',website_status='UNVERIFIED',public_contact='new',
                        contact_source_url='https://example.invalid/new',offer_type='Новый оффер',estimated_cost=0)
            saved=json.loads(sql(f'SELECT ingest_batch({literal([lead])}::jsonb);'))['leads'][0]
            for field in ('source_url','company_name','niche','city','website','website_status','public_contact','contact_source_url','offer_type'):
                self.assertEqual(saved[field],lead[field],field+' must reflect the current source')
            self.assertEqual(saved['status'],'DNC')
            self.assertEqual(float(saved['estimated_cost']),.2)
        finally:
            sql(f"DELETE FROM notification_outbox WHERE lead_id='{id}';DELETE FROM lead_events WHERE lead_id='{id}';DELETE FROM leads WHERE lead_id='{id}';")


if __name__ == '__main__':
    unittest.main()
