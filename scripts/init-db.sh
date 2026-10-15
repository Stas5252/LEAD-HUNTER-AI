#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  --set=app_password="$APP_DB_PASSWORD" --set=n8n_password="$N8N_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE lead_hunter LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS(SELECT FROM pg_roles WHERE rolname='lead_hunter') \gexec
SELECT format('CREATE ROLE n8n LOGIN PASSWORD %L', :'n8n_password')
WHERE NOT EXISTS(SELECT FROM pg_roles WHERE rolname='n8n') \gexec
SELECT 'CREATE DATABASE lead_hunter OWNER lead_hunter'
WHERE NOT EXISTS(SELECT FROM pg_database WHERE datname='lead_hunter') \gexec
SELECT 'CREATE DATABASE n8n OWNER n8n'
WHERE NOT EXISTS(SELECT FROM pg_database WHERE datname='n8n') \gexec
REVOKE ALL ON DATABASE lead_hunter FROM PUBLIC;
REVOKE ALL ON DATABASE n8n FROM PUBLIC;
SQL
