#!/usr/bin/env python3
"""Import reproducible workflows and encrypted n8n credentials, never publish."""
import json
import os
import argparse
from common import ROOT, config, compose, sql, literal
from credential_policy import should_replace


def private_json(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f, ensure_ascii=False)


def backup_workflows():
    """Export before overwriting IDs; fail closed if preservation fails."""
    from datetime import datetime,timezone
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    remote='/tmp/lh-workflow-backup-'+stamp+'.json'
    dest=ROOT/'backups'/('workflows-'+stamp+'.json');dest.parent.mkdir(mode=0o700,exist_ok=True)
    try:
        compose('exec','-T','n8n','n8n','export:workflow','--all','--output='+remote,text=True,capture_output=True)
        compose('cp','n8n:'+remote,str(dest),text=True,capture_output=True)
        dest.chmod(0o600)
        data=json.loads(dest.read_text())
        if not isinstance(data,list):raise ValueError('Invalid workflow backup')
    finally:
        compose('exec','-T','n8n','rm','-f',remote,text=True,capture_output=True)
    encrypted_remote='/tmp/lh-credential-backup-'+stamp+'.json'
    encrypted_dest=dest.with_name(dest.name.replace('workflows-','credentials-'))
    try:
        compose('exec','-T','n8n','n8n','export:credentials','--all','--output='+encrypted_remote,text=True,capture_output=True)
        compose('cp','n8n:'+encrypted_remote,str(encrypted_dest),text=True,capture_output=True)
        encrypted_dest.chmod(0o600)
        if not isinstance(json.loads(encrypted_dest.read_text()),list):raise ValueError('Invalid encrypted credential backup')
    finally:compose('exec','-T','n8n','rm','-f',encrypted_remote,text=True,capture_output=True)
    return dest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--activate-local',action='store_true',help='Enable local collector/webhooks; does not publish posts or contact prospects')
    args=p.parse_args()
    cfg = config()
    local = ROOT / '.local'
    local.mkdir(exist_ok=True)
    backup=backup_workflows()
    existing_ids={c['id'] for c in json.loads(backup.with_name(backup.name.replace('workflows-','credentials-')).read_text())}
    credentials = [{'id': 'lh-postgres', 'name': 'LEAD HUNTER PostgreSQL', 'type': 'postgres',
                    'data': {'host': 'postgres', 'port': 5432, 'database': 'lead_hunter',
                             'user': 'lead_hunter', 'password': cfg['APP_DB_PASSWORD'], 'ssl': 'disable'}},
                   {'id':'lh-webhook','name':'LEAD HUNTER local webhook','type':'httpHeaderAuth',
                    'data':{'name':'X-Telegram-Bot-Api-Secret-Token','value':cfg['TELEGRAM_WEBHOOK_SECRET']}}]
    credentials.append({'id':'lh-form-key','name':'LEAD HUNTER server form key','type':'httpHeaderAuth','data':{'name':'X-LH-Form-Key','value':cfg['INGEST_TOKEN']}})
    if cfg.get('TELEGRAM_BOT_TOKEN'):
        credentials.append({'id': 'lh-telegram', 'name': 'LEAD HUNTER Telegram', 'type': 'telegramApi',
                            'data': {'accessToken': cfg['TELEGRAM_BOT_TOKEN']}})
    credentials.append({'id': 'lh-openai', 'name': 'LEAD HUNTER OpenAI', 'type': 'httpHeaderAuth',
                        'data': {'name': 'Authorization', 'value': 'Bearer ' + ((cfg.get('AI_ACCESS_KEY') if cfg.get('AI_PROVIDER_MODEL') else cfg.get('LH_OPENAI_API_KEY') or cfg.get('OPENAI_API_KEY')) or 'DISABLED_NO_CREDENTIALS')}})
    provided_ai=(cfg.get('AI_ACCESS_KEY') if cfg.get('AI_PROVIDER_MODEL') else cfg.get('LH_OPENAI_API_KEY') or cfg.get('OPENAI_API_KEY'))
    credentials=[c for c in credentials if c['id']!='lh-openai' or should_replace('lh-openai',provided_ai,existing_ids)]
    secrets_file = local / 'credentials.json'
    private_json(secrets_file, credentials)
    try:
        r = compose('exec', '-T', 'n8n', 'n8n', 'import:credentials', '--input=/opt/lead-hunter/credentials.json',
                    text=True, capture_output=True)
    finally:
        secrets_file.unlink(missing_ok=True)
    flows = [json.loads(p.read_text()) for p in sorted((ROOT / 'workflows').glob('*.json'))]
    private_json(local / 'workflows.json', flows)
    compose('exec', '-T', 'n8n', 'n8n', 'import:workflow', '--input=/opt/lead-hunter/workflows.json',
            text=True, capture_output=True)
    payload = json.loads((ROOT / 'fixtures/leads.json').read_text())
    sql(f'INSERT INTO demo_dataset(id,payload) VALUES(true,{literal(payload)}::jsonb) ON CONFLICT(id) DO UPDATE SET payload=EXCLUDED.payload;')
    if args.activate_local:
        for flow in flows:
            compose('exec','-T','n8n','n8n','publish:workflow','--id='+flow['id'],text=True,capture_output=True)
    compose('restart','n8n',text=True,capture_output=True)
    import time,urllib.request
    for attempt in range(60):
        try:
            with urllib.request.urlopen('http://127.0.0.1:'+cfg.get('N8N_PORT','5678')+'/healthz/readiness',timeout=2) as r:
                if r.status==200:break
        except (OSError,TimeoutError):pass
        time.sleep(1)
    else:raise RuntimeError('n8n did not become ready')
    if args.activate_local:
        endpoint='http://127.0.0.1:'+cfg.get('N8N_PORT','5678')+'/webhook/lh-transport'
        for attempt in range(60):
            try:
                req=urllib.request.Request(endpoint,data=b'{"action":"status"}',headers={
                    'Content-Type':'application/json','X-Telegram-Bot-Api-Secret-Token':cfg['TELEGRAM_WEBHOOK_SECRET']})
                with urllib.request.urlopen(req,timeout=2) as r:
                    if 'offset' in json.load(r):break
            except (OSError,ValueError,TimeoutError):pass
            time.sleep(1)
        else:raise RuntimeError('Local transport workflow did not become ready')
    print(f'Imported {len(flows)} workflows; local activation={args.activate_local}; credentials encrypted in n8n.')


if __name__ == '__main__':
    main()
