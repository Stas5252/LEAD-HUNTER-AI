#!/usr/bin/env python3
"""Owner content/media controls, using the same authenticated n8n routes as Telegram."""
import argparse,json
from pathlib import Path
from telegram_transport import N8N,settings
from common import sql,literal
from media_factory import register_asset

def main():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
 c=s.add_parser('account');c.add_argument('account_id');c.add_argument('channel',choices=['threads','instagram']);c.add_argument('integration_id');c.add_argument('--enable',action='store_true')
 c=s.add_parser('action');c.add_argument('json_file')
 c=s.add_parser('render');c.add_argument('kind',choices=['video','carousel']);c.add_argument('spec_json')
 c=s.add_parser('register');c.add_argument('file');c.add_argument('rights_json');c.add_argument('--root',default='media')
 s.add_parser('list');a=p.parse_args();cfg=settings();n=N8N(cfg)
 if a.cmd=='account':
  print(sql(f"INSERT INTO publishing_accounts(account_id,channel,integration_id,enabled) VALUES({literal(a.account_id)},{literal(a.channel)},{literal(a.integration_id)},{str(a.enable).lower()}) ON CONFLICT(account_id) DO UPDATE SET channel=EXCLUDED.channel,integration_id=EXCLUDED.integration_id,enabled=EXCLUDED.enabled RETURNING account_id,channel,enabled;"));return
 body={'user_id':int(cfg.get('TELEGRAM_ADMIN_ID') or 0)};route='lh-content'
 if a.cmd=='list':body['action']='list'
 elif a.cmd=='action':body.update(json.loads(Path(a.json_file).read_text()))
 elif a.cmd=='render':route='lh-media';body.update(action='enqueue',kind=a.kind,spec=json.loads(Path(a.spec_json).read_text()))
 else:
  route='lh-media';body.update(action='register',manifest=register_asset(Path(a.file),json.loads(Path(a.rights_json).read_text()),Path(a.root)))
 print(json.dumps(n.post(route,body),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
