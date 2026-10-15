#!/usr/bin/env python3
"""Run unit and integration checks. Intended for an unconnected DEMO instance."""
import sys
import re
import subprocess
from common import ROOT,config


def main():
    cfg=config()
    if cfg.get('TELEGRAM_ADMIN_ID') or cfg.get('AI_ENABLED','false').lower()=='true':
        raise SystemExit('Run integration fixtures in a separate DEMO copy before connecting a real owner/paid API. npm test remains safe.')
    commands=[['node','--test',*map(str,sorted((ROOT/'tests').glob('*.test.js')))],
              [sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-v']]
    for i,cmd in enumerate(commands):
        r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
        log=ROOT/'.local'/('verification-node.log' if i==0 else 'verification-python.log')
        log.write_text(r.stdout+r.stderr);log.chmod(0o600)
        print('\n'.join((r.stdout+r.stderr).splitlines()[-12:]))
        if r.returncode:raise SystemExit(r.returncode)
        text=r.stdout+r.stderr
        if i==0 and not re.search(r'(?:tests|test count)\s+[1-9]',text):raise SystemExit('No Node tests executed')
        if i==1 and not re.search(r'Ran [1-9][0-9]* tests?',text):raise SystemExit('No Python tests executed')
    print('Verification passed. External APIs were mocked; no real Telegram/OpenAI delivery was verified.')


if __name__=='__main__':main()
