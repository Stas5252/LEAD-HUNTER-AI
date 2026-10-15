import json
from datetime import datetime,timezone
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import sql,literal,compose


def mock(path):
    code=f"fetch('http://127.0.0.1:9099/{path}').then(r=>r.text()).then(console.log).catch(()=>process.exit(1))"
    return compose('exec','-T','n8n','node','-e',code,text=True,capture_output=True).stdout.strip()


class OpenAIWorkflowTests(unittest.TestCase):
    def test_http_mock_validation_cache_rate_limit_and_timeout_in_actual_n8n(self):
        cfg=json.loads(sql('SELECT to_jsonb(llm_settings) FROM llm_settings WHERE id=true;'))
        if cfg['enabled']:
            self.skipTest('Live AI configured; use separate test Compose project')
        source='mock_'+uuid4().hex
        day="(now() AT TIME ZONE 'UTC')::date"
        prior=sql(f'SELECT to_jsonb(daily_usage) FROM daily_usage WHERE day={day};')
        s=json.loads(sql('SELECT to_jsonb(app_settings) FROM app_settings WHERE id=true;'))
        script=(ROOT/'tests/mock_responses.js').read_text()
        compose('exec','-d','-T','n8n','node','-e',script,capture_output=True)
        for i in range(30):
            try: mock('stats');break
            except subprocess.CalledProcessError:time.sleep(.2)
        else:self.fail('local HTTP mock did not start')
        paths=[]
        published=datetime.now(timezone.utc).isoformat()
        try:
            sql(f"DELETE FROM daily_usage WHERE day={day}; UPDATE app_settings SET stopped=false,max_llm_calls_per_day=50,daily_api_budget_usd=1 WHERE id=true; UPDATE llm_settings SET enabled=true,mock_mode=true WHERE id=true;")
            def run(suffix):
                raw={'company_name':'DEMO Mock '+source+suffix,'source':source,'source_type':'maps_demo',
                     'source_url':'https://example.invalid/'+source+suffix,'external_id':suffix,
                     'text':'Нужен сайт для кафе с меню','is_demo':True,'published_at':published}
                path=ROOT/'.local'/('mock-'+source+suffix+'.json');paths.append(path)
                path.write_text(json.dumps([raw],ensure_ascii=False));os.chmod(path,0o600)
                r=subprocess.run(['python3','scripts/demo.py','--input',str(path),'--json'],cwd=ROOT,
                                 text=True,capture_output=True,check=True,timeout=100)
                return json.loads(r.stdout)['leads'][0]
            first=run('valid')
            self.assertEqual(first['scoring_method'],'openai_mock','actual HTTP node must execute and validate mock response')
            self.assertEqual(first['score_0_100'],92)
            cached=run('valid')
            self.assertEqual(cached['scoring_method'],'openai_mock')
            self.assertEqual(json.loads(mock('stats'))['calls'],1,'second identical scoring must use cache')
            mock('mode/invalid');self.assertEqual(run('invalid')['scoring_method'],'heuristic')
            mock('mode/rate');self.assertEqual(run('rate')['scoring_method'],'heuristic')
            mock('mode/timeout');self.assertEqual(run('timeout')['scoring_method'],'heuristic')
            self.assertEqual(json.loads(mock('stats'))['calls'],4,'no hidden retries after rate limit or timeout')
            self.assertEqual(sql(f'SELECT calls FROM daily_usage WHERE day={day};'),'4')
        finally:
            try:mock('shutdown')
            except subprocess.CalledProcessError:pass
            sql(f"UPDATE app_settings SET stopped={str(s['stopped']).lower()},max_llm_calls_per_day={s['max_llm_calls_per_day']},daily_api_budget_usd={s['daily_api_budget_usd']} WHERE id=true; UPDATE llm_settings SET enabled=false,mock_mode=false WHERE id=true;")
            sql(f"DELETE FROM llm_cache WHERE cache_key IN (SELECT cache_key FROM llm_cache WHERE result->>'scoring_method'='openai_mock');")
            sql(f"DELETE FROM notification_outbox WHERE lead_id IN (SELECT lead_id FROM leads WHERE source={literal(source)}); DELETE FROM lead_events WHERE lead_id IN (SELECT lead_id FROM leads WHERE source={literal(source)}); DELETE FROM leads WHERE source={literal(source)}; DELETE FROM daily_usage WHERE day={day};")
            if prior:
                data=json.loads(prior);sql(f"INSERT INTO daily_usage(day,calls,reserved_usd) VALUES({literal(data['day'])},{data['calls']},{data['reserved_usd']});")
            for path in paths:path.unlink(missing_ok=True)


if __name__=='__main__':unittest.main()
