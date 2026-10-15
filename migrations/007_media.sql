CREATE TABLE media_assets(asset_id text PRIMARY KEY CHECK(asset_id ~ '^[a-f0-9]{64}$'),manifest jsonb NOT NULL,revoked_at timestamptz,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE media_jobs(job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),kind text NOT NULL CHECK(kind IN ('video','carousel')),spec jsonb NOT NULL,state text NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','RUNNING','DONE','FAILED','CANCELLED')),lease_token uuid,created_at timestamptz NOT NULL DEFAULT now(),started_at timestamptz,finished_at timestamptz,result jsonb,error_code text);
CREATE FUNCTION media_action(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE s app_settings;j media_jobs;m jsonb;ids jsonb;assets jsonb;
BEGIN
 SELECT * INTO s FROM app_settings WHERE id=true FOR UPDATE;
 IF c->>'action' NOT IN ('claim','finish','register','check') AND (s.admin_id IS NULL OR (c->>'user_id')::bigint IS DISTINCT FROM s.admin_id) THEN RETURN '{"status":"FORBIDDEN"}';END IF;
 IF c->>'action'='list' THEN
  RETURN jsonb_build_object('assets',coalesce((SELECT jsonb_agg(to_jsonb(a)) FROM (SELECT asset_id,manifest->'rights' AS rights,revoked_at FROM media_assets ORDER BY created_at DESC LIMIT 10)a),'[]'), 'jobs',coalesce((SELECT jsonb_agg(to_jsonb(q)) FROM (SELECT job_id,kind,state,error_code FROM media_jobs ORDER BY created_at DESC LIMIT 10)q),'[]'));
 ELSIF c->>'action'='register' THEN
  m:=c->'manifest';
  IF m->>'asset_id' IS DISTINCT FROM m->>'sha256' OR m->'rights'->>'kind' NOT IN ('own','licensed','public_domain') OR length(coalesce(m->'rights'->>'grant',''))=0 THEN RAISE EXCEPTION 'Invalid rights manifest';END IF;
  INSERT INTO media_assets(asset_id,manifest) VALUES(m->>'asset_id',m) ON CONFLICT DO NOTHING;RETURN '{"status":"REGISTERED"}';
 ELSIF c->>'action'='revoke' THEN
  UPDATE media_assets SET revoked_at=now() WHERE asset_id=c->>'asset_id';
  UPDATE content_items SET approved_version=NULL,state='DRAFT',version=version+1 WHERE media_ids ? (c->>'asset_id') AND state IN ('DRAFT','APPROVED','SCHEDULED');RETURN '{"status":"REVOKED"}';
 ELSIF c->>'action'='enqueue' THEN
  IF s.stopped THEN RETURN '{"status":"STOPPED"}';END IF;
  IF c->>'kind' NOT IN ('video','carousel') OR octet_length((c->'spec')::text)>20000 THEN RAISE EXCEPTION 'Invalid render spec';END IF;
  INSERT INTO media_jobs(kind,spec) VALUES(c->>'kind',c->'spec') RETURNING * INTO j;RETURN to_jsonb(j);
 ELSIF c->>'action'='claim' THEN
  IF s.stopped THEN RETURN '{"status":"STOPPED"}';END IF;
  UPDATE media_jobs SET state='FAILED',error_code='INTERRUPTED_RENDER',finished_at=now() WHERE state='RUNNING' AND started_at<now()-interval '15 minutes';
  SELECT * INTO j FROM media_jobs WHERE state='PENDING' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED;
  IF NOT FOUND THEN RETURN '{"status":"IDLE"}';END IF;
  UPDATE media_jobs SET state='RUNNING',started_at=now(),lease_token=gen_random_uuid() WHERE job_id=j.job_id RETURNING * INTO j;RETURN to_jsonb(j);
 ELSIF c->>'action'='check' THEN RETURN jsonb_build_object('allowed',NOT s.stopped AND EXISTS(SELECT 1 FROM media_jobs WHERE job_id=(c->>'job_id')::uuid AND lease_token=(c->>'lease_token')::uuid AND state='RUNNING'));
 ELSIF c->>'action'='finish' THEN
  SELECT * INTO j FROM media_jobs WHERE job_id=(c->>'job_id')::uuid AND lease_token=(c->>'lease_token')::uuid AND state='RUNNING' FOR UPDATE;
  IF NOT FOUND THEN RETURN '{"status":"STALE"}';END IF;
  IF c->>'error_code' IS NOT NULL THEN UPDATE media_jobs SET state='FAILED',error_code=c->>'error_code',finished_at=now() WHERE job_id=j.job_id;RETURN '{"status":"FAILED"}';END IF;
  assets:=CASE WHEN j.kind='carousel' THEN c->'result'->'assets' ELSE jsonb_build_array(c->'result') END;ids:='[]';
  FOR m IN SELECT value FROM jsonb_array_elements(assets) LOOP
   PERFORM media_action(jsonb_build_object('action','register','manifest',m));ids:=ids||jsonb_build_array(m->>'asset_id');
  END LOOP;
  UPDATE media_jobs SET state='DONE',finished_at=now(),result=c->'result' WHERE job_id=j.job_id;
  INSERT INTO notification_outbox(dedupe_key,payload) VALUES('media:'||j.job_id,
   jsonb_build_object('type','media_preview','data',jsonb_build_object('_method',CASE j.kind WHEN 'video' THEN 'sendVideo' ELSE 'sendMediaGroup' END,'_asset_ids',ids,'caption','Предпросмотр '||j.job_id||'. Публикация не одобрена.')));
  RETURN jsonb_build_object('status','DONE','asset_ids',ids);
 END IF;RAISE EXCEPTION 'Unknown media action';
END $$;
CREATE FUNCTION valid_content_media(ids jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT jsonb_typeof(ids)='array' AND jsonb_array_length(ids)<=10 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(ids) x WHERE NOT EXISTS(SELECT 1 FROM media_assets a WHERE a.asset_id=x AND a.revoked_at IS NULL));
$$;
ALTER FUNCTION content_action(jsonb) RENAME TO content_action_base;
CREATE FUNCTION content_action(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE i content_items;
BEGIN
 IF c->>'action' IN ('approve','schedule','check') THEN
  SELECT * INTO i FROM content_items WHERE content_id=(c->>'content_id')::uuid;
  IF FOUND AND NOT valid_content_media(i.media_ids) THEN RETURN '{"status":"MEDIA_RIGHTS_REQUIRED","allowed":false}';END IF;
 END IF;
 RETURN content_action_base(c);
END $$;
ALTER FUNCTION handle_command(jsonb) RENAME TO handle_command_content;
CREATE FUNCTION handle_command(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE s app_settings;r jsonb;v_update bigint;args text;a text[];
BEGIN
 SELECT * INTO s FROM app_settings WHERE id=true FOR UPDATE;
 IF c->>'command'<>'media' OR coalesce((c->>'ignored')::boolean,true) OR (c->>'user_id')::bigint IS DISTINCT FROM s.admin_id OR (c->>'chat_id')::bigint IS DISTINCT FROM s.admin_id OR c->>'chat_type'<>'private' THEN RETURN handle_command_content(c);END IF;
 v_update:=(c->>'update_id')::bigint;INSERT INTO processed_updates(update_id) VALUES(v_update) ON CONFLICT DO NOTHING;
 IF NOT FOUND THEN SELECT result INTO r FROM command_results WHERE update_id=v_update AND NOT queued;RETURN coalesce(r,jsonb_build_object('ignored',true,'update_id',v_update));END IF;
 args:=coalesce(c->>'args','');a:=regexp_split_to_array(args,'\s+');
 IF a[1]='revoke' THEN r:=media_action(jsonb_build_object('action','revoke','user_id',s.admin_id,'asset_id',a[2]));
 ELSE r:=media_action(jsonb_build_object('action','list','user_id',s.admin_id));END IF;
 r:=jsonb_build_object('update_id',v_update,'ignored',false,'text',left(jsonb_pretty(r),3400),'callback_id',c->>'callback_id');INSERT INTO command_results VALUES(v_update,r,false);RETURN r;
END $$;
UPDATE source_registry SET access_status='LOCAL_READY',detail='FFmpeg + Pillow, реестр прав, очередь render и Telegram preview; paid generation OFF' WHERE source_type='video';
