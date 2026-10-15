import hashlib,hmac,json,sys,time,unittest,urllib.request,urllib.error
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import config,sql,literal
class FormsFlowTests(unittest.TestCase):
 def test_real_signed_webhook_accepts_once_rejects_bad_signature(self):
  cfg=config();before=sql('SELECT to_jsonb(f) FROM form_settings f;');nonce=uuid4().hex
  body={'nonce':nonce,'timestamp':int(time.time()),'consent':True,'contact':'test@example.invalid','message':'Нужен сайт DEMO integration','name':'DEMO form','source_url':'https://stanislavweb.ru','utm':{'utm_campaign':'lh-test'}}
  raw=json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
  def submit(signature):
   req=urllib.request.Request('http://127.0.0.1:'+cfg.get('N8N_PORT','5678')+'/webhook/lh-form',data=raw,headers={'Content-Type':'application/json','X-LH-Form-Key':cfg['INGEST_TOKEN'],'X-LH-Signature':signature})
   with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
  try:
   sql(f"UPDATE form_settings SET enabled=true,signing_key={literal(cfg['INGEST_TOKEN'])};")
   self.assertEqual(submit('0'*64)['status'],'BAD_SIGNATURE')
   signature=hmac.new(cfg['INGEST_TOKEN'].encode(),raw,hashlib.sha256).hexdigest()
   self.assertEqual(submit(signature)['status'],'ACCEPTED');self.assertEqual(submit(signature)['status'],'DUPLICATE')
  finally:
   sql(f"DELETE FROM form_submissions WHERE nonce={literal(nonce)};DELETE FROM import_requests WHERE origin='website_forms' AND payload->0->>'external_id'={literal('form:'+nonce)};")
   sql(f"UPDATE form_settings SET enabled=x.enabled,signing_key=x.signing_key FROM jsonb_populate_record(NULL::form_settings,{literal(before)}::jsonb)x WHERE form_settings.id=x.id;")
if __name__=='__main__':unittest.main()
