#!/usr/bin/env python3
"""Small polling/HTTP transport. n8n owns all commands, state and scheduling."""
from contextlib import ExitStack
import argparse
import httpx
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request


def settings():
    values={}
    env=Path(__file__).resolve().parents[1]/'.env'
    if env.is_file():
        for line in env.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                key,value=line.split('=',1);values[key.strip()]=value.strip()
    from secrets_store import load_secrets
    values.update(load_secrets())
    values.update({k:v for k,v in os.environ.items() if v or k not in values})
    return values


class BotAPI:
    def __init__(self,token,base_url='https://api.telegram.org',media_root=None):
        self.token=token;self.base=base_url.rstrip('/');self.media_root=Path(media_root if media_root is not None else os.environ.get('MEDIA_ROOT','media'))

    def call(self,method,payload,timeout=30):
        req=urllib.request.Request(f'{self.base}/bot{self.token}/{method}',
            data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)

    def send(self,payload,method='sendMessage'):
        if method in ('sendVideo','sendMediaGroup'):
            return self.send_media(payload,method)
        if method not in ('sendMessage','answerCallbackQuery'):
            return {'state':'FAILED','error':'Unsupported transport method'}
        try:
            result=self.call(method,payload)
            return {'state':'SENT'} if result.get('ok') else {'state':'FAILED','error':'Bot API rejected delivery'}
        except urllib.error.HTTPError as exc:
            if exc.code==429:
                try: retry=int(json.load(exc).get('parameters',{}).get('retry_after',30))
                except (ValueError,TypeError): retry=30
                return {'state':'PENDING','retry_after':max(1,min(retry,3600)),'error':'HTTP 429'}
            # 5xx can be ambiguous after an upstream accepted the message.
            return {'state':'UNCERTAIN' if exc.code>=500 else 'FAILED','error':f'HTTP {exc.code}'}
        except (OSError,ValueError):
            return {'state':'UNCERTAIN','error':'Network/response error; no automatic retry'}

    def send_media(self,payload,method):
        from media_factory import resolve_asset
        ids=payload.get('_asset_ids',[])
        if not isinstance(ids,list) or not (len(ids)==1 if method=='sendVideo' else 2<=len(ids)<=10):return {'state':'FAILED','error':'Invalid asset count'}
        try:
            paths=[resolve_asset(v,self.media_root) for v in ids]
            with ExitStack() as stack:
                files={};data={'chat_id':str(payload['chat_id'])}
                for i,path in enumerate(paths):
                    if method=='sendVideo' and path.suffix.lower()!='.mp4':raise ValueError('Expected MP4')
                    if method=='sendMediaGroup' and path.suffix.lower() not in ('.png','.jpg','.jpeg'):raise ValueError('Expected image')
                    files['file'+str(i)]=(path.name,stack.enter_context(path.open('rb')))
                if method=='sendVideo':
                    files={'video':files['file0']};data['caption']=str(payload.get('caption',''))[:1000];data['supports_streaming']='true'
                else:data['media']=json.dumps([{'type':'photo','media':'attach://file'+str(i),**({'caption':str(payload.get('caption',''))[:1000]} if i==0 else {})} for i in range(len(paths))])
                with httpx.Client(timeout=90,follow_redirects=False) as client:r=client.post(self.base+'/bot'+self.token+'/'+method,data=data,files=files)
                if r.status_code==429:return {'state':'PENDING','retry_after':min(3600,max(5,int(r.json().get('parameters',{}).get('retry_after',30))))}
                if r.status_code>=500:return {'state':'UNCERTAIN','error':'Provider 5xx'}
                if r.status_code>=300:return {'state':'FAILED','error':'Provider rejected media'}
                try:accepted=r.json()
                except ValueError:return {'state':'UNCERTAIN','error':'Media acceptance response invalid; review before retry'}
                return {'state':'SENT'} if accepted.get('ok') else {'state':'FAILED','error':'Provider rejected media'}
        except httpx.TransportError:return {'state':'UNCERTAIN','error':'Media submission response lost; review before retry'}
        except (OSError,ValueError,KeyError):return {'state':'FAILED','error':'Asset verification or response failed'}


class N8N:
    def __init__(self,cfg):
        self.base=cfg.get('LH_N8N_URL','http://127.0.0.1:'+cfg.get('N8N_PORT','5678')).rstrip('/')
        self.secret=cfg['TELEGRAM_WEBHOOK_SECRET']

    def post(self,path,payload):
        req=urllib.request.Request(self.base+'/webhook/'+path,data=json.dumps(payload).encode(),
            headers={'Content-Type':'application/json','X-Telegram-Bot-Api-Secret-Token':self.secret})
        with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)


def drain(n8n,api):
    jobs=n8n.post('lh-transport',{'action':'claim'}).get('jobs',[])
    for job in jobs:
        if not n8n.post('lh-transport',{'action':'check','id':job['id']}).get('allowed'):
            n8n.post('lh-transport',{'action':'report','id':job['id'],'state':'PENDING','retry_after':30})
            continue
        message=job['message'];method=message.pop('_method','sendMessage')
        if method=='answerCallbackQuery':message.pop('chat_id',None)
        result=api.send(message,method)
        n8n.post('lh-transport',{'action':'report','id':job['id'],**result})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true',help='Read-only check of Bot API token and webhook state')
    p.add_argument('--webhook',action='store_true',help='Delivery only; updates arrive via an explicitly registered HTTPS webhook')
    args=p.parse_args();cfg=settings()
    if not cfg.get('TELEGRAM_BOT_TOKEN') or not cfg.get('TELEGRAM_ADMIN_ID'):
        raise SystemExit('NEEDS_CREDENTIALS: configure TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_ID securely.')
    api=BotAPI(cfg['TELEGRAM_BOT_TOKEN'],media_root=cfg.get('MEDIA_ROOT','media'));n8n=N8N(cfg)
    try:
        me=api.call('getMe',{});webhook=api.call('getWebhookInfo',{})
    except (OSError,ValueError):raise SystemExit('Bot API check failed; token values are not logged.') from None
    if not me.get('ok'):raise SystemExit('Bot API token check failed.')
    if args.check:
        print('Bot API getMe: OK. Existing webhook:',bool(webhook.get('result',{}).get('url')))
        return
    if webhook.get('result',{}).get('url') and not args.webhook:
        raise SystemExit('Existing webhook detected. Choose webhook mode or remove it explicitly; polling was not started.')
    state=n8n.post('lh-transport',{'action':'status'})
    if str(state.get('admin_id'))!=cfg['TELEGRAM_ADMIN_ID']:
        raise SystemExit('Owner binding mismatch: run python3 scripts/connect.py first.')
    print('Telegram transport started. Owner commands and consent-based visitor intake are handled by n8n.')
    while True:
        try:
            state=n8n.post('lh-transport',{'action':'status'})
            updates={'ok':True,'result':[]} if args.webhook else api.call('getUpdates',{'offset':state['offset'],'timeout':20,'allowed_updates':['message','edited_message','channel_post','edited_channel_post','callback_query']},timeout=30)
            if not updates.get('ok'):raise ValueError('Bot API rejected polling')
            for update in updates.get('result',[]):
                n8n.post('lh-telegram',update)
            drain(n8n,api)
            if args.webhook:time.sleep(2)
        except (OSError,ValueError):
            print('Transport temporarily unavailable; retry in 10 seconds. Secrets are not logged.',flush=True)
            time.sleep(10)


if __name__=='__main__':main()
