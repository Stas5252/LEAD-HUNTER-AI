#!/usr/bin/env python3
"""Configure permitted sources locally. No credentials in config JSON."""
import argparse,json
from common import sql,literal

def main():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
 c=s.add_parser('configure');c.add_argument('source');c.add_argument('file');c.add_argument('--enable',action='store_true')
 c=s.add_parser('run');c.add_argument('source')
 c=s.add_parser('chat');c.add_argument('id',type=int);c.add_argument('--description',default='');c.add_argument('--disable',action='store_true')
 s.add_parser('status');a=p.parse_args()
 if a.cmd=='configure':
  with open(a.file) as f:cfg=json.load(f)
  if any(k in str(cfg).lower() for k in ('access_token','api_key','password','authorization','bot_token')):raise SystemExit('Keep credentials in environment, never source config')
  print(sql(f"UPDATE connector_configs SET config={literal(cfg)}::jsonb,enabled={str(a.enable).lower()},cursor='{{}}'::jsonb,last_enqueued_at=NULL,updated_at=now() WHERE source_type={literal(a.source)} RETURNING source_type,enabled;"))
 elif a.cmd=='run':print(sql(f"SELECT enqueue_configured({literal(a.source)},true);"))
 elif a.cmd=='chat':
  if a.id>=0:raise SystemExit('Group/channel ID must be negative')
  print(sql(f"INSERT INTO monitored_chats(chat_id,description,enabled) VALUES({a.id},{literal(a.description)},{str(not a.disable).lower()}) ON CONFLICT(chat_id) DO UPDATE SET description=EXCLUDED.description,enabled=EXCLUDED.enabled RETURNING chat_id,enabled;"))
 else:print(sql("SELECT c.source_type,c.enabled,s.access_status,c.last_enqueued_at FROM connector_configs c JOIN source_registry s USING(source_type) ORDER BY 1;"))
if __name__=='__main__':main()
