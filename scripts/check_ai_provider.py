#!/usr/bin/env python3
"""Read-only GET /models for the provider explicitly authorized by the owner.
No prompt generation, retries, or secret values in output.
"""
import json
from urllib.parse import urlsplit
import httpx
from common import config

def main():
 c=config();base=c.get('AI_PROVIDER_BASE_URL','');p=urlsplit(base)
 if p.scheme!='https' or p.hostname!='shprotoness-ai.jq9gfk.workers.dev' or p.path.rstrip('/')!='/v1' or p.username or p.password or p.query or p.fragment:raise SystemExit('Unconfirmed provider URL; stopped')
 key=c.get('AI_ACCESS_KEY')
 if not key:raise SystemExit('NEEDS_KEY: encrypted AI_ACCESS_KEY')
 try:
  with httpx.Client(timeout=20,follow_redirects=False) as client:r=client.get(base.rstrip('/')+'/models',headers={'Authorization':'Bearer '+key})
  if r.status_code>=300:raise SystemExit('Provider discovery HTTP '+str(r.status_code)+'; values suppressed')
  data=r.json();print(json.dumps({'models':[v['id'] for v in data.get('data',[]) if isinstance(v,dict) and isinstance(v.get('id'),str)][:100]},ensure_ascii=False))
 except httpx.HTTPError:raise SystemExit('Provider network unavailable; no generation attempted; key suppressed') from None
if __name__=='__main__':main()
