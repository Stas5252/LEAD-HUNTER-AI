#!/usr/bin/env python3
"""Run JSON/CSV inputs through real n8n; fixture records stay explicitly DEMO."""
import argparse
import csv
import json
import time
from pathlib import Path
from common import ROOT, sql, literal
from run_workflow import execute


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--format', choices=['json', 'csv'], default='json')
    p.add_argument('--input', type=Path, help='Owner-supplied permitted JSON/CSV input; no URL downloads')
    p.add_argument('--json', action='store_true')
    args = p.parse_args()
    path = args.input or ROOT / 'fixtures' / ('leads.' + args.format)
    if path.stat().st_size > 5_000_000:
        raise SystemExit('Input exceeds 5 MB')
    if args.format == 'json':
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    else:
        with path.open(encoding='utf-8-sig', newline='') as f:
            payload = list(csv.DictReader(f))
        for row in payload:
            value = row.get('is_demo', 'false')
            if value not in ('true', 'false'):
                raise SystemExit('CSV is_demo must be true or false')
            row['is_demo'] = value == 'true'
    if not isinstance(payload, list):
        raise SystemExit('Expected JSON array')
    if sql('SELECT stopped FROM app_settings WHERE id=true;') == 't':
        raise SystemExit('STOPPED: resume as owner before collecting')
    request = sql(f'INSERT INTO import_requests(payload,origin) VALUES({literal(payload)}::jsonb,\'owner_cli\') RETURNING request_id;')
    try:
        execute('lh-lead-import')
    except Exception:
        sql(f"UPDATE import_requests SET state='FAILED',updated_at=now() WHERE request_id={literal(request)}::uuid AND state<>'DONE';")
        raise
    for attempt in range(150):
        state = sql(f'SELECT state FROM import_requests WHERE request_id={literal(request)}::uuid;')
        if state in ('DONE','FAILED'):break
        time.sleep(1)
    if state != 'DONE':
        raise SystemExit('This import has not completed; another pending request may have been processed. Retry the workflow.')
    result = json.loads(sql(f'SELECT result FROM import_requests WHERE request_id={literal(request)}::uuid;'))
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        for card in result['cards']:
            print(card['text'] + '\n')
        print(f"Stored {len(result['leads'])} records; newly inserted: {result['inserted']}. No external outreach sent.")


if __name__ == '__main__':
    main()
