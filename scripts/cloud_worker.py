#!/usr/bin/env python3
"""Container bootstrap for platforms without Docker socket (e.g. Railway).
No public HTTP server. PostgreSQL and n8n remain separate mature services.
"""
import os,subprocess,sys,time
from pathlib import Path
from common import config,ROOT,sql

def main():
 if not os.environ.get('DATABASE_URL'):raise SystemExit('DATABASE_URL must be securely configured for app role')
 for attempt in range(120):
  try:
   if sql('SELECT 1;')=='1':break
  except RuntimeError:pass
  time.sleep(1)
 else:raise SystemExit('Database not ready; credentials suppressed')
 import migrate,connect
 migrate.main();connect.main()
 cfg=config();commands=[[sys.executable,str(ROOT/'scripts/connector_worker.py')]]
 if cfg.get('TELEGRAM_BOT_TOKEN') and cfg.get('TELEGRAM_ADMIN_ID'):commands.append([sys.executable,str(ROOT/'scripts/telegram_transport.py')])
 children=[subprocess.Popen(command) for command in commands]
 import signal
 def stop(signum,frame):
  for child in children:child.terminate()
  for child in children:
   try:child.wait(timeout=20)
   except subprocess.TimeoutExpired:child.kill()
  raise SystemExit(0)
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 while True:
  if any(p.poll() is not None for p in children):
   for child in children:child.terminate()
   raise SystemExit('Adapter/transport exited; platform should restart container')
  time.sleep(2)
if __name__=='__main__':main()
