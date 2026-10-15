#!/usr/bin/env python3
"""Create private logical backups; encryption key stays in the original .env."""
from datetime import datetime,timezone
import os
import json,tarfile
from pathlib import Path
from common import ROOT,compose


def main():
    dest=Path(os.environ.get('LH_BACKUP_DIR',ROOT/'backups'))/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    dest.mkdir(parents=True,mode=0o700)
    for db in ('lead_hunter','n8n'):
        password='APP_DB_PASSWORD' if db=='lead_hunter' else 'N8N_DB_PASSWORD'
        user='lead_hunter' if db=='lead_hunter' else 'n8n'
        path=dest/(db+'.sql')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:
            compose('exec','-T','postgres','sh','-c',
              f'PGPASSWORD="${password}" pg_dump -h 127.0.0.1 -U {user} -d {db} --no-owner --no-privileges',stdout=f)
    running=compose('ps','--status','running','--services',text=True,capture_output=True).stdout.splitlines()
    path=dest/'media.tar'
    if 'worker' in running:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:
            code="import tarfile,sys,pathlib; t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|'); root=pathlib.Path('/data/media'); [t.add(p,arcname=p.relative_to(root),recursive=False) for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink() and p.parts[-2] in ('assets','manifests')]; t.close()"
            compose('exec','-T','worker','python3','-c',code,stdout=f)
    elif (ROOT/'media').is_dir():
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f,tarfile.open(fileobj=f,mode='w') as t:
            for p in (ROOT/'media').rglob('*'):
                if p.is_file() and not p.is_symlink() and p.parent.name in ('assets','manifests'):t.add(p,arcname=p.relative_to(ROOT/'media'),recursive=False)
    print(dest)
    print('Store .env/N8N_ENCRYPTION_KEY separately and securely; backups are not encrypted at rest by this script.')


if __name__=='__main__':main()
