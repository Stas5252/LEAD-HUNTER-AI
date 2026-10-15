import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from telegram_transport import BotAPI
from media_factory import render_carousel
class DeliveryMediaTests(unittest.TestCase):
 def test_media_upload_uses_only_registered_assets_and_handles_uncertainty(self):
  with tempfile.TemporaryDirectory() as t:
   result=render_carousel({'title':'DEMO','cards':['Текст']*5,'is_demo':True},Path(t))
   ids=[a['asset_id'] for a in result['assets']]
   api=BotAPI('test-token');api.media_root=Path(t)
   with patch('httpx.Client') as C:
    C.return_value.__enter__.return_value.post.return_value=httpx.Response(200,json={'ok':True})
    self.assertEqual(api.send({'chat_id':1,'_asset_ids':ids,'caption':'DEMO'},'sendMediaGroup')['state'],'SENT')
   self.assertEqual(api.send({'chat_id':1,'_asset_ids':['../../etc/hosts']},'sendVideo')['state'],'FAILED')
if __name__=='__main__':unittest.main()

class MediaRootConfiguration(unittest.TestCase):
 def test_transport_accepts_configured_shared_media_root(self):
  with tempfile.TemporaryDirectory() as t:
   api=BotAPI('test-token',media_root=t)
   self.assertEqual(api.media_root,Path(t))
