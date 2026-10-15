#!/usr/bin/env python3
from common import ROOT, sql, literal


def main():
    sql('CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());')
    for path in sorted((ROOT / 'migrations').glob('*.sql')):
        if sql(f'SELECT count(*) FROM schema_migrations WHERE version={literal(path.name)};') == '1':
            continue
        sql('BEGIN;\n' + path.read_text() + '\nINSERT INTO schema_migrations(version) VALUES (' + literal(path.name) + ');\nCOMMIT;')
        print('Applied:', path.name)


if __name__ == '__main__':
    main()
