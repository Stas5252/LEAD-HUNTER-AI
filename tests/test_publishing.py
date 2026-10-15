import json,sys,unittest
from pathlib import Path
from datetime import datetime,timezone
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:from publishers import PostizClient,ThreadsClient,AmbiguousPublish
except ImportError:PostizClient=ThreadsClient=AmbiguousPublish=None

class PublishingTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(PostizClient,'official publisher clients required')
 def test_postiz_exact_auth_payload_and_no_blind_retry(self):
  requests=[]
  def handler(req):
   requests.append(req);return httpx.Response(200,json=[{'id':'remote-17','integration':'own-1'}])
  c=PostizClient('https://publisher.example.org/api/public/v1','private',transport=httpx.MockTransport(handler))
  result=c.publish({'text':'Проверка','channel':'threads','integration_id':'own-1','due_at':datetime.now(timezone.utc).isoformat()},[])
  self.assertEqual(result[0]['id'],'remote-17');req=requests[0];self.assertEqual(req.headers['authorization'],'private')
  body=json.loads(req.content);self.assertEqual(body['type'],'now');self.assertFalse(body['shortLink']);self.assertEqual(body['posts'][0]['value'][0]['image'],[])
  def timeout(req):raise httpx.ReadTimeout('lost after submission')
  with self.assertRaises(AmbiguousPublish):PostizClient('https://publisher.example.org/api/public/v1','private',transport=httpx.MockTransport(timeout)).publish({'text':'X','channel':'threads','integration_id':'own-1','due_at':datetime.now(timezone.utc).isoformat()},[])
 def test_threads_search_uses_fixed_origin_and_cursor_not_next_url(self):
  calls=[]
  def handler(req):
   calls.append(req)
   return httpx.Response(200,json={'data':[{'id':'12','username':'user','text':'Нужен сайт','permalink':'https://www.threads.com/@user/post/12','timestamp':datetime.now(timezone.utc).isoformat()}],'paging':{'cursors':{'after':'opaque'},'next':'https://attacker.invalid/?access_token=x'}})
  c=ThreadsClient('private',review_confirmed=True,transport=httpx.MockTransport(handler));rows,cursor=c.search('нужен сайт',after='old')
  self.assertEqual(rows[0]['external_id'],'threads:12');self.assertEqual(cursor,'opaque');self.assertEqual(calls[0].url.host,'graph.threads.com')
  self.assertEqual(calls[0].url.params['after'],'old');self.assertEqual(calls[0].url.params['search_type'],'RECENT')
  with self.assertRaises(ValueError):ThreadsClient('private',review_confirmed=False).search('сайт')
 def test_postiz_redirect_cannot_receive_credential(self):
  c=PostizClient('https://publisher.example.org/api/public/v1','private',transport=httpx.MockTransport(lambda r:httpx.Response(302,headers={'Location':'https://evil.invalid'})))
  with self.assertRaises(ValueError):c.integrations()

if __name__=='__main__':unittest.main()
