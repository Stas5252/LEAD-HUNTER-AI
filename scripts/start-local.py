#!/usr/bin/env python3
"""Start one local adapter and one owner-bound Telegram polling process.
Uses existing n8n/PostgreSQL; does not reset STOP, data, webhook or provider settings.
"""
import argparse,os,subprocess,sys,time
from pathlib import Path
from common import ROOT
from telegram_transport import settings,N8N,BotAPI

def alive(name,script):
 path=ROOT/'.local'/(name+'.pid')
 if not path.exists():return False
 try:
  pid=int(path.read_text());cmd=Path('/proc')/str(pid)/'cmdline'
  return cmd.is_file() and str(ROOT/'scripts'/script).encode() in cmd.read_bytes()
 except (ValueError,OSError):return False

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
 cfg=settings();state=N8N(cfg).post('lh-transport',{'action':'status'});items=[('worker','connector_worker.py')]
 if cfg.get('TELEGRAM_BOT_TOKEN') and cfg.get('TELEGRAM_ADMIN_ID'):
  if str(state.get('admin_id'))!=cfg['TELEGRAM_ADMIN_ID']:raise SystemExit('Owner binding mismatch; run scripts/connect.py')
  items.append(('telegram','telegram_transport.py'))
 print('Authenticated n8n status OK; STOP='+str(state.get('stopped')))
 if a.check:
  for name,script in items:print(name,'running='+str(alive(name,script)))
  if not all(alive(*item) for item in items):raise SystemExit(1)
  return
 local=ROOT/'.local';local.mkdir(exist_ok=True)
 for name,script in items:
  if alive(name,script):print(name,'already running');continue
  if name=='telegram':
   api=BotAPI(cfg['TELEGRAM_BOT_TOKEN']);me=api.call('getMe',{});hook=api.call('getWebhookInfo',{})
   if not me.get('ok') or hook.get('result',{}).get('url'):raise SystemExit('Polling prerequisite failed; inspect existing webhook explicitly')
  fd=os.open(local/(name+'.log'),os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
  env=dict(os.environ);env['PYTHONUNBUFFERED']='1'
  with os.fdopen(fd,'ab') as log:child=subprocess.Popen([sys.executable,str(ROOT/'scripts'/script)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  pidfile=local/(name+'.pid');pidfile.write_text(str(child.pid));pidfile.chmod(0o600);time.sleep(1)
  if child.poll() is not None:raise SystemExit(name+' exited; inspect private log')
  print(name,'started')
if __name__=='__main__':main()
