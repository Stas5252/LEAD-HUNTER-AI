import concurrent.futures
import json
from pathlib import Path
import sys
import unittest
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import sql,literal


class BudgetTests(unittest.TestCase):
    def test_atomic_daily_budget_and_disabled_default(self):
        self.assertEqual(sql("SELECT count(*) FROM pg_proc WHERE proname='reserve_score';"),'1','budget function missing')
        original=json.loads(sql('SELECT to_jsonb(app_settings) FROM app_settings WHERE id=true;'))
        llm=json.loads(sql('SELECT to_jsonb(llm_settings) FROM llm_settings WHERE id=true;'))
        if llm.get('enabled'):
            self.skipTest('Live AI configured: use a separate Compose project for budget integration tests')
        day="(now() AT TIME ZONE 'UTC')::date"
        prior=sql(f'SELECT to_jsonb(daily_usage) FROM daily_usage WHERE day={day};')
        key='test-'+str(uuid4())
        item={'lead':{'content_hash':key,'proof_quote':'Нужен сайт','score_0_100':90,'is_demo':False},'request_id':'budget-test'}
        def reserve(i):return json.loads(sql(f'SELECT reserve_score({literal(item)}::jsonb,{literal(key+str(i))},1000,\'{{}}\'::jsonb);'))
        try:
            sql(f'DELETE FROM daily_usage WHERE day={day}; UPDATE app_settings SET stopped=false,max_llm_calls_per_day=1,daily_api_budget_usd=1 WHERE id=true;')
            self.assertEqual(reserve(0)['mode'],'FALLBACK')
            sql("UPDATE llm_settings SET enabled=true,has_credentials=true,input_price=1,output_price=1 WHERE id=true;")
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(reserve,range(6)))
            self.assertEqual(sum(r['mode']=='CALL' for r in results),1)
            self.assertEqual(sql(f'SELECT calls FROM daily_usage WHERE day={day};'),'1')
            sql('UPDATE app_settings SET max_llm_calls_per_day=10,daily_api_budget_usd=0 WHERE id=true;')
            self.assertEqual(reserve(10)['mode'],'FALLBACK')
            sql('UPDATE app_settings SET stopped=true,daily_api_budget_usd=1 WHERE id=true;')
            self.assertEqual(reserve(11)['mode'],'FALLBACK')
        finally:
            sql(f"UPDATE app_settings SET stopped={str(original['stopped']).lower()},max_llm_calls_per_day={original['max_llm_calls_per_day']},daily_api_budget_usd={original['daily_api_budget_usd']} WHERE id=true;")
            sql(f"UPDATE llm_settings SET enabled=false,has_credentials={str(llm['has_credentials']).lower()},input_price={llm['input_price']},output_price={llm['output_price']} WHERE id=true;")
            sql(f'DELETE FROM daily_usage WHERE day={day}; DELETE FROM llm_inflight WHERE cache_key LIKE {literal(key+"%")};')
            if prior:
                data=json.loads(prior)
                sql(f"INSERT INTO daily_usage(day,calls,reserved_usd) VALUES({literal(data['day'])},{data['calls']},{data['reserved_usd']});")


if __name__=='__main__':unittest.main()
