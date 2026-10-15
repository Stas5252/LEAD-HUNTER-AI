#!/usr/bin/env python3
"""Authenticated encrypted local vault. Master key is separate, mode0600.
The vault protects accidental file disclosure; an administrator with both files
can decrypt it. Cloud secret manager may instead inject values at runtime.
"""
import argparse,getpass,json,os,tempfile
from pathlib import Path
from cryptography.fernet import Fernet,InvalidToken
ROOT=Path(__file__).resolve().parents[1]

def paths(root=None):
 root=Path(root) if root is not None else Path(os.environ.get('LH_SECRETS_DIR',ROOT/'.local'))
 return root,root/'secrets.key',root/'secrets.enc'

def load_secrets(root=None):
 folder,key_path,vault=paths(root)
 if not vault.exists():return {}
 try:
  value=json.loads(Fernet(key_path.read_bytes()).decrypt(vault.read_bytes()))
  if not isinstance(value,dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in value.items()):raise ValueError('Invalid encrypted data')
  return value
 except (OSError,ValueError,InvalidToken):raise ValueError('Secret vault unavailable or integrity check failed; values suppressed') from None

def save_secrets(values,root=None):
 folder,key_path,vault=paths(root);folder.mkdir(parents=True,exist_ok=True,mode=0o700)
 if key_path.is_symlink() or vault.is_symlink():raise ValueError('Secret paths must not be symlinks')
 if not key_path.exists():
  fd=os.open(key_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as f:f.write(Fernet.generate_key())
 current=load_secrets(folder);current.update(values)
 ciphertext=Fernet(key_path.read_bytes()).encrypt(json.dumps(current,ensure_ascii=False).encode())
 fd,tmp=tempfile.mkstemp(dir=folder,prefix='vault-',suffix='.tmp')
 try:
  with os.fdopen(fd,'wb') as f:f.write(ciphertext)
  os.replace(tmp,vault);vault.chmod(0o600);key_path.chmod(0o600)
 finally:Path(tmp).unlink(missing_ok=True)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('names',nargs='+');a=p.parse_args()
 if not all(n.isupper() and n.replace('_','').isalnum() for n in a.names):raise SystemExit('Invalid setting name')
 values={}
 for name in a.names:
  value=getpass.getpass(name+' (hidden): ')
  if not value:raise SystemExit('Empty value not saved')
  values[name]=value
 save_secrets(values);print('Encrypted '+str(len(values))+' values; no values logged. Keep master key separately backed up.')
if __name__=='__main__':main()
