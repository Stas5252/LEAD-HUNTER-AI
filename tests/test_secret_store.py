import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:from secrets_store import save_secrets,load_secrets
except ImportError:save_secrets=load_secrets=None
class SecretStoreTests(unittest.TestCase):
 def test_at_rest_encryption_permissions_and_integrity(self):
  self.assertIsNotNone(save_secrets,'encrypted store required')
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);save_secrets({'TELEGRAM_BOT_TOKEN':'test-private-value'},root)
   self.assertNotIn(b'test-private-value',(root/'secrets.enc').read_bytes())
   self.assertEqual(load_secrets(root)['TELEGRAM_BOT_TOKEN'],'test-private-value')
   self.assertEqual((root/'secrets.key').stat().st_mode&0o777,0o600)
   key=(root/'secrets.key').read_bytes();save_secrets({'AI_ACCESS_KEY':'second-private'},root)
   self.assertEqual((root/'secrets.key').read_bytes(),key);self.assertIn('TELEGRAM_BOT_TOKEN',load_secrets(root))
   (root/'secrets.enc').write_bytes(b'broken ciphertext')
   with self.assertRaises(ValueError):load_secrets(root)
if __name__=='__main__':unittest.main()
