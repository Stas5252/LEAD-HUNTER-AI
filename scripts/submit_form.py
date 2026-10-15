#!/usr/bin/env python3
"""Server-side example: sign an already consented website submission.
Do not place INGEST_TOKEN in browser JavaScript.
"""
import argparse,hashlib,hmac,json,time,uuid,urllib.request
from common import config

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('json_file');p.add_argument('--url',required=True);a=p.parse_args()
 cfg=config();body=json.load(open(a.json_file));body.update(timestamp=int(time.time()),nonce=uuid.uuid4().hex)
 if body.get('consent') is not True:raise SystemExit('Explicit consent required')
 raw=json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':'));sig=hmac.new(cfg['INGEST_TOKEN'].encode(),raw.encode(),hashlib.sha256).hexdigest()
 request=urllib.request.Request(a.url,data=raw.encode(),headers={'Content-Type':'application/json','X-LH-Form-Key':cfg['INGEST_TOKEN'],'X-LH-Signature':sig})
 with urllib.request.urlopen(request,timeout=25) as r:print(json.load(r))
if __name__=='__main__':main()
