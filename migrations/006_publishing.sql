ALTER TABLE app_settings ADD COLUMN max_public_posts_per_day integer NOT NULL DEFAULT 2 CHECK(max_public_posts_per_day BETWEEN 0 AND 100);
CREATE TABLE publishing_accounts(account_id text PRIMARY KEY,channel text NOT NULL CHECK(channel IN ('threads','instagram')),integration_id text NOT NULL,enabled boolean NOT NULL DEFAULT false,capabilities jsonb NOT NULL DEFAULT '{}');
CREATE TABLE content_items(
 content_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),account_id text NOT NULL REFERENCES publishing_accounts,
 text text NOT NULL CHECK(length(text) BETWEEN 1 AND 5000),media_ids jsonb NOT NULL DEFAULT '[]',
 version integer NOT NULL DEFAULT 1,approved_version integer,approved_by bigint,approved_at timestamptz,
 state text NOT NULL DEFAULT 'DRAFT' CHECK(state IN ('DRAFT','APPROVED','SCHEDULED','PUBLISHING','SUBMITTED','PUBLISHED','FAILED','UNCERTAIN','CANCELLED')),
 due_at timestamptz NOT NULL DEFAULT now(),created_at timestamptz NOT NULL DEFAULT now(),started_at timestamptz,
 lease_token uuid,provider_result jsonb,error_code text,is_demo boolean NOT NULL DEFAULT false,utm_campaign text
);
CREATE TABLE content_daily_usage(day date PRIMARY KEY,reserved integer NOT NULL DEFAULT 0);
CREATE TABLE content_events(id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,content_id uuid REFERENCES content_items,at timestamptz NOT NULL DEFAULT now(),kind text NOT NULL,detail jsonb NOT NULL DEFAULT '{}');
CREATE TABLE content_metrics(content_id uuid REFERENCES content_items,observed_at timestamptz NOT NULL DEFAULT now(),metrics jsonb NOT NULL,PRIMARY KEY(content_id,observed_at));
CREATE FUNCTION content_action(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE s app_settings;i content_items;a publishing_accounts;act text;r jsonb;used integer;
BEGIN
 SELECT * INTO s FROM app_settings WHERE id=true FOR UPDATE;act:=c->>'action';
 IF act NOT IN ('claim','check','finish','metrics') AND (s.admin_id IS NULL OR (c->>'user_id')::bigint IS DISTINCT FROM s.admin_id) THEN RETURN '{"status":"FORBIDDEN"}';END IF;
 IF act='list' THEN SELECT coalesce(jsonb_agg(to_jsonb(q)),'[]') INTO r FROM (SELECT * FROM content_items ORDER BY created_at DESC LIMIT 10)q;RETURN jsonb_build_object('items',r);END IF;
 IF act='create' THEN
  SELECT * INTO a FROM publishing_accounts WHERE account_id=c->>'account_id';IF NOT FOUND THEN RETURN '{"status":"NEEDS_ACCOUNT"}';END IF;
  IF jsonb_typeof(coalesce(c->'media_ids','[]'))<>'array' OR jsonb_array_length(coalesce(c->'media_ids','[]'))>10 THEN RAISE EXCEPTION 'Invalid media IDs';END IF;
  INSERT INTO content_items(account_id,text,media_ids,is_demo,due_at) VALUES(a.account_id,c->>'text',coalesce(c->'media_ids','[]'),coalesce((c->>'is_demo')::boolean,false),coalesce((c->>'due_at')::timestamptz,now())) RETURNING * INTO i;
  UPDATE content_items SET utm_campaign='lh-'||content_id WHERE content_id=i.content_id RETURNING * INTO i;
  RETURN to_jsonb(i);
 END IF;
 IF act='claim' THEN
  IF s.stopped THEN RETURN '{"status":"STOPPED"}';END IF;
  UPDATE content_items SET state='UNCERTAIN',error_code='INTERRUPTED_RECONCILE_REQUIRED' WHERE state='PUBLISHING' AND started_at<now()-interval '15 minutes';
  SELECT x.* INTO i FROM content_items x JOIN publishing_accounts p USING(account_id) WHERE x.state='SCHEDULED' AND x.approved_version=x.version AND x.due_at<=now() AND p.enabled AND NOT x.is_demo ORDER BY x.due_at LIMIT 1 FOR UPDATE OF x SKIP LOCKED;
  IF NOT FOUND THEN RETURN '{"status":"IDLE"}';END IF;
  INSERT INTO content_daily_usage(day) VALUES((now() AT TIME ZONE 'UTC')::date) ON CONFLICT DO NOTHING;
  SELECT reserved INTO used FROM content_daily_usage WHERE day=(now() AT TIME ZONE 'UTC')::date;
  IF used>=s.max_public_posts_per_day THEN RETURN '{"status":"DAILY_LIMIT"}';END IF;
  UPDATE content_daily_usage SET reserved=reserved+1 WHERE day=(now() AT TIME ZONE 'UTC')::date;
  UPDATE content_items SET state='PUBLISHING',started_at=now(),lease_token=gen_random_uuid() WHERE content_id=i.content_id RETURNING * INTO i;
  SELECT * INTO a FROM publishing_accounts WHERE account_id=i.account_id;
  RETURN to_jsonb(i)||jsonb_build_object('channel',a.channel,'integration_id',a.integration_id);
 END IF;
 SELECT * INTO i FROM content_items WHERE content_id=(c->>'content_id')::uuid FOR UPDATE;
 IF NOT FOUND THEN RETURN '{"status":"NOT_FOUND"}';END IF;
 IF act='check' THEN RETURN jsonb_build_object('allowed',NOT s.stopped AND i.state='PUBLISHING' AND i.lease_token=(c->>'lease_token')::uuid AND i.approved_version=i.version);END IF;
 IF act='finish' THEN
  IF i.state<>'PUBLISHING' OR i.lease_token IS DISTINCT FROM (c->>'lease_token')::uuid THEN RETURN '{"status":"STALE"}';END IF;
  IF c->>'state' NOT IN ('SUBMITTED','PUBLISHED','FAILED','UNCERTAIN') THEN RAISE EXCEPTION 'Invalid publisher state';END IF;
  UPDATE content_items SET state=c->>'state',provider_result=c->'provider_result',error_code=c->>'error_code' WHERE content_id=i.content_id RETURNING * INTO i;
 ELSIF act='metrics' THEN
  INSERT INTO content_metrics(content_id,metrics) VALUES(i.content_id,c->'metrics');RETURN '{"status":"RECORDED"}';
 ELSIF act='get' THEN RETURN to_jsonb(i);
 ELSIF act='cancel' THEN
  IF i.state IN ('PUBLISHING','SUBMITTED','PUBLISHED','UNCERTAIN') THEN RETURN '{"status":"REMOTE_RECONCILIATION_REQUIRED"}';END IF;
  UPDATE content_items SET state='CANCELLED',approved_version=NULL WHERE content_id=i.content_id RETURNING * INTO i;
 ELSIF act='edit' THEN
  IF i.state IN ('PUBLISHING','SUBMITTED','PUBLISHED','UNCERTAIN') THEN RETURN '{"status":"REMOTE_RECONCILIATION_REQUIRED"}';END IF;
  UPDATE content_items SET text=coalesce(c->>'text',text),media_ids=coalesce(c->'media_ids',media_ids),account_id=coalesce(c->>'account_id',account_id),due_at=coalesce((c->>'due_at')::timestamptz,due_at),version=version+1,approved_version=NULL,approved_by=NULL,approved_at=NULL,state='DRAFT' WHERE content_id=i.content_id RETURNING * INTO i;
 ELSIF act='approve' THEN
  IF s.stopped THEN RETURN '{"status":"STOPPED"}';END IF;
  IF i.version IS DISTINCT FROM (c->>'version')::integer OR i.state<>'DRAFT' THEN RETURN '{"status":"STALE_VERSION"}';END IF;
  UPDATE content_items SET state='APPROVED',approved_version=version,approved_by=s.admin_id,approved_at=now() WHERE content_id=i.content_id RETURNING * INTO i;
 ELSIF act='schedule' THEN
  IF s.stopped THEN RETURN '{"status":"STOPPED"}';END IF;
  IF i.state<>'APPROVED' OR i.approved_version IS DISTINCT FROM i.version OR (c->>'version')::integer IS DISTINCT FROM i.version THEN RETURN '{"status":"APPROVAL_REQUIRED"}';END IF;
  SELECT * INTO a FROM publishing_accounts WHERE account_id=i.account_id;
  IF NOT a.enabled THEN RETURN '{"status":"NEEDS_ACCOUNT_ACCESS"}';END IF;
  IF i.is_demo THEN RETURN '{"status":"DEMO_CANNOT_PUBLISH"}';END IF;
  UPDATE content_items SET state='SCHEDULED' WHERE content_id=i.content_id RETURNING * INTO i;
 ELSIF act='reconcile' THEN
  IF i.state NOT IN ('UNCERTAIN','SUBMITTED') OR length(coalesce(c->>'provider_id',''))<1 OR c->>'state' NOT IN ('PUBLISHED','FAILED') THEN RETURN '{"status":"RECONCILIATION_EVIDENCE_REQUIRED"}';END IF;
  UPDATE content_items SET state=c->>'state',provider_result=coalesce(provider_result,'{}')||jsonb_build_object('reconciled_provider_id',c->>'provider_id') WHERE content_id=i.content_id RETURNING * INTO i;
 ELSE RAISE EXCEPTION 'Unknown content action';END IF;
 INSERT INTO content_events(content_id,kind,detail) VALUES(i.content_id,act,jsonb_build_object('version',i.version,'state',i.state));RETURN to_jsonb(i);
END $$;
ALTER FUNCTION handle_command(jsonb) RENAME TO handle_command_sources;
CREATE FUNCTION handle_command(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE s app_settings;cmd text;args text;a text[];r jsonb;t text;op jsonb;v_update bigint;
BEGIN
 SELECT * INTO s FROM app_settings WHERE id=true FOR UPDATE;cmd:=c->>'command';args:=coalesce(c->>'args','');a:=regexp_split_to_array(args,'\s+');v_update:=(c->>'update_id')::bigint;
 IF coalesce((c->>'ignored')::boolean,true) OR (c->>'user_id')::bigint IS DISTINCT FROM s.admin_id OR (c->>'chat_id')::bigint IS DISTINCT FROM s.admin_id OR c->>'chat_type'<>'private' OR cmd NOT IN ('content','publish','cancel','threads','instagram','videos','stats','start') THEN RETURN handle_command_sources(c);END IF;
 INSERT INTO processed_updates(update_id) VALUES(v_update) ON CONFLICT DO NOTHING;
 IF NOT FOUND THEN SELECT result INTO r FROM command_results WHERE update_id=v_update AND NOT queued;RETURN coalesce(r,jsonb_build_object('ignored',true,'update_id',v_update));END IF;
 IF cmd='start' THEN t:=E'LEAD HUNTER AI\n/today /leads /sources /jobs /budget /stats\n/find источник · /source enable|disable источник\n/lead ID /draft ID текст /approve ID версия /reject ID\n/stage ID CONTACTED|REPLIED|NEGOTIATION|WON|LOST\n/followup ID ISO-дата · /chats\n/content list|show|new|edit|approve · /publish ID версия · /cancel ID\n/threads /instagram /videos /stop /resume\nПубликация требует точной версии; КП отправляет владелец вручную.';
 ELSIF cmd='stats' THEN
  SELECT 'Лиды: '||count(*)||' · DEMO: '||count(*) FILTER(WHERE is_demo)||' · REPLIED: '||count(*) FILTER(WHERE status='REPLIED')||' · WON: '||count(*) FILTER(WHERE status='WON')||' · DNC: '||count(*) FILTER(WHERE status='DNC') INTO t FROM leads;
  SELECT t||E'\nКонтент: '||count(*)||' · PUBLISHED: '||count(*) FILTER(WHERE state='PUBLISHED')||' · UNCERTAIN: '||count(*) FILTER(WHERE state='UNCERTAIN') INTO t FROM content_items;
  SELECT t||E'\nЗаявки по UTM: '||count(*)||' (просмотры не считаются лидами)' INTO t FROM leads WHERE attribution ? 'utm_campaign';
 ELSIF cmd IN ('threads','instagram') THEN
  SELECT coalesce(string_agg(account_id||' enabled='||enabled,E'\n'),'NEEDS_ACCOUNT_ACCESS: подключение собственных аккаунтов через Postiz OAuth') INTO t FROM publishing_accounts WHERE channel=cmd;
  IF cmd='threads' THEN t:=t||E'\nSearch: threads_keyword_search + app review; /find threads_search';END IF;
  t:=t||E'\nЧерновики: /content list';
 ELSIF cmd='videos' THEN t:='Локальный FFmpeg и карусели: scripts/media_factory.py. Нужны собственные/лицензированные материалы. Платная генерация выключена. /media list';
 ELSE
  op:=jsonb_build_object('user_id',s.admin_id);
  IF cmd='content' THEN
   IF a[1]='list' OR args='' THEN op:=op||'{"action":"list"}';
   ELSIF a[1]='new' AND a[2] IS NOT NULL THEN op:=op||jsonb_build_object('action','create','account_id',a[2],'text',regexp_replace(args,'^\S+\s+\S+\s*',''));
   ELSIF a[2] ~ '^[a-f0-9-]{36}$' AND a[1] IN ('show','edit','approve') THEN
    op:=op||jsonb_build_object('action',CASE a[1] WHEN 'show' THEN 'get' ELSE a[1] END,'content_id',a[2]);
    IF a[1]='edit' THEN op:=op||jsonb_build_object('text',regexp_replace(args,'^\S+\s+\S+\s*',''));END IF;
    IF a[1]='approve' AND a[3] ~ '^[0-9]+$' THEN op:=op||jsonb_build_object('version',a[3]::integer);END IF;
   END IF;
  ELSIF a[1] ~ '^[a-f0-9-]{36}$' THEN
   op:=op||jsonb_build_object('action',CASE cmd WHEN 'publish' THEN 'schedule' ELSE 'cancel' END,'content_id',a[1]);
   IF a[2] ~ '^[0-9]+$' THEN op:=op||jsonb_build_object('version',a[2]::integer);END IF;
  END IF;
  IF op->>'action' IS NULL THEN t:='/content new ACCOUNT текст · /content show ID · /content edit ID текст · /content approve ID версия · /publish ID версия · /cancel ID';
  ELSE r:=content_action(op);t:=left(jsonb_pretty(r),3400);END IF;
 END IF;
 r:=jsonb_build_object('update_id',v_update,'ignored',false,'text',t,'callback_id',c->>'callback_id');INSERT INTO command_results VALUES(v_update,r,false);RETURN r;
END $$;
UPDATE source_registry SET access_status='NEEDS_ACCOUNT_ACCESS',detail='Postiz official public API; требуется собственный аккаунт и OAuth' WHERE source_type IN ('content','instagram');
