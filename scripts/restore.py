#!/usr/bin/env python3
"""Restore a trusted local dump into a NEW database; never overwrite production."""
import argparse
import re
from pathlib import Path
from common import sql,literal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backup',type=Path,required=True)
    p.add_argument('--database',required=True)
    args=p.parse_args()
    if not re.fullmatch(r'lh_restore_[a-z0-9_]{1,40}',args.database):
        raise SystemExit('Use a NEW database named lh_restore_<name>')
    if sql(f'SELECT count(*) FROM pg_database WHERE datname={literal(args.database)};',admin=True)!='0':
        raise SystemExit('Destination already exists; nothing overwritten')
    sql(f'CREATE DATABASE {args.database} OWNER lead_hunter;',admin=True)
    sql(f'REVOKE ALL ON DATABASE {args.database} FROM PUBLIC;',admin=True)
    sql(args.backup.read_text(),database=args.database)
    print('Restored into',args.database,'· working databases unchanged.')


if __name__=='__main__':main()
