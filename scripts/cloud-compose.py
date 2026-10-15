#!/usr/bin/env python3
"""Prepare a private Compose override for inherited cloud proxy and CA trust."""
import json,os,socket
from pathlib import Path
from urllib.parse import urlsplit
from common import ROOT
p=ROOT/'.local'/'compose.cloud.json';p.parent.mkdir(exist_ok=True)
services={};proxy={k:os.environ[k] for k in ('HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy') if os.environ.get(k)}
ca=os.environ.get('CODEX_PROXY_CERT')
if proxy and (not ca or not Path(ca).is_file()):raise SystemExit('Proxy present but managed CA file is missing; TLS trust must be configured first')
hosts={}
for value in proxy.values():
 host=urlsplit(value).hostname
 if host:hosts[host]=socket.gethostbyname(host)
for name in ('n8n','worker','telegram'):
 d={'environment':{**proxy,'NO_PROXY':'n8n,postgres,localhost,127.0.0.1','no_proxy':'n8n,postgres,localhost,127.0.0.1'},'extra_hosts':hosts}
 if ca:
  d['volumes']=[{'type':'bind','source':str(Path(ca).resolve()),'target':'/opt/lead-hunter/proxy-ca.pem','read_only':True}]
  if name=='n8n':d['environment']['NODE_EXTRA_CA_CERTS']='/opt/lead-hunter/proxy-ca.pem'
 if name=='worker' and ca:d['build']={'secrets':['proxy_ca']}
 services[name]=d
result={'services':services}
if ca:result['secrets']={'proxy_ca':{'file':str(Path(ca).resolve())}}
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as f:json.dump(result,f)
print('Prepared private cloud override. Use COMPOSE_FILE=docker-compose.yml:.local/compose.cloud.json (Linux).')
