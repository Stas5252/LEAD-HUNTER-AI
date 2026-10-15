import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import sql,literal
from safe_http import site_fetch
class SecurityRegressions(unittest.TestCase):
 def test_proxy_audit_does_not_attempt_direct_or_connect_to_ip(self):
  with patch.dict('os.environ',{'HTTPS_PROXY':'http://example.invalid:1'}),patch('socket.create_connection') as conn:
   with self.assertRaisesRegex(ValueError,'NEEDS_SAFE_TRANSPORT'):site_fetch('https://example.org')
   conn.assert_not_called()
 def test_same_asset_retargeted_account_must_invalidate_content(self):
  # A bound account ID can be updated by local CLI; prior content approval must
  # not authorize a different remote social profile.
  result=sql("""BEGIN;UPDATE app_settings SET admin_id=123,stopped=false;INSERT INTO publishing_accounts VALUES('retarget-test','threads','old-profile',true,'{}');SELECT content_action('{"action":"create","user_id":123,"account_id":"retarget-test","text":"Текст"}');SELECT content_action(jsonb_build_object('action','approve','user_id',123,'content_id',content_id,'version',version)) FROM content_items WHERE account_id='retarget-test';UPDATE publishing_accounts SET integration_id='different-profile' WHERE account_id='retarget-test';SELECT state||':'||version FROM content_items WHERE account_id='retarget-test';ROLLBACK;""")
  self.assertEqual(result.splitlines()[-1],'DRAFT:2')
 def test_forms_require_exact_https_origin(self):
  import subprocess
  code="const f=require('./lib/forms');try{f.parseForm({nonce:'test-123456789',timestamp:Math.floor(Date.now()/1000),contact:'x@y',message:'Нужен сайт',consent:true,source_url:'https://stanislavweb.ru.evil.invalid'},'a'.repeat(64));process.exit(2)}catch(e){process.exit(0)}"
  self.assertEqual(subprocess.run(['node','-e',code],cwd=Path(__file__).resolve().parents[1]).returncode,0)
if __name__=='__main__':unittest.main()
