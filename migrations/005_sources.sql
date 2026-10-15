CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE connector_configs (
 source_type text PRIMARY KEY REFERENCES source_registry, config jsonb NOT NULL DEFAULT '{}',
 enabled boolean NOT NULL DEFAULT false, interval_minutes integer NOT NULL DEFAULT 360 CHECK(interval_minutes>=30),
 last_enqueued_at timestamptz, cursor jsonb NOT NULL DEFAULT '{}', updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO connector_configs(source_type) SELECT source_type FROM source_registry WHERE source_type<>'maps_demo';
CREATE TABLE connector_jobs (
 job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),source_type text NOT NULL REFERENCES source_registry,
 config jsonb NOT NULL, dedupe_key text NOT NULL UNIQUE, state text NOT NULL DEFAULT 'PENDING'
 CHECK(state IN ('PENDING','RUNNING','DONE','FAILED','CANCELLED')),
 lease_token uuid, created_at timestamptz NOT NULL DEFAULT now(),started_at timestamptz,finished_at timestamptz,
 result jsonb,error_code text,import_id uuid REFERENCES import_requests
);
CREATE INDEX connector_pending ON connector_jobs(state,created_at);
CREATE TABLE monitored_chats(chat_id bigint PRIMARY KEY, enabled boolean NOT NULL DEFAULT true, description text NOT NULL DEFAULT '');
CREATE TABLE form_settings(id boolean PRIMARY KEY DEFAULT true CHECK(id), signing_key text NOT NULL DEFAULT '', enabled boolean NOT NULL DEFAULT false);
INSERT INTO form_settings(id) VALUES(true);
CREATE TABLE form_submissions(nonce text PRIMARY KEY,created_at timestamptz NOT NULL DEFAULT now(),import_id uuid REFERENCES import_requests);

CREATE FUNCTION enqueue_connector(kind text,cfg jsonb,k text) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE j connector_jobs;
BEGIN
 PERFORM 1 FROM app_settings WHERE id=true FOR UPDATE;
 IF (SELECT stopped FROM app_settings WHERE id=true) THEN RETURN '{"status":"STOPPED"}'; END IF;
 IF kind NOT IN ('maps','new_business','telegram_monitor','audit','niche','subcontract','website_forms','partners','content','threads_search') THEN RAISE EXCEPTION 'Unsupported source';END IF;
 IF octet_length(cfg::text)>5000000 THEN RAISE EXCEPTION 'Config too large';END IF;
 INSERT INTO connector_jobs(source_type,config,dedupe_key) VALUES(kind,cfg,k) ON CONFLICT DO NOTHING RETURNING * INTO j;
 IF j.job_id IS NULL THEN SELECT * INTO j FROM connector_jobs WHERE dedupe_key=k;END IF;
 RETURN jsonb_build_object('job_id',j.job_id,'status',j.state);
END $$;
CREATE FUNCTION enqueue_configured(kind text,force_run boolean DEFAULT false) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE c connector_configs;
BEGIN
 SELECT * INTO c FROM connector_configs WHERE source_type=kind FOR UPDATE;
 IF NOT FOUND OR NOT c.enabled OR c.config='{}'::jsonb THEN RETURN '{"status":"NEEDS_CONFIGURATION"}';END IF;
 IF NOT force_run AND c.last_enqueued_at>now()-make_interval(mins=>c.interval_minutes) THEN RETURN '{"status":"CACHED"}';END IF;
 UPDATE connector_configs SET last_enqueued_at=now() WHERE source_type=kind;
 RETURN enqueue_connector(kind,c.config,'schedule:'||kind||':'||gen_random_uuid()::text);
END $$;
CREATE FUNCTION connector_action(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE s app_settings;j connector_jobs;v_id uuid;v_payload jsonb;
BEGIN
 SELECT * INTO s FROM app_settings WHERE id=true FOR UPDATE;
 IF c->>'action'='claim' THEN
  IF s.stopped THEN RETURN '{"status":"STOPPED"}';END IF;
  UPDATE connector_jobs SET state='FAILED',error_code='INTERRUPTED_REVIEW_REQUIRED',finished_at=now() WHERE state='RUNNING' AND started_at<now()-interval '15 minutes';
  SELECT * INTO j FROM connector_jobs WHERE state='PENDING' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED;
  IF NOT FOUND THEN RETURN '{"status":"IDLE"}';END IF;
  UPDATE connector_jobs SET state='RUNNING',started_at=now(),lease_token=gen_random_uuid() WHERE job_id=j.job_id RETURNING * INTO j;
  RETURN to_jsonb(j)||jsonb_build_object('max_leads',s.max_leads_per_run);
 ELSIF c->>'action'='check' THEN
  RETURN jsonb_build_object('allowed',NOT s.stopped AND EXISTS(SELECT 1 FROM connector_jobs WHERE job_id=(c->>'job_id')::uuid AND lease_token=(c->>'lease_token')::uuid AND state='RUNNING'));
 ELSIF c->>'action'='finish' THEN
  SELECT * INTO j FROM connector_jobs WHERE job_id=(c->>'job_id')::uuid AND lease_token=(c->>'lease_token')::uuid AND state='RUNNING' FOR UPDATE;
  IF NOT FOUND THEN RETURN '{"status":"STALE"}';END IF;
  IF c->>'error_code' IS NOT NULL THEN
   UPDATE connector_jobs SET state='FAILED',error_code=left(c->>'error_code',100),finished_at=now() WHERE job_id=j.job_id;
   RETURN '{"status":"FAILED"}';
  END IF;
  v_payload:=coalesce(c->'leads','[]');
  IF jsonb_typeof(v_payload)<>'array' OR jsonb_array_length(v_payload)>s.max_leads_per_run THEN RAISE EXCEPTION 'Invalid leads';END IF;
  IF jsonb_array_length(v_payload)>0 THEN
   INSERT INTO import_requests(payload,origin) VALUES(v_payload,j.source_type) RETURNING request_id INTO v_id;
  END IF;
  UPDATE connector_jobs SET state='DONE',result=jsonb_build_object('count',jsonb_array_length(v_payload)),finished_at=now(),import_id=v_id WHERE job_id=j.job_id;
  UPDATE connector_configs SET cursor=coalesce(c->'cursor',cursor) WHERE source_type=j.source_type;
  RETURN jsonb_build_object('status','DONE','import_id',v_id,'count',jsonb_array_length(v_payload));
 END IF;
 RAISE EXCEPTION 'Unknown connector action';
END $$;
CREATE FUNCTION monitor_update(u jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE m jsonb;cid bigint;v_update bigint;url text;row jsonb;
BEGIN
 m:=coalesce(u->'channel_post',u->'edited_channel_post',u->'message',u->'edited_message');
 IF m IS NULL OR m->'chat'->>'type'='private' THEN RETURN '{"ignored":true}';END IF;
 cid:=(m->'chat'->>'id')::bigint;v_update:=(u->>'update_id')::bigint;
 PERFORM 1 FROM app_settings WHERE id=true FOR UPDATE;
 IF NOT EXISTS(SELECT 1 FROM monitored_chats WHERE chat_id=cid AND enabled) THEN RETURN '{"ignored":true}';END IF;
 IF EXISTS(SELECT 1 FROM processed_updates WHERE update_id=v_update) THEN RETURN '{"status":"DUPLICATE"}';END IF;
 IF NOT (SELECT stopped FROM app_settings WHERE id=true) AND length(coalesce(m->>'text',m->>'caption','')) BETWEEN 3 AND 12000 THEN
  url:=CASE WHEN m->'chat'->>'username' IS NOT NULL THEN 'https://t.me/'||(m->'chat'->>'username') ELSE 'https://t.me/c/'||regexp_replace(abs(cid)::text,'^100','') END||'/'||(m->>'message_id');
  row:=jsonb_build_object('source','telegram_monitor','source_type','telegram_monitor','source_url',url,'external_id',cid||':'||(m->>'message_id'),
   'company_name',coalesce(m->'chat'->>'title','Telegram запрос'),'proof_quote',coalesce(m->>'text',m->>'caption'),
   'published_at',to_timestamp((m->>'date')::bigint),'is_demo',false);
  INSERT INTO import_requests(payload,origin) VALUES(jsonb_build_array(row),'telegram_monitor');
 END IF;
 INSERT INTO processed_updates(update_id) VALUES(v_update) ON CONFLICT DO NOTHING;
 UPDATE app_settings SET telegram_offset=greatest(telegram_offset,v_update+1) WHERE id=true;
 RETURN '{"status":"ACCEPTED"}';
END $$;
CREATE FUNCTION receive_form(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE f form_settings; p jsonb;v_id uuid;
BEGIN
 SELECT * INTO f FROM form_settings WHERE id=true;
 IF NOT f.enabled OR f.signing_key='' THEN RETURN '{"status":"NEEDS_CONFIGURATION"}';END IF;
 IF encode(hmac(c->>'signing_input',f.signing_key,'sha256'),'hex') IS DISTINCT FROM c->>'signature' THEN RETURN '{"status":"BAD_SIGNATURE"}';END IF;
 p:=c->'payload';
 IF (c->>'signing_input')::jsonb IS DISTINCT FROM p OR p->'consent'<>'true'::jsonb OR abs(extract(epoch FROM now())-(p->>'timestamp')::numeric)>300 THEN RETURN '{"status":"INVALID"}';END IF;
 PERFORM 1 FROM app_settings WHERE id=true FOR UPDATE;
 IF (SELECT stopped FROM app_settings WHERE id=true) THEN RETURN '{"status":"STOPPED"}';END IF;
 INSERT INTO form_submissions(nonce) VALUES(p->>'nonce') ON CONFLICT DO NOTHING;
 IF NOT FOUND THEN RETURN '{"status":"DUPLICATE"}';END IF;
 INSERT INTO import_requests(payload,origin) VALUES(jsonb_build_array(jsonb_build_object('source','website_forms','source_type','website_forms',
  'source_url','https://stanislavweb.ru','external_id','form:'||(p->>'nonce'),'company_name',left(coalesce(p->>'name','Заявка с сайта'),200),
  'public_contact',p->>'contact','proof_quote',p->>'message','published_at',now(),'attribution',coalesce(p->'utm','{}'),
  'consent',true,'is_demo',false)),'website_forms') RETURNING request_id INTO v_id;
 UPDATE form_submissions SET import_id=v_id WHERE nonce=p->>'nonce';
 RETURN jsonb_build_object('status','ACCEPTED','request_id',v_id);
END $$;
ALTER FUNCTION handle_command(jsonb) RENAME TO handle_command_stage_a;
CREATE FUNCTION handle_command(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE s app_settings;cmd text;args text;a text[];t text;r jsonb;l leads;v_update bigint;
BEGIN
 SELECT * INTO s FROM app_settings WHERE id=true FOR UPDATE;
 cmd:=c->>'command';args:=coalesce(c->>'args','');a:=regexp_split_to_array(args,'\s+');v_update:=(c->>'update_id')::bigint;
 IF coalesce((c->>'ignored')::boolean,true) OR (c->>'user_id')::bigint IS DISTINCT FROM s.admin_id OR (c->>'chat_id')::bigint IS DISTINCT FROM s.admin_id OR c->>'chat_type'<>'private' THEN RETURN handle_command_stage_a(c);END IF;
 IF cmd NOT IN ('source','stage','followup','jobs','chats') AND NOT(cmd='find' AND a[1] NOT IN ('demo','maps_demo','')) THEN RETURN handle_command_stage_a(c);END IF;
 INSERT INTO processed_updates(update_id) VALUES(v_update) ON CONFLICT DO NOTHING;
 IF NOT FOUND THEN SELECT result INTO r FROM command_results WHERE update_id=v_update AND NOT queued;RETURN coalesce(r,jsonb_build_object('ignored',true,'update_id',v_update));END IF;
 IF cmd='source' THEN
  IF a[1] IN ('enable','disable') AND EXISTS(SELECT 1 FROM connector_configs WHERE source_type=a[2]) THEN
   UPDATE connector_configs SET enabled=(a[1]='enable') WHERE source_type=a[2];UPDATE source_registry SET enabled=(a[1]='enable') WHERE source_type=a[2];t:='Источник '||a[2]||': '||a[1]||'. Конфигурация на сервере: scripts/sources.py';
  ELSE t:='/source enable|disable maps|new_business|audit|niche|subcontract|partners|threads_search';END IF;
 ELSIF cmd='find' THEN r:=enqueue_configured(a[1],true);t:=r::text;
 ELSIF cmd IN ('stage','followup') THEN
  IF a[1] !~ '^[a-f0-9-]{36}$' THEN t:='Нужен UUID лида';
  ELSE
   SELECT * INTO l FROM leads WHERE lead_id=a[1]::uuid FOR UPDATE;
   IF NOT FOUND THEN t:='Лид не найден';ELSIF l.status='DNC' THEN t:='DNC: действия запрещены';
   ELSIF cmd='stage' AND a[2] IN ('CONTACTED','REPLIED','NEGOTIATION','WON','LOST') THEN
    UPDATE leads SET status=a[2] WHERE lead_id=l.lead_id;INSERT INTO lead_events(lead_id,kind,detail) VALUES(l.lead_id,'STAGE_CHANGED',jsonb_build_object('status',a[2]));t:='Статус: '||a[2];
   ELSIF cmd='followup' THEN
    BEGIN UPDATE leads SET next_followup_at=a[2]::timestamptz WHERE lead_id=l.lead_id;t:='Напоминание сохранено';EXCEPTION WHEN invalid_datetime_format OR datetime_field_overflow THEN t:='Укажите дату ISO с часовым поясом';END;
   ELSE t:='/stage ID CONTACTED|REPLIED|NEGOTIATION|WON|LOST · /followup ID ISO-date';END IF;
  END IF;
 ELSIF cmd='chats' THEN SELECT coalesce(string_agg(chat_id||' '||description,E'\n'),'Нет разрешённых чатов. scripts/sources.py chat ID') INTO t FROM monitored_chats WHERE enabled;
 ELSE SELECT coalesce(string_agg(source_type||' '||state||' '||coalesce(error_code,''),E'\n'),'Нет заданий') INTO t FROM (SELECT * FROM connector_jobs ORDER BY created_at DESC LIMIT 8) j;
 END IF;
 r:=jsonb_build_object('update_id',v_update,'ignored',false,'text',t,'callback_id',c->>'callback_id');INSERT INTO command_results VALUES(v_update,r,false);RETURN r;
END $$;
CREATE FUNCTION queue_reminders() RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE l leads;n integer:=0;
BEGIN
 PERFORM 1 FROM app_settings WHERE id=true FOR UPDATE;
 IF (SELECT stopped OR admin_id IS NULL FROM app_settings WHERE id=true) THEN RETURN '{"status":"PAUSED"}';END IF;
 FOR l IN SELECT * FROM leads WHERE next_followup_at<=now() AND status NOT IN ('DNC','WON','LOST') LIMIT 20 FOR UPDATE SKIP LOCKED LOOP
  INSERT INTO notification_outbox(lead_id,dedupe_key,payload) VALUES(l.lead_id,'reminder:'||l.lead_id||':'||l.next_followup_at,
   jsonb_build_object('type','message','data',jsonb_build_object('text','Напоминание: '||l.company_name||' /lead '||l.lead_id))) ON CONFLICT DO NOTHING;
  UPDATE leads SET next_followup_at=NULL WHERE lead_id=l.lead_id;n:=n+1;
 END LOOP;RETURN jsonb_build_object('reminders',n);
END $$;
UPDATE source_registry SET access_status=CASE source_type WHEN 'maps' THEN 'NEEDS_CONFIGURATION' WHEN 'audit' THEN 'NEEDS_SAFE_TRANSPORT' WHEN 'niche' THEN 'READY' WHEN 'new_business' THEN 'IMPORT_READY' WHEN 'telegram_monitor' THEN 'NEEDS_CHAT_ACCESS' WHEN 'website_forms' THEN 'NEEDS_CONFIGURATION' WHEN 'subcontract' THEN 'IMPORT_READY' WHEN 'partners' THEN 'IMPORT_READY' ELSE access_status END,
 detail=CASE source_type WHEN 'maps' THEN 'OSM/Overpass: bbox и tag; Яндекс/2ГИС не подключены' WHEN 'audit' THEN 'Ограниченный HTML-аудит; в proxy среде fail closed' WHEN 'new_business' THEN 'Законная выгрузка/разрешённый feed; регистрация не означает спрос' WHEN 'subcontract' THEN 'Разрешённый RSS/Atom или импорт; автоматический web search требует провайдера' WHEN 'partners' THEN 'Разрешённый RSS/Atom или импорт' ELSE detail END;
