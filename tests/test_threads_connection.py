import json,sys,unittest
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:from connect_threads import inspect_threads
except ImportError:inspect_threads=None
from publishers import ThreadsClient
class ThreadsConnectionTests(unittest.TestCase):
 def inspect(self,handler,**cfg):
  self.assertIsNotNone(inspect_threads,'Threads connection verifier required')
  return inspect_threads({'THREADS_ACCESS_TOKEN':'TEST_PRIVATE_VALUE','THREADS_EXPECTED_USERNAME':'stanislav.web',**cfg},check_search=True,client_factory=lambda token:ThreadsClient(token,transport=httpx.MockTransport(handler)))
 def test_missing_token_does_not_contact_meta(self):
  self.assertIsNotNone(inspect_threads,'Threads connection verifier required')
  r=inspect_threads({},client_factory=lambda token:self.fail('No credential must mean no request'))
  self.assertEqual(r['status'],'NEEDS_TOKEN')
 def test_verifies_own_account_and_actual_search_permission_without_post(self):
  calls=[]
  def handler(req):
   calls.append(req);self.assertEqual(req.method,'GET');self.assertEqual(req.url.host,'graph.threads.com');self.assertNotIn('TEST_PRIVATE_VALUE',str(req.url))
   return httpx.Response(200,json={'id':'123456','username':'stanislav.web'} if req.url.path.endswith('/me') else {'data':[]})
  r=self.inspect(handler);self.assertEqual(r['status'],'SEARCH_CONNECTED');self.assertEqual(r['user_id'],'123456');self.assertEqual(len(calls),2)
 def test_other_account_is_not_enabled(self):
  calls=[]
  def handler(req):calls.append(req);return httpx.Response(200,json={'id':'777','username':'someone_else'})
  r=self.inspect(handler);self.assertEqual(r['status'],'ACCOUNT_MISMATCH');self.assertEqual(len(calls),1)
 def test_basic_profile_permission_is_not_claimed_as_search_access(self):
  def handler(req):return httpx.Response(200,json={'id':'123','username':'stanislav.web'}) if req.url.path.endswith('/me') else httpx.Response(403,json={'error':{'message':'not granted'}})
  r=self.inspect(handler);self.assertFalse(r['search_available']);self.assertNotEqual(r['status'],'SEARCH_CONNECTED')
 def test_network_errors_cannot_leak_access_token(self):
  def handler(req):raise httpx.ReadTimeout('TEST_PRIVATE_VALUE')
  r=self.inspect(handler);self.assertEqual(r['status'],'PROFILE_UNAVAILABLE');self.assertNotIn('TEST_PRIVATE_VALUE',json.dumps(r))
 def test_invalid_identity_cannot_be_saved_as_verified(self):
  r=self.inspect(lambda req:httpx.Response(200,json={'id':'untrusted/identity','username':'stanislav.web'}));self.assertEqual(r['status'],'INVALID_PROFILE_RESPONSE')
if __name__=='__main__':unittest.main()
