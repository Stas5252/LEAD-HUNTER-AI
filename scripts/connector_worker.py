#!/usr/bin/env python3
"""Bounded source/media adapters. n8n owns scheduling and durable queues."""
import argparse,time,json,os
from pathlib import Path
from media_factory import resolve_asset,render_video,render_carousel
from publishers import PostizClient,ThreadsClient,AmbiguousPublish
from collectors import collect
from telegram_transport import N8N,settings


def run_source(n8n,fetch=None):
    j=n8n.post('lh-worker',{'action':'claim'})
    if not j.get('job_id'):return False
    identity={'job_id':j['job_id'],'lease_token':j['lease_token']}
    if not n8n.post('lh-worker',{'action':'check',**identity}).get('allowed'):return False
    try:
        if j['source_type']=='threads_search':
            cfg=settings();client=ThreadsClient(cfg.get('THREADS_ACCESS_TOKEN',''),review_confirmed=cfg.get('THREADS_REVIEW_CONFIRMED','false').lower()=='true')
            try:leads,cursor=client.search(j['config'].get('query','нужен сайт'),after=j['config'].get('after'))
            finally:client.close()
        else:leads=collect(j['source_type'],j['config'],fetch)
        if len(leads)>j['max_leads']:raise ValueError('LEAD_LIMIT')
        result={'leads':leads}
        if j['source_type']=='threads_search':result['cursor']={'after':cursor}
    except Exception as exc:
        # Upstream exceptions may include query parameters or contact data.
        msg=str(exc)
        code='NEEDS_SAFE_TRANSPORT' if 'NEEDS_SAFE_TRANSPORT' in msg else 'RATE_LIMITED' if 'RATE_LIMITED' in msg else 'ADAPTER_'+type(exc).__name__.upper()
        result={'error_code':code}
    n8n.post('lh-worker',{'action':'finish',**identity,**result})
    return True

def run_media(n8n,root):
    j=n8n.post('lh-media',{'action':'claim'})
    if not j.get('job_id'):return False
    identity={'job_id':j['job_id'],'lease_token':j['lease_token']}
    if not n8n.post('lh-media',{'action':'check',**identity}).get('allowed'):return False
    try:
        ids=[x['asset_id'] for x in j['spec'].get('scenes',[])]
        if j['spec'].get('audio_asset_id'):ids.append(j['spec']['audio_asset_id'])
        if not n8n.post('lh-media',{'action':'verify_assets','asset_ids':ids}).get('allowed'):raise ValueError('Asset rights unavailable')
        result=(render_video if j['kind']=='video' else render_carousel)(j['spec'],root)
        outcome={'result':result}
    except Exception as exc:outcome={'error_code':'RENDER_'+type(exc).__name__.upper()}
    n8n.post('lh-media',{'action':'finish',**identity,**outcome});return True

def run_publish(n8n,cfg,client=None):
    if client is None and (not cfg.get('POSTIZ_API_KEY') or not cfg.get('POSTIZ_API_URL')):return False
    j=n8n.post('lh-content',{'action':'claim'})
    if not j.get('content_id'):return False
    identity={'content_id':j['content_id'],'lease_token':j['lease_token']}
    owned=client is None
    try:
        client=client or PostizClient(cfg['POSTIZ_API_URL'],cfg['POSTIZ_API_KEY'])
        accounts=client.integrations()
        if not any(a.get('id')==j['integration_id'] and not a.get('disabled') and str(a.get('identifier','')).startswith(j['channel']) for a in accounts):raise ValueError('Own account disabled or mismatched')
        paths=[resolve_asset(a,Path(cfg.get('MEDIA_ROOT','media'))) for a in j['media_ids']]
        if not n8n.post('lh-content',{'action':'check',**identity}).get('allowed'):
            outcome={'state':'FAILED','error_code':'STOP_OR_APPROVAL_REVOKED'}
        else:
            media=[]
            for path in paths:
                if not n8n.post('lh-content',{'action':'check',**identity}).get('allowed'):raise ValueError('STOP during upload')
                uploaded=client.upload(path)
                if not uploaded.get('id') or not uploaded.get('path'):raise AmbiguousPublish('Upload response missing identity')
                media.append({'id':uploaded['id'],'path':uploaded['path']})
            if not n8n.post('lh-content',{'action':'check',**identity}).get('allowed'):raise ValueError('STOP before publish')
            response=client.publish(j,media)
            if not response:raise AmbiguousPublish('Empty publish response')
            # Postiz acceptance does not prove the social network published it.
            outcome={'state':'SUBMITTED','provider_result':response}
    except AmbiguousPublish:outcome={'state':'UNCERTAIN','error_code':'RECONCILE_PROVIDER_BEFORE_RETRY'}
    except Exception as exc:outcome={'state':'FAILED','error_code':'PUBLISH_'+type(exc).__name__.upper()}
    finally:
        if owned and client:client.close()
    n8n.post('lh-content',{'action':'finish',**identity,**outcome});return True

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--once',action='store_true');args=p.parse_args()
    cfg=settings();n8n=N8N(cfg);root=Path(cfg.get('MEDIA_ROOT','media'))
    while True:
        try:
            active=run_source(n8n)
            active=run_media(n8n,root) or active
            active=run_publish(n8n,cfg) or active
        except (OSError,ValueError):active=False;print('Worker connection unavailable; details suppressed',flush=True)
        Path('/tmp/lh-worker-heartbeat').touch()
        if args.once:return
        time.sleep(1 if active else 5)

if __name__=='__main__':main()
