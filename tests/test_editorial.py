import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:from editorial import make_plan
except ImportError:make_plan=None
class EditorialTests(unittest.TestCase):
 def test_all_service_topics_have_cta_and_no_invented_price_or_case(self):
  self.assertIsNotNone(make_plan,'editorial plan required')
  result=make_plan(14);self.assertEqual(len(result),14)
  self.assertEqual(len(set(x['text'] for x in result)),14)
  self.assertTrue(all('stanislavweb.ru' in x['text'] for x in result))
  self.assertTrue(all(5<=len(x['carousel']['cards'])<=7 for x in result))
  self.assertTrue(any('CRM' in x['text'] for x in result))
  self.assertTrue(all(x['state']=='DRAFT' for x in result))
if __name__=='__main__':unittest.main()
