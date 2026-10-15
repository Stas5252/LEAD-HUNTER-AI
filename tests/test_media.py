import json,sys,tempfile,unittest,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:from media_factory import register_asset,render_carousel,render_video,resolve_asset,synthetic_demo
except ImportError:register_asset=render_carousel=render_video=resolve_asset=synthetic_demo=None
class MediaTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(register_asset,'rights-aware media factory required')
 def test_rights_path_and_hash_guard(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'source.txt').write_text('original')
   with self.assertRaises(ValueError):register_asset(root/'source.txt',{'kind':'reference','source_url':'https://example.org/clip'},root)
   a=register_asset(root/'source.txt',{'kind':'own','grant':'Создано владельцем','owner':'Owner'},root)
   self.assertTrue(resolve_asset(a['asset_id'],root).is_file())
   resolve_asset(a['asset_id'],root).write_text('altered')
   with self.assertRaises(ValueError):resolve_asset(a['asset_id'],root)
   (root/'outside').symlink_to('/etc/hosts')
   with self.assertRaises(ValueError):register_asset(root/'outside',{'kind':'own','grant':'own'},root)
 def test_carousel_has_five_to_seven_cyrillic_cards(self):
  from PIL import Image
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   result=render_carousel({'title':'Как получать заявки','cards':['Проверьте форму заявки','Уточните предложение','Покажите реальные работы','Добавьте контакты','Обсудим вашу задачу'],'cta':'stanislavweb.ru','is_demo':True},root)
   self.assertEqual(len(result['assets']),5)
   for a in result['assets']:
    with Image.open(resolve_asset(a['asset_id'],root)) as im:self.assertEqual(im.size,(1080,1350))
   with self.assertRaises(ValueError):render_carousel({'cards':['only one']},root)
 def test_actual_demo_clip_render_probe_decode_and_no_filter_injection(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);src=synthetic_demo(root)
   spec={'scenes':[{'asset_id':src['asset_id'],'seconds':1,'caption':'Сайт помогает клиенту'}],'title':'DEMO','cta':'stanislavweb.ru','is_demo':True}
   result=render_video(spec,root);path=resolve_asset(result['asset_id'],root)
   probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))
   self.assertEqual(probe['streams'][0]['width'],720);self.assertGreater(float(probe['streams'][0]['duration']),0)
   subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],check=True,capture_output=True)
   with self.assertRaises(ValueError):render_video({**spec,'scenes':[{'asset_id':'../../etc/passwd','seconds':1}]},root)
   with self.assertRaises(ValueError):render_video({**spec,'scenes':[{'asset_id':src['asset_id'],'seconds':500}]},root)
if __name__=='__main__':unittest.main()
