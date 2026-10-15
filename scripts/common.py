"""Local CLI utilities. Secrets are read by name, never included in argv/logs."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def config():
    result = {}
    path=ROOT/'.env'
    if not path.is_file():path=ROOT/'.env.example'
    for line in (path.read_text() if path.is_file() else '').splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            result[key.strip()] = value.strip()
    from secrets_store import load_secrets
    result.update(load_secrets())
    result.update({k:v for k,v in os.environ.items() if v or k not in result})
    return result


def compose(*args, **kwargs):
    return subprocess.run(['docker', 'compose', *args], cwd=ROOT, check=True, **kwargs)


def sql(query, *, admin=False, database=None):
    if os.environ.get('DATABASE_URL'):
        if admin or database:raise ValueError('Remote admin/alternate database requires an explicit maintenance connection')
        import psycopg
        def field(v):
            if v is None:return ''
            if isinstance(v,bool):return 't' if v else 'f'
            if isinstance(v,(dict,list)):return json.dumps(v,ensure_ascii=False)
            return str(v)
        try:
            rows=[]
            with psycopg.connect(os.environ['DATABASE_URL'],autocommit=True,connect_timeout=15) as conn,conn.cursor() as cur:
                cur.execute(query,prepare=False)
                while True:
                    if cur.description:rows.extend('|'.join(map(field,row)) for row in cur.fetchall())
                    if not cur.nextset():break
            return '\n'.join(rows)
        except psycopg.Error:raise RuntimeError('Database operation failed; remote details suppressed') from None
    user = 'postgres' if admin else 'lead_hunter'
    db = database or ('postgres' if admin else 'lead_hunter')
    if not db.replace('_', '').isalnum():
        raise ValueError('Invalid database name')
    password = 'POSTGRES_PASSWORD' if admin else 'APP_DB_PASSWORD'
    cmd = f'PGPASSWORD="${password}" psql -X -qAt -v ON_ERROR_STOP=1 -U {user} -d {db}'
    try:
        r = compose('exec', '-T', 'postgres', 'sh', '-c', cmd,
                    input=query, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        # SQL may contain user data; do not echo the full submitted query.
        raise RuntimeError('Database operation failed: ' + exc.stderr.splitlines()[0]) from None
    return r.stdout.strip()


def literal(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return "'" + str(value).replace("'", "''") + "'"
