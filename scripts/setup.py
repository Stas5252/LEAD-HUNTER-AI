#!/usr/bin/env python3
"""Generate local-only configuration; never overwrite an existing file."""
import argparse
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--env-file', type=Path, default=ROOT / '.env')
    args = p.parse_args()
    # Bind-mounted init script must be readable after PostgreSQL drops root.
    (ROOT / 'scripts/init-db.sh').chmod(0o644)
    if args.env_file.exists():
        print('Existing configuration preserved.')
        return
    template = (ROOT / '.env.example').read_text()
    for name in ('POSTGRES_PASSWORD', 'APP_DB_PASSWORD', 'N8N_DB_PASSWORD',
                 'N8N_ENCRYPTION_KEY', 'INGEST_TOKEN', 'TELEGRAM_WEBHOOK_SECRET'):
        template = template.replace(name + '=\n', name + '=' + secrets.token_hex(32) + '\n')
    fd = os.open(args.env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(template)
    (ROOT / '.local').mkdir(exist_ok=True)
    print('Local configuration created; secret values are not printed.')


if __name__ == '__main__':
    main()
